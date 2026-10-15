# trading-strategies

The global trading strategies, implemented with the Strategy pattern on top of
[`trading-indicators`](../indicators/README.md). The package is pure Python: it depends only on
numpy, pandas and trading-indicators, and does no I/O.

The live signal engine (backend) uses it today. Backtesting (Y11), custom strategies (Y12),
risk management (Y13) and recommendations (Y17) will build on it.

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

## Adding a strategy

1. Subclass `Strategy` and set `key`, `title`, `description`, `category` and `params`
   (`trading_indicators.Param`).
2. Implement `indicators()` (lines to draw), `computed_indicators()` if you read more than you
   draw, `check()` for cross-parameter rules, and `_generate()`. In `_generate()`, build the
   buy/sell masks with vectorised, past-only operations and pass them to `events()`.
3. Add the class to `STRATEGY_CLASSES`, then add a hand-built test. The no-look-ahead and
   registry tests pick the new strategy up automatically.
