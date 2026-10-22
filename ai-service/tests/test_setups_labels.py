import numpy as np
import pandas as pd
import pytest

from app.config import instruments, strategy
from app.setups.builder import Plan
from app.setups.labels import Bars, label_all, resolve, round_trip
from tests.test_smc_detector import EMPTY, _resample, _walk

P = strategy("V5-S")  # entry window 8, horizon 48
XAU = instruments()["XAUUSD"]  # cost: spread + max(50%, 0.10); SL slippage 0.10
PLAN = Plan("ARMED", "", entry=100.0, sl=98.0, tp=104.0, risk=2.0, r_multiple=2.0, target=None)
SPREAD = 0.3  # round trip 0.3 + max(0.15, 0.10) = 0.45


def buy_bars(rows: list[tuple[float, float, float, float]]) -> Bars:
    """Bar 0 is the decision bar; rows are (open, high, low, close) of bars 1, 2, ..."""
    data = np.array([(101.0, 101.5, 100.5, 101.0)] + rows, float)
    return Bars(1.0, data[:, 0], data[:, 1], data[:, 2], data[:, 3])


QUIET = (100.6, 101.0, 100.4, 100.8)  # never touches the entry 100


def test_round_trip_cost() -> None:
    assert round_trip(0.3, XAU) == pytest.approx(0.45)
    assert round_trip(0.1, XAU) == pytest.approx(0.2)  # the $0.10 minimum


def test_fill_then_tp() -> None:
    lab = resolve(
        buy_bars([QUIET, (100.5, 100.8, 99.8, 100.2), (100.2, 104.2, 100.1, 104.0)]),
        0,
        PLAN,
        SPREAD,
        P,
        XAU,
    )
    assert (lab.state, lab.reason, lab.fill_idx, lab.exit_idx, lab.y) == ("CLOSED", "tp", 2, 3, 1)
    assert lab.gross_r == pytest.approx(2.0)
    assert lab.net_r == pytest.approx(2.0 - 0.45 / 2.0)
    assert lab.net_r_2x == pytest.approx(2.0 - 0.9 / 2.0)


def test_fill_then_sl_pays_the_slippage() -> None:
    lab = resolve(
        buy_bars([(100.5, 100.8, 99.8, 100.2), (100.2, 100.4, 97.9, 98.5)]), 0, PLAN, SPREAD, P, XAU
    )
    assert (lab.reason, lab.y, lab.exit_price) == ("sl", 0, pytest.approx(97.9))
    assert lab.gross_r == pytest.approx(-1.0)
    assert lab.net_r == pytest.approx(-1.0 - 0.05 - 0.225)
    assert lab.net_r_2x == pytest.approx(-1.0 - 0.1 - 0.45)


def test_an_ambiguous_bar_counts_as_sl() -> None:
    lab = resolve(
        buy_bars([(100.5, 100.8, 99.8, 100.2), (100.2, 104.5, 97.5, 101.0)]),
        0,
        PLAN,
        SPREAD,
        P,
        XAU,
    )
    assert lab.reason == "sl"


def test_on_the_fill_bar_only_the_sl_counts() -> None:
    # The fill bar also reaches the TP: not counted, the trade stays open (pending here).
    tp_on_fill = resolve(buy_bars([(100.5, 104.5, 99.9, 104.2), QUIET]), 0, PLAN, SPREAD, P, XAU)
    assert (tp_on_fill.state, tp_on_fill.fill_idx) == ("PENDING", 1)
    sl_on_fill = resolve(buy_bars([(100.5, 100.8, 97.5, 98.0)]), 0, PLAN, SPREAD, P, XAU)
    assert (sl_on_fill.reason, sl_on_fill.fill_idx, sl_on_fill.exit_idx) == ("sl", 1, 1)


def test_gap_through_the_sl_after_the_fill_exits_at_the_open() -> None:
    lab = resolve(
        buy_bars([(100.5, 100.8, 99.8, 100.2), (97.0, 97.5, 96.5, 97.2)]), 0, PLAN, SPREAD, P, XAU
    )
    assert (lab.reason, lab.exit_price) == ("sl", pytest.approx(96.9))
    assert lab.gross_r == pytest.approx(-1.5)


def test_before_the_fill_gap_through_sl_or_tp_first_invalidates() -> None:
    gap = resolve(buy_bars([(97.5, 98.0, 97.0, 97.5)]), 0, PLAN, SPREAD, P, XAU)
    assert (gap.state, gap.reason) == ("INVALIDATED", "gap_through_sl")
    tp = resolve(buy_bars([(101.0, 104.5, 100.8, 104.0)]), 0, PLAN, SPREAD, P, XAU)
    assert (tp.state, tp.reason) == ("INVALIDATED", "tp_before_fill")


def test_no_fill_in_the_window_expires() -> None:
    lab = resolve(buy_bars([QUIET] * 8), 0, PLAN, SPREAD, P, XAU)
    assert (lab.state, lab.reason) == ("EXPIRED", "no_fill")
    assert resolve(buy_bars([QUIET] * 5), 0, PLAN, SPREAD, P, XAU).state == "PENDING"


def test_horizon_exits_at_the_close_of_the_48th_bar() -> None:
    rows = (
        [(100.5, 100.8, 99.8, 100.2)]
        + [(100.4, 101.0, 99.0, 100.6)] * 46
        + [(100.6, 101.0, 99.5, 101.0)]
    )
    lab = resolve(buy_bars(rows), 0, PLAN, SPREAD, P, XAU)
    assert (lab.reason, lab.fill_idx, lab.exit_idx, lab.y) == ("timeout", 1, 48, 0)
    assert lab.gross_r == pytest.approx(0.5)
    assert resolve(buy_bars(rows[:-1]), 0, PLAN, SPREAD, P, XAU).state == "PENDING"


def test_sell_is_the_mirror() -> None:
    data = np.array(
        [(99.0, 99.5, 98.5, 99.0), (99.5, 100.2, 99.2, 99.8), (99.8, 99.9, 95.8, 96.0)], float
    )
    sell = Bars(-1.0, -data[:, 0], -data[:, 2], -data[:, 1], -data[:, 3])
    plan = Plan("ARMED", "", entry=100.0, sl=102.0, tp=96.0, risk=2.0, r_multiple=2.0, target=None)
    lab = resolve(sell, 0, plan, SPREAD, P, XAU)
    assert (lab.reason, lab.fill_idx, lab.exit_idx, lab.exit_price, lab.gross_r) == (
        "tp",
        1,
        2,
        96.0,
        pytest.approx(2.0),
    )


def test_labels_never_change_when_bars_are_appended() -> None:
    v1 = strategy()
    m15 = _walk(16000, seed=11, freq="15min")
    m15["spread_mean"] = 0.2
    full = {"15m": m15, "1h": _resample(m15, "1h"), "4h": _resample(m15, "4h"), "D1": EMPTY}
    whole = label_all(full, "XAUUSD", v1)
    assert (whole["state"] == "CLOSED").sum() >= 3
    for n in (6000, 12000):
        cut = m15["close_utc"].iloc[n - 1]
        part = {k: v[v["close_utc"] <= cut].reset_index(drop=True) for k, v in full.items()}
        got = label_all(part, "XAUUSD", v1).set_index("setup_id")
        ref = whole.set_index("setup_id").loc[got.index]
        done = got["state"] != "PENDING"
        pd.testing.assert_frame_equal(got[done], ref[done])
