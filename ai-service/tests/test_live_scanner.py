"""P6 task 3: the live scanner on hand-built bars, and no look-ahead when bars are appended."""

import pandas as pd
import pytest

from app.config import instruments, strategy
from app.contract import SetupState as S
from app.live.scanner import scan, slots_after
from app.setups.labels import round_trip
from tests.test_smc_detector import EMPTY, PATTERN, START, _frame, _resample, _walk

P = strategy("L1")
XAU = instruments()["XAUUSD"]
J = 20
M15 = pd.Timedelta(minutes=15)


def frames(after: list[tuple[float, float, float, float]], d1_high: float = 113.0) -> dict:
    """Quiet bars, the detector test's sweep -> CHoCH (bar J + 8, close 104.0) after the
    previous day's low 100, then ``after``. The previous day's high is the target."""
    entry = _frame([(101, 102, 100, 101)] * J + PATTERN + after, START, "15min")
    d1 = _frame([(103, d1_high, 100.0, 104)], "2024-01-14 22:00", "1D")
    return {"15m": entry, "1h": EMPTY, "4h": EMPTY, "D1": d1}


QUIET = (104.0, 104.5, 103.5, 104.0)


def test_a_new_setup_is_armed_and_active_at_the_decision_close() -> None:
    f = frames([])
    (ls,) = scan(f, P, XAU)
    decision = f["15m"]["close_utc"].iloc[J + 8]
    assert not ls.rejected and ls.setup.setup_id.startswith("buy:pd:low:")
    assert [(s.state, s.at) for s in ls.path] == [(S.ARMED, decision), (S.ACTIVE, decision)]
    assert ls.created_at == decision and ls.valid_until == decision + M15
    assert ls.setup.plan.entry == 104.0 and ls.setup.plan.tp == 113.0


def test_the_trade_closes_at_the_target_with_net_r() -> None:
    f = frames([QUIET, QUIET, (104.0, 113.5, 103.8, 113.2)])
    (ls,) = scan(f, P, XAU)
    pl = ls.setup.plan
    last = ls.path[-1]
    assert (last.state, last.reason) == (S.CLOSED, "tp")
    assert last.at == f["15m"]["close_utc"].iloc[J + 11]
    gross = (113.0 - 104.0) / pl.risk
    assert last.realized_r == pytest.approx(gross - round_trip(0.0, XAU) / pl.risk, abs=1e-6)


def test_a_stop_hit_closes_at_minus_one_r_and_slippage() -> None:
    f = frames([QUIET, (104.0, 104.2, 95.0, 96.0)])
    (ls,) = scan(f, P, XAU)
    pl = ls.setup.plan
    assert (ls.state, ls.path[-1].reason) == (S.CLOSED, "sl")
    want = -1.0 - (XAU.sl_slippage + round_trip(0.0, XAU)) / pl.risk
    assert ls.path[-1].realized_r == pytest.approx(want, abs=1e-6)


def test_the_horizon_ends_a_trade_at_its_close() -> None:
    f = frames([QUIET] * P.horizon_bars)
    (ls,) = scan(f, P, XAU)
    assert (ls.state, ls.path[-1].reason) == (S.CLOSED, "timeout")
    assert ls.path[-1].at == f["15m"]["close_utc"].iloc[J + 8 + P.horizon_bars]
    assert ls.horizon_until == ls.path[-1].at  # no closed hours in between


def test_a_pattern_without_a_target_is_rejected() -> None:
    (ls,) = scan(frames([], d1_high=105.0), P, XAU)
    assert ls.rejected and ls.label.reason == "REJECT_NO_TARGET" and ls.path == ()


def test_the_horizon_skips_closed_hours() -> None:
    # Friday 16:45 New York: one bar to the weekly close, the rest from Sunday 18:00
    t = pd.Timestamp("2024-01-19 21:45", tz="UTC")
    assert slots_after(t, 1, M15, XAU) == t + M15
    assert slots_after(t, 2, M15, XAU) == pd.Timestamp("2024-01-21 23:15", tz="UTC")


def test_live_setups_never_change_when_bars_are_appended() -> None:
    m15 = _walk(16000, seed=3, freq="15min")
    full = {"15m": m15, "1h": _resample(m15, "1h"), "4h": _resample(m15, "4h"), "D1": EMPTY}
    whole = {ls.setup.setup_id: ls for ls in scan(full, P, XAU)}
    armed = [ls for ls in whole.values() if not ls.rejected]
    rejected = [ls for ls in whole.values() if ls.rejected]
    assert len(armed) >= 5 and rejected
    # cut on a decision bar, inside a trade, and on a rejected pattern's bar
    cuts = [armed[0].setup.decision_idx, armed[1].setup.decision_idx + 3]
    cuts += [armed[-1].setup.decision_idx + 20, rejected[0].setup.decision_idx]
    for i in cuts:
        n = i + 1
        cut = m15["close_utc"].iloc[n - 1]
        part = {k: v[v["close_utc"] <= cut].reset_index(drop=True) for k, v in full.items()}
        got = scan(part, P, XAU)
        assert {ls.setup.setup_id for ls in got} == {
            k for k, ls in whole.items() if ls.created_at <= cut
        }
        for ls in got:
            ref = whole[ls.setup.setup_id]
            assert ls.setup == ref.setup and ls.rejected == ref.rejected
            assert ls.path == tuple(s for s in ref.path if s.at <= cut)
            assert ls.horizon_until == ref.horizon_until


def test_only_market_entry_rule_sets_are_served() -> None:
    m15 = _walk(100, seed=1, freq="15min")
    with pytest.raises(NotImplementedError):
        scan({"15m": m15, "1h": EMPTY, "4h": EMPTY, "D1": EMPTY}, strategy("V5-S"), XAU)
