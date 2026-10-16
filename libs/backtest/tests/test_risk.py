"""Risk rules on tiny frames where every level, quantity and fill is known by hand: stops
(percent, ATR, swing), trailing (percent, ATR chandelier, activation, breakeven), partial
targets, sizing modes with caps and min notional, account guards, the entry bar, plans."""

import json
import math

import pytest
import trading_indicators as ti

from tests.conftest import NO_COSTS, bars, signals, synthetic_ohlcv
from trading_backtest import BacktestConfig, ConfigError, plan_trade, run_backtest
from trading_backtest.risk import TEMPLATES, breakeven_level, validate_risk_config

approx = pytest.approx
CALM = (100, 101, 99, 100)  # true range 2 every bar -> ATR = 2 once warmed up


def run(rows, events, config, **kw):
    df = bars(rows)
    return run_backtest(df, signals(df, events), {**NO_COSTS, **config}, **kw), df


# --- stops ---------------------------------------------------------------------------------------


def test_percent_stop_and_its_alias_are_the_same() -> None:
    rows = [CALM, (100, 101, 99, 100), (99, 100, 97, 98)]
    new, _ = run(rows, {0: 1}, {"stop": {"type": "percent", "value": 2}})
    old, _ = run(rows, {0: 1}, {"exits": {"stop_loss_pct": 2}})
    (t,) = new.trades
    assert (t.exit_reason, t.exit_price, t.initial_stop) == ("stop_loss", 98, 98)
    assert old.trades == new.trades


def test_atr_stop_uses_the_signal_bar_atr() -> None:
    rows = [CALM] * 6 + [(100, 101, 99.5, 100), (100, 100.5, 95, 96)]
    cfg = {"stop": {"type": "atr", "length": 3, "multiplier": 2}}
    res, df = run(rows, {5: 1}, cfg)
    assert ti.atr(df, 3).iloc[5] == approx(2.0)
    (t,) = res.trades
    assert t.initial_stop == approx(96.0)  # 100 - 2 x 2
    assert (t.exit_reason, t.exit_price, t.exit_index) == ("stop_loss", approx(96.0), 7)
    assert plan_trade(df, 5, "buy", {"stop": cfg["stop"]}, 10_000).stop == approx(96.0)


def test_atr_stop_unavailable_during_warm_up_skips_the_entry() -> None:
    res, _ = run([CALM] * 5, {1: 1}, {"stop": {"type": "atr", "length": 3}})
    assert res.trades == []
    assert res.metrics["skipped_entries"] == {"stop_unavailable": 1}


def test_swing_stop_below_the_lowest_low_with_buffer() -> None:
    rows = [CALM, CALM, (100, 101, 98, 100), (100, 101, 97, 100), (100, 101, 99, 100)]
    rows += [(100, 101, 99, 100), (99, 100, 95, 96)]
    cfg = {"stop": {"type": "swing", "lookback": 3, "buffer_pct": 1}}
    res, df = run(rows, {4: 1}, cfg)
    (t,) = res.trades
    assert t.initial_stop == approx(97 * 0.99)  # lowest low of bars 2..4, 1 % below
    assert (t.exit_reason, t.exit_price) == ("stop_loss", approx(96.03))
    short = plan_trade(df, 4, "sell", {"stop": cfg["stop"]}, 10_000)
    assert short.stop == approx(101 * 1.01)


def test_swing_stop_on_the_wrong_side_of_the_fill_is_skipped() -> None:
    rows = [CALM, CALM, CALM, (90, 91, 89, 90)]  # gaps below the swing low (99 x 0.99)
    res, _ = run(rows, {2: 1}, {"stop": {"type": "swing", "lookback": 3, "buffer_pct": 1}})
    assert res.trades == [] and res.metrics["skipped_entries"] == {"stop_wrong_side": 1}


def test_stop_of_a_short() -> None:
    rows = [CALM] * 6 + [(100, 101, 99, 100), (101, 104.5, 100, 104)]
    cfg = {"direction": "long_short", "stop": {"type": "atr", "length": 3, "multiplier": 2}}
    res, _ = run(rows, {5: -1}, cfg)
    (t,) = res.trades
    assert (t.side, t.initial_stop, t.exit_price) == ("short", approx(104), approx(104))


# --- entry bar ---------------------------------------------------------------------------------


def test_entry_bar_stop_first_and_no_gap_rule() -> None:
    # bar 1 opens at 100 (the fill), touches both 98 (stop) and 104 (target): stop first
    rows = [CALM, (100, 105, 97, 101)]
    cfg = {"stop": {"type": "percent", "value": 2}, "take_profit": {"type": "percent", "value": 4}}
    res, _ = run(rows, {0: 1}, cfg)
    assert (res.trades[0].exit_reason, res.trades[0].exit_price) == ("stop_loss", 98)
    res, _ = run([CALM, (100, 105, 99, 101)], {0: 1}, cfg)
    assert (res.trades[0].exit_reason, res.trades[0].exit_price) == ("take_profit", 104)
    off, _ = run([CALM, (100, 105, 97, 101)], {0: 1}, {**cfg, "check_entry_bar": False})
    assert off.trades[0].exit_reason == "end_of_data"


# --- trailing ------------------------------------------------------------------------------------


def test_percent_trailing_is_updated_at_the_close_and_applies_next_bar() -> None:
    rows = [
        CALM,
        (100, 102, 99, 101),  # entry; close: highest high 102 -> stop 96.9
        (101, 110, 103, 108),  # low 103 > 96.9; close: highest 110 -> stop 104.5
        (108, 109, 104, 105),  # low 104 <= 104.5 -> out at 104.5
    ]
    res, _ = run(rows, {0: 1}, {"trailing": {"type": "percent", "value": 5}})
    (t,) = res.trades
    assert (t.exit_reason, t.exit_price, t.exit_index) == ("trailing_stop", approx(104.5), 3)
    assert t.initial_stop is None and t.r_multiple is None


def test_trailing_never_moves_against_you() -> None:
    rows = [CALM, (100, 110, 99, 109), (109, 109.5, 106, 107), (107, 108, 103, 104)]
    res, _ = run(rows, {0: 1}, {"trailing": {"type": "percent", "value": 5}})
    # stop 104.5 after bar 1; bar 2's lower high must not lower it; bar 3 hits 104.5
    assert res.trades[0].exit_price == approx(104.5)


def test_atr_chandelier_trailing() -> None:
    rows = [CALM] * 6 + [(100, 102, 99.5, 101), (101, 106, 100.5, 105), (105, 105.5, 97, 98)]
    cfg = {"trailing": {"type": "atr", "length": 3, "multiplier": 2}}
    res, df = run(rows, {5: 1}, cfg)
    atr = ti.atr(df, 3).to_numpy()
    level = 106 - 2 * atr[7]  # set at bar 7's close from its highest high since entry
    (t,) = res.trades
    assert (t.exit_reason, t.exit_index) == ("trailing_stop", 8)
    assert t.exit_price == approx(level)


def test_trailing_activation_r() -> None:
    # R = 2 (2 % stop at 100); trail 1 % only after +2 R (high >= 104)
    cfg = {
        "stop": {"type": "percent", "value": 2},
        "trailing": {"type": "percent", "value": 1, "activation_r": 2},
    }
    rows = [CALM, (100, 103, 99, 102), (102, 102.5, 100, 101)]
    res, _ = run(rows, {0: 1}, cfg)
    assert res.trades[0].exit_reason == "end_of_data"  # 103 < 104: the stop stays at 98
    rows = [CALM, (100, 105, 99, 104), (104, 104.5, 103, 103.5)]
    res, _ = run(rows, {0: 1}, cfg)
    (t,) = res.trades
    assert (t.exit_reason, t.exit_price) == ("trailing_stop", approx(105 * 0.99))


def test_breakeven_covers_the_costs() -> None:
    cfg = {
        "fee_bps": 10,
        "slippage_bps": 5,
        "stop": {"type": "percent", "value": 2},
        "trailing": {"breakeven_r": 1},
    }
    rows = [CALM, (100, 103, 99.9, 102), (102, 102, 99, 100)]
    df = bars(rows)
    res = run_backtest(df, signals(df, {0: 1}), cfg)
    (t,) = res.trades
    level = breakeven_level(1, 100 * 1.0005, 0.001, 0.0005)
    assert (t.exit_reason, t.fills[0]["price"]) == ("breakeven_stop", approx(level * 0.9995))
    assert t.net_pnl == approx(0, abs=1e-9)


# --- targets -------------------------------------------------------------------------------------

LEVELS = {
    "stop": {"type": "percent", "value": 2},
    "take_profit": {
        "type": "r_multiple",
        "levels": [{"r": 1, "close_pct": 50}, {"r": 2, "close_pct": 50}],
    },
}


def test_partial_targets() -> None:
    rows = [CALM, (100, 102.5, 99, 102), (102, 104.5, 101, 104)]
    res, _ = run(rows, {0: 1}, LEVELS)
    (t,) = res.trades
    assert [(f["price"], f["quantity"], f["reason"]) for f in t.fills] == [
        (102, 50, "partial_tp"),
        (104, 50, "take_profit"),
    ]
    assert (t.quantity, t.exit_price, t.gross_pnl, t.exit_reason) == (100, 103, 300, "take_profit")
    assert t.risk_amount == approx(200) and t.r_multiple == approx(1.5)
    assert res.metrics["exits_by_reason"] == {"partial_tp": 1, "take_profit": 1}
    assert res.metrics["final_equity"] == approx(10_300)


def test_stop_after_a_partial_target_and_runner() -> None:
    rows = [CALM, (100, 102.5, 99, 102), (101, 101.5, 97, 97.5)]
    res, _ = run(rows, {0: 1}, LEVELS)
    (t,) = res.trades
    assert [f["reason"] for f in t.fills] == ["partial_tp", "stop_loss"]
    assert t.net_pnl == approx(50 * 2 - 50 * 2)  # +1 R on half, -1 R on half
    runner = {
        **LEVELS,
        "take_profit": {"type": "r_multiple", "levels": [{"r": 1, "close_pct": 50}]},
    }
    rows = [CALM, (100, 102.5, 99, 102), (102, 110, 101, 109)]
    res, _ = run(rows, {0: 1}, runner)
    assert [(f["reason"], f["quantity"]) for f in res.trades[0].fills] == [
        ("partial_tp", 50),
        ("end_of_data", 50),
    ]


def test_gap_through_both_targets_fills_at_the_open() -> None:
    rows = [CALM, (100, 101, 99, 100), (106, 107, 105, 106)]
    res, _ = run(rows, {0: 1}, LEVELS)
    fills = res.trades[0].fills
    assert [(f["price"], f["reason"]) for f in fills] == [(106, "partial_tp"), (106, "take_profit")]


def test_percent_target_levels() -> None:
    cfg = {
        "take_profit": {
            "type": "percent",
            "levels": [{"pct": 1, "close_pct": 25}, {"pct": 3, "close_pct": 75}],
        }
    }  # noqa: E501
    rows = [CALM, (100, 101.5, 99, 101), (101, 103, 100, 102)]
    res, _ = run(rows, {0: 1}, cfg)
    assert [(f["price"], f["quantity"]) for f in res.trades[0].fills] == [(101, 25), (103, 75)]


# --- sizing --------------------------------------------------------------------------------------


def test_risk_sizing() -> None:
    cfg = {"stop": {"type": "percent", "value": 2}, "sizing": {"mode": "risk", "risk_pct": 1}}
    res, _ = run([CALM, CALM, (99, 100, 97, 98)], {0: 1}, cfg)
    (t,) = res.trades
    assert t.quantity == approx(50)  # 1 % of 10,000 = 100 at risk, 2 per unit
    assert (t.risk_amount, t.risk_pct, t.r_multiple) == (approx(100), approx(1), approx(-1))
    assert res.metrics["final_equity"] == approx(9_900)
    # with fees: (entry - stop) + both fees per unit
    df = bars([CALM, CALM])
    plan = plan_trade(df, 0, 1, {**cfg, "fee_bps": 10}, 10_000)
    assert plan.quantity == approx(100 / (2 + (100 + 98) * 0.001))
    assert plan.risk_amount == approx(100) and plan.risk_pct == approx(1)


def test_sizing_caps_and_min_notional() -> None:
    tight = {"stop": {"type": "percent", "value": 0.1}, "sizing": {"mode": "risk", "risk_pct": 1}}
    res, _ = run([CALM, CALM, CALM], {0: 1}, tight)
    assert res.trades[0].quantity == approx(100)  # 1,000 units wanted, capped at 100 % equity
    half = {**tight, "sizing": {"mode": "risk", "risk_pct": 1, "max_position_pct": 50}}
    res, _ = run([CALM, CALM, CALM], {0: 1}, half)
    assert res.trades[0].quantity == approx(50)
    tiny = {"sizing": {"mode": "fixed", "value": 5}}
    res, _ = run([CALM, CALM, CALM], {0: 1}, tiny)
    assert res.trades == [] and res.metrics["skipped_entries"] == {"size_below_min": 1}
    res, _ = run([CALM, CALM, CALM], {0: 1}, {"sizing": {**tiny["sizing"], "min_notional": 1}})
    assert res.trades[0].quantity == approx(0.05)


def test_volatility_sizing() -> None:
    cfg = {"sizing": {"mode": "volatility", "target_pct": 1, "length": 3}}
    res, _ = run([CALM] * 8, {5: 1}, cfg)
    assert res.trades[0].quantity == approx(50)  # 1 % of 10,000 / ATR 2
    res, _ = run([CALM] * 8, {1: 1}, cfg)
    assert res.metrics["skipped_entries"] == {"atr_unavailable": 1}


# --- guards --------------------------------------------------------------------------------------


def test_max_drawdown_guard_halts_new_entries() -> None:
    cfg = {"stop": {"type": "percent", "value": 6}, "guards": {"max_drawdown_pct": 5}}
    rows = [CALM, CALM, (93, 94, 92, 93), *[CALM] * 5]
    res, _ = run(rows, {0: 1, 3: 1, 5: 1}, cfg)
    assert len(res.trades) == 1 and res.trades[0].exit_reason == "stop_loss"
    assert res.metrics["skipped_entries"] == {"max_drawdown": 2}


def test_daily_loss_guard_resets_next_day() -> None:
    # hourly bars from 2025-01-01 00:00: bars 0-23 day 1, bar 24 on day 2
    rows = [CALM, (100, 101, 95, 95.5), *[CALM] * 24]  # stopped out at 96 on bar 1: -4 %
    cfg = {"stop": {"type": "percent", "value": 4}, "guards": {"max_daily_loss_pct": 3}}
    df = bars(rows)
    res = run_backtest(df, signals(df, {0: 1, 5: 1, 24: 1}), {**NO_COSTS, **cfg})
    assert [t.entry_index for t in res.trades] == [1, 25]  # bar 6 skipped, day 2 allowed
    assert res.metrics["skipped_entries"] == {"daily_loss": 1}


def test_cooldown_after_a_stop_out() -> None:
    cfg = {"stop": {"type": "percent", "value": 2}, "guards": {"cooldown_bars": 3}}
    rows = [CALM, (100, 101, 97, 98), *[CALM] * 8]  # stopped out on bar 1
    res, _ = run(rows, {0: 1, 1: 1, 2: 1, 3: 1, 4: 1}, cfg)
    # entries on bars 2, 3, 4 (<= 1 + 3) are skipped; the signal of bar 4 fills on bar 5
    assert [t.entry_index for t in res.trades] == [1, 5]
    assert res.metrics["skipped_entries"] == {"cooldown": 3}


def test_pause_after_consecutive_losses() -> None:
    cfg = {"guards": {"max_consecutive_losses": 2, "cooldown_bars": 4}}
    rows = [CALM, CALM, (99, 99, 99, 99), CALM, (99, 99, 99, 99), *[CALM] * 7]
    rows.append((101, 101, 101, 101))  # the third trade wins
    events = {0: 1, 1: -1, 2: 1, 3: -1, 4: 1, 8: 1}
    res, _ = run(rows, events, cfg)
    # two losing trades (100 -> 99 and 100 -> 99), the second closes on bar 4: entries on bars
    # <= 8 are paused, so the buy of bar 4 is skipped and the buy of bar 8 fills on bar 9
    assert [t.entry_index for t in res.trades] == [1, 3, 9]
    assert res.metrics["skipped_entries"] == {"loss_streak": 1}
    assert res.metrics["max_consecutive_losses"] == 2


# --- plans and metrics -------------------------------------------------------------------------


RISKY = {
    "stop": {"type": "atr", "length": 14, "multiplier": 2},
    "trailing": {"type": "atr", "length": 14, "multiplier": 3, "breakeven_r": 1},
    "take_profit": LEVELS["take_profit"],
    "sizing": {"mode": "risk", "risk_pct": 1},
}


def test_plan_trade_is_what_the_engine_used_at_entry() -> None:
    df = synthetic_ohlcv(2000, seed=3)
    import trading_backtest as tb

    res = tb.backtest(df, "ma_crossover", None, {**RISKY, "direction": "long_short"})
    assert len(res.trades) > 20
    for t in res.trades:
        plan = plan_trade(
            df,
            t.entry_index - 1,
            t.side,
            BacktestConfig.from_dict({**RISKY, "direction": "long_short"}),
            t.entry_equity,
            entry=t.entry_price,
        )
        assert plan.valid
        assert plan.stop == t.initial_stop and plan.quantity == t.quantity
        assert plan.risk_amount == t.risk_amount and plan.risk_pct == t.risk_pct


def test_plan_fields_and_reference_entry() -> None:
    df = bars([CALM] * 20)
    plan = plan_trade(df, 19, "buy", {**RISKY, "fee_bps": 0}, 10_000)
    d = plan.to_dict()
    json.dumps(d)
    assert (d["side"], d["entry_ref"], d["stop"]) == ("long", 100.0, 96.0)  # close - 2 x ATR 2
    assert d["targets"] == [
        {"price": 104.0, "r": 1.0, "close_pct": 50.0},
        {"price": 108.0, "r": 2.0, "close_pct": 50.0},
    ]
    assert (d["quantity"], d["notional"], d["risk_amount"], d["risk_pct"], d["rr"]) == (
        25.0,
        2500.0,
        100.0,
        1.0,
        1.0,
    )
    assert d["invalid_reason"] is None and d["trailing"]["type"] == "atr"
    short = plan_trade(df, 19, "sell", {**RISKY, "fee_bps": 0}, 10_000, entry=101, stop=103)
    assert (short.stop, short.targets[0]["price"], short.quantity) == (103, 99, 50)
    wrong = plan_trade(df, 19, "sell", RISKY, 10_000, stop=99)
    assert wrong.invalid_reason == "stop_wrong_side"
    early = plan_trade(df, 3, "buy", RISKY, 10_000)
    assert early.invalid_reason == "stop_unavailable"
    with pytest.raises(ValueError, match="side"):
        plan_trade(df, 3, "up", RISKY, 10_000)


def test_plan_trade_never_reads_bars_after_the_signal() -> None:
    df = synthetic_ohlcv(600, seed=4)
    shocked = df.copy()
    shocked.iloc[401:] *= 1.7
    for i in (100, 250, 400):
        a = plan_trade(df, i, "buy", RISKY, 10_000).to_dict()
        assert a == plan_trade(shocked, i, "buy", RISKY, 10_000).to_dict()


def test_r_metrics_by_hand() -> None:
    cfg = {
        "stop": {"type": "percent", "value": 2},
        "take_profit": {"type": "r_multiple", "value": 2},
    }
    rows = [CALM, (100, 105, 99, 104), CALM, CALM, (99, 100, 97, 98), CALM]
    res, _ = run(rows, {0: 1, 2: 1}, cfg)
    m = res.metrics
    # trade 1: 100 units, risk 200, +400 = +2 R; trade 2: 104 units stopped out = -1 R
    rs = [t.r_multiple for t in res.trades]
    assert rs[0] == approx(2.0) and rs[1] == approx(-1.0)
    assert m["avg_r"] == approx(0.5)
    assert m["expectancy_r"] == approx(
        sum(t.net_pnl for t in res.trades) / sum(t.risk_amount for t in res.trades)
    )  # noqa: E501
    # buckets are [low, high): exactly -1 R (no costs) is in "-1..0"
    assert m["r_distribution"] == {
        "<-2": 0, "-2..-1": 0, "-1..0": 1, "0..1": 0, "1..2": 0, "2..3": 1, ">=3": 0
    }  # fmt: skip
    assert m["avg_risk_pct"] == approx(2.0)  # 2 % stop with all equity in: 2 % at risk
    assert m["max_consecutive_losses"] == 1
    assert m["exits_by_reason"] == {"stop_loss": 1, "take_profit": 1}


# --- validation, templates -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("config", "path", "message"),
    [
        ({"stop": {"type": "atr", "multiplier": 0}}, "stop.multiplier", "greater than 0"),
        ({"stop": {"type": "magic"}}, "stop", "stop needs 'type'"),
        ({"stop": {"type": "percent", "value": 2, "x": 1}}, "stop.x", "unknown field"),
        (
            {"trailing": {"type": "percent", "value": 2, "activation_r": 1}},
            "trailing.activation_r",
            "needs a stop",
        ),  # noqa: E501
        ({"trailing": {"breakeven_r": 1}}, "trailing.breakeven_r", "needs a stop"),
        ({"take_profit": {"type": "r_multiple", "value": 2}}, "take_profit.type", "need a stop"),
        ({"sizing": {"mode": "risk"}}, "sizing.mode", "risk sizing needs a stop"),
        ({"sizing": {"mode": "yolo"}}, "sizing", "sizing.mode must be one of"),
        ({"sizing": {"mode": "risk", "risk_pct": 0}}, "sizing.risk_pct", "greater than 0"),
        ({"take_profit": {"type": "percent"}}, "take_profit", "give either value or levels"),
        (
            {
                "take_profit": {
                    "type": "percent",
                    "levels": [{"pct": 2, "close_pct": 60}, {"pct": 1, "close_pct": 40}],
                }
            },  # noqa: E501
            "take_profit",
            "ascending",
        ),
        (
            {
                "take_profit": {
                    "type": "percent",
                    "levels": [{"pct": 1, "close_pct": 60}, {"pct": 2, "close_pct": 60}],
                }
            },  # noqa: E501
            "take_profit",
            "at most 100",
        ),
        ({"guards": {"max_consecutive_losses": 2}}, "guards", "needs cooldown_bars"),
        ({"guards": {"max_drawdown_pct": 0}}, "guards.max_drawdown_pct", "greater than 0"),
        ({"check_entry_bar": "yes"}, "check_entry_bar", "boolean"),
        (
            {"stop": {"type": "percent", "value": 2}, "exits": {"stop_loss_pct": 2}},
            "",
            "either stop or exits.stop_loss_pct",
        ),
    ],
)
def test_validation_paths(config: dict, path: str, message: str) -> None:
    with pytest.raises(ConfigError) as exc:
        BacktestConfig.from_dict(config)
    first = exc.value.errors[0]
    assert first["path"] == path, exc.value.errors
    assert message in first["message"]
    assert str(exc.value).startswith(f"{path}: ") if path else message in str(exc.value)


def test_risk_config_normalisation_and_templates() -> None:
    assert set(TEMPLATES) == {"conservative", "balanced", "aggressive"}
    for name, template in TEMPLATES.items():
        normalised = validate_risk_config(template)
        assert validate_risk_config(normalised) == normalised, name
        json.dumps(normalised)
    balanced = validate_risk_config(TEMPLATES["balanced"])
    assert balanced["sizing"] == {
        "mode": "risk",
        "risk_pct": 1.0,
        "max_position_pct": 100.0,
        "min_notional": 10.0,
    }
    assert balanced["take_profit"]["levels"][1] == {"r": 2.0, "close_pct": 50.0}
    assert validate_risk_config({})["stop"] is None
    with pytest.raises(ConfigError) as exc:
        validate_risk_config({"initial_capital": 5})
    assert exc.value.errors[0]["path"] == "initial_capital"
    df = synthetic_ohlcv(1500, seed=9)
    import trading_backtest as tb

    for template in TEMPLATES.values():
        cfg = BacktestConfig.from_risk(template)
        result = tb.backtest(df, "ma_crossover", None, cfg)
        assert result.trades and all(t.initial_stop is not None for t in result.trades)
        assert not math.isnan(result.metrics["final_equity"])
