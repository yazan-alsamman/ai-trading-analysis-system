from datetime import date

import pandas as pd
import pytest

from app.config import strategy
from app.setups.builder import build, plan
from app.smc import detector
from tests.test_smc_detector import EMPTY, _resample, _walk, frames

P = strategy("V5-S")
T = pd.Timestamp("2024-01-16", tz="UTC")


def lv(price: float, side: str, source: str = "1h") -> detector.Level:
    return detector.Level(price, side, source, T, T, date(2024, 1, 16))


BUY = dict(direction="buy", extreme=99.4, atr=2.0, spread=0.3, fvg_low=101.0, fvg_high=101.6)
# entry 101.6, SL 99.4 - 0.2 - 0.3 = 98.9, risk 2.7


def test_buy_plan_takes_the_nearest_liquidity_with_r_of_at_least_the_minimum() -> None:
    pl = plan(
        **BUY, close=104.0, targets=[lv(103.0, "high"), lv(110.0, "high"), lv(108.0, "high")], p=P
    )
    assert (pl.state, pl.reason, pl.entry, pl.sl) == ("ARMED", "", 101.6, pytest.approx(98.9))
    assert pl.risk == pytest.approx(2.7)
    assert pl.tp == 108.0 and pl.r_multiple == pytest.approx(6.4 / 2.7)  # 103 is below 1.5R


def test_nearest_qualifying_level_beyond_max_r_is_rejected_not_capped() -> None:
    pl = plan(**BUY, close=104.0, targets=[lv(115.0, "high"), lv(120.0, "high")], p=P)
    assert (pl.state, pl.reason, pl.tp) == ("REJECTED", "REJECT_TARGET_BEYOND_MAX_R", 115.0)


def test_no_liquidity_far_enough_is_rejected() -> None:
    targets = [
        lv(103.0, "high"),
        lv(100.0, "high"),
        lv(130.0, "low"),
    ]  # too close, below, wrong side
    pl = plan(**BUY, close=104.0, targets=targets, p=P)
    assert (pl.state, pl.reason) == ("REJECTED", "REJECT_NO_TARGET")


def test_decision_bar_closing_at_or_below_the_entry_is_rejected() -> None:
    pl = plan(**BUY, close=101.6, targets=[lv(110.0, "high")], p=P)
    assert pl.reason == "REJECT_PRICE_AT_ENTRY"


def test_stop_at_or_beyond_the_entry_is_rejected() -> None:
    args = {**BUY, "extreme": 101.9, "spread": 0.0}  # SL 101.7 above the entry 101.6
    pl = plan(**args, close=104.0, targets=[lv(110.0, "high")], p=P)
    assert pl.reason == "REJECT_NON_POSITIVE_RISK"


def test_sell_plan_is_the_mirror() -> None:
    pl = plan(
        direction="sell",
        extreme=200.6,
        atr=2.0,
        spread=0.3,
        fvg_low=198.4,
        fvg_high=199.0,
        close=196.0,
        targets=[lv(190.0, "low"), lv(197.0, "low")],
        p=P,
    )
    assert (pl.state, pl.entry, pl.sl, pl.tp) == ("ARMED", 198.4, pytest.approx(201.1), 190.0)
    assert pl.r_multiple == pytest.approx(8.4 / 2.7)


def test_a_detected_pattern_is_planned_with_the_previous_day_high_as_target() -> None:
    f = frames([100.0])  # previous day: high 110, low 100
    (s,) = build(f, detector.detect(f, strategy()), strategy())
    pl = s.plan
    assert (pl.state, pl.entry, pl.tp, pl.target.source) == ("ARMED", 101.6, 110.0, "pd")
    assert pl.sl == pytest.approx(99.4 - 0.1 * s.pattern.sweep.atr)  # no spread column: 0
    assert s.setup_id == s.pattern.pattern_id


def test_setups_never_change_when_bars_are_appended() -> None:
    v1 = strategy()
    m15 = _walk(16000, seed=11, freq="15min")
    full = {"15m": m15, "1h": _resample(m15, "1h"), "4h": _resample(m15, "4h"), "D1": EMPTY}
    whole = build(full, detector.detect(full, v1), v1)
    assert len(whole) >= 5
    for n in (4000, 11000):
        cut = m15["close_utc"].iloc[n - 1]
        part = {k: v[v["close_utc"] <= cut].reset_index(drop=True) for k, v in full.items()}
        got = build(part, detector.detect(part, v1), v1)
        assert got == [s for s in whole if s.decision_idx < n]


def test_market_entry_plans_from_the_decision_close_without_an_fvg() -> None:
    l1 = strategy("L1")
    pl = plan("buy", 99.4, 2.0, 0.3, None, None, 102.0, [lv(108.0, "high")], l1)
    assert (pl.state, pl.entry, pl.sl) == ("ARMED", 102.0, pytest.approx(98.9))
    assert pl.r_multiple == pytest.approx(6.0 / 3.1)
