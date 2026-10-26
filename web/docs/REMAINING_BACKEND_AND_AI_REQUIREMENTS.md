# Remaining backend and AI requirements

_26 October 2026 · branch `e/backend-integration` · backend at `main` `1afe445` (merged into the branch)._

This lists what the web client needs that the backend in this repository (`backend/`, FastAPI) and the AI service (`ai-service/`) **do not provide yet**. Each entry was checked against the source and the OpenAPI document (`docs/api/openapi.json`, 155 operations). It was not taken from the web client's assumptions.

Every capability the backend provided when this integration round started (`main` `5b91175`) is now connected in the web client (see `FINAL_RELEASE_READINESS_REPORT.md`).

**New on `main` while this round ran (not yet connected in the web client).** `main` gained 77 commits on 26 October, now merged into the branch. They add the following backend capabilities, which have no web screen yet:

| Capability | Endpoints | Notes |
| --- | --- | --- |
| **AI setups** (B7–B11, ai-service P6) | `GET/PUT/DELETE /me/ai/follows*`, `GET /ai/setups/{id}/size`, `GET /ai/setups/{id}/explanation`, `POST/DELETE /ai/setups/{id}/take`, `GET /me/ai/trades`; `ai_setup` notifications | v1 is **rules-only** (`versions.model` is null, `docs/ai-contract.md`). Setups reach a user through follows and notifications; there is no per-instrument "latest analysis" listing. |
| Economic calendar (B6) | `GET /calendar/events`, `GET /calendar/events/{key}/history` | — |
| Data health, instrument specs, session calendar (B4, B5) | `GET /health/data`, new fields on instruments and candles | The web client accepts the added fields |
| AI risk inputs, leverage | `ai_risk` and `leverage` on `/me/risk-profile` | — |
| XAU/USD live feed from cTrader (B1) | admin only | Shipped **disabled** until the cTrader app is approved |

These are the next integration round. Until then, the AI panels in backend mode keep saying "Not available yet": the backend still has no endpoint for the opportunity per instrument and timeframe that those panels show (R1). The items below are the only reasons a screen still says "Not available yet", "Pricing to be announced" or "rule-based".

Nothing here was added to the backend by the web work. The contracts proposed below are suggestions for the owning team; the web client already has the matching domain types (`web/src/domain/*`), so each one becomes one adapter in `web/src/services/api/`.

## Classification

| # | Capability | Status in this repository | Owner |
| --- | --- | --- | --- |
| R1 | AI trading opportunities (probability, zones, explanation) | **Not implemented**: the AI service is a placeholder | AI team + backend |
| R2 | Prediction history, accuracy and calibration | **Not implemented**: no table or endpoint | AI team + backend |
| R3 | AI assistant (language model) | **Not implemented**: no provider and no endpoint | Backend (product decision) |
| R4 | Real market prices | **Not implemented**: no collector exists | Data / backend |
| R5 | Password reset (forgot password) | **Not implemented**: no endpoints, no e-mail flow | Backend |
| R6 | Platform membership (Essential / Professional / Elite) and entitlements | **Not implemented**: only *expert* subscriptions exist | Backend + business |
| R7 | Real payments | **Not implemented by design**: expert subscriptions use the backend's demo payment provider | Business + backend |
| R8 | E-mail, Telegram and push delivery in an environment | **Implemented, needs credentials** | DevOps |
| R9 | Additional instruments (AUD/USD, USD/CAD, USD/CHF, NZD/USD) | **Partial**: an admin can add them, but none are seeded and there is no collector | Data / backend |

## R1 — AI trading opportunities

**Evidence (updated for `main` `1afe445`):**

- ai-service now serves `POST /v1/evaluate` and `POST /v1/size` (P6). v1 runs the setup rules without a trained model (`versions.model` is null, contract 0.2.1). The P4 model gate was not passed (documented in the ai-service history).
- The backend evaluates on a schedule (B9) and stores AI setups (B8). It delivers them to followers (B11) and exposes per-setup size, explanation and take (see the table above).
- No backend route returns **the latest analysis per instrument and timeframe** with probability, zones and factors, which is what the web Opportunity panels show.

**What the web client shows today:**

- In backend mode, the Workspace AI panel, Overview hero and Signals "model" columns say "Not available yet: not exposed by the backend".
- Strategy-engine signals (`GET /signals`, rule-based) are shown separately and labelled as such. They are never presented as AI output.

**Needed:**

1. A trained model behind the AI service (the probability fields need one; v1 is rules-only).
2. Either connect the web client to the AI-setup endpoints now on `main`, which is the next web round, or add a per-instrument listing that serves the model output. Proposed contract, matching `web/src/domain/opportunity.ts`:

```
GET /api/v1/opportunities?instrument_id=&timeframe=      → list (latest per instrument/timeframe)
GET /api/v1/opportunities/latest?instrument_id=&timeframe= → one

{
  "id": "uuid", "instrument_id": "uuid", "timeframe": "1h",
  "status": "detected" | "not_detected",
  "direction": "long" | "short" | "neutral",
  "setup_type": "trend_following" | "mean_reversion" | "breakout" | "scalping",
  "risk_level": "low" | "medium" | "high",
  "probability": 0.0–1.0,                     // P(TP before SL within the horizon)
  "confidence_band": {"low": .., "high": ..}, // optional, never synthesised
  "entry_zone": {"low": .., "high": ..}, "stop_loss_zone": {..}, "take_profit_zone": {..},
  "risk_reward": 2.0, "expected_value_r": 0.4,          // optional
  "factors": [{"id": "", "label": "", "detail": "", "contribution": 0.12}],  // top 5, signed
  "forecast": [{"time": 1772323200, "value": 2650.1}],  // optional
  "horizon_candles": 24, "signal_candle_time": 1772323200,
  "generated_at": "ISO", "valid_until": "ISO", "model_version": "f12-2026.10.1"
}
```

3. Optionally, push new analyses on the existing `/ws/market` topic so the panel updates without polling.

## R2 — Prediction history and model analytics

**Evidence:** no table, model or route for resolved predictions.

**Web:** the Insights page (accuracy, calibration, history) shows "Not available yet" in backend mode.

**Needed:** persist every published opportunity and resolve it (TP hit / SL hit / expired, realised R). Expose it with endpoints matching `web/src/domain/predictions.ts`:

```
GET /api/v1/predictions?limit=&offset=&instrument_id=&timeframe=
  → items[{id, instrument_id, timeframe, direction, probability, risk_reward,
            generated_at, resolved_at?, outcome: tp_hit|sl_hit|expired|open,
            realized_r?, model_version}], total
GET /api/v1/predictions/stats  → {total, resolved, open, hit_rate, calibration: [{from, to, count, mean_predicted, observed_rate}]}
```

## R3 — AI assistant (language model)

**Evidence:** no LLM provider, key or endpoint in `backend/`.

**Web:** the assistant is a rule-based composer that answers only from the on-screen context, and it says so on every reply.

**Needed:**

1. A product decision on the provider and cost.
2. A server-side endpoint that keeps the credentials on the server, for example:

```
POST /api/v1/assistant/replies
  {messages: [{role, content}], context: {instrument_id, timeframe, last_price, opportunity?, risk_profile?}}
  → {reply, sources: [...], model}
```

The web interface `AssistantService` (`services/types.ts`) already has this shape. The browser never holds a provider key.

## R4 — Real market prices

**Evidence:**

- `seed_service.py` describes demo candles as "until real collectors run".
- `main` now has an XAU/USD live feed from the cTrader Open API (B1, `docs/ctrader-feed.md`). It ships **disabled** until the cTrader app is approved and an account is linked.
- There is no Twelve Data or Binance fetch code.
- Prices come only from `seed-demo-candles` / `simulate-live` (synthetic) or `POST /admin/instruments/{id}/candles` (an external push).

**Web:** backend prices are labelled "Backend feed", never "Live".

**Needed:**

1. A collector, external or a Celery task, that pushes real candles.
2. An instrument field stating whether a feed is real or seeded, so the UI can say "Live" honestly.

Choosing a market-data provider is a paid, external decision. The web work did not introduce one.

## R5 — Password reset

**Evidence:** `backend/app/api/v1/auth.py` and `users.py` contain no reset routes. SMTP settings exist for notifications only.

**Web:**

- In backend mode, "Forgot password?" on the sign-in page explains that self-service recovery is not available and that the administrator must reset the account. No fake reset form is shown.
- A signed-in user can change their password in Settings → Account (`POST /users/me/password`, connected).

**Needed:**

```
POST /api/v1/auth/password-reset/request  {email}            → 202 always (no account enumeration)
POST /api/v1/auth/password-reset/confirm  {token, new_password} → 204; revoke all refresh tokens
```

These need short-lived single-use tokens, per-IP and per-email rate limits, and SMTP configured (R8). When they exist, the web adds a `/forgot-password` page and a `/reset-password?token=` page.

## R6 — Platform membership and entitlements

**Evidence:** no plan, subscription or entitlement endpoints exist for the platform. `/subscriptions/*` covers expert subscriptions only.

**Web:** `/membership` shows "Pricing to be announced", and the in-app gate is a labelled demo preview, not access control.

**Needed:**

1. Commercial decisions: plans, prices and the feature matrix.
2. Backend plans, subscriptions and an entitlement check, for example `GET /api/v1/me/entitlements` → `{plan, features: {...}}`. Gating must be enforced on the server, not only in the UI.

## R7 — Real payments

**Evidence:** `docs/subscriptions.md` states that payments are demo only. The checkout page accepts test cards (`4242 4242 4242 4242`).

**Web:** every checkout entry point says "Demo payment — no real money is charged".

**Needed:**

1. A payment provider choice (business and legal).
2. Swapping the backend's demo provider for it. The web flow (`checkout` → hosted page → `return_url`) does not change.

## R8 — Notification delivery credentials

**Evidence:** `backend/app/core/config.py` has `telegram_bot_token`, `smtp_*` and `fcm_*` settings, all empty by default.

**Web:**

- Settings → Notifications shows each channel's server status from `GET /me/notifications/channels`.
- A channel that is not configured on the server is shown as "Not configured on this server" and cannot be selected.

**Needed:** a Telegram bot token, SMTP and FCM credentials in the target environment. These are secrets: they go into server environment variables, never into the repository.

## R9 — Additional instruments

**Evidence:** instruments are data (`POST /admin/instruments`), but only the seeded ones exist.

**Web:** the chart UI supports the instruments listed in `web/src/domain/instruments.ts`. The Strategies and Backtests pages list every instrument the backend returns, including ones the chart does not chart.

**Needed:** seed or add the instruments, plus a collector (R4).

## Smaller backend observations (not blockers)

- **Expert signal feed** (`GET /experts/{id}/signals`): the response items are not described in the OpenAPI schema. The web renders them generically as key/value rows. A typed schema would allow a proper layout.
- **Signal plans** (`GET /me/signal-plans`): `plan` is an untyped object in the schema, so the web shows it generically.
- **Workspace state:** the web chart has a single panel. The server's multi-panel state (`docs/workspace-state.schema.json`) is mapped for the first panel only, and further panels are preserved only when a server workspace is not overwritten from the web.
