"""An account currency that differs from the instrument's quote currency (B9, Fadi's report:
"the Sizer gives a USD/JPY size about 150x too small").

The hand example used by every test here: a USD account of 10,000, risk 1 % = 100 USD, USD/JPY
at 150.00 with the stop 50 pips away (149.50). One lot is 100,000 USD, so a 0.50 move costs
50,000 JPY per lot = 50,000 / 150 = 333.33 USD per lot, and 100 / 333.33 = **0.30 lots** =
**30,000 units**. Treating the 10,000 USD as 10,000 JPY gives 100 JPY / 0.50 = 200 units
(0.002 lots): 150x too small.
"""

import pytest

import trading_backtest as tb
from tests.conftest import NO_COSTS, bars, signals
from trading_backtest import ContractSpec, direct_rate, lots_for_risk, plan_trade

approx = pytest.approx
USDJPY = ContractSpec(100_000, 0.01, "JPY", min_lot=0.01, max_lot=100)
BALANCE, RISK_PCT, ENTRY, STOP = 10_000.0, 1.0, 150.0, 149.5
EXPECTED_UNITS = (BALANCE * RISK_PCT / 100) / ((ENTRY - STOP) / ENTRY)  # 30,000
EXPECTED_LOTS = 0.30
STOP_PCT = (ENTRY - STOP) / ENTRY * 100  # 0.333...% below a 150.00 fill = 149.50


def test_hand_example() -> None:
    assert EXPECTED_UNITS == approx(30_000)
    assert EXPECTED_UNITS / USDJPY.contract_size == approx(EXPECTED_LOTS)


def test_lots_for_risk_converts_with_the_inverse_price() -> None:
    """The B4/B10 helper (``local_size`` goes through it): right already."""
    rate = direct_rate("USD", "JPY", "USD", ENTRY)
    assert rate == approx(1 / 150)
    size = lots_for_risk(BALANCE * RISK_PCT / 100, ENTRY, STOP, USDJPY, "USD", rate)
    assert size.feasible and size.lots == EXPECTED_LOTS
    assert size.risk_per_lot == approx(333.3333333)
    assert size.risk_amount == approx(100)


def test_plan_trade_converts_without_specs() -> None:
    """A trade plan with a conversion rate but no contract specs (live plans and the calculator
    on an instrument without specs) sizes on the equity in the quote currency."""
    df = bars([(ENTRY, ENTRY, ENTRY, ENTRY)] * 3)
    rules = {"stop": {"type": "percent", "value": 1}, "sizing": {"mode": "risk", "risk_pct": 1}}
    plan = plan_trade(df, 2, "buy", rules, BALANCE, stop=STOP, conversion_rate=1 / ENTRY)
    assert plan.quantity == approx(EXPECTED_UNITS / (1 + 0.001 * (ENTRY + STOP) / 0.5))
    rules["fee_bps"] = 0
    plan = plan_trade(df, 2, "buy", rules, BALANCE, stop=STOP, conversion_rate=1 / ENTRY)
    assert plan.quantity == approx(EXPECTED_UNITS)
    assert plan.risk_amount == approx(100)  # account currency
    assert plan.lots is None  # no specs: no lots


def _usdjpy_run(conversion: dict | None, **extra):
    """Buy at the open of bar 1 (150.00), then the stop (149.50) is hit on bar 3."""
    df = bars(
        [
            (150.0, 150.0, 150.0, 150.0),
            (150.0, 150.2, 149.9, 150.1),
            (150.1, 150.3, 150.0, 150.2),
            (150.2, 150.2, 149.4, 149.6),
            (149.6, 149.7, 149.5, 149.6),
        ]
    )
    config = {
        **NO_COSTS,
        "initial_capital": BALANCE,
        # 3x notional: allow up to 10x (the default 100 % = no leverage would cap it)
        "sizing": {"mode": "risk", "risk_pct": RISK_PCT, "max_position_pct": 1000},
        "stop": {"type": "percent", "value": STOP_PCT},
        **({"conversion": conversion} if conversion is not None else {}),
        **extra,
    }
    return tb.run_backtest(df, signals(df, {0: 1}), config)


def test_backtest_risk_sizing_in_the_account_currency() -> None:
    """The engine with a USD account on USD/JPY: 0.30 lots, and a stop-out loses 100 USD."""
    result = _usdjpy_run({"type": "inverse_price"})
    [trade] = result.trades
    assert trade.entry_price == 150.0 and trade.initial_stop == approx(STOP)
    assert trade.quantity == approx(EXPECTED_UNITS)
    assert trade.quantity / USDJPY.contract_size == approx(EXPECTED_LOTS)
    assert trade.risk_amount == approx(100)  # USD
    # the stop fills at 149.50: 0.50 x 30,000 = 15,000 JPY = 100 USD at 149.50
    assert trade.net_pnl == approx(-15_000 / 149.5)
    assert result.equity.iloc[-1] == approx(BALANCE - 15_000 / 149.5)
    assert trade.r_multiple == approx(-150 / 149.5)


def test_backtest_fixed_rate() -> None:
    """A fixed rate (e.g. EUR/JPY for a USD account, rate from a USD/JPY quote)."""
    result = _usdjpy_run({"type": "fixed", "rate": 1 / 150})
    [trade] = result.trades
    assert trade.quantity == approx(EXPECTED_UNITS)
    assert trade.net_pnl == approx(-100)


def test_without_conversion_the_capital_is_in_the_quote_currency() -> None:
    """Unchanged (documented): no ``conversion`` = the capital is in the quote currency, so
    10,000 here means 10,000 JPY and 1 % of it is 100 JPY (200 units)."""
    [trade] = _usdjpy_run(None).trades
    assert trade.quantity == approx(200)


def test_conversion_config_round_trip_and_validation() -> None:
    config = tb.BacktestConfig.from_dict({"conversion": {"type": "fixed", "rate": 0.5}})
    assert config.to_dict()["conversion"] == {"type": "fixed", "rate": 0.5}
    assert tb.BacktestConfig.from_dict(config.to_dict()) == config
    assert "conversion" not in tb.BacktestConfig.from_dict({}).to_dict()
    with pytest.raises(tb.ConfigError, match="conversion"):
        tb.BacktestConfig.from_dict({"conversion": {"type": "fixed"}})
    with pytest.raises(tb.ConfigError, match="conversion"):
        tb.BacktestConfig.from_dict({"conversion": {"type": "inverse_price", "rate": 2}})
