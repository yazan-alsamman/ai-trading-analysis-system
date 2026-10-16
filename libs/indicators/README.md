# trading-indicators

Technical indicators on pandas OHLCV data, shared by:
- the backend API (indicator lines on the charts),
- the strategy engine,
- the AI feature pipeline (`ai-service/`, Colab and Kaggle notebooks).

It depends only on `numpy` and `pandas`, needs Python 3.10 or newer, and has no I/O and no global state.

## Install

```bash
# from the repo (backend, local dev)
pip install -e libs/indicators

# Colab / Kaggle / any machine, straight from GitHub
pip install "git+https://github.com/yazan-alsamman/ai-trading-analysis-system@main#subdirectory=libs/indicators"
```

## Use

```python
import pandas as pd
import trading_indicators as ti

# columns open, high, low, close, volume; DatetimeIndex in UTC, ascending
df = pd.read_csv("btc_1h.csv", index_col="time", parse_dates=True)

df["rsi"] = ti.rsi(df["close"], length=14)  # Series aligned to df.index
macd = ti.macd(df["close"])  # DataFrame: macd, signal, histogram
bands = ti.compute("bollinger", df, length=20, std=2)  # generic entry point, validated params
ti.lookback("macd")  # 33 warm-up bars before all outputs are valid
ti.catalog()  # JSON-able list for UIs
```

Every function returns values **aligned to the input index**, with `NaN` during the warm-up.

## Indicators

| name | placement | params (defaults) | outputs | warm-up |
|---|---|---|---|---|
| `sma` | overlay | length=20 | sma | length-1 |
| `ema` | overlay | length=20 | ema | length-1 |
| `wma` | overlay | length=20 | wma | length-1 |
| `macd` | pane | fast=12, slow=26, signal=9 | macd, signal, histogram | slow+signal-2 |
| `adx` | pane | length=14 | adx, plus_di, minus_di | 2·length-1 |
| `supertrend` | overlay | length=10, multiplier=3.0 | supertrend, direction | length |
| `ichimoku` | overlay | tenkan=9, kijun=26, senkou=52, displacement=26 | tenkan, kijun, senkou_a, senkou_b | max(lengths)-1+displacement |
| `rsi` | pane (30/70) | length=14 | rsi | length |
| `stoch` | pane (20/80) | k_length=14, k_smooth=3, d_smooth=3 | k, d | sum-3 |
| `stochrsi` | pane (20/80) | rsi_length=14, stoch_length=14, k_smooth=3, d_smooth=3 | k, d | sum-3 |
| `cci` | pane (±100) | length=20, constant=0.015 | cci | length-1 |
| `williams_r` | pane (-80/-20) | length=14 | williams_r | length-1 |
| `roc` | pane (0) | length=10 | roc | length |
| `mfi` | pane (20/80) | length=14 | mfi | length |
| `bollinger` | overlay | length=20, std=2.0 | upper, middle, lower | length-1 |
| `atr` | pane | length=14 | atr | length |
| `keltner` | overlay | length=20, multiplier=2.0, atr_length=10 | upper, middle, lower | max(length-1, atr_length) |
| `donchian` | overlay | length=20 | upper, middle, lower | length-1 |
| `obv` | pane | – | obv | 0 |
| `vwap` | overlay | – (daily, UTC) | vwap | 0 |
| `volume_sma` | pane | length=20 | volume_sma | length-1 |

## Conventions

- **No look-ahead.** The value at bar `t` only uses bars `≤ t`. A property test appends random
  future bars to every indicator and checks that existing values stay bit-for-bit identical.
- **Matches TA-Lib.** EMA is seeded with the SMA of the first `length` values. RSI, ATR and ADX
  use Wilder's smoothing (RMA, `alpha = 1/length`), and ADX/DI use TA-Lib's Wilder sums.
  Bollinger uses the population standard deviation. MACD starts both EMAs at bar `slow-1`, as
  TA-Lib does. All of these are tested against TA-Lib to `1e-8`.
- **Multi-output indicators** emit each output as soon as it is valid (e.g. MACD's `macd` line
  before its `signal`). TA-Lib instead starts all outputs at the same bar.
- **0/0 cases are defined:**
  - RSI, Stoch, StochRSI and MFI are 50 when there is no movement or range.
  - Williams %R is -50 and CCI is 0 in the same situation.
  - DI and ADX are 0 when the true range is 0.
  - ROC is NaN when the reference close is 0.
  - No numpy warnings are emitted.
- **Missing data:**
  - Leading `NaN` values are skipped, so the warm-up starts at the first valid value.
  - A later `NaN` gives `NaN` at that bar. Rolling windows stay `NaN` while the gap is inside them.
  - Recursive smoothers keep their state and continue.
  - OBV compares with the last valid close.
- **VWAP** resets at 00:00 UTC and needs a `DatetimeIndex` (naive timestamps are taken as UTC).
  While the day has no volume yet it equals the typical price.
- **Ichimoku** returns the cloud *as drawn at each bar*: `senkou_a` and `senkou_b` are computed
  `displacement` bars earlier. The cloud projected beyond the last bar and the chikou span are
  not returned, because both need future bars at the index they are drawn on.
- **Supertrend** follows TradingView, but `direction` is `+1` for an uptrend and `-1` for a
  downtrend (TradingView uses the opposite signs). The first valid bar starts as a downtrend.
- **Invalid parameters** (length < 1, non-integer length, `fast >= slow`, missing columns,
  unsorted index) raise `ValueError`. A series shorter than the warm-up returns all `NaN`.

## Development

```bash
pip install -e "libs/indicators[dev]"   # adds pytest, ruff and TA-Lib (test reference only)
cd libs/indicators && ruff check . && pytest -q
```

TA-Lib is only used in tests as a reference implementation, never at runtime. The real-data fixture
`tests/fixtures/btcusdt_1h_binance.csv` holds 1,000 BTCUSDT 1h candles from Binance's public klines API.
