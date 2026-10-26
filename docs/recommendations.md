# Recommendations (Y17)

Each user gets a ranked list of what to look at now, built from their own strategies, follows
and risk settings. They also get, per market, the strategies that have actually worked there.

**Advisory only.** A score ranks what to look at first, from past outcomes:
- It is **not** a forecast, not a probability that a trade wins, and never a guarantee.
- Past hit rates can change.
- Every number comes from the Y16 outcomes ([predictions.md](predictions.md)).

Code: `app/services/recommendation_service.py` and `app/api/v1/recommendations.py`. The outcome
expressions and grouped counts are reused from `app/services/prediction_service.py`
(`signal_outcome`, `ai_outcome`, `ai_generated_at`, `track_records`). There is no second
definition of an outcome.

## 1. Sources of `GET /me/recommendations`

| Source | What is listed |
|---|---|
| `strategy` | buy/sell signals of your **active** activations (`user_strategies` with `is_active`: same instrument, timeframe, strategy key and params hash). Each must be at most `RECOMMENDATION_MAX_AGE_BARS` (3) closed bars old and still `open` in Y16 (no outcome yet). Private strategies you may no longer use are left out (B12) |
| `ai` | ARMED or ACTIVE AI setups of the instruments and profiles you **follow** (`/me/ai/follows`) that you may read. A follow's `min_grade` applies only while `AI_GRADES_ENABLED`, as for the alerts |

Inactive activations, other users' activations, resolved signals and older signals are not listed.

**Fields of each item:**
- `id`: the Y16 prediction id (`sig:<uuid>` or `ai:<setup_id>`), so the app can open
  `GET /predictions/{id}`.
- `source`, `instrument_id`, `symbol`, `timeframe`, `strategy_key` (the profile for AI),
  `direction`, `generated_at`.
- `age_bars`: closed bars of its timeframe since then. 0 means the signal is on the last closed
  bar. For AI setups it is counted in 15m bars from when the setup was published.
- `user_strategy_id`.
- `plan`: your **stored** plan. For a signal this is the `signal_plans.plan` of your
  activation. For an AI setup it is your stored size (lots, risk_amount, currency,
  margin_required, feasible, warnings, source).
  - Nothing is sized in this request.
  - Without a stored plan, `plan` is null and `plan_missing_reason` says why: `no_plan_stored`
    for a signal, or `not_sized_yet` for an AI setup (`GET /ai/setups/{id}/size` sizes it).
- `track_record`, `score`, `score_reasons`: see below.

The list is sorted by score, then newest first. `limit` is at most 50.

It costs two queries for the items, plus one for the track records, or none when they are
cached. Each source reads at most 500 candidate rows.

## 2. Track record

The Y16 outcomes of the **same strategy key** (or AI profile), on the **same instrument and
timeframe**, over every user's predictions:
- `resolved` = tp_hit + sl_hit + expired;
- `decided` = tp_hit + sl_hit;
- `hit_rate` = tp_hit / decided;
- `hit_rate_lower`: the Wilson 95 % lower bound;
- `mean_return_pct` (signals) or `mean_realized_r` (AI setups).

Rows with a data gap are left out, as in Y16. With no decided rows, the rates are null.

### The Wilson lower bound

A hit rate of 3 out of 4 is not as good as 600 out of 800. The Wilson score interval accounts
for how many predictions a rate is based on. Its lower bound, at 95 % (z = 1.96):

```
p = hits / n
lower = (p + z²/(2n) − z·sqrt(p(1 − p)/n + z²/(4n²))) / (1 + z²/n)
```

| hits / n | hit rate | lower bound |
|---|---|---|
| 0 / 0 | – | 0 (shown as null) |
| 5 / 10 | 50 % | 0.2366 |
| 58 / 100 | 58 % | 0.4821 |
| 70 / 120 | 58 % | 0.4939 |
| 10 / 10 | 100 % | 0.7225 |

## 3. The score

```
base   = hit_rate_lower      if decided ≥ RECOMMENDATION_MIN_SAMPLES (20)
       = 0.5 (neutral prior)  otherwise ("not enough history")
age    = 0.85 ^ age_bars      (15 % less per bar of age)
bonus  = 0.05                 if your risk profile is complete, else 0
score  = min(1, base × age + bonus), rounded to 4 decimals
```

**"Risk profile complete"** means that sizing is risk-based (`sizing.mode = risk` with
`risk_pct`) and both guards (`max_daily_loss_pct`, `max_drawdown_pct`) are set: none of the
AI risk inputs comes from a default. The default template has no guards, so it does not count.

`score_reasons` lists each step in words, for example:
`["track record: 70 of 120 hit (58%), 95% lower bound 49%", "1 bar old: x0.85", "risk profile complete: +0.05"]`.

**Worked example.** An `ma_crossover` signal on XAU/USD 15m:
- The track record there is 70 of 120 decided.
- The signal is 1 bar old.
- The user's risk profile is complete.

The score is 0.4939 × 0.85 + 0.05 = **0.4698**. The same signal with 12 decided predictions
would use the 0.5 prior instead: 0.5 × 0.85 + 0.05 = **0.475**.

## 4. `GET /recommendations/strategies`: which strategy fits a market

Query: `instrument_id` and `timeframe`, both required; `limit` up to 20. A missing parameter or
an unknown timeframe gives 422; an unknown instrument gives 404.

- **Candidates:** the built-in catalog, plus the custom strategies you may use: your own and
  public ones (B12). Another user's private strategy never appears.
- **Each entry:** `rank`, `strategy_key`, `name`, `kind` (`builtin` or `custom`), and the
  track record on this instrument and timeframe (`resolved`, `decided`, `hit_rate`,
  `hit_rate_lower`, `mean_return_pct`). It also has:
  - `insufficient_history`: decided < `RECOMMENDATION_MIN_SAMPLES`;
  - `already_active`: you run it here;
  - `backtest`: your latest **completed** backtest here (`id`, `total_return_pct`,
    `win_rate_pct`, `max_drawdown_pct`, `finished_at`), for information only. It is not part
    of the rank.
- **Rank:** by `hit_rate_lower`, highest first. Entries with insufficient history come last,
  most history first.
- **Cache:** the per-(instrument, timeframe) counts are cached in Redis under
  `reco:track:{instrument_id}:{timeframe}` for `RECOMMENDATION_CACHE_SECONDS` (300). The same
  cache serves `/me/recommendations`.
  - Nothing user-specific is cached: `already_active`, backtests, plans and visibility are read
    per request.
  - The cached counts include every key. Each user is shown only the keys they may use.

## 5. Signal notification line (optional)

With `RECOMMENDATIONS_NOTIFY=true`, the signal notification for an activation gets one more
line when its strategy has a track record on that market:

> Track record: this strategy hit 58% of 120 signals on XAU/USD 15m (past results, not a guarantee)

The Arabic version reads "السجل: أصابت هذه الاستراتيجية 58% من 120 إشارة على XAU/USD 15m (نتائج سابقة وليست ضماناً)".

The line uses the same cached counts. A failure only drops the line; the notification still
goes out. **Off by default:** the notification is then exactly as before.

## 6. What v1 can and cannot show

- **Can:** hit rates, their lower bounds and mean returns of strategy signals per market (once
  Y16 has resolved enough of them), and the outcomes of AI setups (mean realized R).
- **Cannot:** any probability. ai-service v1 has no model, so `probability` is null. Signal
  `strength` is not a probability and is never used as one. The score is built from past hit
  rates only.
- **Early days:** most entries say "not enough history" until 20 predictions of a key are
  decided on a market. Until then the score is the neutral 0.5, adjusted only for age and the
  risk bonus.

## 7. Settings

| Setting | Default | |
|---|---|---|
| `RECOMMENDATION_MAX_AGE_BARS` | 3 | older signals are not listed |
| `RECOMMENDATION_MIN_SAMPLES` | 20 | decided predictions before a track record counts |
| `RECOMMENDATION_CACHE_SECONDS` | 300 | Redis cache of the per-market counts |
| `RECOMMENDATIONS_NOTIFY` | false | the notification line (off: unchanged) |

There is no migration, no new service and no new Celery task. The endpoints are read-only and
run in the backend. The notification line, when turned on, runs in the existing signal engine,
reading the cache.
