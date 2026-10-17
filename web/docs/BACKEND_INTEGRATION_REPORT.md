# Backend integration — report

_18 October 2026 · branch `e/backend-integration` (from `main` `07b3d11`)._
Companion documents: `BACKEND_INTEGRATION_SETUP.md` (how to run it) and
`BACKEND_INTEGRATION_GAP_ANALYSIS.md` (what could not be connected, and why).

**Deployment readiness: READY WITH DOCUMENTED LIMITATIONS**, for the verified capabilities:

- **Verified:** every integration is checked against the backend's contract and its *recorded real
  responses*, with unit, contract and browser tests on the real backend-mode bundle.
- **Not run:** against a live backend server. None was safely available here (no Docker locally; production
  was probed read-only). See §7.

---

## 1. Repository synchronisation

| | |
| --- | --- |
| Repository | `github.com/yazan-alsamman/ai-trading-analysis-system` (one monorepo: `web/`, `backend/`, `ai-service/`, `libs/`, `infra/`, `mobile/`) |
| Starting point | Local `e/web-client` at `c4b3a34` (already merged into `main` via PR #4); local `main` older |
| Remote | `origin/main` at `07b3d11` (PR #26: deploy the web client). All backend feature branches (Y10–Y20) were already merged into `main`. No open PRs. |
| Action | `git fetch`; local `main` fast-forwarded to `07b3d11` (`--ff-only`); new branch **`e/backend-integration`** created from it |
| Conflicts | None. No reset, no force, nothing discarded. Untracked local files (round-6 PDF, third-party reference captures) left untouched. |
| Baseline before changes | typecheck 0 · lint 0 · 152/152 unit tests · build OK |

## 2. Backend audit

| Item | Finding |
| --- | --- |
| Framework | FastAPI, PostgreSQL (asyncpg, Alembic), Redis, Celery; served behind Nginx |
| Contract | `docs/api/openapi.json`: OpenAPI 3.1, **155 operations**, validated in CI (`api-contract` job) |
| Recorded responses | `docs/postman/tools/examples.json`: real responses for 164 requests. Used as **contract fixtures** here. |
| API prefix | `/api/v1`; WebSocket hub `/ws/market` |
| Authentication | Bearer JWT. `POST /auth/login` → `{access_token, refresh_token, expires_in}` (access 30 min). Refresh tokens **rotate**, and presenting a used one **revokes every session of the user** (`auth_service.refresh`). WebSocket: access token in the `token` query parameter (documented; browsers cannot set WS headers). No cookies. |
| Authorisation | Server-side roles (trader, analyst, expert, admin) and per-endpoint guards. The web client never gates by role; the server is authoritative. |
| Market data | Seeded instruments: XAU/USD, EUR/USD, GBP/USD, USD/JPY (+5 crypto). Candles come from a collector **or the synthetic `seed-demo-candles` random walk**. The API does not say which, so the client labels them "Backend feed", never "Live". |
| Signals | `GET /signals` = **rule-based strategy engine** (side, strength, price, reason). The ML model's output (Feature 12) is **not exposed**. |
| Production probe (read-only) | `GET /api/v1/health` → 200; `/health/ready` → database ok, redis ok; `/market/instruments` without a token → 401 (correct); `/openapi.json` → 404 (docs disabled, correct); CORS rejects foreign origins (correct). No accounts created, nothing mutated. |

## 3. Architecture

The existing service boundary (`src/services/types.ts`) was kept: UI code depends on interfaces, with a
demo implementation and an API implementation. Integration replaced the API implementation's
*proposed* paths with the **verified** contract.

```
UI (features/*)  ──►  Services interfaces (services/types.ts)
                         ├─ services/demo/*   simulated (VITE_DATA_SOURCE=demo, default)
                         └─ services/api/*    backend   (VITE_DATA_SOURCE=api)
                               ├─ http.ts         fetch, timeouts, cancellation, error normalisation,
                               │                  401 → single refresh → one retry, x-request-id
                               ├─ session.ts      token manager: proactive + on-401 refresh, single-flight,
                               │                  cross-tab Web Lock, adopts tokens rotated by other tabs
                               ├─ marketSocket.ts one shared WebSocket: subscriptions, ping, back-off,
                               │                  4401 → refresh → reconnect, user-topic events
                               ├─ endpoints.ts    every path, each in openapi.json
                               ├─ backend.ts      Zod schemas of the backend's own shapes
                               ├─ mappers.ts      backend → UI domain (never invents missing fields)
                               └─ index.ts        the services
```

- **No new dependency.** No second data-fetching library: the existing `useResource` hook is reused.
- **Configuration** (`services/config.ts`): same-origin `/api/v1` by default; WebSocket URL derived; invalid
  configuration falls back to demo mode; the dev server proxies `/api` and `/ws` (`BACKEND_URL`, dev only).

## 4. Verified endpoint inventory (used by the web client)

| Endpoint | Auth | Web consumer | Notes |
| --- | --- | --- | --- |
| `POST /auth/login` | public | Sign in | 401 → "The email or password is incorrect." (not "session expired") |
| `POST /auth/register` | public | Register | 409 → email field error; 422 details → field errors; then signs in |
| `POST /auth/refresh` | public | Token manager | single-flight, cross-tab locked; rotated tokens persisted synchronously |
| `POST /auth/logout` | bearer | Sign out | body `{refresh_token}` (revoked server-side) |
| `GET /users/me` | bearer | Sign-in, **session restore on load** | protected routes wait ("restoring") before redirecting |
| `PATCH /users/me` | bearer | Settings → Account | `{full_name}` |
| `POST /users/me/password` | bearer | Settings → Account | `{current_password, new_password}`; backend rules mirrored |
| `GET /market/instruments` | bearer | Instrument registry | symbol mapping `XAU/USD` → `XAUUSD`; cached per session |
| `GET /market/instruments/{id}/candles` | bearer | Workspace chart, watchlist quotes | quotes: last 25 hourly candles (price vs 24 h ago) |
| WS `/ws/market` (candles, user topic) | token | Chart and watchlist streaming; notification push | replaces the old 1 s polling (rate-limit safe) |
| `GET /signals` | bearer | **New:** Signals → Strategy-engine signals | shown as rule-based signals, never as AI probabilities |
| `GET/PUT /me/risk-profile` | bearer | Capital & risk | only overlapping fields edited; the rest of the server config preserved |
| `POST /risk/position-size` | bearer | Capital & risk → **Server cross-check** | explicit action; the browser calculation stays primary; differences explained |
| `GET/POST /me/price-alerts`, `PATCH/DELETE /me/price-alerts/{id}` | bearer | Alerts | server evaluates alerts; the client-side alert engine runs only in demo mode |
| `GET /me/notifications`, `POST …/{id}/read`, `POST …/read-all` | bearer | Notification centre | mirrored; pushed over WS; 2-min polling fallback; cleared on sign-out |
| `GET /news` | bearer | Community → News | sentiment and source link; no invented "impact" |
| `GET/POST /posts`, `GET/POST /posts/{id}/comments` | bearer | Community → Posts | required title = the first line of the post |
| `GET /experts` | bearer | Community → Experts | chat availability, real cheapest plan, subscribed state |
| `POST /conversations`, `GET/POST /conversations/{id}/messages` | bearer | Expert chat | 403 (no subscription) shown with the server's reason |

That is 29 REST operations plus the WebSocket. Everything the backend offers but the web client does
not use yet is listed in the gap analysis §2.

## 5. Feature mapping

| Area | Backend mode behaviour | Status |
| --- | --- | --- |
| Public website (`/`, `/about`, `/ai-assistant`, legal, membership) | Unchanged; **makes no API calls** (e2e-verified). All public market visuals remain labelled simulated showcases, because the backend has no public market data (market endpoints require auth). | ✅ |
| Sign in / register / sign out / session restore / refresh | Real | ✅ |
| Profile name, password change | Real | ✅ |
| Workspace chart and watchlist | Real candles + WebSocket streaming, "Backend feed" label | ✅ |
| Strategy-engine signals | Real (new panel) | ✅ |
| AI analysis, personalised AI signals, model analytics, AI-opportunity alerts | "Not available yet: not exposed by the backend" | ⛔ backend (G1–G3) |
| Risk calculator | Browser calculation (unchanged formulas) + server profile sync + server cross-check | ✅ |
| Price alerts | Real (create/list/pause/delete). Editing is limited to the conditions the web form validates. | ✅ |
| Notification centre | Real inbox, push, read state | ✅ |
| News, posts, comments, experts, chat | Real | ✅ |
| Assistant | Rule-based composer on the real on-screen context, labelled "Rule-based — no AI provider is connected" | ⛔ backend (G4) |
| Membership plans and gates | Presentation and labelled demo preview only | ⛔ backend (G5) |
| Notification channel settings, workspaces sync | Not connected (endpoints exist) | 🟡 follow-up (A1, A2) |

**UI states:**

- A capability the backend lacks shows a neutral **"Not available yet"** with the reason: no red error
  and no pointless retry (`StateViews.ErrorState`).
- Network, timeout, 401, 403 (with the server's reason), 404, 409, 422 (field errors), 429 and 5xx have
  distinct, plain messages. 5xx internals are never shown.
- `x-request-id` is captured for support.

## 6. Security review

| Check | Result |
| --- | --- |
| Secrets in the frontend | None. `VITE_*` variables are public URLs and modes only. `BACKEND_URL` is dev-only and not bundled. |
| Default API URL | Changed from `http://localhost:8000/api/v1` to same-origin `/api/v1`, so a production build can no longer point at a visitor's localhost by accident. Verified: the bundle no longer contains it. |
| Token handling | Bearer header only (never in REST URLs, never logged). The WS token is in the query string **as the backend requires**; HTTPS is needed in production (gap E3). Refresh is single-flight and cross-tab coordinated, so a rotated token is never reused (which would revoke all sessions). A refused refresh ends the session; a network failure does not. |
| Token storage | `localStorage` (pre-existing design; needed for cross-tab sessions). Exposed if an XSS ever occurred, so: no raw HTML rendering anywhere (verified: no `dangerouslySetInnerHTML`/`innerHTML`); Markdown is parsed to React elements; external links use `noopener`. Recommendation for later: backend-issued HttpOnly refresh cookie. |
| Open redirects | Post-sign-in destination accepts only in-app paths (`safeRedirect`, unit-tested). |
| Frontend authorisation | None relied on. The demo plan gate is labelled a UI preview; the server enforces roles and subscriptions. |
| Data between accounts | Sign-out clears the session, the mirrored server notifications and the in-app assistant thread. Another tab's sign-out propagates. |
| Retries and polling | No automatic retry of mutations. One retry only after a 401 refresh (rejected before execution). WS back-off capped at 30 s. Inbox polling every 2 min. No unbounded loops. |
| Third parties | None added: no analytics, scripts or telemetry. |

## 7. Verification

| Check | Result |
| --- | --- |
| Type check | ✅ 0 errors |
| Lint | ✅ 0 errors, 0 warnings |
| Unit / component / contract tests | ✅ **198 / 198** (18 files; +46). New: `contract.test.ts` (28: **all 22 recorded backend responses parse**, mappings) and `client.test.ts` (18: config, refresh-and-retry, single-flight, cross-tab adoption, revocation versus offline, proactive refresh, WebSocket lifecycle incl. 4401, request bodies, risk-config preservation, safe redirects, honest demo services) |
| Production build | ✅ (main chunk 119.6 KB gzip, was 113: API adapter, socket and mappers) |
| Browser E2E: backend-mode bundle vs contract mock | ✅ **9 / 9** (`e2e/api-mode.spec.ts`): protected-route redirect and return; wrong password; Authorization header (never URLs); expired token → one refresh → retry; revoked → signed out and storage cleared; workspace REST + WebSocket streaming + "Backend feed"; alert creation body; inbox read-all; profile save; sign-out revocation; news, experts; public site makes no API calls; **the client called no endpoint outside the contract** |
| Browser E2E: demo build (regression) | ✅ **89 / 89**: flows 40, axe WCAG 2.1 AA 39 (19 routes × 2 themes + keyboard), visual matrix 10 (19 routes × 5 widths × 2 themes, no overflow, no console errors) |
| Live backend integration | ⛔ **Not run.** No Docker/PostgreSQL/Redis on this machine; production probed read-only only. Next action: `BACKEND_INTEGRATION_SETUP.md` §5 on a Docker machine or a staging server. |

## 8. Also fixed

- Price-alert dialog: the condition list would have offered server-only conditions the form cannot
  validate. It is now restricted, and server-only alerts can be paused or deleted but not edited.
- Notification channels form: saved only to the browser, so in backend mode it is replaced by an
  explanation, not a false "saved".
- "Clear" in the notification centre no longer pretends to delete server notifications.
- Chart legend: backend data previously had no provenance label at all; it now reads "Backend feed".
- The `Live` label is renamed **Backend feed** / **Streaming**, because the API cannot confirm prices are real.

## 9. Remaining blockers

See the gap analysis. The critical ones:

- **G1:** the AI model's output API
- **G5:** platform membership and entitlements
- **G4:** an assistant provider
- **E1:** a live run against a running stack
- **E3:** HTTPS
