"""Lot sizing (trading_backtest.sizing) and lots in trade plans. The four cases required by B4
are computed by hand in the docstrings; the helper must reproduce them exactly."""

import json
import math

import pytest

from tests.conftest import bars
from trading_backtest import (
    ContractSpec,
    direct_rate,
    lots_for_risk,
    plan_trade,
    round_lots,
    value_per_price_unit,
)

approx = pytest.approx
GOLD = ContractSpec(
    contract_size=100, lot_step=0.01, quote_currency="USD", min_lot=0.01, max_lot=100
)
FX_JPY = ContractSpec(100_000, 0.01, "JPY", min_lot=0.01, max_lot=100)
FX_USD = ContractSpec(100_000, 0.01, "USD", min_lot=0.01, max_lot=100)


# --- the four hand-computed cases ---------------------------------------------------------------


def test_xauusd_hand_computed() -> None:
    """Balance 2,000 USD, risk 1% = 20 USD, entry 2400.00, stop 2395.00 (a 5.00 move).
    1.00 of price on 1 lot (100 oz) = 100 USD, so 1 lot risks 500 USD: 20 / 500 = 0.04 lots."""
    size = lots_for_risk(0.01 * 2_000, 2400.00, 2395.00, GOLD, "USD", 1.0)
    assert size.feasible and size.warnings == []
    assert size.value_per_price_unit == 100
    assert size.risk_per_lot == approx(500)
    assert size.lots == 0.04
    assert size.risk_amount == approx(20)


def test_usdjpy_hand_computed() -> None:
    """Entry 150.000, stop 149.500, risk 100 USD, 100,000 per lot, USD account. One JPY is
    1/150 USD, so 1 lot loses 0.5 x 100,000 / 150 = 333.33 USD: 100 / 333.33 = 0.3000 -> 0.30
    after rounding down (and not 0.29 because of 0.3 / 0.01 = 29.999...)."""
    rate = direct_rate("USD", "JPY", "USD", 150.000)
    assert rate == approx(1 / 150)
    size = lots_for_risk(100, 150.000, 149.500, FX_JPY, "USD", rate)
    assert size.feasible
    assert size.risk_per_lot == approx(333.3333333)
    assert size.raw_lots == approx(0.3)
    assert size.lots == 0.30
    assert size.risk_amount == approx(100)


def test_eurusd_hand_computed() -> None:
    """EUR/USD with a USD account: entry 1.08500, stop 1.08300 (20 pips = 0.00200), risk
    100 USD. 1 lot = 100,000 EUR, so 0.002 x 100,000 = 200 USD per lot: 100 / 200 = 0.50."""
    size = lots_for_risk(
        100, 1.08500, 1.08300, FX_USD, "USD", direct_rate("EUR", "USD", "USD", 1.085)
    )
    assert (size.lots, size.feasible, size.conversion_rate) == (0.5, True, 1.0)
    assert size.risk_per_lot == approx(200)


def test_min_lot_infeasible() -> None:
    """Balance 100 USD, risk 1% = 1 USD, XAU/USD 2400 -> 2395: 0.01 lot already risks
    0.01 x 500 = 5 USD > 1 USD, so nothing can be traded."""
    size = lots_for_risk(0.01 * 100, 2400, 2395, GOLD, "USD", 1.0)
    assert size.lots == 0 and size.feasible is False
    assert size.raw_lots == approx(0.002)
    assert size.warnings == [
        "below the minimum of 0.01 lots",
        "the minimum 0.01 lots would risk 5.00 USD, more than the 1.00 USD allowed",
    ]


# --- conversion ----------------------------------------------------------------------------------


def test_value_per_price_unit() -> None:
    assert value_per_price_unit(100, "USD", "USD", None) == 100
    assert value_per_price_unit(100_000, "JPY", "USD", 1 / 150) == approx(666.6666667)
    assert value_per_price_unit(100_000, "GBP", "USD", 1.27) == approx(127_000)
    with pytest.raises(ValueError, match="no conversion rate from JPY to USD"):
        value_per_price_unit(100_000, "JPY", "USD", None)
    with pytest.raises(ValueError, match="no conversion rate"):
        value_per_price_unit(100_000, "JPY", "USD", 0)
    with pytest.raises(ValueError, match="must be 1"):
        value_per_price_unit(100, "USD", "USD", 1.1)


def test_direct_rate() -> None:
    assert direct_rate("XAU", "USD", "USD", 2400) == 1.0
    assert direct_rate("USD", "JPY", "USD", 150) == approx(1 / 150)
    assert direct_rate("EUR", "GBP", "USD", 0.85) is None  # needs a GBP/USD (or USD/GBP) price


def test_missing_rate_is_never_assumed_one() -> None:
    size = lots_for_risk(100, 150, 149.5, FX_JPY, "USD", None)
    assert size.lots == 0 and not size.feasible
    assert size.warnings == ["no conversion rate from JPY to USD"]


# --- rounding and limits -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0.049999, 0.04), (0.3, 0.3), (0.29999999999999993, 0.3), (1.239, 1.23), (0.01, 0.01)],
)
def test_round_lots_down(raw: float, expected: float) -> None:
    lots, feasible, warnings = round_lots(raw, GOLD)
    assert (lots, feasible, warnings) == (expected, True, [])


def test_round_lots_limits() -> None:
    assert round_lots(250, GOLD) == (100, True, ["capped at the maximum of 100 lots"])
    assert round_lots(0.009, GOLD) == (0.0, False, ["below the minimum of 0.01 lots"])
    assert round_lots(0, GOLD)[1] is False
    assert round_lots(math.nan, GOLD)[1] is False
    coarse = ContractSpec(1, 0.5, "USDT", min_lot=1.0)
    assert round_lots(1.9, coarse) == (1.5, True, [])
    assert round_lots(0.9, coarse)[0:2] == (0.0, False)
    no_min = ContractSpec(1, 0.001, "USDT")  # min defaults to one step
    assert round_lots(0.0019, no_min) == (0.001, True, [])


def test_bad_inputs() -> None:
    assert lots_for_risk(0, 2400, 2395, GOLD, "USD", 1.0).warnings == [
        "the risk amount must be > 0"
    ]
    assert not lots_for_risk(20, 2400, 2400, GOLD, "USD", 1.0).feasible
    with pytest.raises(ValueError, match="min_lot"):
        ContractSpec(100, 0.01, "USD", min_lot=2, max_lot=1)
    with pytest.raises(ValueError):
        ContractSpec(0, 0.01, "USD")
    json.dumps(lots_for_risk(20, 2400, 2395, GOLD, "USD", 1.0).to_dict())


# --- lots in trade plans -------------------------------------------------------------------------

# 1% risk, no fees and a high position cap, so the plan matches the hand-computed cases
RISK_1PCT = {
    "stop": {"type": "percent", "value": 1},  # replaced by the explicit stop of each plan
    "sizing": {"mode": "risk", "risk_pct": 1, "max_position_pct": 1000},
    "fee_bps": 0,
}


def _frame(close: float):
    return bars([(close, close, close, close)] * 3)


def test_plan_gold_lots() -> None:
    plan = plan_trade(
        _frame(2400), 2, "buy", RISK_1PCT, 2_000, stop=2395, spec=GOLD, conversion_rate=1.0
    )
    d = plan.to_dict()
    assert d["quantity"] == approx(4.0)  # oz
    assert (d["lots"], d["lots_feasible"], d["conversion_rate"]) == (0.04, True, 1.0)
    assert d["risk_amount"] == approx(20) and d["lots_risk_amount"] == approx(20)
    assert d["risk_pct"] == approx(1.0) and d["sizing_warnings"] == []


def test_plan_usdjpy_is_no_longer_150x_too_small() -> None:
    """2,000 USD, 1% = 20 USD at USD/JPY 150 -> 149.5: 20 / 333.33 = 0.06 lots = 6,000 USD."""
    legacy = plan_trade(_frame(150), 2, "buy", RISK_1PCT, 2_000, stop=149.5)
    assert legacy.quantity == approx(40)  # the old bug: 20 "JPY" of risk
    plan = plan_trade(
        _frame(150), 2, "buy", RISK_1PCT, 2_000, stop=149.5, spec=FX_JPY, conversion_rate=1 / 150
    )
    assert plan.quantity == approx(6_000)
    assert plan.quantity / legacy.quantity == approx(150)
    assert plan.lots == 0.06 and plan.lots_feasible
    assert plan.risk_amount == approx(20)  # USD, the account currency
    assert plan.risk_pct == approx(1.0)
    assert plan.notional == approx(900_000)  # JPY, the quote currency


def test_plan_fees_and_infeasible_min_lot() -> None:
    # 10 bps on both fills: the cost per oz is 5 + (2400 + 2395) x 0.001 = 9.795
    cfg = {**RISK_1PCT, "fee_bps": 10}
    plan = plan_trade(_frame(2400), 2, "buy", cfg, 2_000, stop=2395, spec=GOLD, conversion_rate=1.0)
    assert plan.quantity == approx(20 / 9.795)
    assert plan.lots == 0.02  # 0.0204 rounded down
    tiny = plan_trade(
        _frame(2400), 2, "buy", RISK_1PCT, 100, stop=2395, spec=GOLD, conversion_rate=1.0
    )
    assert tiny.lots == 0 and tiny.lots_feasible is False
    assert tiny.sizing_warnings == ["below the minimum of 0.01 lots"]


def test_plan_without_rate_or_spec() -> None:
    no_rate = plan_trade(_frame(150), 2, "buy", RISK_1PCT, 2_000, stop=149.5, spec=FX_JPY)
    assert no_rate.lots == 0 and no_rate.lots_feasible is False
    assert "no conversion rate from JPY" in no_rate.sizing_warnings[0]
    assert no_rate.quantity == approx(40)  # unchanged, flagged by the warning
    plain = plan_trade(_frame(150), 2, "buy", RISK_1PCT, 2_000, stop=149.5).to_dict()
    assert (plain["lots"], plain["lots_feasible"], plain["conversion_rate"]) == (None, None, None)
    assert plain["sizing_warnings"] == []
    wrong_side = plan_trade(
        _frame(2400), 2, "buy", RISK_1PCT, 2_000, stop=2401, spec=GOLD, conversion_rate=1.0
    )
    assert wrong_side.invalid_reason == "stop_wrong_side"
    assert (wrong_side.lots, wrong_side.lots_feasible) == (0.0, False)
