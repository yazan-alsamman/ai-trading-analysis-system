# Notifications

Events reach users on the channels they choose:

- **In-app**: the inbox (always stored) and the WebSocket `notification` message.
- **Telegram**: a bot the user links to their account.
- **Email**: to the account email.
- **Mobile push**: FCM, for Batoul's Flutter app.

There are preferences per event and channel, quiet hours, an hourly cap with digests,
retries, and a delivery log.

Everything is produced through one function (`app.notifications.service.notify` / `prepare`).
It stores the inbox row, publishes the WebSocket message and queues the external deliveries on
the Celery queue `notifications`. Nothing calls a channel directly.

## Events

| `type` | Producer | Severity | Content (`data`) |
|---|---|---|---|
| `signal` | live signal engine, for every user whose active setup produced the signal **with `notify = true`** | `info` | `signal` (the same object as the WebSocket `signal`), `strategy_name`, `instrument` `{id, symbol, price_precision, quantity_precision}`, `user_strategy_ids`, `plan` (the user's trade plan, Y13; may carry `invalid_reason`), `plans` (one per activation) |
| `backtest_completed` | backtest task | `success` | `backtest_id`, `strategy_key`, `strategy_name`, `symbol`, `timeframe`, `metrics` (headline) |
| `backtest_failed` | backtest task | `warning` | the same plus `error` |
| `security` | sign-in from a new IP/device, password changed, API key created / revoked, account locked by the login lockout | `warning` / `info` / **`critical`** (locked) | `event` (`new_login`, `password_changed`, `api_key_created`, `api_key_revoked`, `account_locked`) plus `ip`, `user_agent`, `key_name`, `key_prefix` or `minutes` |
| `system` | admin broadcast, test messages | any | `title`, `body` (`broadcast_id`), or `test`, `channel` |
| `new_post` (Y18) | an author you follow published a post (fan-out task, batches of 500) | `info` | `post_id`, `title`, `excerpt`, `author_id`, `author_name`, `instrument_symbol`, `direction` |
| `comment_reply` (Y18) | a comment on your post, or a reply to your comment (never your own) | `info` | `post_id`, `comment_id`, `post_title`, `excerpt`, `author_name`, `kind` (`post` \| `comment`) |
| `post_liked` (Y18) | likes on your post: **in-app only, one row per post and UTC day**, updated (and marked unread) by every like | `info` | `post_id`, `post_title`, `count` |
| `content_hidden` (Y18) | moderation hid your post or comment | `warning` | `target_type`, `target_id`, `post_id`, `comment_id`, `excerpt`, `reason` |
| `chat_message` (Y19) | a chat message while none of your connections looks at the conversation; one external notification per conversation per 5 min, the inbox row is updated meanwhile ([chat.md](chat.md)) | `info` | `conversation_id`, `message_id`, `sender_id`, `sender_name`, `excerpt`, `count` |
| `subscription_started`, `subscription_renewed`, `subscription_payment_failed` (warning), `subscription_canceled` (Y19) | your subscription to an expert ([subscriptions.md](subscriptions.md)) | `info` / `warning` | `subscription_id`, `expert_id`, `expert_name`, `plan_name`, `price`, `currency`, `interval`, `status`, `period_end`, plus `invoice_number`, `amount`, `reason`, `grace_end`, `trial` |
| `new_subscriber` (Y19) | to the expert | `info` | the same, with `subscriber_name`, `trial_days` |
| `price_alert` (Y18) | one of your price alerts fired ([price-alerts.md](price-alerts.md)) | `warning` | `alert_id`, `instrument`, `condition`, `value`, `price`, `bar_time`, `note`, ... |
| `ai_setup` (B11) | an AI setup you follow became ARMED, or one you took changed state (below) | `warning` (ARMED) / `info` | `setup_id`, `state`, `transition`, `instrument`, prices, scores, `size` (ARMED), `explanation`, `pnl` (end) |

- There is **one notification per (event, user)**: `dedup_key` (unique per user) makes
  producing idempotent. Examples: `signal:<signal_id>` (several activations of the same user on
  one signal are listed in `data`), `backtest:<id>:backtest_completed`, `broadcast:<id>`.
- A sign-in is "new" when `sha256(user, IP, user agent)` was never seen for the account. The
  first sign-in of an account is recorded silently.
- `title` and `body` are rendered in the user's language (`ar` default, `en`) when the event is
  stored. External channels render again in the current language when they send. The texts live
  in one place: `backend/app/notifications/templates/messages.py`.

### Example (`GET /me/notifications`, English)

```json
{"id": "37f23c43-…", "type": "signal", "severity": "info", "read_at": null,
 "created_at": "2026-10-16T13:15:10.512Z",
 "title": "SELL signal: BTC/USDT 1m",
 "body": "Strategy: Moving Average Crossover · strength 0.74\nPrice: 36,417.32\n\nTrade plan (10,000 USDT account):\nEntry ≈ 36,417.32\nStop: 36,497.04\nTarget 1: 36,337.60 (1.0R, close 50%)\nTarget 2: 36,257.87 (2.0R, close 50%)\nSize: 0.27432 (9,990.01 USDT)\nRisk: 41.87 USDT (0.42%) · R:R 1.00",
 "data": {"signal": {"id": "1bd03869-…", "side": "sell", "price": 36417.32, "strength": 0.74, "…": "…"},
          "strategy_name": "Moving Average Crossover",
          "instrument": {"id": "76aa70d6-…", "symbol": "BTC/USDT", "price_precision": 2, "quantity_precision": 5},
          "user_strategy_ids": ["…"], "plan": {"stop": 36497.04, "…": "…"}, "plans": ["…"]}}
```

## WebSocket

Every stored notification is also sent on the user's own topic (no subscription needed):

```json
{"type": "notification", "topic": "user:<uuid>", "sent_at": 1792156510640,
 "notification": {"id": "…", "type": "signal", "title": "…", "body": "…", "data": {…},
                  "severity": "info", "created_at": "…", "read_at": null}}
```

The existing messages are unchanged (`signal` with `plan`, `backtest_progress`,
`backtest_completed`, `backtest_failed`, `workspace_updated`). A client that only shows the
inbox can listen to `notification` alone.

## Inbox API (`/api/v1`, JWT only; API keys get 403)

| Method | Path | |
|---|---|---|
| GET | `/me/notifications` | `Page`, newest first; `type`, `unread=true\|false`, `limit` (≤ 100), `offset` |
| GET | `/me/notifications/unread-count` | `{"count": 3}` |
| POST | `/me/notifications/{id}/read` | 204 (404 if not yours) |
| POST | `/me/notifications/read-all` | 204 |
| DELETE | `/me/notifications/{id}` | 204 |
| GET / PUT | `/me/notification-preferences` | below |
| GET | `/me/notifications/channels` | what each channel can do for you |
| POST | `/me/notifications/test` | `{"channel": "in_app" \| "telegram" \| "email" \| "push"}`, rate-limit cost 5 |
| POST | `/me/notifications/telegram/link` | `{code, deep_link, bot_username, expires_in}` |
| DELETE | `/me/notifications/telegram` | unlink, 204 |
| POST / GET | `/me/devices` | register or refresh an FCM token / list |
| DELETE | `/me/devices/{id}` | 204 |
| POST | `/admin/notifications/broadcast` | admin: `{title, body, severity?, roles?, id?}` → 202 `{broadcast_id, recipients}` |
| GET | `/admin/notifications/stats` | admin: last 24 h per channel and status, circuit breakers, held deliveries, queue length |

Retention: read notifications are deleted after 90 days, unread ones after 180 days (daily
task).

```json
GET /me/notifications/channels
{"in_app":   {"enabled_on_server": true},
 "telegram": {"enabled_on_server": true, "linked": true, "username": "alice_tg", "mode": "polling"},
 "email":    {"enabled_on_server": false, "address": "alice@example.com"},
 "push":     {"enabled_on_server": true, "devices": 2}}
```

`enabled_on_server: false` means the server has no settings for that channel. Show it as
"not available". The test endpoint then returns a `skipped` delivery instead of an error.

## Preferences

```json
GET /me/notification-preferences   (created with the defaults on first read)
{
  "matrix": {
    "signal":             {"telegram": true,  "email": false, "push": true},
    "backtest_completed": {"telegram": false, "email": false, "push": true},
    "backtest_failed":    {"telegram": false, "email": false, "push": true},
    "security":           {"telegram": false, "email": true,  "push": false},
    "system":             {"telegram": true,  "email": false, "push": true},
    "new_post":           {"telegram": false, "email": false, "push": true},
    "comment_reply":      {"telegram": false, "email": false, "push": true},
    "content_hidden":     {"telegram": false, "email": true,  "push": true},
    "price_alert":        {"telegram": true,  "email": false, "push": true},
    "chat_message":       {"telegram": true,  "email": false, "push": true},
    "subscription_started":        {"telegram": false, "email": true, "push": true},
    "subscription_renewed":        {"telegram": false, "email": true, "push": false},
    "subscription_payment_failed": {"telegram": true,  "email": true, "push": true},
    "subscription_canceled":       {"telegram": false, "email": true, "push": true},
    "new_subscriber":              {"telegram": false, "email": true, "push": true}
  },
  "min_signal_strength": 0.0,
  "only_valid_plans": false,
  "quiet_hours": null,
  "language": "ar",
  "max_per_hour": {"telegram": 30, "email": 30, "push": 30},
  "updated_at": "…"
}
```

`post_liked` has no matrix entry: it never leaves the app (a `PUT` that sets it is a 422).

`PUT` takes the same fields. A missing field gets its default, and a missing matrix entry
keeps the default for that event and channel. Example:
`{"matrix": {"signal": {"email": true}}, "quiet_hours": {"start": "23:00", "end": "07:00", "tz": "Asia/Damascus"}, "language": "en"}`.
A 422 lists every error with its `loc`, e.g. `["body", "quiet_hours", "tz"]` for an unknown
time zone.

The in-app inbox always stores every event. For each external channel, the rules apply in
this order:

1. **Event enabled** for the channel in `matrix`. The channel also needs a target: a linked
   Telegram chat, the account email, or registered devices.
2. **Signal filters**: `strength ≥ min_signal_strength`, and with `only_valid_plans` a trade
   plan without `invalid_reason`.
3. **Quiet hours** `{start, end, tz}` (local time; `23:00`–`07:00` spans midnight). Deliveries
   are held until the end, then sent as **one digest**.
4. **Hourly cap** `max_per_hour` per channel (default 30). Beyond it, deliveries are held until
   the next full hour, then sent as one digest.

`critical` events (the account lockout) ignore quiet hours and caps. A digest is one message
per channel and target: `"3 notifications"`, then one line per held item (at most 20, then
"…and N more"). When only one item is waiting, it goes out as the normal message. A beat task
checks for due digests every minute.

## Telegram

**Linking.**
1. The app calls `POST /me/notifications/telegram/link` and gets
   `{"code": "N5FjmM56UGkkryNF", "deep_link": "https://t.me/<bot>?start=N5FjmM56UGkkryNF", "bot_username": "<bot>", "expires_in": 600}`
   (409 if the server has no bot).
2. The app opens `deep_link`. Telegram opens the bot with a **Start** button, which sends
   `/start <code>`.
3. The bot links that chat to the account and replies "✅ …".
   - The code works once, for 10 minutes; an expired or reused code gets "invalid or expired".
   - A chat belongs to one account; linking it again moves it.
4. `GET /me/notifications/channels` now shows `telegram.linked = true`.

**Unlinking.** `/stop` in the bot, `DELETE /me/notifications/telegram`, or automatically when
the user blocks the bot (Telegram answers 403). `/status` in the bot shows the linked account
(masked email).

**Messages** use HTML parse mode with every value escaped, like this:

```
<b>إشارة بيع: BTC/USDT 1m</b>
الاستراتيجية: Moving Average Crossover · القوة 0.74
السعر: 36,417.32

خطة الصفقة (حساب 10,000 USDT):
الدخول ≈ 36,417.32
وقف الخسارة: 36,497.04
الهدف 1: 36,337.60 (1.0R، إغلاق 50%)
…
```

**Polling vs webhook.**
- The server has no domain or HTTPS yet, so the `telegram-bot` service uses **long polling**
  (`getUpdates`); it only handles `/start`, `/stop` and `/status`. The notifications themselves
  are sent by the Celery worker.
- To switch to a webhook later (behind HTTPS), set `TELEGRAM_MODE=webhook` and
  `TELEGRAM_WEBHOOK_SECRET=<random>`, then register
  `https://<domain>/api/v1/telegram/webhook/<secret>` with `setWebhook` and
  `secret_token=<secret>`. Requests without the matching `X-Telegram-Bot-Api-Secret-Token` get
  404, and the polling service idles in that mode.

## Push (FCM HTTP v1) — for the Flutter app

**Register the device** on every app start and whenever FCM rotates the token
(`FirebaseMessaging.instance.onTokenRefresh`):

```http
POST /api/v1/me/devices
Authorization: Bearer <access token>
{"token": "<FCM registration token>", "platform": "android", "app_version": "1.2.0", "locale": "ar"}
```

- The answer is 201 the first time and 200 for a token already known (it is refreshed and, if
  it belonged to another account, moved to this one). The response never contains the token,
  only `token_suffix`.
- `platform` is `android`, `ios` or `web`.
- On sign-out call `DELETE /api/v1/me/devices/{id}`.
- Tokens that FCM reports as invalid (`UNREGISTERED`, `INVALID_ARGUMENT`) are deleted by the
  server.

**The message the app receives** (what the server sends to FCM):

```json
{"message": {
  "token": "<FCM token>",
  "notification": {"title": "إشارة بيع: BTC/USDT 1m",
                   "body": "الاستراتيجية: Moving Average Crossover · القوة 0.74 · السعر: 36,417.32 · …"},
  "data": {"notification_id": "37f23c43-…", "type": "signal",
           "screen": "signal", "signal_id": "1bd03869-…"},
  "android": {"priority": "high", "notification": {"channel_id": "signals"}},
  "apns": {"headers": {"apns-priority": "10"}, "payload": {"aps": {"sound": "default"}}}}}
```

- **`data`** (all strings) tells the app where to open:

  | `screen` | extra field |
  |---|---|
  | `signal` | `signal_id` |
  | `backtest` | `backtest_id` |
  | `security` | — |
  | `notifications` | — (system messages, and digests with `type: "digest"` and `count`) |
  | `post` | `post_id`, and `comment_id` for comments (`new_post`, `comment_reply`, `post_liked`, `content_hidden`) |
  | `price_alert` | `alert_id`, `instrument_id` |
  | `chat` | `conversation_id` (`chat_message`) |
  | `subscription` | `subscription_id` (`subscription_*`) |
  | `earnings` | `subscription_id` (`new_subscriber`) |

  With `notification_id` the app can mark it read (`POST /me/notifications/{id}/read`).
- The body is the first whole lines of the inbox text, at most 240 characters.
- On Android, create the notification channel `signals`.

## Delivery, retries, failures

- Each delivery is a row in `notification_deliveries`, one per notification, channel and
  target (`telegram` = chat id, `email` = address, `push` = device id; never a secret).
  - `status`: `pending`, `sent`, `failed`, `skipped`.
  - It also stores `attempts`, `last_error` (short, no secrets) and `provider_message_id`.
- Sending is idempotent: a delivery is claimed with a row lock and only while `pending`, so a
  duplicated task never sends twice.
- **Retries**: up to 5 attempts with exponential backoff and jitter (2, 4, 8, 16 s, +≤50 %).
  A provider `retry_after` (Telegram 429, FCM `Retry-After`) is honoured and does not count as
  a provider failure.
  Each retry records when it is due (`next_attempt_at`); a lost send or retry task is picked
  up by the sweeper ([Stuck deliveries](#stuck-deliveries-sweeper)).
- **Permanent errors** fail at once:
  - a blocked bot also unlinks the chat;
  - an invalid push token also deletes the device;
  - an SMTP 5xx rejection.
- **Circuit breaker** per channel: after 5 consecutive failures (timeouts, 5xx, SMTP down) the
  channel pauses for 5 minutes.
  - Deliveries are held (`hold = circuit_open`) instead of creating retry tasks, and the
    opening is logged once.
  - Afterwards the held ones are sent again. A success closes the circuit; a failure opens it
    again.
- **Timeouts**: every outbound call has a 10 s timeout. Sends run on the `notifications`
  queue, never inside the signal engine.
- **Big signals**: for 500 users, the engine stores the inbox rows and deliveries in its own
  transaction (≈ 0.9 s) and enqueues one fan-out task. A worker splits that into send tasks of
  50 deliveries.

## AI setup alerts (B11)

AI setups come from ai-service (docs/ai-contract.md); their states are DEVELOPING, ARMED,
ACTIVE, CLOSED, EXPIRED and INVALIDATED. B11 tells users about the state changes. Code:
`app/ai/alerts.py`, `store.enqueue_alerts`, the task `ai_alerts.dispatch`.

### The outbox: no alert lost on a crash

- **Written with the evaluation.** `store.apply_evaluation` writes one `ai_setup_outbox` row
  per state change, in the **same transaction** as the setup change: both are stored, or
  neither is.
  - DEVELOPING is never written, not even for a setup born DEVELOPING.
  - Unique `(setup_id, to_state)`: a replayed evaluation adds nothing.
- **Sent by `ai_alerts.dispatch`**, on the `notifications` queue. Beat runs it every 30 s, and
  the caller of `apply_evaluation` (B9) calls `app.ai.alerts.kick()` after its commit to send at
  once.
  - Up to `AI_ALERTS_BATCH` due `pending` rows are taken per run, oldest first, each claimed
    with `FOR UPDATE SKIP LOCKED`, so two workers never handle the same row.
  - Each row is handled in one transaction: its inbox and delivery rows
    (`notifications.prepare`) and its new status (`done`, or `skipped` with a reason) commit
    together. The sends are enqueued and the live frame published only after that commit.
- **Failures** (an exception while handling a row) count an `attempt`, record `last_error`, and
  retry with the delivery backoff (2, 4, 8 … 300 s, plus jitter).
  - After `AI_ALERTS_MAX_ATTEMPTS` (8) the row is `failed`: an ERROR log and a `system`
    notification to the admins.
  - `POST /api/v1/admin/ai/outbox/{id}/retry` puts it back.
- **No duplicates.** The inbox `dedup_key` is `ai:{setup_id}:{to_state}`. If a row is handled
  again (a crash after the commit of the inbox but before the row is marked done, or an admin
  retry), it creates no second inbox row and no second delivery.

### Who gets what

`alerts.recipients(session, setup, to_state)` is the one rule:

| State | Recipients |
|---|---|
| `ARMED` (also a setup born ARMED) | active users who **follow** the setup's instrument and profile, whose `min_grade` the setup meets (A best; a follow without `min_grade` takes every grade), and who may read it (`may_read_ai_setup`) |
| `ACTIVE`, `CLOSED`, `EXPIRED`, `INVALIDATED` | only the users who **took** the setup (`POST /ai/setups/{id}/take`) |
| `DEVELOPING` | nobody, never |

A follower who did not take a setup hears nothing after ARMED.

### No late alerts

- **An ARMED row is `skipped`** (`last_error` = `stale: …`) in three cases:
  - the setup is no longer ARMED when the row is handled;
  - its `valid_until` has passed;
  - the row is older than `AI_ALERTS_MAX_AGE_SECONDS` (900).
- **The outcome is always sent** (`ACTIVE`, `CLOSED`, `EXPIRED`, `INVALIDATED` for takers). An
  older one carries `late: true`, and the text says "(late notice)".

### Content (`type: ai_setup`)

- **Severity:** `warning` for ARMED, `info` for the others.
- **Default channels:** Telegram and push, not email. Preferences, quiet hours (digests) and
  the hourly cap apply as for every event.
- **`data`:**
  - always: `setup_id`, `state`, `transition {from, to, at, reason, realized_r}`, `direction`,
    `instrument {id, symbol, source, price_precision, quantity_precision}`, `profile`, `entry`,
    `sl`, `tp`, `r_multiple`, `probability`, `ev_r`, `grade`, `valid_until`, `reason`,
    `realized_r` and `late`;
  - **on ARMED**: the user's own `size {lots, risk_amount, currency, margin_required, feasible,
    warnings, source}`, from the B10 sizing of every recipient, done once per alert. A failed
    size gives `size: {error}`, and an infeasible one shows its warning; neither ever blocks
    the alert. Also `explanation`, when there is one (below);
  - **on CLOSED, EXPIRED and INVALIDATED**: the user's `take {lots, risk_amount, pnl,
    realized_r}` and `pnl`.
- **Texts** (`messages.py`, ar and en): one title per state (e.g. "BUY setup XAU/USD: entry
  2,400.00", "Setup closed: BUY XAU/USD +1.50R"), with prices at the instrument's precision.
- **Push:** `data.screen = "ai_setup"`, with `setup_id`, `state` and `instrument_id`.

**Explanation (ARMED only):**
- ai-service `/v1/explain` is asked once per language the recipients use (`AI_EXPLAIN_LANGS`:
  `ar`, `en`), with an 8 s timeout and one attempt.
- The answer is stored in `ai_setup_explanations` and reused.
- If ai-service is unavailable or answers 404, the alert goes out with the template text only.
  The explanation is not retried, and the rest of that run stops asking.
- An answer with `verified: false` is stored and logged, but never sent.

### Live view

- **Topic:** `ai:setups:{instrument_id}`, public, gated by `may_read_ai_setup` (everyone today).
- **Frame:** `{"type": "ai_setup", "setup": {...}, "transition": {setup_id, from, to, at,
  reason, realized_r}}`, published once per state change after the row is done. It is never
  published before the change is stored, and never for skipped rows or DEVELOPING.
- **Subscribe:** `{"op": "subscribe", "topic": "ai_setups", "instrument_id": "…"}`.

### Follows

| Method | Path | |
|---|---|---|
| GET | `/me/ai/follows` | your follows |
| PUT | `/me/ai/follows/{instrument_id}/{profile}` | body `{min_grade?}` (`A`–`D`); idempotent upsert, 200; 404 unknown instrument, 422 unknown profile (today: `intraday`) |
| DELETE | `/me/ai/follows/{instrument_id}/{profile}` | 204; 404 when not followed |

There is **no automatic follow**: a user gets ARMED alerts only after following.

### For the apps (web and Flutter)

- **Following:** on the AI setups screen of an instrument, offer a "Notify me of new setups"
  switch.
  - It calls `PUT /me/ai/follows/{instrument_id}/intraday`, and DELETE to turn it off.
  - Offer an optional "only grade A / A–B" choice as `min_grade`, and read the state with
    `GET /me/ai/follows`.
- **After ARMED:** remind users that they hear about a setup only if they mark it taken
  (`POST /ai/setups/{id}/take`).
- **Live screen:** subscribe to `ai_setups` with the instrument.
- **Inbox and push:** an `ai_setup` item carries everything listed under Content. Push opens
  `screen = ai_setup` with `setup_id`. Show `size.lots` and `size.warnings`, `explanation`
  when present, and `pnl` for closed takes.

## Stuck deliveries (sweeper)

`after_commit` enqueues the sends after the producer commits. If the process dies in between,
or a scheduled retry task is lost, deliveries stay `pending` and nobody sends them. This
affects every type, not only AI alerts.

**The rule.** The beat task `notifications.sweep` (every minute) re-enqueues deliveries that
are:
- `pending`, with no `hold` (quiet hours, hourly cap and open circuits are left to the
  digests);
- due: `release_at` is null or past;
- overdue by more than `NOTIFICATION_SWEEP_AFTER_SECONDS` (120): `next_attempt_at` for a
  scheduled retry, otherwise `created_at`.

At most `NOTIFICATION_SWEEP_BATCH` (500) per run, oldest first, with one INFO line:
`notifications.sweep requeued=N`. A partial index makes the idle query cheap.

**Why it cannot double-send.** It only enqueues; it never sends. A send claims the delivery
with `FOR UPDATE SKIP LOCKED`, and only while it is `pending` without a hold. So a delivery
being sent right now is skipped, and one already sent is a no-op. That claim is the single
guarantee against double sends.

## Enabling the channels in production

With the settings empty, every channel is **disabled**: the app runs normally, `channels` shows
`enabled_on_server: false`, deliveries are `skipped` ("channel disabled on server"), and there
are no retries. Secrets go only into `/opt/trading/.env` on the server, never into git. After
editing it, redeploy (Actions → Deploy → Run workflow) so the containers read the new values.

| Channel | Variables |
|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN` (from @BotFather), optional `TELEGRAM_BOT_USERNAME` (else read with `getMe`), `TELEGRAM_MODE=polling` (default) or `webhook` + `TELEGRAM_WEBHOOK_SECRET` |
| Email | `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` (`true`) |
| Push | `FCM_PROJECT_ID`, `FCM_CREDENTIALS_JSON` (the service-account JSON on one line, or a path inside the container) |

Development: `docker compose up` starts **Mailpit**; every email appears at
http://localhost:8025. Without a bot token, the `telegram-bot` service only logs that it is
idle.
