"""A fixed round-trip cost per unit (``cost_per_unit``, per instrument: XAU/USD 0.25 per oz,
Fadi): charged in full at the entry as the trade's fee, fills at the chart prices, fee_bps and
slippage_bps ignored, and the risk per unit is ``|entry - stop| + cost``. Every number by hand."""

import pytest

from tests.conftest import bars, signals
from trading_backtest import BacktestConfig, ContractSpec, lots_for_risk, plan_trade, run_backtest
from trading_backtest.risk import breakeven_level

approx = pytest.approx
GOLD = ContractSpec(contract_size=100, lot_step=0.01, quote_currency="USD", min_lot=0.01,
                    max_lot=100)  # fmt: skip


def test_long_to_the_cent() -> None:
    df = bars(
        [
            (2399, 2400, 2398, 2400),  # 0: buy signal
            (2400.00, 2405, 2399, 2404),  # 1: filled at this open, 2400.00
            (2404, 2412, 2403, 2411),  # 2: sell signal
            (2410.00, 2410, 2410, 2410),  # 3: exit at this open, 2410.00
        ]
    )
    config = {"cost_per_unit": 0.25, "sizing": {"mode": "fixed", "value": 4800}}
    res = run_backtest(df, signals(df, {0: 1, 2: -1}), config)
    (t,) = res.trades

    # by hand: 4,800 / 2,400 = 2 oz; +10.00 per oz; the round trip costs 0.25 x 2 = 0.50
    assert (t.entry_price, t.exit_price, t.quantity) == (2400.0, 2410.0, 2.0)
    assert t.gross_pnl == 20.0 and t.fees == 0.5 and t.net_pnl == 19.5
    assert res.metrics["total_fees"] == 0.5
    assert res.metrics["final_equity"] == approx(10_019.5, abs=0.005)
    eq = res.equity.tolist()
    assert eq[1] == approx(10_000 - 2 * 2400 - 0.5 + 2 * 2404)  # paid at the entry
    assert eq[3] == approx(10_019.5)


def test_short_stopped_out_loses_exactly_the_risk() -> None:
    df = bars(
        [
            (2401, 2402, 2399, 2400),  # 0: sell signal
            (2400.00, 2401, 2398, 2399),  # 1: short at this open, 2400.00
            (2399, 2407, 2398, 2405),  # 2: the high goes through the stop
        ]
    )
    config = {
        "initial_capital": 100_000,
        "direction": "long_short",
        "cost_per_unit": 0.25,
        "stop": {"type": "percent", "value": 0.25},  # 2400 x 1.0025 = 2406.00
        "sizing": {"mode": "risk", "risk_pct": 0.1},  # 100 USD
    }
    res = run_backtest(df, signals(df, {0: -1}), config)
    (t,) = res.trades

    # by hand: risk per oz = 6.00 + 0.25 = 6.25 -> 100 / 6.25 = 16 oz
    assert t.side == "short" and t.exit_reason == "stop_loss"
    assert t.quantity == approx(16.0)
    assert t.exit_price == approx(2406.0)  # exactly the stop: no slippage
    assert round(t.gross_pnl, 2) == -96.00  # (2400 - 2406) x 16
    assert round(t.fees, 2) == 4.00  # 0.25 x 16
    assert round(t.net_pnl, 2) == -100.00
    assert round(t.risk_amount, 2) == 100.00 and t.r_multiple == approx(-1.0)
    assert round(res.metrics["final_equity"], 2) == 99_900.00


def test_fee_and_slippage_are_ignored_when_set() -> None:
    df = bars(
        [(100, 101, 99, 100), (100, 103, 99, 102), (102, 104, 101, 103), (104, 104, 104, 104)]
    )
    sig = signals(df, {0: 1, 2: -1})
    base = {"cost_per_unit": 0.25, "stop": {"type": "percent", "value": 2},
            "sizing": {"mode": "risk", "risk_pct": 1}}  # fmt: skip
    plain = run_backtest(df, sig, {**base, "fee_bps": 0, "slippage_bps": 0})
    costly = run_backtest(df, sig, {**base, "fee_bps": 50, "slippage_bps": 20})
    assert [t.to_dict() for t in costly.trades] == [t.to_dict() for t in plain.trades]
    assert costly.equity.tolist() == plain.equity.tolist()
    (t,) = plain.trades
    assert t.entry_price == 100 and t.exit_price == 104  # the chart prices
    assert t.fees == approx(0.25 * t.quantity)
    # without the fixed cost the bps apply as before
    bps = run_backtest(df, sig, {**{k: v for k, v in base.items() if k != "cost_per_unit"},
                                 "fee_bps": 50, "slippage_bps": 20})  # fmt: skip
    assert bps.trades[0].entry_price == approx(100 * 1.002)


def test_partial_exits_pay_nothing_more() -> None:
    df = bars(
        [
            (100, 100, 100, 100),  # 0: buy signal
            (100, 100, 100, 100),  # 1: long 100 at 100.00; stop 98, targets 102 and 104
            (101, 102.5, 100.5, 102),  # 2: first target (half)
            (103, 104.5, 102.5, 104),  # 3: second target (the rest)
        ]
    )
    config = {
        "initial_capital": 20_000,  # the 100 % position cap (199 units) does not bind
        "cost_per_unit": 0.5,
        "stop": {"type": "percent", "value": 2},
        "take_profit": {"type": "r_multiple", "levels": [{"r": 1, "close_pct": 50},
                                                         {"r": 2, "close_pct": 50}]},
        "sizing": {"mode": "risk", "risk_pct": 1.25},  # 250 / (2 + 0.5) = 100 units
    }  # fmt: skip
    (t,) = run_backtest(df, signals(df, {0: 1}), config).trades
    assert t.quantity == approx(100.0)
    assert [(f["price"], f["quantity"]) for f in t.fills] == [(102.0, 50.0), (104.0, 50.0)]
    assert t.gross_pnl == approx(2 * 50 + 4 * 50) and t.fees == approx(50.0)
    assert t.net_pnl == approx(250.0)


def test_breakeven_stop_covers_the_cost() -> None:
    assert breakeven_level(1, 2400.0, 0.0, 0.0, 0.25) == 2400.25
    assert breakeven_level(-1, 2400.0, 0.0, 0.0, 0.25) == 2399.75
    assert breakeven_level(1, 100.0, 0.001, 0.0) == approx(100 * 1.001 / 0.999)  # as before


def test_config_round_trip_and_cost_model() -> None:
    config = BacktestConfig.from_dict({"cost_per_unit": 0.25, "fee_bps": 10})
    assert config.cost_model == "fixed_per_unit" and config.cost_per_unit == 0.25
    assert config.fee_rate == 0.0 and config.slippage_rate == 0.0
    assert BacktestConfig.from_dict(config.to_dict()) == config
    plain = BacktestConfig.from_dict({})
    assert plain.cost_model == "bps" and "cost_per_unit" not in plain.to_dict()
    with pytest.raises(ValueError, match="cost_per_unit"):
        BacktestConfig.from_dict({"cost_per_unit": -0.1})


def test_trade_plan_counts_the_cost_in_the_risk() -> None:
    """XAU/USD, 100 oz a lot, USD account 10,000, risk 0.2 % = 20 USD, entry 2400, stop 2395:
    (5.00 + 0.25) per oz -> 3.8095 oz -> 0.03 lots (0.04 without the cost)."""
    df = bars([(2400, 2401, 2399, 2400)])
    risk = {"stop": {"type": "percent", "value": 1}, "sizing": {"mode": "risk", "risk_pct": 0.2},
            "fee_bps": 10}  # fmt: skip
    kw = {"entry": 2400.0, "stop": 2395.0, "spec": GOLD, "conversion_rate": 1.0}
    plan = plan_trade(df, 0, "buy", risk, 10_000, cost_per_unit=0.25, **kw)
    assert plan.quantity == approx(20 / 5.25)
    assert plan.risk_amount == approx(20.0)  # the fee_bps of the profile is not added
    assert plan.lots == 0.03 and plan.lots_risk_amount == approx(0.03 * 100 * 5.25)
    out = plan.to_dict()
    assert out["cost_per_unit"] == 0.25
    assert any("0.25 per unit" in w for w in out["sizing_warnings"])

    without = plan_trade(df, 0, "buy", {**risk, "fee_bps": 0}, 10_000, **kw)
    assert without.quantity == approx(4.0) and without.lots == 0.04
    assert "cost_per_unit" not in without.to_dict()


def test_lots_for_risk_with_the_cost() -> None:
    sized = lots_for_risk(20, 2400, 2395, GOLD, "USD", 1.0, cost_per_unit=0.25)
    assert sized.risk_per_lot == approx(525.0) and sized.lots == 0.03
    assert sized.risk_amount == approx(15.75)
    assert lots_for_risk(20, 2400, 2395, GOLD, "USD", 1.0).lots == 0.04  # as before
