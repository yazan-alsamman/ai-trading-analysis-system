# Membership — frontend specification

_Round 4 · 16 October 2026._

**Scope: frontend only.**

- No billing, no subscription service and no server-side enforcement exist.
- Everything described here is presentation plus a clearly labelled **demo** state.
- **Frontend gating is not security.**

## 1. Files

| File | Role |
| --- | --- |
| `src/domain/membership.ts` | **Single source of truth.** Plans, features, feature status, access matrix, `suggestPlan`, helpers |
| `src/app/membershipStore.ts` | Frontend state: `selected` (sessionStorage) and `demo` (localStorage), both zod-validated |
| `src/marketing/membership/PlanComponents.tsx` | `PlanCard`, `PlanGrid` (radiogroup), `CompareTable` (table ≥ md; per-plan list on phones), `StatusLegend`, `PlanFit` |
| `src/marketing/membership/PlanConfirmSheet.tsx` | Confirmation sheet: what happens next and the honest activation notice |
| `src/marketing/membership/Journey.tsx`, `useJourneyPlan.ts` | Sign-up progress and plan summary; reads `?plan=` |
| `src/marketing/pages/MembershipPage.tsx` | `/membership` |
| `src/marketing/pages/WelcomePage.tsx` | `/welcome`: review the plan and enter the app |
| `src/features/membership/*` | In-app demo: `PlanGate`, `DemoPlanChip`, `useFeatureAccess`, Settings → Membership |
| `src/domain/membership.test.ts`, `src/marketing/marketing.test.tsx`, `e2e/round4.spec.ts` | Tests |

## 2. Package schema

```ts
type PlanId = 'essential' | 'professional' | 'elite';
type FeatureStatus = 'available' | 'demo' | 'backend' | 'planned';   // what the feature runs on TODAY
type Access = boolean | string;                                       // false = not included; string = included with this scope
type Price = { kind: 'tba' } | { kind: 'amount'; amount: number; currency: string; period: 'month' | 'year' };

interface Plan {
  id: PlanId; name: string; tagline: string; audience: string;
  highlights: string[];
  access: Record<FeatureId, Access>;   // every feature must be defined (tested)
  price: Price;                        // all 'tba' today (tested)
  cta: string;
  activation: 'unavailable';           // until billing exists (tested)
}
```

**Changing the commercial offer** means editing `PLANS` only:

- Set `price: { kind: 'amount', … }` when real prices are approved. `formatPrice()` renders it.
- Edit `access` to change what each plan includes. Tests enforce that every feature is defined and that tiers are cumulative.
- Billing-period wording, trials and refunds are **not** modelled. Add fields when the owner defines them; do not hard-code them in components.

## 3. Feature mapping

The access matrix is proposed and awaits a product-owner decision.

| Feature | Status today | Essential | Professional | Elite |
| --- | --- | --- | --- | --- |
| Market workspace | Demo data | ✓ | ✓ | ✓ |
| Instruments | Demo data | Gold (XAU/USD) | Gold + 7 FX majors | Gold + 7 FX majors |
| Chart timeframes | Demo data | 15m · 1h · 4h | same | same |
| AI analysis | Demo data | ✓ | ✓ | ✓ |
| Research explanations | Demo data | ✓ | ✓ | ✓ |
| Multi-timeframe alignment | Demo data | — | ✓ | ✓ |
| Personalised signal filters | Demo data | — | ✓ | ✓ |
| Watchlist | Demo data | Gold | Gold + 7 FX majors | Gold + 7 FX majors |
| Capital & risk tools | **Works now** | ✓ | ✓ | ✓ |
| Model analytics | Demo data | ✓ | ✓ | ✓ |
| Price alerts | Demo data | ✓ | ✓ | ✓ |
| Email & Telegram delivery | Needs backend | — | ✓ | ✓ |
| AI assistant | Demo data (rule-based) | — | — | ✓ |
| Research history | Planned | — | — | ✓ |
| Saved workspaces | Works now (browser) | One workspace | Multiple | Multiple |

### Differentiation principles

These replace arbitrary limits:

1. Risk tools and model analytics are in every plan (transparency is not a premium feature).
2. Essential is gold-first, matching the platform's initial focus.
3. Professional adds breadth and personalisation.
4. Elite adds the assistant and history.

There are no numeric caps (alert counts, signals per month), because none have been decided. **No "most popular" badge** is shown: there is no data to support one. The only recommendation comes from `PlanFit` and is derived from the visitor's own answers.

## 4. Routing and selection flow

```
/ (landing, sequence E) ─┐
/membership ─────────────┼─ select plan ─▶ membershipStore.select(id) ─▶ PlanConfirmSheet
                         │                                                 │
                         │       /register?plan=id  ◀── "Create account" ──┤
                         │       /login?plan=id     ◀── "I have an account"┘
                         ▼
   /register?plan=id: progress (Plan ✓ · Account · Review) + PlanSummary + "Change plan"
        │ demo session (demo mode) / FastAPI register+login (API mode)
        ▼
   /welcome?plan=id: review included / not-included + feature status
        ├─ demo mode: "Preview <plan> as a demo" → membershipStore.activateDemo(id) → /overview
        └─ "Enter the platform" → /overview (no plan state written)
```

### Rules

- `?plan=` is validated with `isPlanId`; invalid values are ignored.
- URL and session are display state only, never access.
- Selection survives navigation through sign-up (sessionStorage) and the Sign in ↔ Create account switch, which forwards `?plan=`.
- Back, direct URLs and refresh all work: every step is a real route.
- **No checkout, no payment form and no "payment successful" screen exist.**
- In API mode, `/welcome` requires a session; activation is described as unavailable, and nothing is written.

## 5. In-app demo membership

`membershipStore.demo = { plan, activatedAt, demo: true }`

| State | Behaviour |
| --- | --- |
| No demo plan (default) | Every module is open. The demo shows the whole product, and the existing tests are unaffected. |
| Essential | Signals "For you" → `PlanGate(signal_filters)`. Assistant page and workspace sheet → `PlanGate(assistant)`. Workspace shows a notice on non-gold instruments with a "Switch to XAU/USD" action. |
| Professional | Assistant → `PlanGate(assistant)` |
| Elite | Everything open |

Visibility:

- The sidebar shows "Demo plan · \<name\>" (dashed demo styling), linking to Settings → Membership.
- Settings → Membership: switch the preview plan or exit the preview.

`PlanGate` explains:

- which plan includes the feature
- that this is a preview, not access control
- the available actions: preview the needed plan, compare plans, exit the preview

## 6. Future backend contracts

These are proposals; **none are implemented**. The current backend (`backend/app/api/v1`) has **no** membership or billing endpoints.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/plans` | Commercial plan catalogue `{ id, name, price, period, features }` (replaces the static `PLANS` prices) |
| GET | `/me/subscription` | `{ plan_id, status: none\|trialing\|active\|past_due\|canceled, current_period_end }` |
| POST | `/me/subscription/checkout` | Start a payment-provider checkout. Returns a redirect URL; the frontend never handles card data. |
| POST | `/payments/webhook` | Provider → backend only |
| GET | `/me/entitlements` | `{ features: FeatureId[] }`. **Server-enforced**; the UI uses it in place of the demo state. |

Every module API must check entitlements server-side; hiding a button is not authorisation.

## 7. Current limitations

- Prices, billing terms, trials, refunds and support levels are undefined (commercial decisions).
- The demo membership is per browser and is not tied to an account.
- Gating covers the assistant, personalised signals and the gold-only workspace scope. Other differences (alert delivery, research history) are already unavailable for everyone, because they need the backend or are planned.
