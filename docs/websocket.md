# Live market data over WebSocket (`/ws/market`)

Push updates for charts, so clients never poll. Server code: `backend/app/api/ws.py`,
`backend/app/realtime/`.

## Connect

```
ws://<host>/ws/market?token=<access JWT>        (wss:// in production)
ws://<host>/ws/market?api_key=<tk_... key>      (external programs, key needs the `stream` scope)
```

- Through Nginx (`http://localhost` in docker compose) or directly to the API (`:8000`).
- Browsers cannot set headers on a WebSocket, so the **access** token (from `/api/v1/auth/login`)
  goes in the `token` query parameter. Refresh tokens are rejected.
- External programs can use an API key with the `stream` scope instead (`?api_key=`, see
  [api-keys.md](api-keys.md)). The connection belongs to the key's owner: the topic rules are the
  same, including the owner's own `user:` topic. A `token` wins if both are given.
- If the token or key is missing, invalid, expired or revoked, the key lacks `stream`, or the
  user is inactive, the server accepts and then closes with code **4401**.
- When the access token expires during the connection, the server sends
  `{"type":"error","code":"token_expired",...}` and closes with **4401**. Refresh the token and
  reconnect.

## Client → server

JSON text frames, at most 4 KB each.

```json
{"op": "subscribe",   "topic": "candles", "instrument_id": "<uuid>", "timeframe": "1m"}
{"op": "unsubscribe", "topic": "candles", "instrument_id": "<uuid>", "timeframe": "1m"}
{"op": "subscribe",   "topic": "signals", "instrument_id": "<uuid>"}
{"op": "unsubscribe", "topic": "signals", "instrument_id": "<uuid>"}
{"op": "ping"}
```

A `signals` topic carries the live strategy signals of one instrument, for every timeframe and
strategy setup that users run on it. It has no `timeframe` field and sends no snapshot; use
`GET /api/v1/signals` for past signals.

`timeframe` is one of `1m, 5m, 15m, 1h, 4h, 1d`. Instrument ids come from
`GET /api/v1/market/instruments`.

## Server → client

```json
{"type": "subscribed",   "topic": "candles:<uuid>:1m"}
{"type": "snapshot",     "topic": "candles:<uuid>:1m",
 "candle": {"time": 1760000000, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}}
{"type": "candle",       "topic": "candles:<uuid>:1m", "instrument_id": "<uuid>", "timeframe": "1m",
 "candle": {"time": 1760000040, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 3.5},
 "sent_at": 1760000041234}
{"type": "signal",       "topic": "signals:<uuid>", "sent_at": 1760000071000,
 "signal": {"id": "<uuid>", "instrument_id": "<uuid>", "timeframe": "1h",
            "strategy_key": "rsi_reversal", "params": {"length": 14, "oversold": 30.0, "overbought": 70.0},
            "params_hash": "5cd68c7e…", "time": 1760000000, "bar_time": "2025-10-09T09:00:00+00:00",
            "side": "buy", "strength": 0.42, "price": 61234.5,
            "reason": "rsi_cross_up_oversold",
            "details": {"rsi_prev": 28.4, "rsi": 31.2, "level": 30.0, "extreme": 22.1}}}
{"type": "unsubscribed", "topic": "candles:<uuid>:1m"}
{"type": "pong"}
{"type": "heartbeat"}
{"type": "error", "code": "unknown_instrument", "message": "instrument not found"}
```

- `snapshot` is sent right after `subscribed`. It carries the latest candle, or `null` if there
  is none yet. Use it so the chart is current while you wait for the next tick.
- `candle` is the current, still-forming candle. It is sent every time it changes, and a new
  `time` starts the next candle. `candle` has exactly the same shape as the REST candles
  endpoint, so pass it straight to Lightweight Charts `series.update(msg.candle)`.
- `time` is the bucket start in unix **seconds** (UTC). `sent_at` is the publish time in unix
  **milliseconds**; it is only for diagnostics.
- Error codes:
  - `bad_request`: invalid JSON or schema, binary frame, frame over 4 KB
  - `unknown_instrument`
  - `inactive_instrument`
  - `forbidden`
  - `too_many_subscriptions`
  - `token_expired`
  - `unavailable`: the live feed is temporarily down

  Only `token_expired` closes the socket.
- `signal` messages are published once per new signal, on the closed bar `time` (unix seconds,
  bar start). The signal is actionable at the open of the next bar. To draw a marker, use
  `{time, position: side == "buy" ? "belowBar" : "aboveBar", shape: side == "buy" ? "arrowUp" : "arrowDown"}`.
- Messages sent to a user's own topic (`user:<id>`) arrive automatically, with no
  subscription needed. When one of the user's active strategies (with `notify = true`)
  produces a signal, the user gets `{"type": "signal", "user_strategy_ids": ["<uuid>"],
  "signal": {...}}` with the same `signal` object. Other notifications come in Y15.
- Signals of custom strategies have `strategy_key: "custom:<uuid>"`, empty `params`, the
  definition hash as `params_hash`, `reason` `builder_buy`/`builder_sell` or
  `composite_buy`/`composite_sell`, and `details` explaining the rules or the members' votes
  ([custom-strategies.md](custom-strategies.md)).
- When one of the user's workspaces changes (on any device), every connection of that user gets
  `{"type": "workspace_updated", "workspace_id": "<uuid>" | null, "version": 8 | null,
  "action": "created" | "state_updated" | "renamed" | "default_changed" | "deleted" |
  "reordered" | "shared" | "unshared"}`. Reload the workspace if `version` is newer than yours,
  or the list on `reordered` / `deleted` / `created` (see [workspaces.md](workspaces.md)).
- Backtests of the user report on the same topic: `{"type": "backtest_progress",
  "backtest_id", "status": "running" | "cancelled", "progress": 0..100}`, then
  `{"type": "backtest_completed", "backtest_id", "status": "completed", "progress": 100,
  "metrics": {…headline…}}` or `{"type": "backtest_failed", "backtest_id", "status": "failed",
  "error"}` (see [backtesting.md](backtesting.md)).

## Limits and close codes

| | |
|---|---|
| Subscriptions per connection | 50 candles/signals topics (re-subscribing does not count) |
| Max client frame | 4 KB |
| Server heartbeat | every 25 s |
| Idle timeout | 75 s without any client frame → close **1001** |
| Slow consumer | more than 256 undelivered messages → close **1013** |
| Bad or expired token / API key | close **4401** |
| Concurrent connections | 5 per identity (user for a JWT, key for an API key) → close **4429** |
| New connections | 20 per minute per IP → close **4429** |

Send `{"op":"ping"}` every ~30 s to stay under the idle timeout. Browsers do not expose
protocol-level pings.

## Reconnecting

- Reconnect with exponential backoff: 1 s, 2 s, 4 s … capped at 30 s, plus a little jitter. Reset
  the delay after a successful connection.
- On **4401**, refresh the access token (`POST /api/v1/auth/refresh`) before reconnecting. If the
  refresh fails, send the user to log in.
- On **4429**, you have too many open connections or open them too fast: close unused ones (one
  connection can carry 50 subscriptions) and wait at least 3 s before retrying, backing off as
  above.
- Subscriptions are not remembered across connections. Send your `subscribe` ops again after every
  reconnect; the `snapshot` reply brings the chart up to date.

## Minimal JavaScript example (Lightweight Charts)

```js
const API = "http://localhost";          // Nginx in docker compose

function connectLive({ getToken, instrumentId, timeframe, series }) {
  let delay = 1000;
  let socket;

  async function open() {
    socket = new WebSocket(`${API.replace("http", "ws")}/ws/market?token=${await getToken()}`);
    let keepAlive;

    socket.onopen = () => {
      delay = 1000;
      socket.send(JSON.stringify({ op: "subscribe", topic: "candles", instrument_id: instrumentId, timeframe }));
      keepAlive = setInterval(() => socket.send(JSON.stringify({ op: "ping" })), 30000);
    };

    socket.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if ((msg.type === "candle" || msg.type === "snapshot") && msg.candle) {
        series.update(msg.candle);   // { time, open, high, low, close, volume }
      } else if (msg.type === "error") {
        console.warn("ws error", msg.code, msg.message);
      }
    };

    socket.onclose = async (event) => {
      clearInterval(keepAlive);
      if (event.code === 4401) await refreshAccessToken();     // your auth code
      setTimeout(open, delay + Math.random() * 250);
      delay = Math.min(delay * 2, 30000);
    };
  }

  open();
  return () => { socket.onclose = null; socket.close(); };
}
```

Load the history first with `GET /api/v1/market/instruments/{id}/candles?timeframe=1m` and
`series.setData(...)`, then call `connectLive`.

## Test data without real collectors

```bash
docker compose exec backend python -m app.cli seed-instruments
docker compose exec backend python -m app.cli seed-demo-candles --symbol BTC/USDT --source binance --days 30
docker compose exec backend python -m app.cli simulate-live --symbol BTC/USDT --source binance --interval 2
```

`simulate-live` rewrites the current 1m candle every 2 s with **demo** prices and publishes it
live. Admins can inspect the hub at `GET /api/v1/admin/realtime/stats` (per API process).

## Publishing from server code

```python
from app.realtime import publisher
from app.realtime.topics import candles_topic

await publisher.publish(candles_topic(instrument_id, "1m"), {"type": "candle", ...})
```

After writing 1m candles, collectors should call
`app.services.market_events.publish_candle_updates_safely(session, instrument_id, candles)` once
the write is committed.
