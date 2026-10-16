# trading-backtest

Backtesting of trading strategies on pandas OHLCV data. Pure Python (numpy, pandas,
[`trading-strategies`](../strategies/README.md)), no I/O, deterministic. The backend runs it in
Celery workers (`POST /api/v1/backtests`); it works the same in a notebook.

## Install

```bash
# repo / backend (local packages first: pip cannot resolve their relative paths by itself)
pip install -e libs/indicators -e libs/strategies -e libs/backtest

# Colab / Kaggle
pip install "git+https://github.com/yazan-alsamman/ai-trading-analysis-system@main#subdirectory=libs/indicators"
pip install "git+https://github.com/yazan-alsamman/ai-trading-analysis-system@main#subdirectory=libs/strategies"
pip install "git+https://github.com/yazan-alsamman/ai-trading-analysis-system@main#subdirectory=libs/backtest"
```

## Use

```python
import trading_backtest as tb

result = tb.backtest(
    df,  # open, high, low, close (volume); UTC DatetimeIndex
    "ma_crossover",
    {"fast": 9, "slow": 21},
    {"fee_bps": 10, "slippage_bps": 5, "exits": {"stop_loss_pct": 2, "take_profit_pct": 4}},
    start="2025-01-01",  # bars before start: indicator warm-up only
)
result.metrics["sharpe"], result.metrics["max_drawdown_pct"]
result.trades_frame()  # one row per trade
result.equity, result.drawdown  # per bar (pandas Series)

# any signal source (a model, a custom rule set): 1 buy, -1 sell, 0 nothing per bar
result = tb.run_backtest(df, signals_frame_or_series, config)
```

Give `backtest()` enough bars before `start` for the strategy's warm-up
(`trading_strategies.get_strategy(key).history(params)`).

## Configuration (`BacktestConfig`)

| Field | Default | |
|---|---|---|
| `initial_capital` | 10,000 | quote currency |
| `fee_bps` | 10 | per side, of the fill's notional (0.10 %, Binance spot) |
| `slippage_bps` | 5 | against you on every fill |
| `direction` | `long_only` | `long_only`: sells only close longs. `long_short`: a sell opens a short, a buy closes it; an opposite signal reverses |
| `sizing` | `{"mode": "fraction", "value": 1.0}` | `fraction` of current equity (compounding; notional + entry fee fit in it) or `fixed` quote amount per trade (capped at equity, no leverage) |
| `exits.stop_loss_pct` | none | % from the entry fill |
| `exits.take_profit_pct` | none | % from the entry fill |
| `exits.max_bars_held` | none | closes at the open `n` bars after the entry bar |
| `exits.exit_on_opposite_signal` | true | |

`BacktestConfig.from_dict()` validates JSON input (unknown fields are errors). Sizing (`Sizer`)
and exits (`ExitRules`) are small classes so risk management can add ATR stops, trailing stops
and risk-based sizing later.

## Execution model

- **Fills.** A signal on bar `t` is computed on the closed bar and filled at the **open of bar
  `t + 1`**, never at bar `t`'s close. Only signals on bars inside the window
  (`start`…`end`) are taken. A signal on the last bar is not filled.
- **Costs.** Every fill pays slippage against you (a buy at `price × (1 + s)`, a sell at
  `price × (1 − s)`) and a fee of `fill × quantity × fee_bps / 10,000`, on entry and on exit.
- **One position at a time.** A new entry in the same direction while in a position is ignored.
- **Order inside each bar `i`:**
  1. stop-loss or take-profit already beyond the open (a gap) → filled at the open;
  2. `max_bars_held` reached → closed at the open;
  3. the signal of bar `i − 1` → open, close, or close and reverse, at the open;
  4. stop-loss / take-profit touched by the bar's low/high → filled at the level. Only for
     positions opened before bar `i` (never on the entry bar). If both are touched in the same
     bar, the **stop is assumed first** (conservative);
  5. equity marked to market at the close.
- **End of data.** An open position is closed at the last close (`exit_reason = "end_of_data"`).
- **Exit reasons:** `opposite_signal`, `stop_loss`, `take_profit`, `max_bars`, `end_of_data`.
- **Accounting.** Equity = cash + position value. A long holds `+q × price`; a short keeps the
  sale proceeds in cash and owes `q × price`.
- `bars_held` counts the bars a position was open in (an exit at a bar's open does not count
  that bar). `exposure_pct = Σ bars_held / bars × 100`.

## Metrics

`E_0` is the initial capital, `E_1…E_n` the equity at each bar close of the window and `P` the
bars per year.

| Metric | Formula |
|---|---|
| per-bar return | `r_i = E_i / E_(i−1) − 1` (`r_1` against `E_0`) |
| `total_return_pct` | `(E_n / E_0 − 1) × 100` |
| `cagr_pct` | `((E_n / E_0) ^ (P / n) − 1) × 100` (None if it overflows, e.g. a few hours annualized) |
| `sharpe` | `mean(r) / std(r, ddof = 1) × √P`, risk-free rate 0 |
| `sortino` | `mean(r) / √(mean(min(r, 0)²)) × √P`, target 0, over all periods |
| drawdown | `DD_i = E_i / max(E_0…E_i) − 1`; `max_drawdown_pct = min(DD) × 100`, with the peak (`max_drawdown_start`), the trough (`max_drawdown_end`) and the first bar back at the peak (`max_drawdown_recovered`) |
| `calmar` | `CAGR / |max drawdown|` |
| `win_rate_pct` | trades with `net_pnl > 0` / trades |
| `profit_factor` | Σ winning `net_pnl` / |Σ losing `net_pnl`| (None without losses) |
| `avg_win`, `avg_loss`, `expectancy` | mean `net_pnl` of winners, of losers, of all trades |
| `best_trade_pct`, `worst_trade_pct`, `avg_bars_held`, `exposure_pct`, `total_fees` | |
| `buy_and_hold_return_pct` | `(last close / open of the first window bar − 1) × 100`, no costs |

`P` = 365 days × 24 h / bar length (crypto trades around the clock): 8,760 for 1h, 525,600 for
1m. By default it is inferred from the median bar spacing, or passed as `bars_per_year`.
Undefined ratios (no variance, no losses, no trades) are `None`.

`downsample_indices(equity, drawdown, 2000)` picks at most 2,000 points for charts: the first
and last bar, and in each of 666 equal buckets the equity minimum, the equity maximum and the
deepest drawdown. Peaks, troughs and the worst drawdown always survive, unlike plain striding.

## Guarantees (tests)

- Hand-built frames check every fill, fee and slippage amount to the cent, and both directions,
  stops, targets, gaps, max bars, end of data and sizing.
- Metrics are checked against independent pandas calculations.
- **No look-ahead:** changing every bar from `T` on leaves all trades closed before `T` and the
  equity before `T` bit-identical.
- A vectorised re-implementation (MA crossover, long only, no costs) gives exactly the same
  trades and equity curve.
- Performance: 17,500 bars (2 years of 1h) take about 50 ms; 100,000 1m bars about 260 ms
  (targets 1 s and 5 s).
