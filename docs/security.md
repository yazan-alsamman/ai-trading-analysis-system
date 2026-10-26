# Security

How the platform protects accounts, data and the shared server (for the graduation report).
Each item names where it lives in the code.

## 1. Authentication

- **Passwords**: Argon2id through `pwdlib` (`PasswordHash.recommended()`), never stored or logged in
  clear. Minimum length and character rules on registration (`app/schemas/user.py`). The same
  answer and the same work for unknown e-mails and wrong passwords (no account enumeration).
- **Access tokens**: JWT HS256, 30 minutes (`JWT_ACCESS_MINUTES`). The secret (`JWT_SECRET`) must
  be at least 32 characters in production or the app refuses to start; the deploy generates a
  64-character random one on the server.
- **Refresh tokens**: 14 days, one row each (`refresh_tokens`), **rotated** on every use. A token
  that is presented again after rotation is treated as stolen: all of the user's refresh tokens
  are revoked (`auth_service.refresh`). Changing the password signs out every other session.
- **Login sessions** (B12 part 2): every login starts a session, the refresh-token **family**
  (`refresh_tokens.family_id` = the first row's id; a rotation keeps it). Access tokens carry it
  as the `sid` claim. **Logout** revokes the whole family (not only the presented row, so the
  session cannot be refreshed from an older sibling). A **password change**, a **refresh-token
  reuse** and a deactivation revoke every family and set `users.sessions_revoked_at`.
- **REST is unchanged**: access tokens stay stateless JWTs, so a REST call with an access token
  keeps working until it expires (at most `JWT_ACCESS_MINUTES`), even after a logout or a
  password change. Only WebSockets live long enough to need more: they close when their session
  ends (below).
- **Login protection**: per-IP limits on the auth endpoints, 5 attempts per minute per e-mail,
  and a **lockout** (10 failures in 15 minutes lock that e-mail for 15 minutes, with a `critical`
  notification to the owner). The lockout fails closed: if Redis is down, login answers 503
  instead of allowing unlimited guesses (`app/api/limits.py`).
- **New sign-in** from an unknown IP/device fingerprint notifies the owner (`login_fingerprints`).

## 2. Authorization

- **Roles**: trader, analyst, expert, admin, read from the database on every request (a role
  change applies to existing tokens). `require_roles(...)` guards role-specific endpoints;
  admin passes everywhere (`app/api/deps.py`).
- **Ownership**: every `/me/*` resource is filtered by the caller; another user's id answers
  404, not 403, so ids cannot be probed. Visibility rules for posts (public, followers,
  subscribers), conversations (participants only) and shared workspaces are enforced in the
  services, and the WebSocket hub checks them again on subscribe.
- **Entitlements** (paid features): one function (`app/payments/entitlements.py`).
- **Signal visibility** (B12): a signal whose `strategy_key` is `custom:<uuid>` is visible to a
  user only if they may use that strategy (`strategy_resolver.can_use`: their own, or public).
  Signals of global strategies are visible to everyone; a deleted custom strategy's signals to
  nobody but admins. The experts feed (`GET /experts/{id}/signals`, `signals_feed` perk) is
  unchanged: the public strategies the expert runs. **Admins see every signal**, for
  moderation. The rule is one SQL condition (`strategy_resolver.visible_signal`) applied in the
  query, so pages and `total` only count visible rows, on:
  - `GET /signals` (including `strategy_key=` and `mine=true`);
  - `GET /me/signal-plans` (your plans of a strategy made private are hidden too);
  - the notification inbox and unread count (`signal` notifications);
  - post and chat attachments of type `signal`: you can only attach one you may see, and readers
    who may not see it get `available: false` without its content. A live chat message
    resolves attachments as every user would see them; history resolves them per reader.

  Workspace overlays and strategy previews (markers) already went through
  `strategy_resolver.get` (404 for a private strategy). Backtests and their CSV exports are
  owner-only. Alerts never carry signals.
- **Live signals** (WebSocket): a private strategy's signal is never put on
  `signals:{instrument_id}`. The engine publishes it once to the owner's
  `signals:{instrument_id}:user:{owner}` and once to `signals:{instrument_id}:admins`, and the
  hub subscribes each `signals:{instrument_id}` subscriber to the private topic that matches
  them. Delivery is decided by Redis channels, with no per-message filtering in the fan-out.
  Public signals are still published once for everyone ([websocket.md](websocket.md)).

## 3. API keys

- Format `tk_<prefix>_<secret>` (256-bit secret). Only `sha256(key)` is stored; the full key is
  shown once. A fast hash is right here: the input is uniformly random, so there is nothing to
  brute-force (`app/services/api_key_service.py`).
- **Scopes** (`market:read`, `indicators:read`, `strategies:read`, `signals:read`, `stream`,
  `backtests:read`, `news:read`, `news:write`); a key can never reach `/auth/*`, `/me/*`,
  `/users/me*` or `/admin/*`. `news:write` can only be granted by an admin and stops working if
  the owner is no longer an admin. Keys can expire, be revoked, and have their own lower rate
  limit; `last_used_at` and daily usage are recorded.
- **Open WebSockets are re-authorised** (B12). Every heartbeat (25 s), each socket re-reads its
  user, and its API key if it has one: one primary-key query, run one at a time per API process
  (about 3.5 ms each; 200 sockets make about 8 checks per second). It closes the socket if the
  user is gone or inactive, or the key is revoked, expired or without `stream`. It also drops
  the topics the role or scopes no longer allow (a demoted admin's chats, `news` without
  `news:read`, the admins' private-signal topic). Revoking a key, changing its scopes,
  deactivating a user or changing a role also publishes an event on the Redis channel
  `ws-auth` after the commit. Every API process (both uvicorn workers) wakes the matching
  sockets, so they are checked at once. The heartbeat check stays as the safety net if the
  event is lost. A closed socket gets `{"type":"error","code":"auth_revoked"}` and close code
  **4401** with the reason, and its per-identity connection slot is released. A database error
  during a check keeps the socket until the next heartbeat. Access-token expiry is still
  checked as before (`token_expired`, 4401) (`app/api/ws.py`, `app/realtime/auth_events.py`).
- **Ended sessions close their WebSockets** (B12 part 2). The check above also reads, in the
  same query, whether the socket's login session (the token's `sid`) still has an unrevoked
  refresh token (an indexed `EXISTS` on `refresh_tokens.family_id`). The rule:
  - a socket whose session has no unrevoked refresh token left closes with `session ended`.
    **Logout** ends that session only (event `{"session_id"}`): the user's sockets from other
    logins stay. A **password change** or a **refresh-token reuse** ends every session (event
    `{"user_id"}`), so every login socket of the user closes. A new login afterwards is a new
    session and connects normally;
  - an access token **without `sid`** (issued before this change; they expire within
    `JWT_ACCESS_MINUTES` of the deploy) has no session: only the user-wide events close it,
    when `users.sessions_revoked_at` is later than the token's `iat`;
  - **API-key sockets are not tied to a login**: a password change does not revoke API keys, so
    their sockets stay open. Revoke the keys (`DELETE /me/api-keys/{id}`) to close them;
  - `purge-demo --yes` publishes the `user_id` event for each deleted user after its commit;
    the re-check finds no user and closes with `user not found`;
  - a new WebSocket with an access token whose session has ended is refused (4401,
    `session ended`), although the token has not expired.

## 4. Rate limits

GCRA in Redis (one atomic Lua script), per user for logins and **per key** for API keys:
trader 60, analyst/expert 300, admin 1,000 requests per minute; expensive endpoints cost more
(indicators, preview, test notification, content creation). Every response carries
`RateLimit-*` headers, 429s `Retry-After`. Normal endpoints fail open when Redis is down (logged
and counted), login fails closed. Further limits: posts, comments, reports per day/hour, chat
messages per minute/day, price alerts per role, WebSocket connections per identity and new
connections per IP (`app/core/rate_limit.py`).

## 5. Input rules

- Every request body is a Pydantic model with `extra="forbid"`; unknown fields are 422.
- **User Markdown** (posts, comments, chat, expert bios, plan descriptions) is stored as written
  and the API never returns HTML. Input with raw HTML tags, HTML comments, or links that are not
  relative/http/https/mailto (`javascript:`, `data:`, `vbscript:`, also hidden with entities or
  whitespace) is refused (`app/social/markdown.py`). Clients render Markdown with HTML disabled.
- News from feeds and the ingestion API: HTML stripped, URLs must be http(s), sizes capped.
- SQL: SQLAlchemy expressions and bound parameters everywhere; the few textual queries use
  names from code, never from input (bandit notes in §9).
- Uploads: none (attachments are references to existing rows, checked for access).

## 6. Webhooks and outbound calls

- **Telegram webhook**: a secret path segment plus Telegram's `X-Telegram-Bot-Api-Secret-Token`
  header; anything else is 404. Long polling is used in production (no HTTPS yet).
- **Payment webhook** (demo provider): HMAC-SHA256 over `"<timestamp>.<body>"`, header
  `Demo-Signature: t=…,v1=…`, 5-minute tolerance, constant-time comparison; every event id is
  processed once (`payment_events`). A real provider would plug in its own verification
  (`app/payments/provider.py`).
- **Outbound** (Telegram, SMTP, FCM, RSS): 10-second timeouts, size caps for feeds, retries with
  backoff and a circuit breaker, only to fixed provider hosts or admin-seeded feed URLs (no
  user-supplied URL is ever fetched, so no SSRF).
- **Open redirects**: the demo checkout only returns to the web app's configured origins.

## 7. Secrets

- Never committed: `.env.example` has empty placeholders; the server `.env` is created by the
  deploy with generated secrets (`chmod 600`). Channel secrets (Telegram, SMTP, FCM) are added by
  hand on the server; with them empty the channel is reported as disabled.
- The cTrader app credentials (B1, docs/ctrader-feed.md) come from the GitHub secrets
  `CTRADER_CLIENT_ID` / `CTRADER_CLIENT_SECRET`: the Deploy workflow masks them and sends them
  over SSH on stdin to `infra/deploy/set-env-secrets.sh`, which writes a key into the server
  `.env` only when it is missing or empty (never in argv, never printed).
- The cTrader OAuth tokens live in `feed_credentials`, **encrypted** (Fernet, key derived from
  `JWT_SECRET` with HKDF-SHA256 and its own label): never in `.env`, logs or API answers. The
  feed's WebSocket library logger stays at WARNING (frames carry the client secret and token),
  and the log filter redacts `code=`, `state=` and `client_secret=` in URLs. Rotating
  `JWT_SECRET` means linking the account again.
- Never logged: query-string credentials (`?token=`, `?api_key=`) are redacted by our Nginx log
  format and by the app's log filters; the Telegram bot token and webhook secret are redacted;
  HTTP client loggers are kept at WARNING (they would log URLs). CI runs the whole test suite with
  every log record at DEBUG and fails if the log contains a JWT, API key, bot token, password, the
  JWT secret, an Authorization header or a private key (`scripts/check_log_secrets.py`).
- Never returned: API keys after creation, FCM device tokens (only a suffix), card numbers (the
  demo keeps brand and last 4 only), password hashes, other users' e-mails.

## 8. Transport and server

- **Nginx** (our own container, the only published port 8080): `server_tokens off`;
  `X-Content-Type-Options: nosniff`; `Referrer-Policy: strict-origin-when-cross-origin`;
  `X-Frame-Options: DENY` and `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
  on the API; the demo payment page sets its own strict CSP (no scripts, form and framing only to
  the web app's origins) and `Cache-Control: no-store`. Body size limits: 1 MB by default, 2 MB on
  the API, 10 MB on the news ingestion.
- **Forwarded headers** are trusted only from the Nginx container address
  (`--forwarded-allow-ips`), so clients cannot spoof their IP for the rate limiter.
  - Nginx itself overwrites `X-Forwarded-For` with the connection's address on port 80
    (`:8080`).
  - On port 8090, published on `127.0.0.1` only for the host's HTTPS proxy, it trusts the proxy's
    `X-Forwarded-For` and `X-Forwarded-Proto`, but only from our compose network
    ([https.md](https.md)).
  - The HTTPS site sends `Strict-Transport-Security: max-age=31536000`, without
    `includeSubDomains`.
- **CORS**: an explicit allow-list from `CORS_ORIGINS`; the app refuses to start with `*` (it
  allows credentials).
- **API docs**: Swagger UI, ReDoc and `/openapi.json` are **disabled in production**; the public
  contract is the committed `docs/api/openapi.json`. `API_DOCS_ENABLED` overrides it: empty
  (the default, also what the deploy appends to the server `.env`) = automatic, `true` = on even
  in production, `false` = off everywhere.

### Turning the docs on for demo day

On the server, in `/opt/trading`: set `API_DOCS_ENABLED=true` in `.env` and recreate only our
backend with the command in docs/deployment.md ("تشغيل /docs يوم العرض"):
`docker compose -p trading -f docker-compose.yml --env-file .env --env-file image.env up -d --no-deps --force-recreate backend`.
To turn them off, set `API_DOCS_ENABLED=` (empty) and run the same command; `/docs` then returns
404 again. **Switch them off right after the demo**: deploys never change an existing `.env`
value, so the docs stay public until someone does. While on, they expose the full route list
and schemas (no data, no secrets; every route keeps its normal authentication).
- **Isolation on the shared VPS**: one compose project (`trading`) with its own network, volumes,
  memory and CPU limits; the database and Redis are not published (the database only on
  127.0.0.1 for SSH tunnels). Deploys only touch this stack (`infra/deploy/remote-deploy.sh`).
- **Backups**: daily `pg_dump` on the server, 7 days kept, restore procedure tested. Off-site copy
  every day by the `Off-site backup` workflow: read-only on the server (one `find`, one `scp`),
  encrypted with `gpg --symmetric --cipher-algo AES256` and the `BACKUP_PASSPHRASE` secret before it
  is uploaded (Actions artifacts are readable by anyone who can read the repo), restore-tested after
  decryption, kept 14 days (docs/deployment.md).

## 9. Checks in CI

| Check | Result on this branch |
|---|---|
| `pip-audit` (installed backend dependencies) | no known vulnerabilities |
| `bandit -r app` (fails on high) | 0 high, 0 medium, 21 low |
| secrets in the test-run log | none |
| ruff, tests, ERD/OpenAPI/AsyncAPI up to date | pass |

Accepted bandit findings (low): `assert` used for internal invariants (B101, 7), `random` for
retry jitter and the demo price simulation, not for security (B311, 3), `try/except: pass` in
observability helpers that must never break the work they observe (B110, 6), "hardcoded
password" false positives on Redis key names, error codes and the documented example password of
the OpenAPI examples (B105, 5). Two mediums are annotated with `# nosec` and a reason: a textual
query whose relation names come from an enum (B608) and an HTTP client whose timeout is enforced
by `asyncio.timeout` around each feed (B113).

## 10. Out of scope (for now)

- **HTTPS**: the server is reached by IP on port 8080 over HTTP until a domain exists; then TLS
  terminates at Nginx (Let's Encrypt), HSTS is added and Telegram can switch to the webhook mode.
  Until then, tokens travel unencrypted on the network: acceptable for the demo, not for real use.
- **Real payments**: the demo provider takes no money and stores no card data; a real provider
  (and PCI scope) is future work.
- Two-factor authentication, e-mail verification, account recovery by e-mail.
- A WAF, intrusion detection, centralised log shipping.
