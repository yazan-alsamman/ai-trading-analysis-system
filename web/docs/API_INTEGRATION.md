# API integration

> **Status 18 October 2026:** the web client is now integrated with the real FastAPI contract. The *proposed* endpoints below are kept for history and for the capabilities the backend still lacks; the authoritative description is `BACKEND_INTEGRATION_REPORT.md`.

> **Status (round 3, 16 Oct 2026).** The monorepo backend is **FastAPI** (`backend/`, prefix `/api/v1`). Its **auth endpoints exist**, and the client's API adapter is aligned to them (§3 Auth). Every other endpoint below is still a **PROPOSAL** from the web client, not implemented by the backend.
>
> - Paths live in `src/services/api/endpoints.ts`.
> - Response shapes are enforced at runtime by `src/services/schemas.ts`.
> - Aligning a module means editing those two files.

## 1. Switching to the backend

```bash
# .env.local
VITE_DATA_SOURCE=api
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

In API mode:

- All app routes require a session (`RequireAuth`).
- Requests send `Authorization: Bearer <token>`.
- A `401` response clears the session.
- No demo fixture code runs.

## 2. Conventions assumed by the client

| Topic | Assumption | If the backend differs |
| --- | --- | --- |
| Format | JSON, **camelCase** keys for proposed endpoints (auth uses the backend's snake_case, mapped in the adapter) | Add a mapping step in `services/api/index.ts` |
| Times | Candle `time` = bar **open** time in **UTC epoch seconds**; other timestamps in **epoch milliseconds** | Convert in the adapter, not in components |
| Prices | JSON numbers, not strings | Parse in the adapter |
| Errors | FastAPI `{ "detail": … }` (this backend) or Laravel-style `{ "message", "errors" }`, with 400/401/403/404/409/422/429/5xx | `http.ts` maps these to `ApiError.kind` |
| Auth | JWT bearer access token + refresh token (FastAPI backend) | Tokens are kept in localStorage today; an HttpOnly cookie flow would be safer (KNOWN_ISSUES #9) |
| Provenance | Every market/AI object includes `provenance: "live"` | Required: the UI labels anything not `live` as simulated |

## 3. Endpoints (proposed)

All paths are relative to `VITE_API_BASE_URL`. The TypeScript shapes are in `src/domain/*.ts`, and the runtime schemas are in `src/services/schemas.ts`.

### Auth (SF17): implemented by the backend; client aligned

Source: `backend/app/api/v1/auth.py`, `users.py`, `schemas/auth.py`, `schemas/user.py`. The adapter is `apiAuthService` in `src/services/api/index.ts`. It is unit-tested against these exact shapes in `services.test.ts`.

| Method | Path | Body | Response | Client behaviour |
| --- | --- | --- | --- | --- |
| POST | `/auth/login` | `{ email, password }` | `TokenPair { access_token, refresh_token, token_type: "bearer", expires_in }` | `401` is shown as "The email or password is incorrect." It does **not** end any session. |
| GET | `/users/me` | — (Bearer access token) | `UserRead { id, email, full_name, role, is_active, … }` | Called right after login to build the session user |
| POST | `/auth/register` | `{ email, password, full_name }` | `201 UserRead` (no token) | Followed by login. `409` becomes an email field error. `422` `detail[].loc` is mapped to fields (`full_name` → name). |
| POST | `/auth/logout` | `{ refresh_token }` + Bearer | `204` | Revokes the refresh token |
| POST | `/auth/refresh` | `{ refresh_token }` | `TokenPair` | **Not yet used.** After the 30-minute access lifetime, the next `401` signs the user out (KNOWN_ISSUES #23). |

Password rules shown in the UI match the backend: 8–128 characters, at least one letter and one digit. Self-registration always creates a `trader`; other roles are assigned by an admin (`PATCH /admin/users/{id}/role`).

Error bodies: `http.ts` reads both FastAPI (`{ detail: string | [{loc, msg}] }`) and Laravel-style (`{ message, errors }`) shapes.

### Market data (SF3, SF4, SF9)

| Method | Path | Query | Response |
| --- | --- | --- | --- |
| GET | `/market/candles` | `symbol=EURUSD&timeframe=15m&limit=1500` | `CandleSeries { symbol, timeframe, candles: Candle[], volumeKind: "tick"\|"real", provenance, asOf }` |
| GET | `/market/quotes` | — | `Quote[] { symbol, price, reference (price 24h earlier), time, provenance }` |

- **Symbols:** `EURUSD GBPUSD USDJPY USDCHF AUDUSD USDCAD NZDUSD XAUUSD`.
- **Timeframes:** `15m 1h 4h`.
- **Candles:** sorted ascending by `time`. The last candle may still be forming.

### AI opportunities (AI Feature 12, SF8)

| Method | Path | Query | Response |
| --- | --- | --- | --- |
| GET | `/opportunities/latest` | `symbol, timeframe` | `Opportunity` |
| GET | `/opportunities` | optional `symbol, timeframe` | `Opportunity[]` |

`Opportunity` fields (from the Feature 12 specification):

| Field | Type | Notes |
| --- | --- | --- |
| `status` | `detected` / `not_detected` | |
| `direction` | `long` / `short` / `neutral` | |
| `setupType` | `trend_following` / `mean_reversion` / `breakout` / `scalping` | |
| `riskLevel` | `low` / `medium` / `high` | |
| `probability` | 0–1 | Probability that TP is reached before SL within the horizon |
| `confidenceBand?` | `{low, high}` | **Optional.** The UI shows it only if the model provides it. |
| `entryZone`, `stopLossZone`, `takeProfitZone` | `{low, high}` | |
| `riskReward` | number | |
| `expectedValueR?` | number | |
| `factors[]` | `{ id, label, detail, contribution }` | Top contributors (SHAP → text). Positive = supports the direction. |
| `forecast?` | `{ time, value }[]` | **Optional** projected path. Drawn only if present. |
| `horizonCandles` | number | |
| `signalCandleTime` | epoch s | |
| `generatedAt`, `validUntil` | epoch ms | |
| `modelVersion` | string | |
| `provenance` | `live` | |

### Predictions (SF14, SF15)

| Method | Path | Response |
| --- | --- | --- |
| GET | `/predictions/history` | `PredictionRecord[] { id, symbol, timeframe, direction, probability, riskReward, generatedAt, resolvedAt?, outcome: tp_hit\|sl_hit\|expired\|open, realizedR?, requestedByUser, modelVersion, provenance }` |

The client computes the statistics (hit rate, Brier score, calibration) in `domain/predictions.ts`. If the AI team prefers server-side statistics, add `GET /predictions/stats`.

### Alerts (SF16, SF2, SF7)

| Method | Path | Body / response |
| --- | --- | --- |
| GET | `/alerts/price` | `PriceAlert[]` |
| POST | `/alerts/price` | body `{ symbol, condition: crosses_above\|crosses_below, price, channels[], note? }` → `PriceAlert` |
| PATCH | `/alerts/price/{id}` | partial body (incl. `status: active\|paused`) → `PriceAlert` |
| DELETE | `/alerts/price/{id}` | `204` |
| GET / PUT | `/alerts/opportunity-preferences` | `{ enabled, minProbability, symbols[], timeframes[], directions[], channels[] }` |

### Community (SF11, SF12, SF13)

| Method | Path | Body / response |
| --- | --- | --- |
| GET | `/news` | `NewsItem[]` (impact classified server-side) |
| GET / POST | `/news/{id}/comments` | POST body `{ body }` → `Comment` |
| GET / POST | `/posts` | POST body `{ body, symbols[] }` → `Post` |
| GET | `/experts` | `Expert[]` |
| GET / POST | `/experts/{id}/messages` | POST body `{ body }` → `ChatMessage` |

## 4. Open questions for the backend and AI teams

| # | Question | Blocks |
| --- | --- | --- |
| 1 | Confirm or replace every path above, and share the Postman collection | All integration |
| 2 | ~~Auth contract~~ — resolved: FastAPI JWT (see §3 Auth). Open: should the client use `/auth/refresh`, or move to HttpOnly cookies? | Long sessions |
| 3 | **Streaming**: is there a WebSocket/SSE channel for prices? What are the Twelve Data plan limits? The client currently polls every 1 s per open chart as a fallback. SF9's "10 requests per second" should not be met by polling. | SF9 |
| 4 | Instrument metadata endpoint (precision, pip size, trading hours)? The client uses FX conventions until then. | Formatting |
| 5 | Exact Feature 12 output schema. Does the model output a **forecast path**, or only zones? Is a confidence band available? | AI panel, chart overlay |
| 6 | Is the RL "execution & sizing" stage in the architecture still active, given that Automated Trading (AI 19) is cancelled? The UI shows **no** execution controls either way. | Scope |
| 7 | Metric definitions and evaluation window for SF14/SF15 | Insights |
| 8 | Realtime transport and subscription model for expert chat (SF13) | Experts chat |
| 9 | Workspace persistence API (SF18). Today workspaces live in localStorage. | Multi-device workspaces |
| 10 | Notification delivery (Telegram bot linking, email verification) | SF7 |
| 11 | Use-case diagrams per role (which pages and actions each role may use) | Role-based navigation |

## 5. Integration checklist (per endpoint)

1. Confirm the path and method; update `endpoints.ts`.
2. Compare a real response with the schema in `schemas.ts`. Fix mismatches in the **adapter**, not in the UI.
3. Run the app with `VITE_DATA_SOURCE=api` and test the success, empty, 401, 422 and 500 states.
4. Update this document's status column and `docs/PROGRESS.md`.

## 6. Round 2 additions (proposed)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/market/candles?…&limit=24` | The `limit` parameter is now used for watchlist sparklines (24 × 1h per instrument) |
| GET | `/notifications` | `{ id, kind: price_alert\|opportunity\|system, title, body, createdAt, read, href? }[]` — feeds the notification centre in API mode |
| POST | `/notifications/read` | body `{ ids: string[] }` or `{ all: true }` |
| PATCH | `/alerts/price/{id}` | also accepts `triggeredAt` (set by the server when it evaluates alerts) |

Price-alert evaluation must happen on the server in API mode (the browser may be closed). The demo-only client monitor is in `features/alerts/AlertMonitor.tsx`.

## 7. Round 3 additions (proposed)

### AI assistant: provider-agnostic

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| POST | `/assistant/replies` | `{ messages: [{ role: "user"\|"assistant", content }], context: AssistantContext }` | `{ id, content (Markdown), createdAt (epoch ms), provider: "remote", contextUsed: string[] }` |

- `AssistantContext` (`src/domain/assistant.ts`) is exactly what the user sees listed under **Context**:
  - instrument and timeframe
  - last price and its provenance
  - feed status
  - the model output
  - other timeframes' outputs
  - the risk profile, **only when the user enables "Share my risk profile"**
- The backend chooses and calls the language model. **Provider keys never reach the browser.**
- The backend must not let the model claim data outside `context`.
- Streaming (SSE) and server-side conversation history are optional follow-ups. The UI already supports cancel and retry.

### Profiles (today stored in the browser only)

| Method | Path | Body / response |
| --- | --- | --- |
| GET / PUT | `/me/risk-profile` | `RiskProfile` (`src/domain/risk.ts`): capital, currency, limits, user-reported exposure, contract sizes, volume step |
| GET / PUT | `/me/signal-profile` | `SignalProfile` (`src/domain/signalProfile.ts`) |
| GET | `/instruments` | `{ symbol, pricePrecision, pipSize, contractSize?, volumeStep? }[]`. If the backend can supply broker specifications, the Risk module can show lots without user input. |

The risk calculations stay client-side (pure, unit-tested in `src/domain/risk.test.ts`). They need no endpoint.
