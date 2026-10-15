# API integration

> **Status: no backend is connected.** Every endpoint below is a **PROPOSAL** from the web client. None has been confirmed by the backend team (Yazan / Rami). The paths live in one file, `src/services/api/endpoints.ts`. The response shapes are enforced at runtime by `src/services/schemas.ts`. Aligning the client with the real Laravel routes means editing those two files.

## 1. Switching to the backend

```bash
# .env.local
VITE_DATA_SOURCE=api
VITE_API_BASE_URL=https://<host>/api
```

In API mode:

- All app routes require a session (`RequireAuth`).
- Requests send `Authorization: Bearer <token>`.
- A `401` response clears the session.
- No demo fixture code runs.

## 2. Conventions assumed by the client

| Topic | Assumption | If the backend differs |
| --- | --- | --- |
| Format | JSON, **camelCase** keys | Add a mapping step in `services/api/index.ts` (Laravel API Resources can also emit camelCase) |
| Times | Candle `time` = bar **open** time in **UTC epoch seconds**; other timestamps in **epoch milliseconds** | Convert in the adapter, not in components |
| Prices | JSON numbers, not strings | Parse in the adapter |
| Errors | Laravel default: `{ "message": "...", "errors": { "field": ["msg"] } }` with 401/403/404/422/429/5xx | `http.ts` maps these to `ApiError.kind` |
| Auth | Bearer token (e.g. Laravel Sanctum personal access token) | Cookie-based Sanctum SPA auth is preferable for security: add `credentials: 'include'` and CSRF handling in `http.ts` |
| Provenance | Every market/AI object includes `provenance: "live"` | Required: the UI labels anything not `live` as simulated |

## 3. Endpoints (proposed)

All paths are relative to `VITE_API_BASE_URL`. The TypeScript shapes are in `src/domain/*.ts`, and the runtime schemas are in `src/services/schemas.ts`.

### Auth (SF17)

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| POST | `/auth/login` | `{ email, password }` | `{ user: { id, name, email, role }, token }` |
| POST | `/auth/register` | `{ name, email, password }` | same as login. The **role is assigned by the server** (trader / analyst / expert / admin). |
| POST | `/auth/logout` | — | `204` |

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
| 2 | Auth: Sanctum token or SPA cookie? How are roles returned? | Login, route protection |
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
