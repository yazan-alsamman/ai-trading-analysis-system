# Prediction tracking and accuracy (Y16)

One place that answers "how accurate are our predictions": the history of every published
prediction with its outcome, and aggregate stats over it.

Code:
- `app/services/prediction_service.py`: the list, the detail and the stats, all in SQL.
- `app/services/prediction_resolver.py` and `app/tasks/predictions.py`: the resolver.
- `app/api/v1/predictions.py`: the endpoints.
- `app/models/prediction.py`: `signal_outcomes`, migration 0022.

## 1. Definitions

There are two sources. Both come back in one shape.

| | `source=ai`: AI setups | `source=strategy`: strategy signals |
|---|---|---|
| What counts | setups that were **published**: they reached ARMED (or ACTIVE or CLOSED). DEVELOPING-only setups, and setups dropped before ARMED, are not predictions | every buy/sell row of `signals` (live engine) |
| Stored in | nothing new: derived from `ai_setups` and `ai_setup_events` | `signals`, plus one `signal_outcomes` row once resolved |
| `id` | `ai:<setup_id>` | `sig:<signal uuid>` |
| `timeframe` | `15m` (the decision bar of ai-service) | the signal's timeframe |
| `strategy_key` | the profile (`intraday`) | the strategy key (`ma_crossover`, `custom:<uuid>`, …) |
| `generated_at` | when it was first published (the first ARMED/ACTIVE/CLOSED event; `created_at` if there is none) | when the signal was stored (`signals.created_at`, about the bar's close) |
| `resolved_at` | the event of its final state | `signal_outcomes.resolved_at` |
| `probability` | the setup's probability: **null in v1** (no model) | **null**: `strength` is a 0..1 *signal strength* (for example ADX/50, or the share of agreeing rules), documented in `libs/strategies`, not a probability |
| `risk_reward` | `r_multiple` | null |
| `realized_r` | the setup's `realized_r` | null |
| `return_pct` | null | the move over the horizon, % |
| `model_version` | as stored (null in v1) | null |
| `taken_by_user` | you marked it taken (`ai_setup_takes`) | false |

## 2. Outcome rules

`outcome` is one of `open`, `tp_hit`, `sl_hit` or `expired`, the same values as
`web/src/domain/predictions.ts`.

**AI setups**

| State | Outcome |
|---|---|
| ARMED, ACTIVE | `open` |
| CLOSED with `realized_r > 0` | `tp_hit` |
| CLOSED with `realized_r <= 0` (or null) | `sl_hit` |
| EXPIRED | `expired` |
| INVALIDATED before ACTIVE ("not triggered") | `expired` |
| INVALIDATED after ACTIVE | `expired`, with a **warning** in the log. This should not happen (Fadi) |

**Strategy signals**

| `signal_outcomes` | Outcome |
|---|---|
| no row yet (the horizon has not closed) | `open` |
| `correct = true` | `tp_hit` |
| `correct = false` | `sl_hit` |
| `correct = null` (a data gap) | `expired`, with the reason in `note`, and **left out of every stat** |

## 3. Resolution of strategy signals

The `predictions.resolve_signals` Celery task runs on beat every
`PREDICTION_RESOLVE_INTERVAL_SECONDS` (300). It is on the `maintenance` queue
(worker-backtest), never on the live worker.

- **Horizon.** A signal is resolved on the `H = PREDICTION_HORIZON_BARS` bars (10) of its
  timeframe that follow its bar.
  - These are the bars the market should have, taken from the instrument's session calendar
    (`sessions.expected_bar_starts`), so a weekend or a daily break is not a gap.
  - Without a calendar the instrument trades 24/7, and the horizon ends with the bar at
    `bar_time + H × timeframe`.
  - A signal is due once that last bar is **closed** (the B5 watermark). Until then it stays
    `open`.
  - The `H` used is stored on each row (`horizon_bars`), so changing the setting later does
    not rewrite history.
- **Measures.** All are from the signal's price (`signals.price`) and signed in the signal's
  direction (positive means in its favour), in %:
  - `return_pct`: to the close of the H-th bar (`exit_price`, `exit_ts`);
  - `mfe_pct`: the best high (for a buy) or low (for a sell) of the H bars;
  - `mae_pct`: the worst, negative when the price went against the signal.
- **Cost rule (Fadi's fixed cost).** `correct = side × (exit − entry) > cost`, where `cost` is
  the instrument's `cost_per_unit`: XAU/USD 0.25 per oz, or 0 when it has none. A move that
  does not beat the cost is not correct. The cost used is stored on the row.
  - Example: a buy at 2400.00 that closes the horizon at 2400.20 has gained 0.20, which is
    less than 0.25, so it is `sl_hit` even though `return_pct > 0`.
- **Gaps.** If one of the expected bars is missing, the signal is still resolved, with
  `correct = null`, no prices, and `note` such as `"gap: 1 of 10 bars missing (first …)"`. It is
  shown as `expired` and left out of the stats (`excluded_count`).
- **Batches and memory.** One run handles at most `PREDICTION_RESOLVE_BATCH` (500) due
  signals, oldest first, per instrument and timeframe.
  - For each signal it reads only its H bars from the candle views: no whole-history query and
    no pandas.
  - Old signals are resolved too, gradually: 500 every 5 minutes.
  - Rows are inserted with `ON CONFLICT DO NOTHING`, so a re-run or two overlapping runs never
    write a signal twice.
- A signal deleted later takes its outcome with it (`ON DELETE CASCADE`).

## 4. Stats

`GET /predictions/stats` takes the same filters as the list and computes everything in SQL.
Data-gap rows are left out of all of it, and are counted only in `excluded_count`.

| Field | |
|---|---|
| `total`, `open`, `resolved` | `resolved` = `tp_hit` + `sl_hit` + `expired` |
| `hit_rate` | `tp_hit / (tp_hit + sl_hit)`. Expired rows are not in it (`expired_count`). Null when there is none |
| `tp_hit_count`, `sl_hit_count`, `expired_count`, `excluded_count` | |
| `mean_realized_r` | AI setups, over `tp_hit` and `sl_hit` |
| `mean_return_pct` | strategy signals, over `tp_hit` and `sl_hit` |
| `with_probability`, `mean_predicted` | decided rows (`tp_hit` / `sl_hit`) that have a probability |
| `brier_score` | mean of `(p − y)²`, where y = 1 for `tp_hit` and 0 for `sl_hit`, over those rows only |
| `calibration` | non-empty bins of 0.1: `{from, to, count, mean_predicted, observed_rate}` |
| `by_strategy` | `[{source, strategy_key, total, resolved, hit_rate}]` |

**What v1 can and cannot show.** v1 runs the rules without a model (contract 0.2.1), so no
prediction has a probability:
- `with_probability` is 0, `brier_score` is null and `calibration` is `[]`.
- Nothing is invented: strategy strength is not used as a probability.
- Hit rate, outcomes, mean R and mean return are available now.
- Calibration fills in by itself once ai-service returns probabilities.

## 5. Endpoints (prefix `/api/v1`)

Who can call them: any logged-in user, or an API key with `signals:read`. **B12** applies to
each row in SQL, so lists, totals and stats never count hidden rows:
- a private strategy's signals are seen only by users who may use the strategy (and by admins);
- AI setups are filtered by `strategy_resolver.readable_ai_setups` (every user in v1, the hook
  kept in step with `may_read_ai_setup`).

| Method | Path | |
|---|---|---|
| GET | `/predictions` | `{items, total}`, newest first (`generated_at`). Filters: `source` (`ai`/`strategy`), `instrument_id`, `timeframe`, `strategy_key` (a strategy key, or an AI profile), `profile` (AI only), `outcome`, `from`, `to` (on `generated_at`, inclusive). `limit` up to 200, `offset` |
| GET | `/predictions/stats` | the stats above, with the same filters |
| GET | `/predictions/{id}` | one item plus details. `ai`: the setup's state, entry, sl, tp, grade, ev_r, valid_until and its state events. `signal`: bar_time, price, strength, reason and its `outcome` row (horizon, exit, return, MFE, MAE, correct, cost, note). 404 when the id is unknown or not yours to read |
| GET | `/admin/predictions/resolver` | admin only: settings in use, last run (time, status, resolved, gaps, waiting for the market to reopen, duration, last error and when), `backlog` (signals without an outcome) and `resolved_total` |

Item fields: `id`, `source`, `instrument_id`, `symbol`, `timeframe`, `strategy_key`,
`direction`, `probability`, `risk_reward`, `generated_at`, `resolved_at`, `outcome`,
`realized_r`, `return_pct`, `model_version`, `taken_by_user`, `note`.

## 6. Settings

| Setting | Default | |
|---|---|---|
| `PREDICTION_HORIZON_BARS` | 10 | bars after the signal's bar, stored on each row |
| `PREDICTION_RESOLVE_INTERVAL_SECONDS` | 300 | beat interval of `predictions.resolve_signals` |
| `PREDICTION_RESOLVE_BATCH` | 500 | signals resolved at most per run |
