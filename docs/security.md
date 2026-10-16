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

## 3. API keys

- Format `tk_<prefix>_<secret>` (256-bit secret). Only `sha256(key)` is stored; the full key is
  shown once. A fast hash is right here: the input is uniformly random, so there is nothing to
  brute-force (`app/services/api_key_service.py`).
- **Scopes** (`market:read`, `indicators:read`, `strategies:read`, `signals:read`, `stream`,
  `backtests:read`, `news:read`, `news:write`); a key can never reach `/auth/*`, `/me/*`,
  `/users/me*` or `/admin/*`. `news:write` can only be granted by an admin and stops working if
  the owner is no longer an admin. Keys can expire, be revoked, and have their own lower rate
  limit; `last_used_at` and daily usage are recorded.

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
- **CORS**: an explicit allow-list from `CORS_ORIGINS`; the app refuses to start with `*` (it
  allows credentials).
- **API docs**: Swagger UI, ReDoc and `/openapi.json` are **disabled in production**; the public
  contract is the committed `docs/api/openapi.json`.
- **Isolation on the shared VPS**: one compose project (`trading`) with its own network, volumes,
  memory and CPU limits; the database and Redis are not published (the database only on
  127.0.0.1 for SSH tunnels). Deploys only touch this stack (`infra/deploy/remote-deploy.sh`).
- **Backups**: daily `pg_dump`, 7 days kept, restore procedure tested (docs/deployment.md).

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
