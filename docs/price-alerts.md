# Price alerts (for the mobile task B08)

A user sets alerts on a price; when one fires, it is delivered through the notification system
(in-app inbox and WebSocket, push, Telegram; [notifications.md](notifications.md)).

## Conditions

Alerts are checked on every **closed 1m candle** (never on the minute still forming), about
10 s after the minute ends, using that bar's high, low and close:

| `condition` | `value` | fires when |
|---|---|---|
| `above` | price | the bar's **high ≥ value** |
| `below` | price | the bar's **low ≤ value** |
| `crosses_above` | price | previous close **<** value **≤** this bar's close (a confirmed cross) |
| `crosses_below` | price | previous close **>** value **≥** this bar's close |
| `change_pct` | percent, e.g. `2.5` (0–100] | **\|close / close `window_minutes` ago − 1\| ≥ value %**, up or down |

- `above`/`below` react to wicks inside the minute; the `crosses_*` ones only to closes, so a
  spike that returns does not count. Use `above` for "tell me when it touches 70k", and
  `crosses_above` for "tell me when a minute closes above 70k after being below".
- Data gaps: the previous close is the last 1m candle within the hour before the bar; the
  reference of `change_pct` is the last candle at or before `bar − window`, but not older than
  `bar − 2 × window`. A minute without a candle fires nothing in its own run, but each run
  also catches up on the 4 bars before it that were not evaluated yet, so a candle that arrives
  up to ~5 minutes late is still checked (once: evaluated bars are marked in Redis).
- An alert is first checked on the minute in which it was created.

## Repeat, cooldown, expiry

| `repeat` | |
|---|---|
| `once` (default) | the alert fires once, then `is_active` becomes `false` |
| `every` | fires again when the condition holds after `cooldown_minutes` (1–10,080, default 60), counted from the end of the bar that fired |

`expires_at` (optional, future): the alert is switched off at that time. `trigger_count` and
`last_triggered_at` (end of the bar that fired) are kept on the alert.

Active alerts per user: trader 20, analyst/expert/admin 100 (`PRICE_ALERT_LIMIT_<ROLE>`).

## Endpoints (`/api/v1`, login token only)

| Method | Path | |
|---|---|---|
| GET | `/me/price-alerts` | `Page`, newest first; filters `instrument_id`, `is_active` |
| POST | `/me/price-alerts` | 201; 422 invalid; 400 over the limit; 404 unknown instrument |
| PATCH | `/me/price-alerts/{id}` | any field; the combination is checked again; 404 if not yours |
| DELETE | `/me/price-alerts/{id}` | 204; 404 if not yours |
| GET | `/me/price-alerts/history` | the last triggers with prices (from your notifications); filter `alert_id` |

Create:

```json
POST /me/price-alerts
{"instrument_id": "…", "condition": "change_pct", "value": 2, "window_minutes": 15,
 "repeat": "every", "cooldown_minutes": 30, "note": "volatility", "expires_at": "2026-12-31T00:00:00Z"}
```

→ 201

```json
{
  "id": "…",
  "instrument": {"id": "…", "symbol": "BTC/USDT"},
  "condition": "change_pct", "value": 2.0, "window_minutes": 15,
  "repeat": "every", "cooldown_minutes": 30, "note": "volatility",
  "is_active": true, "last_triggered_at": null, "trigger_count": 0,
  "expires_at": "2026-12-31T00:00:00Z", "created_at": "…", "updated_at": "…",
  "current_price": 64210.5,
  "would_trigger_now": false
}
```

`would_trigger_now` warns that an `above`/`below` alert is already met by the latest price
(it is still created and fires on the next closed minute). 422 examples: `change_pct` without
`window_minutes` (1–1440), `window_minutes` on another condition, `cooldown_minutes` with
`repeat: "once"`, a `value` ≤ 0, an `expires_at` in the past.

PATCH: `{"is_active": false}` pauses an alert (it no longer counts against the limit);
re-activating checks the limit again. Changing the condition away from `change_pct` drops the
window; switching to `every` sets the default cooldown.

History item:

```json
{"notification_id": "…", "alert_id": "…", "instrument_id": "…", "symbol": "BTC/USDT",
 "condition": "above", "value": 102.9, "price": 103.0, "bar_time": "2026-10-16T12:03:00Z",
 "change_pct": null, "note": "tp1", "created_at": "…"}
```

It lasts as long as the notification (inbox retention: 90 days after reading, 180 unread).

## The notification

Type `price_alert`, severity `warning`, default channels in-app + push + Telegram (the user can
change them in the preferences matrix). One per alert and bar (`dedup_key`
`price_alert:<alert_id>:<bar_time>`), so a repeated evaluation never notifies twice.

Texts (the user's language):

```
Price alert: BTC/USDT crossed above 102.00
Price: 102.50 (1m bar 2026-03-02 12:03 UTC)
Rule: close crossed above 102.00 (previous close 101.90)
Note: first target
This alert is now off (it fires once).
```

```
تنبيه سعر: BTC/USDT تحرّك +2.50% خلال 3 دقيقة
السعر: 102.50 (شمعة الدقيقة 2026-03-02 12:03 UTC)
الشرط: حركة ≥ 2.00% خلال 3 دقيقة (من 100.00)
```

`data` of the notification (inbox and the WebSocket `notification` message):

```json
{
  "alert_id": "…",
  "instrument": {"id": "…", "symbol": "BTC/USDT", "price_precision": 2},
  "condition": "crosses_above", "value": 102.0, "window_minutes": null, "repeat": "once",
  "price": 102.5,
  "bar": {"high": 103.0, "low": 101.5, "close": 102.5},
  "bar_time": "2026-03-02T12:03:00+00:00",
  "note": "first target",
  "deactivated": true,
  "previous_close": 101.9
}
```

`price` is the price that met the condition: the high for `above`, the low for `below`, the
close otherwise. `change_pct` alerts add `reference_close` and `change_pct` (signed);
crosses add `previous_close`.

**WebSocket**: besides the `notification` message, the user's topic gets
`{"type": "price_alert", "notification_id": "…", ...data}`.

**Push `data`** (strings) for the deep link:

```json
{"notification_id": "…", "type": "price_alert", "screen": "price_alert",
 "alert_id": "…", "instrument_id": "…"}
```

Open the alert (or the instrument's chart) from it and mark the notification read with
`POST /me/notifications/{notification_id}/read`.

## How it runs

`alerts.tick` (beat, every minute) schedules `alerts.evaluate` for `minute boundary + 10 s` on
the existing `worker`. One run: switch off expired alerts, load all active alerts in one query,
then **one query per instrument** (the closed bar, the previous close and the reference close of
every window) and a vectorised check of all its alerts; fired alerts are stored as notifications
and updated in the same transaction. A Redis lock per bar stops a second run. Measured in the
tests: 1,000 active alerts on 3 instruments in ~70 ms with 10 firing, ~30 ms with none.
