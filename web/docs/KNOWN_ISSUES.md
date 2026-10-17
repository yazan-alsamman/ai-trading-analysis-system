# Known issues and limitations

These are genuine, current limitations. None of them is hidden in the UI.

## Dependencies on other teams

| # | Item | Impact today | Owner |
| --- | --- | --- | --- |
| 1 | No backend connected | All data is simulated (clearly labelled). API mode is implemented but **untested against a real server**. | Backend |
| 2 | Endpoint paths and shapes are proposals | Auth is aligned with the FastAPI backend (round 3); the rest needs alignment once those routes exist (one file each: `endpoints.ts`, `schemas.ts`) | Backend + Elias |
| 3 | No streaming price endpoint confirmed | API mode polls the latest candle every 1 s per open chart, which is acceptable for a demo and unsuitable at scale. SF9 should be met with WebSocket/SSE. | Backend |
| 4 | Feature 12 output schema not final | The panel follows the spec draft. The forecast path and confidence band are optional and hidden if absent. | AI team |
| 5 | Role permissions unknown | The use-case diagrams are not available to the client, so there is **no role-based navigation** and no Admin page. Roles are displayed but do not gate anything. | Team |
| 6 | Expert chat & subscriptions (SF13) | Directory and transcript UI exist. Sending and subscribing are **disabled with an explanation** in demo mode. | Backend |
| 7 | Notification delivery (SF7) | Channel settings are saved locally. Nothing is delivered until the backend exists. | Backend |
| 8 | Workspace sync (SF18) | Workspaces persist in the browser (localStorage) only, not per account | Backend |

## Client-side limitations

| # | Item | Notes / plan |
| --- | --- | --- |
| 9 | Session token stored in localStorage in API mode | Exposed to XSS. Access + refresh tokens (FastAPI JWT) are in localStorage. An HttpOnly-cookie flow would be safer; the change is local to `http.ts` and `AppProviders.tsx`. |
| 10 | Instrument precision and pip size are client constants | Correct for standard FX conventions; should come from a backend metadata endpoint |
| 11 | Chart tick marks are placed on UTC boundaries | Labels follow the selected time zone, but tick *placement* follows the library's UTC grid. With non-UTC zones, day ticks can fall at e.g. 03:00 local. |
| 12 | Market-hours calendar ignores DST and holidays | Uses Sunday 22:00 → Friday 22:00 UTC |
| 13 | ~~Signals table on phones~~ | **Resolved in round 3:** below 768px, Signals render as cards that open the provenance sheet. |
| 14 | Canvas chart is not readable by screen readers | Mitigated with a live text summary (last price, AI levels) linked by `aria-describedby`, plus keyboard zoom/reset buttons. Full data-table alternative not yet provided. |
| 15 | Demo comments and posts last for the session only | Intentional (demo). Alerts, preferences and workspaces persist locally. |
| 16 | No offline cache of historical data across reloads | Offline state is detected and shown, and data already loaded stays visible. A service worker for true offline mode (SF19) is not implemented. |
| 17 | Demo data is plausible-looking | Simulated prices start near realistic levels so formatting is credible. Every surface carries "Simulated", "Demo" or "Sample" labels, and the top bar always shows "Demo data" (the explanatory banner can be hidden per session). |

## Added in round 2

| # | Item | Notes |
| --- | --- | --- |
| 18 | Session board and session text use standard-time UTC hours | DST shifts (±1h for London / New York / Sydney) are not modelled |
| 19 | Price-alert evaluation runs in the browser in demo mode only | Alerts fire only while the app is open. In API mode evaluation must be server-side (it does nothing client-side). |
| 20 | Opportunity notifications (SF2) do not yet produce notification-centre items | Preferences are saved. Generating them needs the backend notification service (or a client rule, if the team prefers). |
| 21 | Notification centre is per browser | Server-delivered notifications need `GET /notifications` (proposed in API_INTEGRATION.md) |
| 22 | Settings has no in-page section navigation | Planned (DESIGN_AUDIT R6) |

## Added in round 3

| # | Item | Notes |
| --- | --- | --- |
| 23 | Access tokens are not refreshed | The FastAPI access token lives 30 min. `/auth/refresh` exists but the client does not call it yet, so the first `401` after expiry signs the user out. |
| 24 | Real-backend auth verified by contract tests only | The adapter is unit-tested against the backend's exact request/response shapes. It has **not** been run end-to-end against a live FastAPI + Postgres stack in this round (Docker stack not started). |
| 25 | AI assistant is a rule-based demo | No language model is connected. The demo composes answers from the on-screen context with fixed rules and says so on every reply. `POST /assistant/replies` is a proposal (API_INTEGRATION.md §7). |
| 26 | Risk and signal profiles are stored per browser | localStorage only. `/me/risk-profile` and `/me/signal-profile` are proposals. |
| 27 | Current exposure is user-reported | The platform never executes or tracks trades. Open risk, today’s loss and open positions are what the user enters. |
| 28 | Lots need user-entered contract sizes | By design: broker specifications are never guessed. Units (oz, currency units) are always available. Margin is not computed (needs leverage). |
| 29 | Cross-currency sizing needs a user rate | When neither currency of the pair is the account currency (e.g. GBP/USD on a EUR account), the user must enter the current quote→account rate. |
| 30 | Daily-loss check is a worst case | It adds realised loss, all open risk and the new trade, as if every stop were hit today. This is stricter than some broker definitions; it is stated on screen. |
| 31 | The Overview hero picks the first timeframe with a detected setup | 1h preferred, then 4h, then 15m. The timeframe shown is always labelled. |

## Added in round 4

| # | Item | Notes |
| --- | --- | --- |
| 32 | Membership is presentation + demo state only | No billing, subscriptions or entitlements. The gate is a UI preview, not access control (MEMBERSHIP_FRONTEND_SPEC.md). |
| 33 | Plan prices and contents not decided | Prices show "Pricing to be announced"; the feature matrix is a proposal |
| 34 | Public demo uses fixtures at a fixed time | `marketing/showcase.ts` (14 Oct 2026 14:00 UTC), labelled Simulated |
| 35 | Cross-browser motion not verified | Chrome only. View transitions degrade to instant navigation where unsupported. |
| 36 | `sitemap.xml` needs `VITE_SITE_URL` | Not emitted without a real production origin |
| 37 | Pinned sequences only at ≥ 1024 × 600 | Smaller and touch screens get static layouts by design |

## Added in round 5

| # | Item | Notes |
| --- | --- | --- |
| 38 | Background footage is licensed stock, not product footage | Coverr and Mixkit (Free licence) clips, self-hosted in `public/media/`. The charts visible in the footage are not the platform's data. See CINEMATIC_MOTION_IMPLEMENTATION.md §4. |
| 39 | Autoplay can be refused | iOS Low Power Mode and some data savers block muted autoplay; the poster stays. Not checked on a physical device. |
| 40 | 3D laptop and masks verified in Chrome only | `mask-composite`, `preserve-3d` and view transitions are not checked in Safari or Firefox. |
| 41 | Text in the turning laptop can rasterise softly | Crisp at rest; a CSS-3D limitation. |
