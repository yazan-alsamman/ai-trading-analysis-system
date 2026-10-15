"""Tiny frames where every fill is known by hand."""

import pytest

from tests.conftest import NO_COSTS, bars, flat, signals
from trading_backtest import BacktestConfig, run_backtest

approx = pytest.approx


def test_entry_at_next_open_with_fees_and_slippage_to_the_cent() -> None:
    df = bars(
        [
            (100, 100, 100, 100),  # 0: buy signal at this close
            (102, 103, 101, 103),  # 1: filled at this open
            (104, 105, 103, 105),  # 2: sell signal
            (110, 110, 110, 110),  # 3: exit at this open
        ]
    )
    res = run_backtest(df, signals(df, {0: 1, 2: -1}), {"fee_bps": 10, "slippage_bps": 5})
    (t,) = res.trades

    # by hand: fee 0.10 %, slippage 0.05 % against us
    entry = 102 * 1.0005  # 102.051
    qty = 10_000 / (entry * 1.001)  # all equity, entry fee included
    entry_fee = entry * qty * 0.001  # 9.99 (10,000 / 1.001 * 0.001)
    exit_ = 110 * 0.9995  # 109.945
    exit_fee = exit_ * qty * 0.001
    gross = (exit_ - entry) * qty
    assert t.side == "long" and t.entry_reason == "test_buy"
    assert t.entry_time == df.index[1] and t.exit_time == df.index[3]
    assert t.entry_price == approx(entry) and t.exit_price == approx(exit_)
    assert t.quantity == approx(qty)
    assert t.fees == approx(entry_fee + exit_fee)
    assert t.gross_pnl == approx(gross)
    assert t.net_pnl == approx(gross - entry_fee - exit_fee)
    assert t.exit_reason == "opposite_signal" and t.bars_held == 2

    # the same numbers to the cent
    assert round(entry_fee, 2) == 9.99
    assert round(exit_fee, 2) == 10.76
    assert round(t.gross_pnl, 2) == 772.76  # 7.894 per unit x 97.8923 units
    assert round(t.net_pnl, 2) == 752.01
    assert round(t.return_pct, 4) == 7.5276  # 752.01 / 9,990.01 entry notional
    assert round(res.metrics["final_equity"], 2) == 10_752.01
    assert round(res.metrics["total_fees"], 2) == 20.75

    # equity: flat before entry; marked at closes; cash after the exit
    eq = res.equity.tolist()
    assert eq[0] == approx(10_000)
    assert eq[1] == approx(103 * qty)  # cash is 0 after spending everything
    assert eq[2] == approx(105 * qty)
    assert eq[3] == approx(10_000 - entry * qty - entry_fee + exit_ * qty - exit_fee)


def test_a_signal_is_never_filled_on_its_own_bar() -> None:
    df = flat([100, 200, 300])
    res = run_backtest(df, signals(df, {0: 1}), NO_COSTS)
    assert res.trades[0].entry_price == 200  # bar 1's open, not bar 0's close


def test_signal_on_the_last_bar_is_not_filled() -> None:
    df = flat([100, 101, 102])
    res = run_backtest(df, signals(df, {2: 1}), NO_COSTS)
    assert res.trades == [] and res.equity.tolist() == [10_000] * 3


def test_long_only_ignores_sells_as_entries_and_repeated_buys() -> None:
    df = flat([100, 100, 100, 100, 100, 100])
    res = run_backtest(df, signals(df, {0: -1, 1: 1, 2: 1, 3: -1, 4: -1}), NO_COSTS)
    (t,) = res.trades
    assert (t.side, t.entry_time, t.exit_time) == ("long", df.index[2], df.index[4])
    assert t.exit_reason == "opposite_signal"


def test_long_short_reverses_on_the_opposite_signal() -> None:
    df = flat([100, 100, 110, 120, 100, 90])
    res = run_backtest(df, signals(df, {0: 1, 2: -1}), {**NO_COSTS, "direction": "long_short"})
    long_, short = res.trades
    assert (long_.side, long_.entry_price, long_.exit_price) == ("long", 100, 120)
    assert long_.exit_reason == "opposite_signal" and long_.net_pnl == approx(2_000)
    # the short opens at the same open with all equity (12,000 / 120 = 100 units)
    assert (short.side, short.entry_time, short.entry_price) == ("short", df.index[3], 120)
    assert short.quantity == approx(100)
    assert short.exit_reason == "end_of_data" and short.exit_price == 90
    assert short.net_pnl == approx((120 - 90) * 100)
    assert res.equity.iloc[4] == approx(12_000 + (120 - 100) * 100)  # short marked to market
    assert res.metrics["final_equity"] == approx(15_000)


def test_long_only_sell_closes_without_reversing() -> None:
    df = flat([100, 100, 110, 120, 100])
    res = run_backtest(df, signals(df, {0: 1, 2: -1}), NO_COSTS)
    assert [t.side for t in res.trades] == ["long"]
    assert res.equity.iloc[-1] == approx(12_000)


def _long_at_100(rows: list[tuple[float, float, float, float]], **exits):
    """Buy signal on bar 0, filled at bar 1's open (100); no costs."""
    df = bars([(100, 100, 100, 100), *rows])
    return run_backtest(df, signals(df, {0: 1}), {**NO_COSTS, "exits": exits}), df


def test_stop_loss_hit_inside_a_bar() -> None:
    res, df = _long_at_100(
        [(100, 101, 99, 100), (99, 100, 94, 96), (96, 97, 95, 96)], stop_loss_pct=5
    )
    (t,) = res.trades
    assert (t.exit_reason, t.exit_price, t.exit_time) == ("stop_loss", 95, df.index[2])
    assert t.bars_held == 2  # bars 1 and 2
    assert t.net_pnl == approx(-500)


def test_take_profit_hit_inside_a_bar() -> None:
    res, df = _long_at_100([(100, 101, 99, 100), (105, 111, 104, 109)], take_profit_pct=10)
    (t,) = res.trades
    assert (t.exit_reason, t.exit_time) == ("take_profit", df.index[2])
    assert t.exit_price == approx(110)  # 100 * 1.10
    assert t.net_pnl == approx(1_000)


def test_stop_first_when_both_levels_are_touched() -> None:
    res, _ = _long_at_100(
        [(100, 101, 99, 100), (100, 112, 94, 105)], stop_loss_pct=5, take_profit_pct=10
    )
    assert (res.trades[0].exit_reason, res.trades[0].exit_price) == ("stop_loss", 95)


def test_gap_through_the_stop_fills_at_the_open() -> None:
    res, df = _long_at_100([(100, 101, 99, 100), (90, 92, 88, 91)], stop_loss_pct=5)
    (t,) = res.trades
    assert (t.exit_reason, t.exit_price, t.exit_time) == ("stop_loss", 90, df.index[2])
    assert t.bars_held == 1  # exit at bar 2's open
    assert t.net_pnl == approx(-1_000)


def test_gap_through_the_target_fills_at_the_open() -> None:
    res, _ = _long_at_100([(100, 101, 99, 100), (115, 116, 114, 115)], take_profit_pct=10)
    assert (res.trades[0].exit_reason, res.trades[0].exit_price) == ("take_profit", 115)


def test_stops_are_not_checked_on_the_entry_bar() -> None:
    res, _ = _long_at_100([(100, 101, 50, 100), (100, 101, 99, 100)], stop_loss_pct=5)
    assert res.trades[0].exit_reason == "end_of_data"


def test_stop_and_target_of_a_short() -> None:
    df = bars([(100, 100, 100, 100), (100, 101, 99, 100), (101, 106, 100, 104)])
    res = run_backtest(
        df,
        signals(df, {0: -1}),
        {**NO_COSTS, "direction": "long_short", "exits": {"stop_loss_pct": 5}},
    )
    (t,) = res.trades
    assert (t.side, t.exit_reason, t.exit_price) == ("short", "stop_loss", 105)
    assert t.net_pnl == approx(-500)
    df = bars([(100, 100, 100, 100), (100, 101, 99, 100), (95, 96, 88, 90)])
    res = run_backtest(
        df,
        signals(df, {0: -1}),
        {**NO_COSTS, "direction": "long_short", "exits": {"take_profit_pct": 10}},
    )
    assert (res.trades[0].exit_reason, res.trades[0].exit_price) == ("take_profit", 90)


def test_stop_fills_pay_slippage() -> None:
    df = bars([(100, 100, 100, 100), (100, 101, 99, 100), (99, 100, 94, 96)])
    res = run_backtest(
        df,
        signals(df, {0: 1}),
        {"fee_bps": 0, "slippage_bps": 10, "exits": {"stop_loss_pct": 5}},
    )
    t = res.trades[0]
    assert t.entry_price == approx(100.1)
    assert t.exit_price == approx(100.1 * 0.95 * 0.999)  # level from the fill, then slippage


def test_max_bars_exit_at_the_open() -> None:
    df = flat([100, 100, 101, 102, 103, 104])
    res = run_backtest(df, signals(df, {0: 1}), {**NO_COSTS, "exits": {"max_bars_held": 2}})
    (t,) = res.trades
    assert (t.exit_reason, t.exit_time, t.exit_price, t.bars_held) == (
        "max_bars",
        df.index[3],
        102,
        2,
    )


def test_end_of_data_closes_at_the_last_close_with_costs() -> None:
    df = bars([(100, 100, 100, 100), (100, 101, 99, 100), (100, 121, 99, 120)])
    res = run_backtest(df, signals(df, {0: 1}), {"fee_bps": 10, "slippage_bps": 0})
    (t,) = res.trades
    qty = 10_000 / (100 * 1.001)
    assert (t.exit_reason, t.exit_price, t.exit_time) == ("end_of_data", 120, df.index[2])
    assert t.bars_held == 2
    assert t.fees == approx(100 * qty * 0.001 + 120 * qty * 0.001)
    assert res.equity.iloc[-1] == approx(res.metrics["final_equity"])
    assert res.metrics["final_equity"] == approx(10_000 + t.net_pnl)


def test_fixed_vs_fraction_sizing() -> None:
    df = flat([100, 100, 150, 150])
    events = signals(df, {0: 1, 2: -1})
    fixed = run_backtest(df, events, {**NO_COSTS, "sizing": {"mode": "fixed", "value": 1_000}})
    assert fixed.trades[0].quantity == approx(10)
    assert fixed.trades[0].net_pnl == approx(500)
    assert fixed.metrics["final_equity"] == approx(10_500)
    half = run_backtest(df, events, {**NO_COSTS, "sizing": {"mode": "fraction", "value": 0.5}})
    assert half.trades[0].quantity == approx(50)
    assert half.metrics["final_equity"] == approx(12_500)
    # fixed amounts above equity are capped (no leverage)
    big = run_backtest(df, events, {**NO_COSTS, "sizing": {"mode": "fixed", "value": 1e9}})
    assert big.trades[0].quantity == approx(100)


def test_fraction_sizing_compounds() -> None:
    df = flat([100, 100, 200, 200, 100, 100, 200, 200])
    res = run_backtest(df, signals(df, {0: 1, 2: -1, 4: 1, 6: -1}), NO_COSTS)
    assert [t.quantity for t in res.trades] == approx([100, 200])
    assert res.metrics["final_equity"] == approx(40_000)


def test_without_exit_on_opposite_signal_only_stops_exit() -> None:
    df = flat([100, 100, 110, 120, 130])
    res = run_backtest(
        df, signals(df, {0: 1, 2: -1}), {**NO_COSTS, "exits": {"exit_on_opposite_signal": False}}
    )
    assert res.trades[0].exit_reason == "end_of_data"


def test_warm_up_bars_do_not_trade() -> None:
    df = flat([100, 100, 100, 110, 120])
    res = run_backtest(df, signals(df, {0: 1, 2: 1}), NO_COSTS, start=df.index[2])
    # the signal on bar 0 (warm-up) is ignored; bar 2's buy fills at bar 3
    assert res.trades[0].entry_time == df.index[3]
    assert res.bars == 3 and res.equity.index[0] == df.index[2]
    assert res.metrics["buy_and_hold_return_pct"] == approx(20)


def test_end_drops_later_bars() -> None:
    df = flat([100, 100, 110, 120, 130])
    res = run_backtest(df, signals(df, {0: 1}), NO_COSTS, end=df.index[2])
    assert res.bars == 3 and res.trades[0].exit_price == 110


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"fee_bps": -1}, "fee_bps"),
        ({"direction": "both"}, "direction"),
        ({"sizing": {"mode": "fraction", "value": 1.5}}, "sizing.value"),
        ({"sizing": {"mode": "fixed"}}, "required"),
        ({"exits": {"stop_loss_pct": 0}}, "stop_loss_pct"),
        ({"exits": {"max_bars_held": 0}}, "max_bars_held"),
        ({"exits": {"trailing": 1}}, "unknown"),
        ({"leverage": 2}, "unknown"),
        ({"initial_capital": 0}, "initial_capital"),
    ],
)
def test_config_validation(config: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        BacktestConfig.from_dict(config)


def test_config_round_trip() -> None:
    config = BacktestConfig.from_dict(
        {"direction": "long_short", "exits": {"stop_loss_pct": 2, "take_profit_pct": 4}}
    )
    assert BacktestConfig.from_dict(config.to_dict()) == config
    assert config.to_dict()["sizing"] == {"mode": "fraction", "value": 1.0}
