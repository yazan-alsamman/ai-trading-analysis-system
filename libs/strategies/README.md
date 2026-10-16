# trading-strategies

The global trading strategies, implemented with the Strategy pattern on top of
[`trading-indicators`](../indicators/README.md). The package is pure Python: it depends only on
numpy, pandas, pydantic (custom strategy definitions) and trading-indicators, and does no I/O.

The live signal engine (backend), backtesting (Y11) and custom strategies (Y12) use it today. Risk
management (Y13) and recommendations (Y17) will build on it.

## Install

```bash
# repo / backend (indicators first: pip cannot resolve the local path dependency by itself)
pip install -e libs/indicators -e libs/strategies

# Colab / Kaggle
pip install "git+https://github.com/yazan-alsamman/ai-trading-analysis-system@main#subdirectory=libs/indicators"
pip install "git+https://github.com/yazan-alsamman/ai-trading-analysis-system@main#subdirectory=libs/strategies"
```

## Use

```python
import trading_strategies as ts

out = ts.run("rsi_reversal", df, length=14, oversold=30, overbought=70)
buys = out[out["signal"] == 1]  # columns: signal, strength, reason, details
ts.get_strategy("ma_crossover").history()  # bars needed before the first valid signal
ts.catalog()  # JSON-able, incl. the indicator lines to draw
ts.params_hash("rsi_reversal", {})  # stable id of a configuration
```

`df` has the columns `open, high, low, close, volume` and a UTC `DatetimeIndex` in ascending
order.

## Signal semantics

- **Closed bars only.** The signal on bar `t` uses bars `≤ t` and is actionable at the open of
  bar `t + 1`. There is no look-ahead; a property test changes or appends future bars and
  checks that earlier rows stay bit-for-bit identical.
- **Events, not positions.** `signal` is `1` (buy) or `-1` (sell) only on the bar where the
  condition triggers, and `0` on every other bar.
- **Entries only.** Exits, stop-loss and take-profit belong to risk management (Y13).
- **Output columns:**
  - `strength` is in `[0, 1]` (0 without a signal).
  - `reason` is a short code, e.g. `rsi_cross_up_oversold`.
  - `details` holds the numbers behind the signal, e.g.
    `{"rsi_prev": 28.4, "rsi": 31.2, "level": 30, "extreme": 22.1}`, so the UI can explain it
    in a sentence.
- **`history(params)`** is the warm-up plus convergence of every indicator a strategy reads,
  plus one bar. From that bar on, signals do not depend on how much older data is supplied.

## Strategies

| key | params (defaults) | buy | sell | strength |
|---|---|---|---|---|
| `ma_crossover` | fast=9, slow=21, adx_min=0 | EMA(fast) crosses above EMA(slow) | crosses below | ADX(14)/50 |
| `rsi_reversal` | length=14, oversold=30, overbought=70 | RSI prev < oversold ≤ RSI now | RSI prev > overbought ≥ RSI now | depth of the excursion past the level, scaled to 0..1 |
| `macd_cross` | fast=12, slow=26, signal=9, zero_filter=0 | MACD crosses above signal (below zero if filtered) | crosses below (above zero if filtered) | \|MACD\| / ATR(14) |
| `bollinger_reversion` | length=20, std=2.0 | previous close below the lower band, this close back inside | previous close above the upper band, this close back inside | how far outside the previous close was, in σ |
| `supertrend_flip` | length=10, multiplier=3.0 | direction flips to up | direction flips to down | \|close − line\| / (multiplier·ATR) |
| `donchian_breakout` | length=20, volume_factor=0 | first close above the previous N-bar high | first close below the previous N-bar low | breakout distance / ATR(14) |

The optional filters are off at 0. ADX filter: ADX ≥ `adx_min`. Volume filter:
volume > `volume_factor` × the SMA of the previous N bars' volume. Invalid combinations
(`fast ≥ slow`, `oversold ≥ overbought`, unknown or out-of-range params) raise `ValueError`.

## Custom strategies (Builder + Composite)

Users' own strategies, defined as JSON documents and validated with Pydantic (no code, nothing
is ever evaluated as an expression). They behave exactly like the global ones (`generate()`,
`history()`, same signal columns):

```python
import trading_strategies as ts

rules = {
    "schema_version": 1,
    "category": "trend",
    "buy": {
        "all": [
            {
                "left": {"type": "indicator", "name": "ema", "params": {"length": 9}},
                "op": "crosses_above",
                "right": {"type": "indicator", "name": "ema", "params": {"length": 21}},
            }
        ]
    },
}
ts.BuilderStrategy(rules).generate(df)  # BuilderStrategy: rules (AND/OR groups)
combo = {
    "schema_version": 1,
    "mode": "weighted",
    "window": 3,
    "threshold": 0.6,
    "members": [{"ref": "rsi_reversal"}, {"ref": "custom:<uuid>", "weight": 2}],
}
ts.CompositeStrategy(combo, resolver=lambda ref: ("builder", rules)).generate(df)
ts.validate("builder", rules)  # errors with JSON paths, normalised definition
snap = ts.snapshot("composite", combo, resolver)  # rebuild later without a resolver
ts.from_snapshot(snap)
ts.snapshot_hash(snap)  # the setup's identity (like params_hash)
ts.json_schemas()
ts.operand_catalog()  # what editors are generated from
```

Builder and Composite signals are **edge-triggered** (they fire when the rules become true),
and a bar where buy and sell both fire gives no signal. The full format, semantics and the API
built on it are in [docs/custom-strategies.md](../../docs/custom-strategies.md).

## Adding a strategy

1. Subclass `Strategy` and set `key`, `title`, `description`, `category` and `params`
   (`trading_indicators.Param`).
2. Implement `indicators()` (lines to draw), `computed_indicators()` if you read more than you
   draw, `check()` for cross-parameter rules, and `_generate()`. In `_generate()`, build the
   buy/sell masks with vectorised, past-only operations and pass them to `events()`.
3. Add the class to `STRATEGY_CLASSES`, then add a hand-built test. The no-look-ahead and
   registry tests pick the new strategy up automatically.
