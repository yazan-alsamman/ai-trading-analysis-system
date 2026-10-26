# Final release readiness report — frontend ↔ backend integration

_26 October 2026 · branch `e/backend-integration` · integration round against `main` `5b91175`; `main` `1afe445` merged afterwards_

The existing FastAPI backend (`backend/`) was kept exactly as it is. None of its code, migrations or data were changed. The web client (`web/`) now uses **every capability the backend offers**. What the backend does not offer is listed in [`REMAINING_BACKEND_AND_AI_REQUIREMENTS.md`](REMAINING_BACKEND_AND_AI_REQUIREMENTS.md).

## 1. Verdict

| Area | Status |
| --- | --- |
| Integration of the backend's capabilities | **Complete.** The web client calls **172 of the backend's 181 operations** (all of them except the 9 in §2a, none of which belongs in a website). This includes the **admin console** (users, moderation, content, market data, AI engine, payments, API access, system status). |
| Verified against the **real** backend | **Two layers:**<br>• The service layer for all features: 9/9 live tests on 26 Oct 2026, plus the 29 API and 12 browser checks from 18 Oct.<br>• The **new pages**: verified in the browser against the backend's *recorded* responses only. A live browser run was not possible (see §4). |
| Demo mode | Unchanged. All 89 demo browser tests pass on a fresh build, including the 10 visual-regression screenshots. |
| Ready to deploy | **No, configuration first** (§5): `deploy.yml` still builds demo mode. HTTPS now exists on `main` (trading.yazanalsamman.com, #51). |
| AI predictions, real prices, password reset, LLM assistant, platform membership | **Backend gaps.** The screens say "Not available yet" and never show stand-in data (§6). |

## 2. Feature table

"Mocked" means the production backend-mode bundle in Chrome, against responses **recorded from the real backend** (`docs/postman/tools/examples.json`). Any request to an endpoint the backend does not have fails the test. "Live" means the real backend stack (FastAPI, PostgreSQL/TimescaleDB, Redis, Celery) with nothing mocked.

| Feature | Frontend UI | Backend API | Real integration tested | Remaining work |
| --- | --- | --- | --- | --- |
| Register, sign in, sign out, token refresh | Auth pages, session | `/auth/*` | **Live** (browser, 18 Oct) | — |
| Profile name, password change | Settings → Account | `/users/me*` | **Live** (browser) | — |
| Password reset | "Forgot password?" explains it is unavailable | — none | n/a | Backend R5 |
| Market candles and live updates | Workspace chart | `/market/*`, `/ws/market` | **Live** (browser) | Real prices: backend R4 |
| Strategy-engine signals | Signals page | `/signals` | **Live** (browser) | — |
| Price alerts | Alerts page | `/me/price-alerts*` | **Live** (browser) | — |
| Alert trigger history | Alerts → Trigger history | `/me/price-alerts/history` | Mocked (browser) | Live browser run |
| Notification inbox (read, read-all) | Bell / notification centre | `/me/notifications*` | **Live** (browser) | — |
| Notification delete, unread count | Notification centre | `/me/notifications/{id}`, `/unread-count` | **Live** (service) + mocked (browser) | Live browser run |
| Notification preferences, quiet hours, language | Settings → Notifications | `/me/notification-preferences` | **Live** (service) + mocked (browser) | Live browser run |
| Channel status, test delivery, Telegram link/unlink | Settings → Notifications | `/me/notifications/channels`, `/test`, `/telegram*` | **Live** (service); Telegram needs a bot token | Credentials (backend R8) |
| Risk profile, server position size | Capital & risk | `/me/risk-profile`, `/risk/position-size` | **Live** (browser) | — |
| Strategy catalog, activations, preview chart | Strategies → Catalog / My strategies | `/strategies*`, `/me/strategies*` | **Live** (service) + mocked (browser) | Live browser run |
| Custom strategies (builder/composite, versioned, 409) | Strategies → Custom (JSON editor, server validation) | `/me/custom-strategies*`, `/custom-strategies/*` | **Live** (service, incl. 409) + mocked | A visual drag-and-drop builder (optional) |
| Public strategies, clone | Strategies → Community | `/custom-strategies/public*` | **Live** (service) + mocked | — |
| Signal plans | Strategies → Signal plans | `/me/signal-plans` | **Live** (service) + mocked | Typed plan schema (backend) |
| Backtests: run, progress, results, trades, CSV, compare, cancel/delete | Backtests list + detail | `/backtests*`, WebSocket progress | **Live** (service, run by the Celery worker) + mocked (browser incl. CSV download) | Live browser run |
| Server workspaces with 409 conflict handling | Settings → Server workspaces | `/me/workspaces*` | **Live** (service, incl. 409) + mocked (browser: conflict dialog → explicit overwrite) | Reorder/share UI (not in the service layer) |
| News | Community → News | `/news` | **Live** (browser) | — |
| Posts, comments | Community → Posts | `/posts*` | **Live** (browser) | — |
| Likes, edit/delete (server-granted), replies, reports, direction/timeframe/visibility, "Following" feed | Community → Posts | `/posts/{id}/like`, `/comments/{id}`, `/reports` | **Live** (service) + mocked (browser: like) | Live browser run |
| Follows, profiles, followers/following | Community → People, profile page | `/users/{id}/follow`, `/users/{id}/profile`, `/me/follow*` | **Live** (service) + mocked (browser: follow) | — |
| Experts, expert chat | Community → Experts | `/experts`, `/conversations*` | **Live** (browser) | — |
| Expert detail, plans, signal feed | Expert page | `/experts/{id}`, `/experts/{id}/signals` | **Live** (service) + mocked | Typed signal schema (backend) |
| Expert subscriptions (**demo payments**) | Subscribe → backend demo checkout → return page; Settings → Subscriptions (cancel/resume, invoices) | `/subscriptions/checkout`, `/me/subscriptions*` | **Live** (service: paid with test card 4242…, cancel/resume) + mocked | Real payments: backend R7 |
| Expert studio (profile, plans, earnings) | Settings → Expert studio (expert role) | `/me/expert-profile`, `/me/plans*`, `/me/earnings` | **Live** (service) | Live browser run |
| API keys (shown once) | Settings → API keys | `/me/api-keys*` | **Live** (service) + mocked (browser) | — |
| **AI setups:** follows (min grade), setups the server sent, live state changes, size for your account, verified explanation (ar/en), "I took this trade" record, taken setups with results | AI setups page (`/ai-setups`); `ai_setup` notifications open it | `/me/ai/follows*`, `/ai/setups/{id}/size`, `/explanation`, `/take`, `/me/ai/trades`, `/me/notifications?type=ai_setup`, WebSocket `ai_setups` | Mocked (browser, incl. a live frame) + contract tests on recordings; live checks written, **not yet run** | v1 is rules-only: probability, EV and grade show "Not provided" |
| **Economic calendar:** week view, currency and impact filters, revision history, next high-impact event | Economic calendar page (`/calendar`) | `/calendar/events`, `/calendar/events/{key}/history` | Mocked (browser) + contract tests; live check written, **not yet run** | — |
| AI opportunities per instrument, prediction history, model analytics | "Not available yet" | No per-instrument listing; no model in v1 | n/a | Backend/AI R1, R2 |
| **Data health** | Warning banner above every page when an instrument is degraded or has no data (dismissible) | `/health/data` (a 503 still carries the report) | Mocked (browser, degraded case) + contract | — |
| **Admin console** (admin role only; hidden and refused for others) | `/admin`: System (readiness, system status, hub, rate limits, delivery stats) · Users (search, role, activate) · Moderation (reports: hide/dismiss with a note; conversations) · Content (news sources, publish article, sentiment, calendar refresh and CSV import, broadcast) · Market data (instruments and specs, 1m candle upload, cTrader feed) · AI engine (setups and detail, alert outbox retry, models) · Payments (statistics, subscriptions, refund, demo fast-forward) · API access (all keys, revoke) | every `/admin/*` operation, `/ingest/news*`, `/health/ready` | Mocked (browser: every tab loads, resolve and broadcast send the contract) + 8 contract tests | No admin invoice list in the backend: refunds take an invoice ID |
| **Workspace order and sharing** | Settings → Server workspaces (move up/down, share link, stop sharing); `/workspaces/shared/:slug` read-only page with "Copy to my workspaces" | `/me/workspaces/order`, `/me/workspaces/{id}/share`, `/workspaces/shared/{slug}[/import]` | Mocked (browser) + contract | — |
| **Expert chat moderation** | Expert chat: block/unblock, edit (15 min) and delete your own messages | `/conversations/{id}[/block|/unblock]`, `/messages/{id}` | Contract tests | Deleted messages disappear instead of showing the server tombstone |
| **News detail, sentiment, sources** | `/community/news/:id`; sentiment panel (1h/24h/7d) and sources list on News | `/news/{id}`, `/news/sentiment`, `/news/sources` | Mocked (browser) + contract | — |
| **Server indicators** | Strategies → Indicators: the server's library and computed lines on the server's candles | `/indicators`, `/market/instruments/{id}/indicators` | Mocked (browser) + contract | — |
| **Risk templates** | Capital & risk: the server's conservative / balanced / aggressive templates compared | `/risk/schema` | Contract | — |
| **Push devices** | Settings → Notifications: devices registered by the mobile app, remove | `GET /me/devices`, `DELETE /me/devices/{id}` | Contract | Registering this browser for push would need Firebase (not added) |

### 2a. Backend operations the website deliberately does not call (9)

| Operation | Why |
| --- | --- |
| `GET /pay/demo/{id}`, `POST /pay/demo/{id}/confirm`, `GET /pay/demo/{id}/done` | The backend's own hosted demo payment page; the website sends the browser there and back |
| `POST /payments/webhook/{provider}` | Server-to-server callback from a payment provider |
| `GET /admin/feeds/ctrader/callback` | The redirect target of the cTrader login, opened by cTrader, not by the website (the admin page starts the flow and accepts a pasted code) |
| `GET /health`, `GET /health/live` | Infrastructure probes (the admin console uses `/health/ready` and `/health/data`) |
| `POST /auth/token` | OAuth2 form login for the API docs; the website uses `/auth/login` |
| `POST /me/devices` | Registers an FCM push token; the mobile app does it. Web push would need Firebase, a new external dependency that was not added |
| AI assistant (LLM) | Rule-based, labelled | — none | n/a | Backend R3 |
| Platform membership | "Pricing to be announced", labelled preview | — none | n/a | Backend R6 |

## 3. Test evidence

| Suite | Kind | Result |
| --- | --- | --- |
| `pnpm typecheck` (strict TS) | static | clean |
| `pnpm lint` | static | clean (0 errors, 0 warnings) |
| `vitest run` | unit, contract (recorded responses), config | **221 passed**, including 9 contract tests for AI setups and the calendar and 12 for the admin console and user extras; 11 live tests skipped without a backend |
| `src/services/api/live.services.test.ts` | **live**, real backend, service layer of every new feature | **9/9 passed** (26 Oct 2026, before the local stack was stopped) |
| `playwright test` (demo + api-mode projects) | browser, mocked backend from recordings | **109/109 on fresh builds (final state):** backend-mode project 20/20; demo project 79/79 plus 10/10 visual screenshots (run in two parts because of low memory).<br>(An earlier post-merge run had hit stale preview servers; it is not counted.)<br>The tests include the admin console, workspace sharing, news detail, server indicators, data-health banner, AI setups, calendar and the strategies, backtests, settings (workspace 409), community and alert-history tests |
| `e2e-live/live.spec.ts` | **live** browser | 12/12 on 18 Oct for the originally connected features; **not re-run** for the new pages (see §4) |

**What the live service suite exercised against the real server:**

- strategy activations, isolated per user
- custom strategies, including a stale-version 409
- a backtest queued and run by the Celery worker, with CSV export and compare
- server workspaces, including a 409 on a stale version
- notification preferences, test delivery and the inbox
- likes, follows, replies, server-granted edit rights and reports
- an expert profile and plan, a demo checkout paid with the test card, cancel/resume, earnings
- API keys

## 4. What was not verified, and why

- **The new pages in a live browser run.** During this session, Windows cleaned the temporary folder that held the local stack's binaries (PostgreSQL, Redis, the Python environment) and part of the database directory.
  - PostgreSQL and the Python environment were rebuilt.
  - Starting a re-downloaded Redis (checksum verified) was refused by the session's permission policy. Without Redis the backend cannot run (rate limits, WebSocket hub, Celery).
  - **To complete it:** start the stack (`BACKEND_INTEGRATION_SETUP.md` §3), then run `LIVE_BACKEND_URL=http://127.0.0.1:8000 pnpm exec vitest run src/services/api/live.services.test.ts` and `pnpm exec playwright test -c playwright.live.config.ts`.
- **E-mail, Telegram and push delivery:** these need server credentials (R8).
- **Safari and Firefox:** not checked (Chrome only).
- **Production:** not touched. No deploy and no production database change.

## 5. Before deploying

1. **Switch the build to backend mode.** `deploy.yml` builds with `VITE_DATA_SOURCE=demo`. Set `VITE_DATA_SOURCE=api` and `VITE_API_BASE_URL=/api/v1`; the Dockerfile default is now `/api/v1`. An invalid value now shows a blocking configuration screen instead of silently falling back to demo mode.
2. **HTTPS.** `main` now serves the platform at `https://trading.yazanalsamman.com` (`docs/https.md`). Use that origin for real accounts: tokens are sent on every request, and the WebSocket token is in its URL.
3. **Celery worker queues.** Run the worker with `-Q celery,notifications,backtests`. Without the `backtests` queue, backtests stay queued.
4. Optional: Telegram, SMTP and FCM credentials in the server environment (never in the repository).

## 6. Data integrity and safety

- **Concurrent edits:** server workspaces and custom strategies send the version they edited. A 409 opens a dialog. Overwriting is an explicit choice, and the other device's change is never lost silently.
- **No stand-in data:**
  - Demo mode rejects every backend-only capability with "Not available yet". Nothing is simulated in its place.
  - Rule-based strategy output, backtests (labelled historical, not a forecast) and AI output are always labelled distinctly.
- **No trading or real money:**
  - The platform never places trades, and no screen offers it.
  - Payments are labelled "Demo payment — no real money".
- **Secrets:**
  - The browser never holds a provider key.
  - API key secrets are shown once and never stored by the client.
  - No secret, `.env` file or database is committed.
