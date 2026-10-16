# Expert chat

One conversation per (expert, subscriber). REST for sending and history, the WebSocket hub
(`/ws/market`, [websocket.md](websocket.md)) for live delivery. Base URL `/api/v1`, login token
only. Subscriptions and perks: [subscriptions.md](subscriptions.md).

## Rights

- A subscriber whose subscription has the **`chat` perk** (and is entitled: trialing, active, or
  past_due within the grace period) opens the conversation and writes. The expert's profile must
  have `chat_enabled`.
- The **expert can always reply**.
- When the subscription ends, the conversation becomes **read-only for the subscriber**; the
  history stays.
- **Block**: either side; a blocked conversation takes no new messages from anyone. Only the
  side that blocked (or an admin) unblocks.
- **Admins** read every conversation (REST and WebSocket) but do not write;
  `GET /admin/conversations?status=blocked`.

## REST

| Method | Path | |
|---|---|---|
| GET | `/conversations` | yours (as subscriber or expert), most recent first |
| POST | `/conversations` | `{"expert_id"}` → 201 new / 200 existing; 403 no chat perk or chat disabled; 404 unknown expert |
| GET | `/conversations/{id}` | one conversation (404 if you are not a participant) |
| GET | `/conversations/{id}/messages?before=<message id>&limit=50` | newest first; `next_before` for older ones (`null` at the start) |
| POST | `/conversations/{id}/messages` | send (below) |
| PATCH | `/messages/{id}` | `{"body"}`, the sender within **15 minutes** (403 after) |
| DELETE | `/messages/{id}` | the sender; leaves a **tombstone** (`deleted: true`, `body: null`) |
| POST | `/conversations/{id}/read` | `{"message_id"?}`: move your read marker (to that message, or to now); markers only move forward |
| POST | `/conversations/{id}/block` · `/unblock` | |
| POST | `/reports` | `{"target_type": "message", "target_id", "reason"}` (participants only); admins hide it → tombstone, the sender gets `content_hidden` |

A conversation:

```json
{
  "id": "…", "expert_id": "…", "user_id": "…",
  "other": {"id": "…", "display_name": "Sami Expert", "role": "expert"},
  "my_role": "subscriber",
  "status": "open",
  "blocked_by_me": false,
  "can_send": true,
  "read_only_reason": null,
  "unread": 3,
  "last_message": {"id": "…", "sender_id": "…", "excerpt": "Here is the plan", "created_at": "…"},
  "last_message_at": "…",
  "other_last_read_at": "…",
  "created_at": "…"
}
```

`unread`: messages of the other side after your read marker (deleted ones excluded).
`other_last_read_at` drives "seen" ticks on your messages.

### Sending, idempotently

```http
POST /api/v1/conversations/{id}/messages
{"body": "What is your stop for BTC?", "client_id": "6f1c…(uuid made by the app)",
 "attachments": [{"type": "signal", "id": "…"}]}
```

- 201 with the message; **200 with the first message** when the same `client_id` is sent again
  (a retry after a timeout never duplicates). Generate one `client_id` per message and keep it
  until the server confirms.
- `body`: 1–4,000 characters, plain text or light Markdown, same rules as comments (raw HTML and
  script links → 422).
- `attachments` (≤ 5): `signal`, `backtest` (your own), `post` (shareable), `custom_strategy`
  (yours or public); resolved when read, like post attachments.
- 403: read-only, blocked, or admin. 429: more than **30 messages per minute** or **2,000 per day**
  (`Retry-After`).

A message:

```json
{"id": "…", "conversation_id": "…", "sender_id": "…", "body": "What is your stop for BTC?",
 "attachments": [], "client_id": "6f1c…", "edited_at": null, "deleted": false,
 "created_at": "…"}
```

`client_id` is only returned to its sender (to match the optimistic copy).

## WebSocket

Subscribe on `/ws/market` (with your token):

```json
{"op": "subscribe", "topic": "chat", "conversation_id": "<uuid>"}
```

Only the two participants (and admins) may subscribe; others get
`{"type": "error", "code": "forbidden"}`. While a participant is subscribed they count as
**present** (no notifications for that conversation). Messages on topic `chat:<uuid>`:

```json
{"type": "chat_message", "topic": "chat:…", "conversation_id": "…", "message": {…message…}}
{"type": "chat_message_updated", "conversation_id": "…", "message": {…edited or tombstone…}}
{"type": "chat_read", "conversation_id": "…", "user_id": "…", "read_at": "…"}
{"type": "chat_typing", "conversation_id": "…", "user_id": "…"}
```

Typing (ephemeral, not stored): send `{"op": "typing", "conversation_id": "<uuid>"}` while the
user types. You must be subscribed to the topic. At most **one per 3 seconds** per user is
forwarded (others are dropped silently); both sides receive it, so ignore your own `user_id`.
Hide the indicator after ~5 s without a new one.

Live flow: POST the message → render it at once (optimistic, keyed by `client_id`) → the
`chat_message` event confirms it on every device.

## Notifications

`chat_message` through the notification system ([notifications.md](notifications.md)) to the
recipient **only when none of their connections is subscribed to the conversation** (presence in
Redis, refreshed with every heartbeat, expires 75 s after a crash).

Collapse: at most **one external notification (Telegram / email / push) per conversation per
5 minutes** (`CHAT_NOTIFY_COLLAPSE_MINUTES`). Within that window the same inbox row is updated
and marked unread again: "3 new messages from Sami Expert" (Arabic: "رسائل جديدة من Sami
Expert: 3"), with the latest excerpt. Default channels: in-app, Telegram, push. Push `data`:
`{"screen": "chat", "conversation_id"}`.

## Limits (configuration)

| Setting | Default |
|---|---|
| `CHAT_MESSAGES_PER_MINUTE` / `CHAT_MESSAGES_PER_DAY` | 30 / 2,000 |
| `CHAT_EDIT_WINDOW_MINUTES` | 15 |
| `CHAT_NOTIFY_COLLAPSE_MINUTES` | 5 |
