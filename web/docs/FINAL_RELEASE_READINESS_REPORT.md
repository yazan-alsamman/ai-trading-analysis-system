# Final release readiness report — frontend ↔ backend integration

_26 October 2026 · branch `e/backend-integration` · integration round against `main` `5b91175`; `main` `1afe445` merged afterwards_

The existing FastAPI backend (`backend/`) was kept exactly as it is. None of its code, migrations or data were changed. The web client (`web/`) now uses **every capability the backend offers**. What the backend does not offer is listed in [`REMAINING_BACKEND_AND_AI_REQUIREMENTS.md`](REMAINING_BACKEND_AND_AI_REQUIREMENTS.md).

## 1. Verdict

| Area | Status |
| --- | --- |
| Integration of the backend's capabilities | **Complete**: every user-facing backend feature in the table below has a screen, including **AI setups** and the **economic calendar**, which were added on `main` (`1afe445`) during this round. Not connected: data health (`/health/data`, an operations endpoint) and admin-only features. |
| Verified against the **real** backend | **Two layers:**<br>• The service layer for all features: 9/9 live tests on 26 Oct 2026, plus the 29 API and 12 browser checks from 18 Oct.<br>• The **new pages**: verified in the browser against the backend's *recorded* responses only. A live browser run was not possible (see §4). |
| Demo mode | Unchanged. All 103 browser tests pass, including the visual-regression screenshots. |
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
| Data health | — | `/health/data` | n/a | Optional operations view |
| AI assistant (LLM) | Rule-based, labelled | — none | n/a | Backend R3 |
| Platform membership | "Pricing to be announced", labelled preview | — none | n/a | Backend R6 |

## 3. Test evidence

| Suite | Kind | Result |
| --- | --- | --- |
| `pnpm typecheck` (strict TS) | static | clean |
| `pnpm lint` | static | clean (0 errors, 0 warnings) |
| `vitest run` | unit, contract (recorded responses), config | **209 passed**, including 9 contract tests for AI setups and the calendar; 11 live tests skipped without a backend |
| `src/services/api/live.services.test.ts` | **live**, real backend, service layer of every new feature | **9/9 passed** (26 Oct 2026, before the local stack was stopped) |
| `playwright test` (demo + api-mode projects) | browser, mocked backend from recordings | **Before the merge:** 103/103.<br>**After merging `main` and adding AI setups and the calendar, on fresh builds:**<br>• backend-mode project: 16/16, including the new AI-setup and calendar tests<br>• full run: 98 of 105 finished with no failure before the system stopped it for low memory; 6 demo visual screenshots and 1 other test did not run.<br>(An earlier post-merge run had hit stale preview servers; it is not counted.)<br>The tests include the new strategies, backtests, settings (workspace 409), community and alert-history tests |
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
