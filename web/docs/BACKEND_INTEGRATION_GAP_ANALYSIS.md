# Backend integration — gap analysis

> **Update 26 October 2026:** every row marked "In backend, not connected" below is now **Connected** (strategies, custom strategies, backtests, notification preferences, Telegram linking, workspace sync with 409 handling, likes and follows, expert subscription checkout with demo payments). See `FINAL_RELEASE_READINESS_REPORT.md` and, for the backend gaps that remain, `REMAINING_BACKEND_AND_AI_REQUIREMENTS.md`.

_18 October 2026 · branch `e/backend-integration` · backend at `main` `07b3d11`. The backend in this repository
(`backend/`, FastAPI) is the source of truth; nothing was added to or replaced in it._

**Evidence:**

- the backend source (`backend/app`)
- its OpenAPI document (`docs/api/openapi.json`, 155 operations, identical to the live server's)
- a **live run** of the backend on 18 October 2026 (`BACKEND_INTEGRATION_REPORT.md` §7)

## 1. Classification of every requested capability

**Classes:**

- **Connected:** implemented in the backend, connected in the web client, verified live.
- **In backend, not connected:** implemented in the backend; the web client does not use it yet (follow-up).
- **Partial:** part of it exists.
- **Not implemented:** the backend does not have it.
- **Unverified:** cannot be verified here.

| Capability | Class | Evidence | What is needed |
| --- | --- | --- | --- |
| Accounts: register, login, logout, profile, password change | **Connected** | `/auth/*`, `/users/me`, `/users/me/password`; live tests | — |
| Token refresh with rotation and reuse detection | **Connected** | `auth_service.refresh`; reuse revokes the whole family (verified live) | — |
| Market candles (all timeframes) | **Connected** | `/market/instruments/{id}/candles` from TimescaleDB continuous aggregates; live | — |
| Live market updates (WebSocket) | **Connected** | `/ws/market`: `subscribed` → `snapshot` → `candle` received live | — |
| **Real market prices** | **Not implemented in this repository** | No collector fetches prices: `seed_service.py` says demo candles are for use "until real collectors run"; there is no fetch code for Twelve Data or Binance. Prices come only from `seed-demo-candles` / `simulate-live` (synthetic) or from an external push (`POST /admin/instruments/{id}/candles`). | A data collector (AI/data team, "F03 adapters") pushing real candles. The UI labels backend prices "Backend feed", not "Live". |
| Additional pairs (AUD/USD, USD/CAD, USD/CHF, NZD/USD) | **Partial** | Instruments are data: an admin can add them (`POST /admin/instruments`), but none are seeded and there is no collector (above) | Seed or add them, plus a collector |
| Strategy-engine signals | **Connected** (display) | `/signals`; produced by the Celery task `signals.tick` for strategies users activate | — |
| Strategies (activate, custom builder), backtesting | **In backend, not connected** | `/me/strategies`, `/me/custom-strategies`, `/backtests` | A web UI (analyst feature) |
| **AI inference / AI-generated trading signals** | **Not implemented** | `ai-service/app/main.py`: `/v1/signal` is a **placeholder** that always returns `direction: "hold"`, `confidence: 0.0`, `model_version: "placeholder"`; `ai-service/notebooks/` is empty; the backend never calls the AI service (`ai_service_url` is defined but unused) | A trained model behind the AI service, plus a backend endpoint exposing its output (probability, zones, factors). The web shows "Not available yet: not exposed by the backend". |
| Prediction history / model analytics | **Not implemented** | No endpoint or table | Depends on the above |
| AI assistant (LLM) | **Not implemented** | No endpoint, no provider | A server-side provider. The web's assistant is labelled rule-based. |
| Risk profile and server position sizing | **Connected** | `/me/risk-profile`, `/risk/position-size`; live | — |
| Price alerts | **Connected** | `/me/price-alerts*`; created in the UI, verified stored, deleted, live | Firing needs the Celery worker (see report §7) |
| Notification inbox | **Connected** | `/me/notifications*`; a server notification reached the UI and read state was saved, live | — |
| Notification preferences | **In backend, not connected** | `GET/PUT /me/notification-preferences` | Settings UI (the old browser-only form is replaced by an explanation in backend mode) |
| Telegram linking | **In backend, not connected** | `/me/notifications/telegram/link` → deep link (needs `TELEGRAM_BOT_*` on the server) | Settings UI |
| Workspace synchronisation | **In backend, not connected** | `/me/workspaces*` (versioned, ETag, sharing) | Sync logic with 409 conflict handling |
| News | **Connected** | `/news` (RSS fetcher + sentiment ingestion API) | — |
| Posts and comments | **Connected** | `/posts`, `/posts/{id}/comments`. Publishing is limited by `POST_ROLES` (default analyst, expert, admin): a trader gets the server's "Your role cannot publish posts", shown in the UI (verified live). Everyone may comment. | — |
| Likes and follows | **In backend, not connected** | `/posts/{id}/like`, `/users/{id}/follow` | Small UI additions |
| Experts and expert chat | **Connected** | `/experts`, `/conversations*`; chat needs a subscription (403 with reason) | — |
| **Expert subscription checkout** | **In backend, not connected** | `/subscriptions/checkout` with **demo payments only** (`docs/subscriptions.md`) | Product decision; then a checkout flow |
| **Platform membership and entitlements** (Essential / Professional / Elite) | **Not implemented** | No plans, subscription or entitlement endpoints for the *platform*. Expert subscriptions are a different product. | Backend plans, subscription and entitlements; commercial decisions. The web shows "Pricing to be announced" and a labelled demo preview. |
| Password reset (forgot password) | **Not implemented** | No reset endpoints or e-mail flow in `auth.py` / `users.py` | Reset request + confirm endpoints |
| News comments, news impact rating | **Not implemented** (by design) | Comments exist only on posts; articles carry sentiment, not impact | None required |

## 2. Unverified, and what would verify it

| Item | Why unverified | Evidence needed |
| --- | --- | --- |
| A price alert **firing** end-to-end in the UI | Needs the worker evaluating live candles crossing the level (demo prices make this timing-dependent) | Run the worker with `simulate-live` and set a level just above the current price |
| Behaviour against the **production** server | Only read-only probes were made there (health, 401 on protected data); no accounts created | A staging server with test accounts |
| E-mail, Telegram and push delivery | Need SMTP, a Telegram bot and FCM credentials | Server credentials in a test environment |
| Safari, Firefox, mobile browsers | Live tests ran in Chrome | Cross-browser run |

## 3. Configuration and deployment work (not code)

| Item | Status |
| --- | --- |
| Production builds the web in **demo** mode (`deploy.yml`: `VITE_DATA_SOURCE=demo`) | Not changed (team-owned). Switch: `VITE_DATA_SOURCE=api`, `VITE_API_BASE_URL=/api/v1`. |
| **HTTPS** | Required before real users sign in: tokens are sent on every request, and the WebSocket token is in its URL (the backend's documented mechanism). No domain or TLS yet. |
| CORS | Not needed in production (one Nginx serves both) or in development (Vite proxy). Needed only for a split-origin deployment: `CORS_ORIGINS` (exact origins; `*` is refused by the backend). |
| WebSocket through Nginx | `infra/nginx/default.conf` already proxies `/ws/` with upgrade headers |
| Rate limits for test environments | Production defaults (5 registrations / 10 logins per IP per minute) are correct; automated live suites need higher test-only values (setup §6) |
