# Data quality gate (B5)

The AI engine (ai-service, stateless) will be called on every closed 15m bar of
`fxpro:XAU/USD` (B9). Before each call the backend has to answer two questions: **which bar is
closed**, and **is the data good enough to evaluate it**. This page describes both, the state
the platform keeps, and the health endpoint.

Code: `app/services/market_service.py` (watermark, closed candles), `app/services/data_quality.py`
(the checks, pure), `app/services/data_health.py` (state, transitions),
`app/tasks/data_quality.py` (beat task), `app/api/v1/health.py` (`/health/data`). The session
calendar is described in [instruments.md](instruments.md#session-calendar).

## 1. Closed bars only

`candles_1m` is the source of truth. `candles_5m` … `candles_1d` are hierarchical continuous
aggregates with `materialized_only = false` (migration 0003), so the newest bucket of every
aggregate is **still forming**. It is built from the 1m bars that exist so far. The aggregates
are not changed. The cut is applied when reading.

**Watermark** = the end of the last closed 1m bar:

```
watermark = min(floor_to_minute(now), next_open(last_1m_ts + 1 minute))
```

- `floor_to_minute(now)`: the minute that is still running is never closed.
- `last_1m_ts + 1 minute`: a bar that has not arrived cannot be used.
- `next_open(...)` (session calendar): if the market closed right after the last bar, the bars
  of the closure never come. The watermark then follows the clock, so the bar that ends at a
  break or a weekend counts as closed once its wall-clock end has passed. Without a calendar
  (24/7) this is just `last_1m_ts + 1 minute`.

A bar of any timeframe is **closed** when `ts + interval <= watermark`.

**Example.** At 10:07:20, with 1m data up to the 10:06 bar, the watermark is 10:07. The 15m
bucket 10:00 ends at 10:15 and is still forming, so **09:45 is the last closed 15m bar**. At
10:15:05 with data up to 10:14, the watermark is 10:15 and 10:00 is closed. For 1h at 10:07:20,
the last closed bar is 09:00.

**Do sources write still-forming 1m bars?** Yes, so the `floor_to_minute(now)` cap is needed:

| Path | Writes the running minute? |
|---|---|
| `simulate-live` (CLI, demo) | yes: it rewrites the current minute's candle on every tick |
| `seed-demo-candles` (CLI, demo) | yes: its last candle is the minute of `now` |
| `POST /admin/instruments/{id}/candles` | it does not refuse one (any minute-aligned `ts` is accepted) |
| FxPro cTrader feed (next prompt) | to be decided there; the cap makes it safe either way |

Rows dated in the future are ignored. Holes before the last bar do not move the watermark
back: the `gaps` check reports them.

**Reading closed bars:**

- `market_service.closed_watermark(session, instrument, now=None)`: one index lookup.
- `market_service.get_closed_candles(session, instrument_id, timeframe, start=None, end=None,
  limit=500)`: like `get_candles`, only closed buckets; it also returns `watermark` and
  `last_closed_bar_ts`, the newest closed bar even when paging back with `end`.
- `GET /api/v1/market/instruments/{id}/candles?timeframe=15m&closed_only=true`: the same over
  HTTP, with `last_closed_bar` (unix seconds) in the answer. The default, `closed_only=false`,
  keeps today's behaviour, because charts want the forming bar.

## 2. The checks

`data_quality.assess(candles_1m, *, calendar, now, timeframe="15m", lookback=200, thresholds)`
is pure: no database. It evaluates **the last closed `timeframe` bar in which the market traded**,
or `bar=` when the caller names one, plus the `lookback` buckets of wall-clock time ending with
it (200 × 15m = 50 hours). Weekends, the daily break and holidays come from the instrument's
`session_calendar`. An instrument without one trades 24/7.

| Check | Fails when | Threshold (setting) |
|---|---|---|
| `no_data` | there is no 1m candle in the window | – |
| `closed_bar` | the bar has not ended by the watermark, or one of its 1m bars is missing. Minutes in which the market was closed do not count | – |
| `gaps` | any expected 1m bar is missing **inside the evaluated bar**, or the missing share over the window exceeds the limit. The detail gives the count, the share and the longest gap | `DATA_QUALITY_MAX_MISSING_PCT=1.0` (%) |
| `ohlc` | any 1m bar in the window has a price `<= 0`, inconsistent OHLC (`high < low`, …) or a negative spread. On the evaluated bar it also fails on a **spike**, `abs(close / previous close − 1)` above the limit (not across a weekend or break), or a spread above `max_spread` when that is set | `DATA_QUALITY_SPIKE_PCT=2.0` (%), `max_spread` unset |
| `freshness` | while the market is open: `lag = now − watermark` is above the limit. A grace period of the same length follows every open | `DATA_QUALITY_MAX_LAG_SECONDS=120` |

"Expected" bars come from `sessions.expected_bar_starts`, so the closed stretches of the
calendar are never gaps. The database already enforces `high >= low` and the other OHLC checks
on `candles_1m`. The re-check is cheap and protects the engine from other paths. The
thresholds are global settings for now (`Thresholds.from_settings()`); a per-instrument
override can come later.

### Statuses, and what B9 must do

| Status | When | B9 |
|---|---|---|
| `ok` | the market is open and every check passed | **evaluate** the bar in `last_closed_bar` |
| `closed` | the market is closed now (`next_open` and the `freshness` detail say when it opens). Also when nothing was expected in the window | **skip** |
| `degraded` | the market is open and a check failed (`checks[].ok == false`) | **skip and log** the failed checks |
| `no_data` | no 1m candle in the window while bars were expected, or the instrument does not exist | **skip and log** |

The last bar before a break or the weekend closes when the market is already closed, so it is
assessed as `closed` and skipped: nobody could trade on it before the next open anyway.

`QualityReport`: `instrument`, `timeframe`, `status`, `checks` (`name`, `ok`, `detail`),
`last_closed_bar`, `watermark`, `evaluated_at`, `lag_seconds`, `next_open`.

`data_quality.load_and_assess(session, instrument, timeframe, now=None)` reads the inputs with
**two queries**: the newest 1m candle (an index lookup), then the 1m candles of the window. On
200 bars of 15m (3,000 minutes, 2,870 rows once the daily breaks are excluded) it takes about
70 ms on the local Docker database, of which about 32 ms is the pure assessment.

## 3. State, alerts, health

- **Beat task `data_quality.check`**: every minute, 15 s after the boundary when the last 1m
  bar has arrived, on the default queue (`worker`). It expires if it has not started within
  55 s. For each instrument of `DATA_QUALITY_INSTRUMENTS` it runs `load_and_assess`: one query
  for the instruments, two per instrument. The report is stored in Redis as JSON at
  `dq:report:<source>:<symbol>` with a TTL of 300 s. The last status is kept at
  `dq:status:<source>:<symbol>` (7 days), swapped atomically (`SET … GET`).
- **Transitions**: a status change is logged **once**, at WARNING when the new status is
  `degraded`/`no_data` and INFO otherwise, with the failed checks. When an instrument turns
  bad, or recovers, every active admin also gets **one** `system` notification (in-app, plus
  Telegram/push by their preferences). Changes between `ok` and `closed` (the daily break,
  the weekend) and the first check after a fresh start are only logged. A status that does
  not change logs nothing, so a missing instrument does not spam the logs.
- **Flapping cooldown (B9)**: after an alert, no other alert about the same instrument is sent
  for `DATA_QUALITY_ALERT_COOLDOWN_SECONDS` (default 1800). The state itself
  (`dq:status:…`, `/health/data`, the AI evaluation's gate) still changes at once. What the
  admins were last told is kept at `dq:alerted:<source>:<symbol>` (`bad`/`good`) and the
  cooldown at `dq:alert-cooldown:<source>:<symbol>`; the check runs every minute, so a change
  held back by the cooldown is sent once when it ends if the instrument is still in that
  state (ok → degraded → ok within 30 minutes sends one alert; staying ok sends the recovery
  after the cooldown). `0` turns the cooldown off.
- **`GET /api/v1/health/data`**: public and read-only, like `/health/ready`, with no rate limit.
  It reads the stored reports and computes a missing one on the spot (cached for 60 s).

  ```json
  {"status": "no_data",
   "instruments": [{"instrument": "fxpro:XAU/USD", "timeframe": "15m", "status": "no_data",
                    "last_closed_bar": null, "lag_seconds": null, "next_open": null,
                    "evaluated_at": "2026-10-20T10:00:15Z",
                    "failed_checks": [{"name": "no_data", "ok": false,
                                       "detail": "no 1m candles between … and …"}]}]}
  ```

  It returns **503** if any monitored instrument is `degraded` or `no_data`, and 200 when all
  are `ok` or `closed`. With `DATA_QUALITY_ENABLED=false` (or an empty list) it returns 200
  `{"status": "disabled", "instruments": []}`. Its 503 is logged at WARNING, not counted as an
  unhandled error.
- **Admin system status** (`GET /admin/system/status`): `data_quality` lists the full reports,
  and `celery.tasks` shows the last run of `data_quality.check`.

### `/health/data` vs `/health/ready`

`/health/ready` keeps exactly its meaning: `"status": "ok"` when the database and Redis
answer. The deploy (`infra/deploy/remote-deploy.sh`) waits for that and **rolls back** when it
does not come. The answer now also has `"data": "<worst status>"` (`ok`, `closed`, `degraded`,
`no_data`, `unknown` when no report is stored, `disabled`). It is for information only, read
from Redis, and never changes `status` or the HTTP code.

This deviates from the original design, which put data quality into readiness. Production has
no FxPro candles yet (the feed comes in the next prompt), so `fxpro:XAU/USD` is `no_data`
there. A readiness check that failed on it would roll back every deploy. Bad market data is
also not a reason to restart or remove the API. Monitoring that cares about the data watches
`/health/data`.

## 4. Settings

| Setting | Default | |
|---|---|---|
| `DATA_QUALITY_ENABLED` | `true` | the beat task and `/health/data` |
| `DATA_QUALITY_INSTRUMENTS` | `fxpro:XAU/USD` | comma list of `source:symbol` |
| `DATA_QUALITY_MAX_LAG_SECONDS` | `120` | `freshness` |
| `DATA_QUALITY_MAX_MISSING_PCT` | `1.0` | `gaps` |
| `DATA_QUALITY_SPIKE_PCT` | `2.0` | `ohlc` spike on 1m |
