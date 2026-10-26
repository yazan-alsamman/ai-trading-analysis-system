# XAU/USD live feed from the cTrader Open API (B1)

> **Shipped disabled.** Nothing connects to cTrader on the server until the account is linked
> and `CTRADER_ENABLED=true` (see [enabling](#7-enabling-it-after-fxpro-approves-the-app)).

The `feed-ctrader` service streams XAU/USD quotes from FxPro's cTrader account through the
cTrader Open API and writes **1-minute bars** into `candles_1m` of the instrument
`fxpro:XAU/USD` (`CTRADER_INSTRUMENT`). The continuous aggregates build 5m to 1d from them, the
data-quality gate (B5) checks them, and the AI evaluation (B9) reads them.

| Where | What |
|---|---|
| `backend/app/feeds/ctrader/protocol.py` | the messages, payload types and price scaling, each with its official source |
| `backend/app/feeds/ctrader/connection.py` | one JSON-over-WebSocket connection (requests matched by `clientMsgId`) |
| `backend/app/feeds/ctrader/candles.py` | bars from quotes (pure) |
| `backend/app/feeds/ctrader/service.py` | the service loop (`python -m app.feeds.ctrader`) |
| `backend/app/feeds/ctrader/credentials.py`, `linking.py` | OAuth, the tokens (encrypted), the linked account |
| `backend/app/feeds/ctrader/backfill.py` | the long backfill by hand (Celery `feeds.ctrader_backfill`) |
| `backend/app/api/v1/admin_feeds.py` | the admin endpoints |
| `tools/fake_ctrader/fake_ctrader.py` | a mock cTrader server for development and CI (never in production) |

## 1. Protocol

JSON over WebSocket (`wss://demo.ctraderapi.com:5036` or `wss://live.ctraderapi.com:5036` by
`CTRADER_ENV`; an account only works on its own environment's host). Every message is
`{"clientMsgId", "payloadType", "payload"}`; answers carry the request's `clientMsgId`.

| Step | Request → answer (payload type) |
|---|---|
| application auth | `ProtoOAApplicationAuthReq` 2100 → 2101 (`clientId`, `clientSecret`) |
| token refresh (when < 7 days are left, or after a token error) | `ProtoOARefreshTokenReq` 2173 → 2174 (a new access **and** refresh token) |
| account auth | `ProtoOAAccountAuthReq` 2102 → 2103 (`ctidTraderAccountId`, `accessToken`) |
| the symbol | `ProtoOASymbolsListReq` 2114 → 2115 (find `CTRADER_SYMBOL`), then `ProtoOASymbolByIdReq` 2116 → 2117 (`digits`) |
| backfill of the gap | `ProtoOAGetTrendbarsReq` 2137 → 2138, period M1 (1), one day per request |
| live quotes | `ProtoOASubscribeSpotsReq` 2127 → 2128 with `subscribeToSpotTimestamp`, then `ProtoOASpotEvent` 2131 |
| keep-alive | `ProtoHeartbeatEvent` 51 every 10 s; after 30 s without any message a `ProtoOAVersionReq` (2104) checks the connection |
| events that end a session | `ProtoOAAccountsTokenInvalidatedEvent` 2147 (refresh, then reconnect), `ProtoOAClientDisconnectEvent` 2148, `ProtoOAAccountDisconnectEvent` 2164, errors 50 / 2142 |

**Prices** are integers in **1/100000 of a unit of price**: `ProtoOASpotEvent.bid/ask` ("e.g.
123000 in protocol means 1.23, 53423782 means 534.23782"), and trend bars as `low` plus
`deltaOpen/deltaHigh/deltaClose` over 100000 with the open time `utcTimestampInMinutes × 60`.
`digits` only sets the rounding.

Sources: [openapi-proto-messages](https://github.com/spotware/openapi-proto-messages) (commit
3fd8bddf), the official [OpenApiPy](https://github.com/spotware/OpenApiPy) sample
(`samples/jupyter/main.ipynb`), and help.ctrader.com:
[endpoints](https://help.ctrader.com/open-api/proxies-endpoints/),
[JSON](https://help.ctrader.com/open-api/protocol-buffers-json/),
[authentication](https://help.ctrader.com/open-api/account-authentication/), and the rate limits
(5 history requests a second per connection; we use at most 4).

**Reconnects.** Any failure ends the session: wait `min(60, 2^n) × uniform(0.5, 1)` seconds
(1, 2, 4 … 60), then connect, authenticate, backfill the gap and subscribe again. A session that
lasted 5 minutes resets the backoff. The service never exits on an error (no crash loop).

## 2. Bars from quotes

- **Bid basis**: OHLC on the bid (the instrument's `price_basis = bid`, like FxPro's charts). A
  quote that only changes the ask updates the spread, not the OHLC.
- **Spread, time-weighted**: `ask − bid` in price units, averaged over the minute weighted by
  how long each quote stood (from the minute's first quote to its end; the last quote counts
  until the minute's end). The decision bar of the AI evaluation always has one.
- **Volume = tick count**: spot events carry no traded volume, so `volume` is the number of
  quotes in the minute (`trades` stays null). Backfilled bars carry cTrader's own tick volume.
- **Close**: a bar is written when the first quote of a later minute arrives, or at the minute's
  end + `CTRADER_CLOSE_GRACE_SECONDS` (3) when no quote comes. **A minute without quotes has no
  bar** (weekends, the daily break).
- Every bar has `source = "fxpro_ctrader"` and `received_at`, and goes through
  `market_service.upsert_candles` and `market_events.publish_candle_updates_safely` (live
  candle updates on the WebSocket).
- The first bar after a (re)connect began mid-minute: when it closes, its OHLC and ticks come
  from that minute's trend bar (the spread stays the live one), and the minutes that passed while
  the gap backfill ran are fetched with it.

## 3. Backfill

- **Automatic**, on every start and reconnect: M1 trend bars from the minute after the last
  stored `fxpro_ctrader` bar (at most `CTRADER_BACKFILL_MAX_DAYS` = 7 days back) to the last
  closed minute, a day per request (an answer with `hasMore` is completed with more requests).
- **By hand** for a longer range (Fadi needs about a year of D1 and 20 days of 15m):
  `POST /api/v1/admin/feeds/ctrader/backfill {"from": "...", "to": "..."}` (at most 400 days).
  It runs as the Celery task `feeds.ctrader_backfill` on the maintenance queue
  (`worker-backtest`), a day at a time, and refreshes the continuous aggregates once at the end;
  its progress is in the status (`backfill`). Running it again is harmless (idempotent). It
  opens its own connection and never refreshes the tokens while the live feed is enabled (the
  feed owns the refresh).
- **The live value wins**: backfilled bars have `spread = null` (trend bars carry no spread) and
  are written with `upsert_candles(..., keep_live=True)`: a stored bar that has a spread is never
  overwritten (`ON CONFLICT … DO UPDATE … WHERE spread IS NULL`). A live bar does overwrite a
  backfilled one.

## 4. Tokens and the linked account

- **OAuth** (authorization code). Scope **`accounts`** ("view only": account information and
  prices; trading impossible) is enough for quotes and trend bars, so `trading` is never asked
  for. The code lives one minute.
- Access tokens last about 30 days (`expiresIn` 2,628,000 s); the refresh token does not expire
  but **changes on every refresh** (the old pair stops working). So the tokens live in the
  database, table `feed_credentials`, **encrypted**: Fernet with a key derived from
  `JWT_SECRET` by HKDF-SHA256 with its own label. No new secret to manage; the cost is that
  rotating `JWT_SECRET` makes them unreadable: the feed then idles with `relink_required` and the
  account must be linked again.
- The feed refreshes the tokens when fewer than 7 days are left (checked at every connect and
  every hour) and after any token error (`OA_AUTH_TOKEN_EXPIRED`, `CH_ACCESS_TOKEN_INVALID`,
  `ACCOUNT_NOT_AUTHORIZED`, or the token-invalidated event), and stores the new pair at once.
- Tokens, codes and the client secret are **never** logged or returned by the API. The
  connection's WebSocket library logger is kept at WARNING (it would print frames at DEBUG), and
  the log filter redacts `code=`, `state=` and `client_secret=` in URLs.

### Linking (admin, once)

| Endpoint (admin JWT) | |
|---|---|
| `GET /api/v1/admin/feeds/ctrader/connect` | the cTrader authorization URL with a one-time `state` (10 minutes), and the redirect URI |
| `GET /api/v1/admin/feeds/ctrader/callback?code=&state=` | where cTrader sends the browser back: no JWT, the `state` authorises it |
| `POST /api/v1/admin/feeds/ctrader/code {code, state}` | the same with a code pasted by hand |
| `PATCH /api/v1/admin/feeds/ctrader {account_id}` | choose the account (one the token can see) |
| `GET /api/v1/admin/feeds/ctrader` | the status (below) |
| `POST /api/v1/admin/feeds/ctrader/backfill {from, to}` | the long backfill |

The callback exchanges the code, stores the tokens, lists the accounts the token can see
(`ProtoOAGetAccountListByAccessTokenReq`) and chooses one: `CTRADER_ACCOUNT_ID` when set,
otherwise the only account of `CTRADER_ENV`; with several, pick one with `PATCH`.

**The redirect URI to register in the cTrader app** (Applications page, "Redirect URIs"):

```
http://187.127.76.76:8080/api/v1/admin/feeds/ctrader/callback
```

or, once `PUBLIC_BASE_URL` is set to the HTTPS name (docs/https.md),
`https://trading.yazanalsamman.com/api/v1/admin/feeds/ctrader/callback`. The `connect` answer
always shows the exact one the server will use; it must match the registered one character for
character. cTrader's docs only require a URI registered in the app; examples on its forum use
`http://` redirect URIs, so plain HTTP on 8080 should be accepted. If it is refused, or the
callback comes back **without** `state` (cTrader's docs do not say it is sent back): register a
URI cTrader accepts (e.g. `http://localhost/ctrader`), open the connect URL, copy the `code`
from the address bar where the browser lands, and within a minute call
`POST /api/v1/admin/feeds/ctrader/code {"code": "...", "state": "<from the connect answer>"}`.
A callback without state is accepted only when exactly one link was started in the last 10
minutes.

## 5. Status and the data-quality gate

`GET /api/v1/admin/feeds/ctrader` (and `feeds.ctrader` in `/api/v1/admin/system/status`):
`enabled`, `env`, `app_credentials` (set or not, never the values), `linked` and `link`
(account, environment, scope, linked/refreshed times, **token expiry**), `state` (`disabled`,
`no_app_credentials`, `not_linked`, `no_account`, `env_mismatch`, `relink_required`,
`instrument_missing`, `connecting`, `streaming`, `backoff`, `stopped`), `connected`,
`last_tick_at`, `last_bar` (time, close, spread), `reconnects_24h`, `last_error`, and the last
manual `backfill`. Never a token.

The B5 gate needs nothing new: while the feed streams, `fxpro:XAU/USD` gets a bar a minute and
`/health/data` is `ok` (with the backfill covering its 50-hour lookback); when the feed stops,
the lag passes `DATA_QUALITY_MAX_LAG_SECONDS` (120) and it turns `degraded` (and the AI
evaluation skips, B9). Tested with the mock.

## 6. Service, settings, secrets

`feed-ctrader`: the backend image with `python -m app.feeds.ctrader`, `restart: unless-stopped`,
`mem_limit: 128m`, `cpus: 0.25`, **no port** (one outbound WebSocket), in both compose files.
Idle (disabled, not linked …) it checks every minute and logs the reason once an hour.

| Setting | Default | |
|---|---|---|
| `CTRADER_ENABLED` | `false` | |
| `CTRADER_ENV` | `demo` | `demo` or `live`: the host of the account |
| `CTRADER_ACCOUNT_ID` | empty | empty: the account chosen when linking |
| `CTRADER_SYMBOL` | `XAUUSD` | the broker's symbol name |
| `CTRADER_INSTRUMENT` | `fxpro:XAU/USD` | the instrument the bars go to |
| `CTRADER_CLOSE_GRACE_SECONDS` | `3` | |
| `CTRADER_BACKFILL_MAX_DAYS` | `7` | |
| `CTRADER_CLIENT_ID`, `CTRADER_CLIENT_SECRET` | empty | written by the deploy (below) |
| `CTRADER_WS_URL` | empty | development/CI only: the mock |

**The app credentials on the server.** GitHub has the secrets `CTRADER_CLIENT_ID` and
`CTRADER_CLIENT_SECRET`. The Deploy workflow sends them over SSH **on stdin** to
`infra/deploy/set-env-secrets.sh`, which writes a key into `/opt/trading/.env` **only when it
is missing or empty** (a value already on the server is kept, so rotating the secret in GitHub
needs a manual edit of `.env`). They are masked (`::add-mask::`), never in argv, `set -x` or the
log; `.env.example` only has empty placeholders. Without the secrets in GitHub the step is
skipped.

## 7. Enabling it after FxPro approves the app

1. **Register the redirect URI** in the cTrader app (id.ctrader.com → Open API → Applications →
   your app → Redirect URIs): `http://187.127.76.76:8080/api/v1/admin/feeds/ctrader/callback`
   (or the HTTPS one, see section 4). Check the deploy wrote the app credentials:
   `GET /api/v1/admin/feeds/ctrader` shows `"app_credentials": true`.
2. **Open the connect URL as admin**: `GET /api/v1/admin/feeds/ctrader/connect` (admin JWT),
   open its `url` in the browser, sign in with the cTID that has the FxPro account and allow
   access. The browser lands on the callback and shows `"linked": true`.
3. **Pick the account** if the answer has `account_id: null`:
   `PATCH /api/v1/admin/feeds/ctrader {"account_id": <one of "accounts">}` (the demo one for
   `CTRADER_ENV=demo`).
4. **Set the env** on the server:

   ```bash
   ssh -i ~/.ssh/trading_deploy deploy-trading@187.127.76.76
   cd /opt/trading
   sed -i 's/^CTRADER_ENV=.*/CTRADER_ENV=demo/' .env            # or live, as the account is
   sed -i 's/^CTRADER_ENABLED=.*/CTRADER_ENABLED=true/' .env
   grep -E '^CTRADER_(ENABLED|ENV|ACCOUNT_ID|SYMBOL|INSTRUMENT)=' .env
   ```

5. **Restart only `feed-ctrader`** of project `trading`:

   ```bash
   docker compose -p trading -f docker-compose.yml --env-file .env --env-file image.env \
     up -d --no-deps --force-recreate feed-ctrader
   docker compose -p trading -f docker-compose.yml --env-file .env --env-file image.env \
     logs --tail 20 feed-ctrader     # "backfilled … M1 bars", then "streaming XAUUSD"
   ```

6. **Check**: `GET /api/v1/admin/feeds/ctrader` → `"state": "streaming"`, `"connected": true`,
   a recent `last_tick_at` and `last_bar` with a spread; `GET /api/v1/health/data` →
   `fxpro:XAU/USD` `ok` (once 50 hours of bars exist: run the long backfill first,
   `POST /api/v1/admin/feeds/ctrader/backfill {"from": "<a year ago>", "to": "<now>"}`).

Turning it off: `CTRADER_ENABLED=false` and the same restart. Unlinking: delete the
`feed_credentials` row (or link again, which replaces it).

## 8. Development and CI

`tools/fake_ctrader/fake_ctrader.py` is a mock server with the same JSON messages (auth, the
accounts, refresh, symbols, spots at a set rate, trend bars with `hasMore`, heartbeats, an
expired token, a dropped connection, the weekly close). The tests run it in-process on a clock
60 times faster than real time. Locally: `docker compose --profile fake-ctrader up -d
fake-ctrader`, then `CTRADER_WS_URL=ws://fake-ctrader:5036` (the OAuth token endpoint is only
mocked in the tests).
