# Backtesting

Run a global strategy over historical candles and get everything a results page needs:
metrics, equity and drawdown curves, trades and chart markers. The engine is the
[`trading-backtest`](../libs/backtest/README.md) package. Its README has the complete
execution model and every metric formula; the essentials are repeated here.

## Execution model (summary)

- A signal on bar `t` is filled at the **open of bar `t + 1`** (never at `t`'s close).
  Strategies only use bars `≤ t` (no look-ahead, property-tested).
- Candles before `start` are loaded only as the strategy's warm-up history (the same amount as
  `strategy.history(params)`, like the preview endpoint). Trading happens only on bars in
  `[start, end]`.
- **Costs:** fee `fee_bps` (default 10 = 0.10 %) per side, and slippage `slippage_bps`
  (default 5) against you on every fill. **Except** on an instrument with a fixed
  `cost_per_unit` (XAU/USD: 0.25 per oz per round trip, Fadi): the server puts it in the
  config, `fee_bps` and `slippage_bps` are ignored, fills are at the chart prices and the whole
  round trip (`cost_per_unit × quantity`) is charged at the entry as the trade's fee
  ([risk-management.md](risk-management.md#fixed-cost-per-unit-per-instrument)).
- **Direction:** `long_only` (default: sells only close longs) or `long_short` (a sell opens a
  short; an opposite signal reverses).
- **Sizing:** `fraction` of current equity (default 1.0, compounding), a `fixed` quote amount,
  `risk` (lose `risk_pct` % at the stop) or `volatility` (1 ATR = `target_pct` % of equity),
  capped at `max_position_pct` (100 = no leverage), skipped below `min_notional`.
- **Exits** (all rules and formulas: [risk-management.md](risk-management.md)):
  - stops: percent, ATR (of the signal bar) or swing; trailing (percent or ATR chandelier,
    `activation_r`, `breakeven_r`), updated at the close and effective from the next bar;
  - targets in % or R, with partial exits (`levels`); every exit fill is recorded;
  - checked with each bar's high/low, **including the entry bar** (`check_entry_bar`, default
    true; the Y11 behaviour is `false`);
  - a gap beyond the stop or a target fills at the open;
  - if a stop and a target are touched in one bar, the stop is assumed first;
  - `max_bars_held`;
  - exit on opposite signal (default on).
- **Guards:** max daily loss, max drawdown, cooldown after a stop-out, pause after consecutive
  losses. Skipped entries are counted per reason in `metrics.skipped_entries`.
- One position at a time. An open position is closed at the last close (`end_of_data`).
- **Sharpe / Sortino:** annualized from per-bar returns with `P = 365 × 24 h / bar length`
  (8,760 for 1h), risk-free rate 0. `sharpe = mean(r) / std(r) × √P`;
  `sortino = mean(r) / √(mean(min(r, 0)²)) × √P`.
- **Benchmark:** buy & hold from the first window bar's open to the last close.

## API (`/api/v1`)

| Method | Path | Access | |
|---|---|---|---|
| POST | `/backtests` | JWT | Queue a backtest → **202** `{id, status: "queued"}`. Costs 5 rate-limit units. |
| GET | `/backtests` | JWT or API key `backtests:read` | Yours, newest first (`Page`), filters `status`, `strategy_key`, `instrument_id`; `headline` metrics once completed |
| GET | `/backtests/{id}` | JWT or `backtests:read` | Full result (below) |
| GET | `/backtests/{id}/trades` | JWT or `backtests:read` | Trades, paginated (`limit` ≤ 500) |
| GET | `/backtests/{id}/trades.csv` | JWT or `backtests:read` | All trades as CSV |
| DELETE | `/backtests/{id}` | JWT | Cancel if queued/running, otherwise delete (204) |
| POST | `/backtests/compare` | JWT | `{ids: [2..6]}` of your completed backtests: metrics side by side, equity normalised to 100 |

Another user's backtest answers 404.

### Create

```json
POST /api/v1/backtests
{
  "instrument_id": "76aa70d6-069f-42a3-8500-ff324f4da1d1",
  "timeframe": "1h",
  "strategy_key": "ma_crossover",
  "params": { "fast": 9, "slow": 21 },
  "start": "2026-03-01T00:00:00Z",
  "end": "2026-10-15T00:00:00Z",
  "config": {
    "initial_capital": 10000, "fee_bps": 10, "slippage_bps": 5,
    "direction": "long_only",
    "sizing": { "mode": "risk", "risk_pct": 1.0 },
    "stop": { "type": "atr", "length": 14, "multiplier": 2 },
    "take_profit": { "type": "r_multiple", "levels": [ { "r": 1, "close_pct": 50 }, { "r": 2, "close_pct": 50 } ] },
    "trailing": { "type": "atr", "length": 14, "multiplier": 3 },
    "guards": { "max_drawdown_pct": 15 },
    "check_entry_bar": true,
    "exits": { "max_bars_held": null, "exit_on_opposite_signal": true }
  }
}
```

The Y11 fields `exits.stop_loss_pct` and `exits.take_profit_pct` are still accepted (aliases of
a percent stop and a percent target). `"risk_profile": true` in `config` uses your risk profile
(its rules, fee and account size; request fields win) and stores a snapshot of it in
`config.risk_profile`.

`params` and `config` are optional (defaults filled in and stored resolved). `strategy_key`
can also be a custom strategy, `custom:<uuid>` (yours or a public one, with empty `params`). Its
definition is then stored as a snapshot in `config.strategy`, so the backtest stays reproducible
after the strategy is edited or deleted ([custom-strategies.md](custom-strategies.md)). Errors:

| Status | Cause |
|---|---|
| 422 | Unknown strategy, bad params or config (config errors are a list with `loc` and `path`, e.g. `stop.multiplier`); `start ≥ end`; `end` in the future; no candles in the range; more than 200,000 bars (the message gives the count) |
| 404 | Unknown instrument |
| 429 | Quota (below) |

### Result (`GET /backtests/{id}`)

```json
{
  "id": "…", "status": "completed", "progress": 100, "error": null,
  "instrument": { "id": "…", "symbol": "BTC/USDT", "source": "binance" },
  "timeframe": "1h", "strategy_key": "ma_crossover", "params": { "fast": 9, "slow": 21, "adx_min": 0.0 },
  "params_hash": "…", "config": { "…": "resolved" },
  "cost_model": "bps", "cost_per_unit": null,
  "start": "…", "end": "…", "first_bar": "…", "last_bar": "…", "bars": 5480,
  "metrics": { "total_return_pct": 12.3, "cagr_pct": 19.8, "max_drawdown_pct": -8.1,
               "max_drawdown_start": "…", "max_drawdown_end": "…", "max_drawdown_recovered": "…",
               "sharpe": 1.21, "sortino": 1.9, "calmar": 2.4, "trades": 47, "win_rate_pct": 38.3,
               "profit_factor": 1.4, "avg_win": 210.5, "avg_loss": -95.2, "expectancy": 26.1,
               "best_trade_pct": 9.8, "worst_trade_pct": -3.1, "avg_bars_held": 31.2,
               "exposure_pct": 26.8, "total_fees": 950.4, "buy_and_hold_return_pct": 18.0,
               "final_equity": 11230.0, "initial_capital": 10000.0, "bars": 5480,
               "bars_per_year": 8760.0,
               "avg_r": 0.21, "expectancy_r": 0.19, "avg_risk_pct": 1.0, "max_consecutive_losses": 5,
               "r_distribution": { "<-2": 0, "-2..-1": 18, "-1..0": 9, "0..1": 6, "1..2": 14, "2..3": 0, ">=3": 0 },
               "exits_by_reason": { "stop_loss": 18, "partial_tp": 14, "take_profit": 9, "opposite_signal": 20 },
               "skipped_entries": { "max_drawdown": 2 } },
  "equity":   [ { "time": 1772323200, "value": 10000.0 }, "…" ],
  "drawdown": [ { "time": 1772323200, "value": 0.0 }, "…" ],
  "markers":  [ { "time": 1772420400, "position": "belowBar", "shape": "arrowUp", "color": "#2196F3", "text": "#1 Long" },
                { "time": 1772542800, "position": "aboveBar", "shape": "arrowDown", "color": "#26a69a", "text": "#1 TP +4.00%" } ],
  "created_at": "…", "started_at": "…", "finished_at": "…", "duration_ms": 1830, "engine_ms": 95
}
```

- `cost_model` is `bps` (`fee_bps` + `slippage_bps`) or `fixed_per_unit` (the instrument's
  `cost_per_unit`, also in `config.cost_per_unit`; an XAU/USD run says `"cost_model":
  "fixed_per_unit", "cost_per_unit": 0.25`). `config.cost_per_unit` is set by the server only:
  a request that sets it gets a 422.
- `equity` and `drawdown` are Lightweight Charts line data (unix seconds). There are at most
  2,000 points: per bucket the equity min/max and the deepest drawdown are kept, so peaks,
  troughs and the worst drawdown are always visible.
- `markers` can be passed straight to `series.setMarkers()`. Exit texts are
  `#n Exit|SL|Trail|BE|TP|Time|End ±P&L%`, green for winners and red for losers. A partial
  exit gets its own marker, `#n Partial TP ±move%`.
- Trades (`GET /backtests/{id}/trades`) also have `initial_stop`, `risk_amount`, `r_multiple`
  and `fills` (`[{time, index, price, quantity, reason}]`); the CSV has the first three.

## Execution and progress

Backtests run as Celery tasks on the queue `backtests`, served by the compose service
`worker-backtest` (concurrency 2), so they never delay the live signal engine (`worker`).

Progress goes to the owner's WebSocket `user:{id}` topic (see [websocket.md](websocket.md)):

```json
{"type": "backtest_progress", "backtest_id": "…", "status": "running", "progress": 30}
{"type": "backtest_completed", "backtest_id": "…", "status": "completed", "progress": 100,
 "metrics": {"total_return_pct": …, "buy_and_hold_return_pct": …, "max_drawdown_pct": …,
             "sharpe": …, "trades": …, "win_rate_pct": …, "profit_factor": …}}
{"type": "backtest_failed", "backtest_id": "…", "status": "failed", "error": "…"}
```

`progress`: 5 = started, 30 = candles loaded, 80 = computed, 100 = saved. A cancel
publishes `backtest_progress` with `status: "cancelled"`.

- **Time limit:** 300 s per backtest (Celery soft limit). Beyond it the backtest is `failed`
  with "Time limit exceeded …".
- **Worker crash:** a task lost with its worker is not retried. A beat task (every 5 min, and
  whenever a worker starts) fails backtests that have been `running` for longer than the limit
  plus 1 minute, or `queued` for more than 6 hours.
- **Cancellation:** `DELETE` on a queued or running backtest sets `cancelled`. The task checks
  after loading, after computing and when saving, and stops without storing anything.

## Quotas

| Role | Queued + running at once | Per UTC day |
|---|---|---|
| trader | 2 | 30 |
| analyst / expert | 5 | 200 |
| admin | 10 | unlimited |

Over a quota → 429 with a message saying which one. Settings: `BACKTEST_CONCURRENT_<ROLE>`,
`BACKTEST_DAILY_<ROLE>`, `BACKTEST_MAX_BARS`, `BACKTEST_TIME_LIMIT_SECONDS`.
