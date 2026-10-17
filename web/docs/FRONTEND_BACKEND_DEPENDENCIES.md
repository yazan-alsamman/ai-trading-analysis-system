# Frontend ↔ backend dependencies

_Round 6 · 17 October 2026. Verified against `origin/main` (merged into `e/web-client` on 17 Oct; backend PRs up to #25: Y18 news, posts and price alerts; Y19 expert chat and subscriptions; Y20 hardening)._

**This round changed no backend code.** The tables below record which frontend features already have a real backend endpoint, which have one the client does not use yet, and which have none.

| Status | Meaning |
| --- | --- |
| ✅ **Integrated** | The API adapter calls the real endpoint (contract-tested) |
| 🟡 **Available, not integrated** | The backend endpoint exists on `main`; the web client still uses demo data or a proposed path |
| ⛔ **Missing** | No backend endpoint exists |

## 1. By frontend feature

| Frontend feature | Backend today (`/api/v1`) | Status | Work needed (frontend) |
| --- | --- | --- | --- |
| Sign in / register / sign out | `POST /auth/login`, `/auth/register`, `/auth/logout`, `GET /users/me` | ✅ | Use `POST /auth/refresh` before the 30-min expiry (KNOWN_ISSUES #23) |
| Password recovery | — | ⛔ | Backend reset endpoints. The UI says recovery is unavailable. |
| Market candles and quotes | `GET /market/instruments`, `GET /market/instruments/{id}/candles?timeframe=` | 🟡 | The adapter uses the proposed `/market/candles?symbol=`: map symbol → instrument id and align `CandleSeries` |
| Live prices | WebSocket `/ws/market?token=` (`docs/websocket.md`) | 🟡 | Replace the 1-second polling fallback with the WebSocket hub; refresh the token on close code 4401 |
| AI opportunities (Feature 12) | `GET /signals` (strategy engine) | 🟡 / ⛔ | `/signals` serves strategy signals. The ML model's probability, zones, factors and forecast (Feature 12) are not exposed yet. |
| Risk profile | `GET/PUT /me/risk-profile` (`{account_size, quote_currency, config}`), `POST /risk/position-size`, `GET /me/signal-plans` | 🟡 | Map the client `RiskProfile` ↔ backend config. The client calculations stay as an offline preview; the server result is authoritative when connected. |
| Signal profile (personalised) | — | ⛔ | Proposed `/me/signal-profile` (API_INTEGRATION.md §7) |
| Notifications / alerts | `/me/notifications*`, `/me/notification-preferences`, Telegram link, devices | 🟡 | Feed the notification centre and Settings → channels from these endpoints |
| Price alerts | `GET/POST/PATCH /me/price-alerts`, `/me/price-alerts/history` (`docs/price-alerts.md`) | 🟡 | Replace the demo alerts store (`ata.demo.alerts.v1`) |
| Workspaces | `/me/workspaces` (versioned state, ETag, sharing) | 🟡 | Replace localStorage workspaces; handle `409` version conflicts |
| Prediction history / analytics | — | ⛔ | Proposed `/predictions/history` |
| News and market context | `GET /news`, `/news/{id}`, `/news/sentiment`, `/news/sources` — RSS ingestion running; FinBERT sentiment via the ingestion API (`docs/news-ingestion.md`, `docs/news-posts.md`) | 🟡 | Map `/news` to `NewsItem`; then the public site's "Market context" panel and Community → News can show real, sourced items instead of labelled samples |
| Community posts and comments | `GET/POST /posts`, comments, follow (`docs/news-posts.md`) | 🟡 | Replace the demo posts |
| Experts, expert chat and expert subscriptions | `/me/expert-profile`, `/me/plans`, checkout with **demo payments**, `/conversations` (`docs/subscriptions.md`, `docs/chat.md`) | 🟡 | Community → Experts. These are subscriptions **to individual experts**, not platform membership. |
| AI assistant | — | ⛔ | Proposed `POST /assistant/replies`; the provider is called server-side |
| **Platform membership** (Essential / Professional / Elite) | — | ⛔ | `/plans`, `/me/subscription`, checkout, webhook, `/me/entitlements` (MEMBERSHIP_FRONTEND_SPEC.md §6). The new expert-subscription service could be a model, but it does not cover platform plans. |
| **Payments** | Demo payment provider behind an interface (expert subscriptions only) | ⛔ for membership | No real provider. Platform membership has no checkout; the frontend must only redirect when one exists. |
| Mobile apps (store links) | — | ⛔ | `mobile/` holds only a README; no published app. Footer shows "coming soon" (`src/config/externalLinks.ts`). |

## 2. Public website

The public website (`/`, `/membership`) needs **no backend**:

- It renders the platform's own simulated fixtures at a fixed time (`src/marketing/showcase.ts`), labelled "Simulated".
- In API mode it still works without a session. Only the "Open the live demo" link is hidden, because the app then requires sign-in.

## 3. Configuration

| Variable | Purpose |
| --- | --- |
| `VITE_DATA_SOURCE` | `demo` (default) or `api` |
| `VITE_API_BASE_URL` | e.g. `http://localhost:8000/api/v1`. The shared VPS is `http://187.127.76.76:8080/api/v1` (`docs/deployment.md`). |
| `VITE_SITE_URL` | **New.** Public origin, used for canonical URLs, Open Graph and `sitemap.xml`. Optional; nothing is emitted without it. |

## 4. Prioritised integration order

1. **Workspaces + risk profile + notifications.** The endpoints exist; the work is frontend-only adapter alignment.
2. **Market data + WebSocket.** Replaces the simulated prices.
3. **Token refresh.**
4. **Feature 12 model output.** Needs the AI service to expose its outputs.
5. **Membership, subscriptions and payments.** Needs product decisions (prices, terms) and new backend services.
6. **Assistant, prediction history, community, password reset.** These need new backend services.
