"""No look-ahead, determinism, an independent cross-check and the performance targets."""

import os
import time

import numpy as np
import pandas as pd
import pytest
import trading_strategies as ts

import trading_backtest as tb
from tests.conftest import NO_COSTS, synthetic_ohlcv

CONFIGS = [
    {},
    {"direction": "long_short"},
    {"exits": {"stop_loss_pct": 2, "take_profit_pct": 4, "max_bars_held": 30}},
    {"direction": "long_short", "sizing": {"mode": "fixed", "value": 2_500}},
    {  # risk rules on: ATR stop, partial targets, chandelier trailing + breakeven, risk sizing
        "direction": "long_short",
        "stop": {"type": "atr", "length": 14, "multiplier": 2},
        "take_profit": {
            "type": "r_multiple",
            "levels": [{"r": 1, "close_pct": 50}, {"r": 2, "close_pct": 50}],
        },
        "trailing": {"type": "atr", "length": 14, "multiplier": 3, "breakeven_r": 1},
        "sizing": {"mode": "risk", "risk_pct": 1},
        "guards": {"max_drawdown_pct": 30, "cooldown_bars": 2, "max_consecutive_losses": 4},
    },
    {
        "stop": {"type": "swing", "lookback": 10, "buffer_pct": 0.1},
        "trailing": {"type": "percent", "value": 3, "activation_r": 1},
        "sizing": {"mode": "volatility", "target_pct": 1},
        "guards": {"max_daily_loss_pct": 3},
    },
]


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("key", ["ma_crossover", "rsi_reversal", "donchian_breakout"])
def test_no_look_ahead(ohlcv: pd.DataFrame, key: str, config: dict) -> None:
    """Changing every bar from T on changes nothing that was decided before T."""
    cut = 2_000
    base = tb.backtest(ohlcv, key, None, config)
    changed = ohlcv.copy()
    rng = np.random.default_rng(7)
    factor = rng.uniform(0.7, 1.3, len(ohlcv) - cut)
    for column in ("open", "high", "low", "close"):
        changed.iloc[cut:, changed.columns.get_loc(column)] *= factor
    changed["high"] = changed[["open", "high", "low", "close"]].max(axis=1)
    changed["low"] = changed[["open", "high", "low", "close"]].min(axis=1)
    other = tb.backtest(changed, key, None, config)

    closed_before = [t for t in base.trades if t.exit_index < cut]
    assert closed_before, "the scenario should have trades before the cut"
    assert [t for t in other.trades if t.exit_index < cut] == closed_before
    np.testing.assert_array_equal(base.equity.to_numpy()[:cut], other.equity.to_numpy()[:cut])
    assert base.equity.iloc[cut:].to_numpy().tolist() != other.equity.iloc[cut:].tolist()


@pytest.mark.parametrize("config", CONFIGS)
def test_deterministic(ohlcv: pd.DataFrame, config: dict) -> None:
    a = tb.backtest(ohlcv, "macd_cross", None, config).to_dict()
    b = tb.backtest(ohlcv.copy(), "macd_cross", None, config).to_dict()
    assert a == b


def test_cross_check_against_a_vectorised_calculation(ohlcv: pd.DataFrame) -> None:
    """MA crossover, long only, no stops, no costs: positions are the forward-filled signal
    state shifted to the next open; each trade is open -> open (the last one to the last
    close). Written independently of the engine's loop."""
    signals = ts.run("ma_crossover", ohlcv)
    s = signals["signal"].to_numpy()
    state = pd.Series(np.where(s == 1, 1.0, np.where(s == -1, 0.0, np.nan))).ffill().fillna(0)
    held = state.shift(1).fillna(0).to_numpy()  # in the market during bar i (from its open)
    change = np.diff(np.concatenate(([0.0], held)))
    entries = np.flatnonzero(change == 1)
    exits = np.flatnonzero(change == -1)
    opens, closes, index = ohlcv["open"].to_numpy(), ohlcv["close"].to_numpy(), ohlcv.index
    expected = []
    for k, entry in enumerate(entries):
        if k < len(exits):
            expected.append((index[entry], opens[entry], index[exits[k]], opens[exits[k]]))
        else:
            expected.append((index[entry], opens[entry], index[-1], closes[-1]))
    growth = np.prod([x / e for _, e, _, x in expected])

    result = tb.run_backtest(ohlcv, signals, NO_COSTS)
    got = [(t.entry_time, t.entry_price, t.exit_time, t.exit_price) for t in result.trades]
    assert got == expected
    assert len(got) > 50
    assert result.metrics["final_equity"] == pytest.approx(10_000 * growth, rel=1e-12)
    # the equity curve too: flat between trades, units x close while in a trade
    equity = np.empty(len(ohlcv))
    cash, done = 10_000.0, 0
    for k, entry in enumerate(entries):
        equity[done:entry] = cash
        units = cash / opens[entry]
        stop = exits[k] if k < len(exits) else len(ohlcv)
        equity[entry:stop] = units * closes[entry:stop]
        cash = units * (opens[stop] if stop < len(ohlcv) else closes[-1])
        done = stop
    equity[done:] = cash
    np.testing.assert_allclose(result.equity.to_numpy(), equity, rtol=1e-12)


def test_series_signals_and_input_checks(ohlcv: pd.DataFrame) -> None:
    signals = ts.run("ma_crossover", ohlcv)["signal"]
    a = tb.run_backtest(ohlcv, signals)
    assert a.trades and a.trades[0].entry_reason is None
    with pytest.raises(ValueError, match="aligned"):
        tb.run_backtest(ohlcv, signals.iloc[1:])
    with pytest.raises(ValueError, match="-1, 0 or 1"):
        tb.run_backtest(ohlcv, signals * 2)
    with pytest.raises(ValueError, match="no bars"):
        tb.run_backtest(ohlcv, signals, start=ohlcv.index[-1] + pd.Timedelta("1h"))
    with pytest.raises(ValueError, match="missing column"):
        tb.run_backtest(ohlcv.drop(columns="low"), signals)


def test_result_shapes(ohlcv: pd.DataFrame) -> None:
    result = tb.backtest(ohlcv, "supertrend_flip", start=ohlcv.index[500])
    assert result.bars == len(ohlcv) - 500
    assert (result.drawdown <= 0).all()
    frame = result.trades_frame()
    assert list(frame.columns)[:4] == ["number", "side", "entry_time", "entry_price"]
    assert set(frame["exit_reason"]) <= set(tb.EXIT_REASONS)
    data = result.to_dict()
    assert len(data["equity"]) == result.bars and data["trades"][0]["number"] == 1
    assert all(t.entry_index >= 501 for t in result.trades)  # first fill after the window start


FACTOR = float(os.environ.get("BACKTEST_PERF_FACTOR", "1"))


RISK_D = {  # the "(d)" configuration of docs/risk-management.md
    "stop": {"type": "atr", "length": 14, "multiplier": 2},
    "take_profit": {"type": "r_multiple", "value": 2},
    "trailing": {"type": "atr", "length": 14, "multiplier": 3},
    "sizing": {"mode": "risk", "risk_pct": 1},
}


@pytest.mark.perf
@pytest.mark.parametrize("config", [None, RISK_D], ids=["plain", "risk"])
@pytest.mark.parametrize(("bars", "freq", "limit"), [(17_500, "h", 1.0), (100_000, "min", 5.0)])
def test_performance_targets(bars: int, freq: str, limit: float, config) -> None:
    df = synthetic_ohlcv(bars, freq=freq)
    tb.backtest(df.iloc[:1000], "ma_crossover", None, config)  # import / first-use costs
    best = min(_timed(lambda: tb.backtest(df, "ma_crossover", None, config)) for _ in range(3))
    label = "risk" if config else "plain"
    print(f"BENCH {bars} bars ({freq}, {label}): {best * 1000:.0f} ms")
    assert best < limit * FACTOR


def _timed(fn) -> float:
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t
