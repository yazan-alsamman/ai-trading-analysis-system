# Economic calendar (B6)

The AI engine (ai-service) abstains within ±30 minutes of a high-impact event. It receives the
calendar in every `POST /v1/evaluate` request (B9), and the same filter runs in backtests. So
the platform keeps the calendar **with its history, point in time**: every version of an event
is stored with the time it became known, and a read "as of T" sees only what was known at T.

Code: `app/calendar/events.py` (the event row, numbers, key, hash; pure),
`app/calendar/forexfactory.py` (the live fetch), `app/calendar/service.py` (storage,
point-in-time reads, `for_evaluate`, the refresh), `app/calendar/csv_import.py` (history),
`app/tasks/calendar.py` (beat task), `app/api/v1/calendar.py` (REST),
`backend/scripts/load_calendar_csv.py` (local loader). Table: `economic_events` (migration 0014).

## 1. Sources and their terms

| Source | `source` | What | Terms |
|---|---|---|---|
| ForexFactory weekly JSON `https://nfs.faireconomy.media/ff_calendar_thisweek.json` | `forexfactory_live` | the current week (Sunday to Saturday, New York), every currency (~100 events) | free and public, no key. The host rate-limits or blocks clients that poll too often, so we stay polite (section 4) |
| Kaggle ForexFactory dataset (CSV, 2018 onward) | `forexfactory_kaggle` | history | **licence to verify before publishing results.** Downloaded by hand by an admin and **never committed** to the repository; the test fixture is a hand-made 30-row file |
| Manual rows (`--source manual`) | `manual` | corrections | ours |

Every currency the source gives is stored (it is cheap). Reads default to
`CALENDAR_CURRENCIES` (`USD`). v1 scope is USD events, which are the ones that move gold.

The live JSON items look like this, and nothing else is required:

```json
{"title": "CPI m/m", "country": "USD", "date": "2026-07-14T08:30:00-04:00",
 "impact": "High", "forecast": "0.3%", "previous": "0.2%"}
```

`actual` appears on some items. `country` is the currency (`All` is kept as `ALL`). `impact` is
`High`/`Medium`/`Low`/`Holiday`. The shape is checked at runtime:

- a body that is not a JSON list fails the fetch (logged; the state shows it);
- an item that does not validate (missing `title`/`country`/`date`/`impact`, unknown impact,
  `date` without an offset) is skipped with a warning, and the others are stored;
- unknown extra fields are ignored.

A bare day (`2026-07-13`) or a `time` field saying `All Day`/`Tentative` gives an event without a
time.

## 2. The table: one row per observed version

| Column | |
|---|---|
| `event_key` varchar(64) | stable identity of the event across its versions |
| `source` | `forexfactory_live`, `forexfactory_kaggle`, `manual` (check constraint) |
| `currency` varchar(8) | upper case (check constraint) |
| `title` | as published |
| `impact` | `high`, `medium`, `low`, `holiday` (check constraint) |
| `scheduled_at` timestamptz | UTC; null for All Day / Tentative |
| `scheduled_date` date | the event's day in New York, always set (see below) |
| `time_label` | `All Day`, `Tentative`, ... when there is no time |
| `actual`, `forecast`, `previous` | raw strings as published (`0.3%`, `-12K`) |
| `actual_value`, `forecast_value`, `previous_value` | parsed: `%` stripped, `K`/`M`/`B`/`T` multiplied; null when not a plain number (`<1.50%`) |
| `fetched_at` timestamptz | when we learned this version |
| `content_hash` varchar(64) | sha256 of the fields that define a version |

Indexes: `(event_key, fetched_at DESC)`, `(scheduled_at)`, `(currency, impact, scheduled_at)`,
and `UNIQUE (event_key, content_hash)`. Migration 0014 only creates this table. Its downgrade
drops it.

`scheduled_date` is one column more than the original design. Without it, an All Day or
Tentative event (null `scheduled_at`) would never appear in a date-range read.

### `event_key`

```
event_key = sha256(source family | currency | normalised title | day in America/New_York)
```

- The **source family** is `forexfactory` for both ForexFactory sources, so live rows and
  history merge. `manual` is its own family.
- The **normalised title** is lower-cased with single spaces.
- The **day** is the scheduled day in New York (ForexFactory's calendar), as first observed.
- **Moved time:** when a live fetch shows a currency and title that are not stored for that
  day, it is matched to an existing event of the same currency and title **in the same
  ForexFactory week** (Sunday to Saturday, New York). The existing event must also be
  **absent from this fetch at its old day**. The event keeps its key, and the new time is a
  new version.
  - The nearest day wins when there are several.
  - History rows (CSV) use their natural key only: a file does not say what moved.

Examples:

- `USD | non-farm employment change | 2026-01-09` is NFP of that Friday.
- NFP fetched on Sunday with `forecast 60K` gets key K. On Friday at 13:31 it comes with
  `actual 50K`: same key K, a second version.
- "Fed Chair Powell Testifies" on Wednesday, then shown on Thursday of the same week and no
  longer on Wednesday: same key, a new version with the new time.
- A new event (a title not stored that week) gets a new key.

**Limits:**

- **Two events with the same title on one day** (two "FOMC Member Speaks") share a key. Their
  versions then mix, and the latest one wins.
- If one of two same-titled events of a week moves onto the other's day, it is taken as that
  event.
- An event moved into **another week** becomes a new event; the old one stays as last seen.
- A title that ForexFactory renames is a new event.

### Versions

A row is inserted only when `content_hash` changes. The hash covers `scheduled_at`,
`time_label`, `impact`, `actual`, `forecast`, `previous` and `title`. The unique
`(event_key, content_hash)` with `ON CONFLICT DO NOTHING` makes every write idempotent: fetching
the same week again inserts nothing (`unchanged`).

One consequence: a value that goes A → B → A cannot store the second A (it is the same version
as the first). The latest version stays B until something else changes. This is rare
(ForexFactory revisions move forward), and it is listed as an open issue.

## 3. Point in time

What was known at T about the events scheduled in `[start, end]`:

```sql
WITH latest AS (
  SELECT DISTINCT ON (event_key) *
  FROM economic_events
  WHERE fetched_at <= :as_of
    AND event_key IN (SELECT event_key FROM economic_events
                      WHERE scheduled_date BETWEEN :start_day - 8 AND :end_day + 8)
  ORDER BY event_key, fetched_at DESC)
SELECT * FROM latest
WHERE (scheduled_at BETWEEN :start AND :end
       OR scheduled_at IS NULL AND scheduled_date BETWEEN :start_day AND :end_day)
  AND impact IN (...) AND currency IN (...)
ORDER BY coalesce(scheduled_at, <start of its New York day>), currency, title
```

This is `service.latest_as_of(session, start, end, *, as_of=None, currencies=None,
min_impact="low")`, one query. The filters apply to the **newest version**, so an event that
moved out of the range, or lost impact, is not shown by an older version. Impact order:
`holiday < low < medium < high`.

### History `fetched_at` (an approximation)

We do not know when each historical value was first published, so the CSV import assumes:

| Row in the CSV | Versions stored |
|---|---|
| without `actual` | one, `fetched_at = scheduled_at − 7 days` |
| with `actual` | two: the row **without** `actual` at `scheduled_at − 7 days`, then the full row at `scheduled_at` |

Rows without a time use the start of their New York day instead of `scheduled_at`.

An "as of" read before the release sees the forecast but never the actual, which is what a
backtest needs. What it cannot see:

- forecast revisions during the week;
- events that were announced less than 7 days ahead (they look known earlier than they were);
- a release time that moved.

The pre-release version is stored even when the forecast is empty: the event was on the
calendar beforehand.

## 4. The live refresh

- **Beat task `calendar.refresh`.**
  - Checked at minutes 7, 22, 37 and 52 of every hour, on the default queue (`worker`).
  - It fetches only when due: the key `cal:attempted` is set on every attempt with a TTL of
    `CALENDAR_FETCH_INTERVAL_MINUTES` (240), and no key means due.
  - A run that is not due costs two Redis reads and no request. The interval survives restarts
    and deploys.
- **One request per run.**
  - `GET CALENDAR_FF_URL` with `User-Agent: AI-Trading-Platform-Calendar/1.0 (+economic
    calendar; ...)` and `Accept: application/json`.
  - A conditional GET with the last `ETag` (`If-None-Match`): a `304` stores nothing.
  - One deadline of `CALENDAR_FETCH_TIMEOUT_SECONDS` (15) for the whole request.
  - A body cap of `CALENDAR_FETCH_MAX_BYTES` (2 MB), checked on `Content-Length` and while
    reading. The real week is about 12 KB.
- **Lock.** A Redis lock (`cal:lock`, `SET NX EX 120`, released only by its owner) keeps two
  workers, or the task and the admin button, from fetching at once. The second one answers
  `locked`.
- **Backoff.**
  - A `429` or `403` stores `cal:backoff_until` = now + `CALENDAR_BACKOFF_HOURS` (6), with the
    same TTL, and logs **one** warning.
  - Until then every run, the admin refresh included, returns `backoff` at DEBUG level and
    sends nothing.
  - Other failures (timeout, 5xx, oversize, a body that is not a list) are logged and stored as
    the last error. The next attempt comes after the normal interval.
- **State in Redis**, shown by `GET /admin/system/status` under `calendar`:
  - `last_success` (`cal:last_ok`: time, status, items, skipped, inserted, unchanged);
  - `last_error` (`cal:last_error`: time and error);
  - `backoff_until`, `next_due_in_seconds`;
  - `rows` and `newest_fetched_at` of the table.

  `calendar.refresh` also appears in `celery.tasks`.
- **Logs.** Each fetch logs `calendar.refresh <status> inserted=N unchanged=N skipped=N`.
- **Off switch.** `CALENDAR_ENABLED=false` makes the task and the admin refresh no-ops.

## 5. Read API

| Endpoint | Who | |
|---|---|---|
| `GET /api/v1/calendar/events` | any logged-in user, or an API key with `market:read` | see below |
| `GET /api/v1/calendar/events/{event_key}/history` | same | every version, oldest first; 404 when unknown |
| `POST /api/v1/admin/calendar/import` | admin (JWT) | history from an uploaded CSV (section 7) |
| `POST /api/v1/admin/calendar/refresh` | admin (JWT) | the live fetch now (not during a backoff) |

`GET /calendar/events` query parameters:

- `start`, `end`: default today 00:00 UTC to +7 days; at most 31 days, otherwise 422.
- `currencies`: comma list; default `CALENDAR_CURRENCIES`; `ALL` for every currency.
- `min_impact`: default `low`, which hides holidays; `holiday` shows everything.
- `as_of`: **admins only**, and silently ignored for everyone else (and for API keys). The
  answer echoes the `as_of` it used.

Each event carries `event_key`, `scheduled_at`, `scheduled_date`, `time_label`, `currency`,
`impact`, `title`, `actual`, `forecast`, `previous`, the three parsed values, `fetched_at` and
`source`.

## 6. `for_evaluate` (B9)

```python
await calendar.service.for_evaluate(session, bar_ts, window=timedelta(hours=6), as_of=None)
```

This returns exactly the `calendar` list of an evaluate request:

```json
[{"ts": "2026-01-09T13:30:00Z", "currency": "USD", "impact": "high",
  "title": "Non-Farm Employment Change"},
 {"ts": "2026-01-09T15:00:00Z", "currency": "USD", "impact": "medium",
  "title": "Prelim UoM Consumer Sentiment"}]
```

- It covers the events with a **time** between `bar_ts − 6 h` and `bar_ts + 6 h`, sorted by time.
  Events without a time (All Day, Tentative) are never sent.
- It filters to `CALENDAR_CURRENCIES` and `min_impact="medium"`. Fadi's filter abstains on
  `high`; `medium` is sent too so the engine can use those events as features. `currencies=`
  and `min_impact=` can override both.
- `as_of`: the live call leaves it empty (now). **A backtest passes the bar's time**, so it sees
  only what was known then.
- One SQL query: about 16 ms on the test week (local Docker).

## 7. Loading history on the server

There is no shell on the server, so the admin import endpoint does what the script does
locally.

1. **Download the dataset by hand.** Never commit it, and check its licence before publishing
   any result built on it. Look at the header. The columns are found by their usual names:

   | field | header names (case-insensitive) |
   |---|---|
   | `date` (required) | Date, DateTime, Date_Time, Timestamp, Start |
   | `time` | Time (`8:30am`, `13:30`, `All Day`, `Tentative`) |
   | `currency` (required) | Currency, Cur, Country, Symbol |
   | `impact` (required) | Impact, Importance, Volatility (`High`, `High Impact Expected`, `Non-Economic`, `red`/`orange`/`yellow`/`gray`, `3`/`2`/`1`) |
   | `title` (required) | Event, Title, Name, Event Name, Detail |
   | `actual`, `forecast`, `previous` | Actual, Forecast/Consensus, Previous/Prior |

   Other names: `map=title=Name,date=Start`. Dates: ISO (with or without a time or offset),
   `01/05/2018` (month first), `2018.01.05`, `Jan 5, 2018`, or your own `date_format=` (strptime).
2. **Know the timezone of the times.** Kaggle ForexFactory exports are usually New York time,
   but check one known event (NFP is 8:30 New York). The import **refuses** a timed row
   without an offset when `tz` is not given; it never guesses.
3. **Log in as admin and run a dry run.** It writes nothing and shows the detected columns,
   5 parsed rows and the counts:

   ```bash
   BASE=http://187.127.76.76:8080/api/v1
   TOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
     -d '{"email":"<admin email>","password":"<password>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
   curl -s -X POST -H "Authorization: Bearer $TOKEN" \
     -F "file=@forexfactory_calendar.csv" \
     "$BASE/admin/calendar/import?tz=America/New_York&from=2018-01-01&dry_run=true"
   ```

   Check `columns`, `sample` (are the UTC times right?), `skipped` and `events_per_impact`.
4. **Import.** It is the same call without `dry_run`:

   ```bash
   curl -s -X POST -H "Authorization: Bearer $TOKEN" -F "file=@forexfactory_calendar.csv" \
     "$BASE/admin/calendar/import?tz=America/New_York&from=2018-01-01"
   ```

   The answer gives `rows_read`, `skipped` (by reason, with the first examples), `versions`,
   `inserted`, `unchanged`, `first_date`/`last_date` and `events_per_impact`. A second upload
   inserts 0: it is safe to repeat.
5. **Check.**

   ```bash
   curl -s -H "Authorization: Bearer $TOKEN" \
     "$BASE/calendar/events?start=2018-01-05T00:00:00Z&end=2018-01-06T00:00:00Z&min_impact=high"
   ```

Limits:

- **Size.** At most 50 MB: the backend answers 413 above, and Nginx allows 51 MB on this one
  path (`infra/nginx/default.conf`).
- **Memory.** The upload is spooled to disk, then read in batches of 5,000 rows, so the file
  is never held in memory.
- **Time.** About 0.2 ms per stored version on the local Docker database (50,000 versions in
  about 10 s). Nginx waits up to 10 minutes on this path.
- **Rows.** A row with a wrong column count, an unknown impact, an unreadable date, or no
  title or currency is skipped and counted. Rows before `from` (default 2018-01-01) are
  skipped too.

Locally, the script does the same against `DATABASE_URL`:

```bash
cd backend
python scripts/load_calendar_csv.py --file ~/Downloads/forexfactory_calendar.csv \
    --tz America/New_York --dry-run
python scripts/load_calendar_csv.py --file ~/Downloads/forexfactory_calendar.csv \
    --tz America/New_York [--from 2018-01-01] [--map title=Name,...] [--date-format ...]
```

## 8. Settings

| Setting | Default | |
|---|---|---|
| `CALENDAR_ENABLED` | `true` | the beat task and the admin refresh |
| `CALENDAR_FF_URL` | `https://nfs.faireconomy.media/ff_calendar_thisweek.json` | |
| `CALENDAR_FETCH_INTERVAL_MINUTES` | `240` | at most one request per interval |
| `CALENDAR_FETCH_TIMEOUT_SECONDS` | `15` | the whole request |
| `CALENDAR_FETCH_MAX_BYTES` | `2097152` | larger bodies are refused |
| `CALENDAR_BACKOFF_HOURS` | `6` | no request after a 429/403 |
| `CALENDAR_CURRENCIES` | `USD` | default of the reads and of `for_evaluate` |
