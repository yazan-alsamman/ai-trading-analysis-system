import numpy as np
import pandas as pd
import pytest

from app.config import instruments, strategy
from app.setups.builder import Plan
from app.setups.labels import Bars
from app.setups.managed import BOTH, BUY, SELL, manage, trades
from tests.test_smc_detector import _resample, _walk

LM = strategy("L1-M")  # horizon 48, cap 192
XAU = instruments()["XAUUSD"]
PLAN = Plan("ARMED", "", entry=100.0, sl=98.0, tp=104.0, risk=2.0, r_multiple=2.0, target=None)
QUIET = (100.2, 100.8, 99.6, 100.4)  # touches neither SL nor TP


def bars(n: int, rows: dict[int, tuple] | None = None) -> Bars:
    data = np.array([(100.0, 100.5, 99.5, 100.0)] + [QUIET] * n, float)
    for j, r in (rows or {}).items():
        data[j] = r
    return Bars(1.0, data[:, 0], data[:, 1], data[:, 2], data[:, 3])


def side(n: int, at: dict[int, int] | None = None) -> np.ndarray:
    s = np.zeros(n + 1, dtype=np.int8)
    for j, v in (at or {}).items():
        s[j] = v
    return s


def run(b: Bars, s: np.ndarray):
    return manage(b, 0, PLAN, s, 0.3, LM, XAU)


def test_without_signals_it_is_l1_timeout_at_48() -> None:
    m = run(bars(60), side(60))
    assert (m.reason, m.exit_idx, m.extensions) == ("timeout", 48, 0)
    assert m.gross_r == pytest.approx(0.2)  # close 100.4


def test_an_opposite_signal_closes_at_its_close_in_profit_or_loss() -> None:
    loss = run(bars(60, {10: (100.0, 100.2, 98.5, 98.8)}), side(60, {10: SELL}))
    assert (loss.reason, loss.exit_idx, loss.gross_r) == ("opposite", 10, pytest.approx(-0.6))
    assert loss.slip_r == 0.0 and loss.net_r() == pytest.approx(-0.6 - 0.45 / 2)
    both = run(bars(60), side(60, {5: BOTH}))
    assert (both.reason, both.exit_idx) == ("opposite", 5)


def test_a_same_direction_signal_extends_to_48_bars_after_it() -> None:
    m = run(bars(120), side(120, {40: BUY}))
    assert (m.reason, m.exit_idx, m.extensions) == ("timeout", 88, 1)


def test_extensions_stop_at_192_bars_from_the_entry() -> None:
    m = run(bars(260), side(260, {40: BUY, 80: BUY, 120: BUY, 160: BUY}))
    assert (m.reason, m.exit_idx, m.extensions) == ("max_hold", 192, 4)


def test_a_signal_on_the_horizon_bar_extends_before_the_horizon_exit() -> None:
    m = run(bars(120), side(120, {48: BUY}))
    assert (m.reason, m.exit_idx) == ("timeout", 96)


def test_sl_and_tp_beat_the_signal_rules() -> None:
    sl = run(bars(60, {20: (100.0, 100.4, 97.5, 98.2)}), side(60, {20: BUY}))
    assert (sl.reason, sl.exit_idx, sl.slip_r) == ("sl", 20, pytest.approx(0.05))
    tp = run(bars(60, {7: (100.0, 104.5, 99.9, 104.2)}), side(60, {7: SELL}))
    assert (tp.reason, tp.exit_idx, tp.gross_r) == ("tp", 7, pytest.approx(2.0))


def test_no_decision_before_the_data_ends() -> None:
    assert run(bars(30), side(30)).state == "PENDING"


def _frames(n: int = 16000) -> dict[str, pd.DataFrame]:
    m15 = _walk(n, seed=11, freq="15min")
    m15["spread_mean"] = 0.2
    return {
        "15m": m15,
        "1h": _resample(m15, "1h"),
        "4h": _resample(m15, "4h"),
        "D1": _resample(m15, "1D"),
    }


def test_one_position_at_a_time_and_within_the_cap() -> None:
    t = trades(_frames(), "XAUUSD", LM)
    done = t[t["state"] == "CLOSED"].reset_index(drop=True)
    assert len(done) >= 3
    exits = done["decision_idx"] + done["bars_held"]
    assert (done["decision_idx"].iloc[1:].to_numpy() >= exits.iloc[:-1].to_numpy()).all()
    assert (done["bars_held"] <= LM.max_hold_bars).all()
    assert set(done["reason"]) <= {"tp", "sl", "opposite", "timeout", "max_hold"}


def test_trades_never_change_when_bars_are_appended() -> None:
    full = _frames()
    whole = trades(full, "XAUUSD", LM)
    whole = whole[whole["state"] == "CLOSED"].set_index("setup_id")
    for n in (6000, 12000):
        cut = full["15m"]["close_utc"].iloc[n - 1]
        part = {k: v[v["close_utc"] <= cut].reset_index(drop=True) for k, v in full.items()}
        got = trades(part, "XAUUSD", LM)
        got = got[got["state"] == "CLOSED"].set_index("setup_id")
        assert len(got) >= 1
        pd.testing.assert_frame_equal(got, whole.loc[got.index])


def test_random_managed_entries_repeat_with_the_seed_and_use_the_real_signals() -> None:
    from app.research.baselines import market
    from app.research.versions import random_managed
    from app.setups.builder import build
    from app.setups.managed import signal_sides
    from app.smc.detector import detect

    f = _frames()
    m = market(f, LM)
    side = signal_sides(len(f["15m"]), build(f, detect(f, LM), LM))
    (year, hour), _ = max(m.pool.items(), key=lambda kv: len(kv[1]))
    draw = [
        random_managed(m, side, year, hour, 1.5, np.random.default_rng(9), LM, XAU)
        for _ in range(2)
    ]
    assert draw[0] == draw[1] and draw[0] is not None
    assert draw[0]["reason"] in {"tp", "sl", "opposite", "timeout", "max_hold"}
