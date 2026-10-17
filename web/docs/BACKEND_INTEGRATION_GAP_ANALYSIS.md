# Backend integration — gap analysis

_18 October 2026 · branch `e/backend-integration` · backend verified at `origin/main` `07b3d11`
(contract: `docs/api/openapi.json`, 155 operations)._

Every web-client capability that could **not** be connected to the backend, with the evidence and
the safest resolution. In backend mode (`VITE_DATA_SOURCE=api`) each of these shows a deliberate
"Not available yet" state with the reason. None falls back to simulated data or a fake success.

**Evidence method:**

- the OpenAPI document (validated in CI)
- the backend source under `backend/app`
- the recorded responses in `docs/postman/tools/examples.json`

"Not in the contract" means no path exists for it in `openapi.json`.

## 1. Blocked by missing backend capability

| # | Frontend feature | Expected behaviour | Missing backend capability | Evidence | Recommended resolution | Backend action? |
| --- | --- | --- | --- | --- | --- | --- |
| G1 | **AI analysis panel** (workspace), Overview hero, **Personalised signals**, Signal detail | The trained model's output per instrument and timeframe: direction, probability (target before stop), confidence band, entry, stop and target zones, contributing factors, projection | No endpoint exposes Feature 12 model output. `GET /signals` serves the **rule-based strategy engine** (side, strength, price, reason), with no probability, zones or factors. | Not in the contract. `SignalRead` schema; `backend/app/services/signal_engine.py` | Expose the model's output, e.g. `GET /analysis/latest?instrument_id=&timeframe=`, matching `OpportunitySchema` (`web/src/services/schemas.ts`). Until then the web shows strategy signals as what they are (new panel) and the model panels say "not exposed by the backend yet". | **Yes** (AI and backend) |
| G2 | **Model analytics** (Insights: hit rate, Brier score, calibration) | Resolved prediction history | No prediction history endpoint | Not in the contract | `GET /predictions/history` (shape: `PredictionRecordSchema`) | **Yes** |
| G3 | **Alerts on AI opportunities** (Alerts → opportunity notifications) | Notify when the model finds a setup matching the user's filters | Depends on G1; no preferences endpoint for it | Not in the contract | After G1: server-side matching plus a preferences endpoint. Strategy-signal notifications already exist on the backend (`type: signal`) and are shown in the notification centre. | **Yes** |
| G4 | **AI assistant with a language model** | Answers from a real AI provider, server-side | No assistant endpoint | Not in the contract | `POST /assistant/replies` (proposal in `docs/API_INTEGRATION.md` §7), provider key held on the server. Today the rule-based composer runs in the browser on the context shown, labelled **"Rule-based — no AI provider is connected"**. | **Yes** |
| G5 | **Platform membership** (Essential / Professional / Elite), entitlements, plan checkout | Real plans, a subscription state, server-enforced feature access | No platform plans, subscription or entitlement endpoints. `/subscriptions/*` and `/me/plans` are **expert** subscriptions (demo payments). | `docs/subscriptions.md`; contract | `GET /plans`, `GET /me/subscription`, `GET /me/entitlements` (`docs/MEMBERSHIP_FRONTEND_SPEC.md` §6). The UI keeps "Pricing to be announced" and the labelled **demo** plan preview, which is not access control. | **Yes**, plus commercial decisions |
| G6 | **Password reset** (forgotten password) | Email a reset link | No reset endpoints (only the signed-in password change) | Not in the contract | `POST /auth/password-reset` + confirm. The sign-in page states that recovery is unavailable. | **Yes** |
| G7 | **Comments on news** | Discussion under a news item | Comments exist only on posts | Contract: `/posts/{id}/comments` only | Either add news comments, or link a news item to a post. Backend news shows no comment button. | Optional |
| G8 | **News impact rating** | High / medium / low per item | Articles carry model **sentiment**, not impact | `ArticleRead` | None needed; the UI shows sentiment and hides the impact filter for backend news. | No |
| G9 | **Instruments AUD/USD, USD/CAD, USD/CHF, NZD/USD** | Same features as the other majors | Not seeded on the backend (seed list: XAU/USD, EUR/USD, GBP/USD, USD/JPY + crypto) | `backend/app/services/seed_service.py` | Admin adds them (`POST /admin/instruments`) and connects a data collector. The web reports "not available on the backend yet" per instrument. | **Yes** (admin/data) |
| G10 | **Real-time market data provenance** | Show whether prices are real | The API does not say whether an instrument's candles come from a real collector or the seeded random walk (`seed-demo-candles`) | `backend/app/cli.py` prints "DEMO DATA … not real prices"; no field in `InstrumentRead` | Add e.g. `data_status: real \| demo` to `InstrumentRead`. The web labels backend prices **"Backend feed"**, never "Live". | **Yes** (small) |

## 2. Available on the backend, not yet connected in the web client

These are not blockers; they are follow-up frontend work. The endpoints exist and are documented.

| # | Feature | Endpoints | Why not in this pass | Effort |
| --- | --- | --- | --- | --- |
| A1 | Server notification **preferences**, Telegram linking, push devices | `/me/notification-preferences`, `/me/notifications/telegram/*`, `/me/devices` | Needs a new Settings UI; the old browser-only channels form is now replaced in backend mode by an explanation | M |
| A2 | **Workspaces** sync (versioned, ETag, sharing) | `/me/workspaces*`, `/workspaces/shared/*` | Needs conflict handling (409 on version) and a migration of locally stored layouts | M–L |
| A3 | Expert **subscription checkout** | `POST /subscriptions/checkout` → hosted demo-payment page; `/me/subscriptions` | Payments are demo-only on the backend; enabling a checkout UI is a product decision | M |
| A4 | Post **likes**, follow, reports, editing; comment replies | `/posts/{id}/like`, `/users/{id}/follow`, `/reports`, `PATCH /posts/{id}` | Not part of the existing web UI | S–M |
| A5 | Strategy activation, custom strategies, backtests, API keys | `/me/strategies`, `/me/custom-strategies`, `/backtests`, `/me/api-keys` | No web UI exists for them (mobile/analyst features) | L |
| A6 | Live **signal** and **news** pushes on the WebSocket | topics `signals`, `news` | The panels refresh on demand; push is an enhancement | S |
| A7 | Chat in real time (typing, read receipts) | WebSocket `chat` topic, `/conversations/{id}/read` | Chat works over REST; realtime is an enhancement | S |

## 3. Blocked by environment (not by code)

| # | Item | Status | Next action |
| --- | --- | --- | --- |
| E1 | **Run against a live backend** (local Docker stack or a staging server) | Not possible here: no Docker, PostgreSQL or Redis on this machine. Production (`http://187.127.76.76:8080`) was probed **read-only** (health checks only); no test accounts were created there. | Run `docker compose up` on a machine with Docker and use `docs/BACKEND_INTEGRATION_SETUP.md` §5 to verify; or provide a staging URL with test accounts. |
| E2 | **Switch production to backend mode** | `deploy.yml` builds the web image with `VITE_DATA_SOURCE=demo` (team-owned deployment config, not changed) | When the team is ready: build with `VITE_DATA_SOURCE=api` and `VITE_API_BASE_URL=/api/v1`. Expect sign-in to be required for the app and G1–G6 panels to show "Not available yet". |
| E3 | HTTPS | No domain yet (`docs/deployment.md`), so the site and its tokens travel over plain HTTP | A domain plus TLS before real users sign in |
