# Known issues and limitations

These are genuine, current limitations. None of them is hidden in the UI.

## Dependencies on other teams

| # | Item | Impact today | Owner |
| --- | --- | --- | --- |
| 1 | No backend connected | All data is simulated (clearly labelled). API mode is implemented but **untested against a real server**. | Backend |
| 2 | Endpoint paths and shapes are proposals | Will need alignment once the Laravel routes exist (one file each: `endpoints.ts`, `schemas.ts`) | Backend + Elias |
| 3 | No streaming price endpoint confirmed | API mode polls the latest candle every 1 s per open chart, which is acceptable for a demo and unsuitable at scale. SF9 should be met with WebSocket/SSE. | Backend |
| 4 | Feature 12 output schema not final | The panel follows the spec draft. The forecast path and confidence band are optional and hidden if absent. | AI team |
| 5 | Role permissions unknown | The use-case diagrams are not available to the client, so there is **no role-based navigation** and no Admin page. Roles are displayed but do not gate anything. | Team |
| 6 | Expert chat & subscriptions (SF13) | Directory and transcript UI exist. Sending and subscribing are **disabled with an explanation** in demo mode. | Backend |
| 7 | Notification delivery (SF7) | Channel settings are saved locally. Nothing is delivered until the backend exists. | Backend |
| 8 | Workspace sync (SF18) | Workspaces persist in the browser (localStorage) only, not per account | Backend |

## Client-side limitations

| # | Item | Notes / plan |
| --- | --- | --- |
| 9 | Session token stored in localStorage in API mode | Exposed to XSS. Prefer Sanctum cookie auth (`HttpOnly`); the change is local to `http.ts` and `AppProviders.tsx`. |
| 10 | Instrument precision and pip size are client constants | Correct for standard FX conventions; should come from a backend metadata endpoint |
| 11 | Chart tick marks are placed on UTC boundaries | Labels follow the selected time zone, but tick *placement* follows the library's UTC grid. With non-UTC zones, day ticks can fall at e.g. 03:00 local. |
| 12 | Market-hours calendar ignores DST and holidays | Uses Sunday 22:00 → Friday 22:00 UTC |
| 13 | Signals table on phones | Scrolls horizontally inside a labelled region (by design, no page overflow). A card layout for < 640px would be easier to scan. |
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
