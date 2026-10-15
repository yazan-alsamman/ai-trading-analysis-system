# API keys and rate limits

API keys let your own programs (bots, notebooks, Colab, scripts) read market data, indicators,
strategy previews and signals, and stream live updates, without your password or a short-lived
login token.

Base URL in docker compose: `http://localhost` (through Nginx). All paths below are under
`/api/v1`.

## 1. Create a key

Keys are managed with your normal login (a JWT), never with another key.

```bash
# log in
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"..."}' | jq -r .access_token)

# create a key that can read market data and signals, valid for 90 days
curl -s -X POST http://localhost/api/v1/me/api-keys \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"my bot","scopes":["market:read","signals:read"],"expires_in_days":90}'
```

```json
{
  "id": "6c0f…",
  "name": "my bot",
  "prefix": "k3x9q2ab",
  "scopes": ["market:read", "signals:read"],
  "rate_limit_per_minute": null,
  "expires_at": "2027-01-13T20:41:07Z",
  "last_used_at": null,
  "revoked": false,
  "revoked_at": null,
  "created_at": "2026-10-15T20:41:07Z",
  "key": "tk_k3x9q2ab_Jq0…"
}
```

**`key` is shown only in this response.** The server stores only a SHA-256 hash of it and cannot
show it again. Keep it in an environment variable or a secret store, never in code or a repository.
If you lose it, revoke the key and create a new one.

| Body field | |
|---|---|
| `name` | 1–100 characters, for you |
| `scopes` | at least one, see below |
| `expires_in_days` | optional, 1–3650; without it the key never expires |
| `rate_limit_per_minute` | optional, your own lower limit; at most your tier |

Managing keys (JWT only):

| | |
|---|---|
| `GET /me/api-keys` | your keys: prefix, name, scopes, limits, `last_used_at`, `expires_at`, `revoked` (never the key) |
| `PATCH /me/api-keys/{id}` | change `name`, `scopes`, `rate_limit_per_minute` (`null` = back to your tier) |
| `DELETE /me/api-keys/{id}` | revoke, immediately and for good (204) |
| `GET /me/api-keys/{id}/usage` | requests and 429s per UTC day, last 7 days |

Active keys per account: trader 2, analyst 5, expert 5, admin 10. Revoked and expired keys do not
count. `last_used_at` is updated at most once a minute.

## 2. Use it

Send the key in the `X-API-Key` header:

```bash
export TK_KEY='tk_k3x9q2ab_Jq0…'
curl -s http://localhost/api/v1/market/instruments -H "X-API-Key: $TK_KEY"
curl -s "http://localhost/api/v1/market/instruments/$ID/candles?timeframe=1h&limit=200" \
  -H "X-API-Key: $TK_KEY"
```

| Status | Meaning |
|---|---|
| 401 | unknown, malformed, revoked or expired key |
| 403 | the key lacks the scope for this endpoint, the endpoint never accepts keys, or the account is inactive |
| 429 | rate limit exceeded (section 4) |

## 3. Scopes

| Scope | Endpoints |
|---|---|
| `market:read` | `GET /market/instruments`, `GET /market/instruments/{id}`, `GET /market/instruments/{id}/candles` |
| `indicators:read` | `GET /indicators`, `POST /market/instruments/{id}/indicators` |
| `strategies:read` | `GET /strategies`, `POST /strategies/{key}/preview` |
| `signals:read` | `GET /signals` (with `mine=true`: signals of the key owner's active strategies) |
| `stream` | WebSocket `/ws/market` (section 6) |

Give a key only the scopes it needs. A key can **never** use `/auth/*`, `/users/me*`, `/me/*`
(including key management and strategy activation) or `/admin/*`, whatever its scopes; those
answer 401/403.

## 4. Rate limits

Every `/api/v1` request except `/health` is limited per minute, per identity: your account for
requests with a login token, **each key separately** for API keys.

| Role | Requests per minute |
|---|---|
| trader | 60 |
| analyst | 300 |
| expert | 300 |
| admin | 1,000 |

A key uses its own `rate_limit_per_minute` if set (never more than its owner's tier), otherwise
its owner's tier.

**Costs.** Most requests cost 1. These cost **5**:
`POST /market/instruments/{id}/indicators` and `POST /strategies/{key}/preview`.

The full minute can be used as a burst; after that capacity comes back continuously (a trader
gets one request per second back). Waiting a full minute always restores the whole allowance.

**Headers** on every limited response:

| Header | |
|---|---|
| `RateLimit-Limit` | your requests per minute |
| `RateLimit-Remaining` | requests you can send right now |
| `RateLimit-Reset` | seconds until the full allowance is back |
| `Retry-After` | only on 429: seconds until this request would be accepted |

A 429 looks like this:

```http
HTTP/1.1 429 Too Many Requests
RateLimit-Limit: 60
RateLimit-Remaining: 0
RateLimit-Reset: 60
Retry-After: 1

{"detail": "Rate limit exceeded", "retry_after": 1}
```

**Handling 429:** wait `Retry-After` seconds and retry. If you get 429 again, back off
exponentially (×2, capped at 60 s, plus a little random jitter). Better: watch
`RateLimit-Remaining` and slow down before you reach 0.

Login and registration have their own limits per IP address (login 10/min, also 5/min per
email; register 5/min; refresh 30/min). After 10 failed logins for one email within 15 minutes,
that email is locked for 15 minutes, even with the right password.

## 5. Python

```python
import os
import random
import time

import httpx

BASE = "http://localhost/api/v1"
client = httpx.Client(base_url=BASE, headers={"X-API-Key": os.environ["TK_KEY"]}, timeout=30)


def get(path: str, **params) -> dict:
    delay = 1.0
    for _ in range(6):
        res = client.get(path, params=params)
        if res.status_code != 429:
            res.raise_for_status()
            return res.json()
        wait = max(float(res.headers.get("Retry-After", delay)), delay)
        time.sleep(wait + random.uniform(0, 0.5))
        delay = min(delay * 2, 60)
    raise RuntimeError("still rate limited")


btc = get("/market/instruments", q="BTC")["items"][0]
candles = get(f"/market/instruments/{btc['id']}/candles", timeframe="1h", limit=500)["candles"]
print(len(candles), "candles; last close", candles[-1]["close"])
```

With pandas:

```python
import pandas as pd

df = pd.DataFrame(candles).set_index("time")  # time in unix seconds
```

## 6. WebSocket

Keys with the `stream` scope can open the live hub. Browsers cannot send headers on a WebSocket,
so the key goes in the query string:

```
ws://localhost/ws/market?api_key=tk_k3x9q2ab_Jq0…
```

The protocol is the same as with a login token ([websocket.md](websocket.md)). The connection
acts as the key's owner, so it may also subscribe to the owner's `user:` topic.

- Missing/invalid/revoked/expired key, or no `stream` scope → closed with **4401**.
- More than 5 open connections for one key (or one user) → closed with **4429**.
- More than 20 new connections per minute from one IP → closed with **4429**.

```python
import asyncio
import json
import os

import websockets


async def main(instrument_id: str) -> None:
    url = f"ws://localhost/ws/market?api_key={os.environ['TK_KEY']}"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps(
            {"op": "subscribe", "topic": "signals", "instrument_id": instrument_id}
        ))
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "signal":
                print(msg["signal"]["strategy_key"], msg["signal"]["side"])


asyncio.run(main("<instrument id>"))
```

Send `{"op":"ping"}` every ~30 s if you subscribe to quiet topics (75 s idle timeout).

## 7. Security notes

- Treat a key like a password. Anyone holding it can read with its scopes.
- The key never appears in server or Nginx logs (`api_key=` values are redacted).
- Prefer short expiries (`expires_in_days`) and one key per program, so you can revoke one
  without touching the others.
