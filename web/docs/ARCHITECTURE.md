# Architecture

## 1. Stack and why

| Choice | Reason |
| --- | --- |
| **React 19 + TypeScript 5.9 (strict)** | Component model suits a dense, stateful trading UI. Strict mode with `noUncheckedIndexedAccess` catches missing-data bugs that matter for financial values. |
| **Vite 7 (SPA)**, not Next.js | The backend is a separate Laravel API. Pages are behind login with no SEO need, and charts are client-only canvas. Server rendering would add complexity without benefit, and a static SPA deploys anywhere. |
| **React Router 7** (library mode) | Real URLs for every page and tab. Filters live in query strings, so views are shareable and Back works. |
| **Tailwind CSS 4** mapped to **semantic CSS tokens** | One source of truth for both themes (see DESIGN_SYSTEM.md). Utilities keep components small. |
| **TradingView Lightweight Charts 5** | Purpose-built financial canvas charts: candles, bars, line, area, panes, crosshair and price lines, plus a primitives API for custom overlays. Fast enough for live ticks. Apache-2.0. |
| **Zod 4** | Runtime validation at every boundary: forms, API responses, localStorage, env. |
| **React Hook Form** | Accessible forms with minimal re-renders. |
| **Vitest + Testing Library + Playwright + axe** | Unit/component tests in jsdom; real-browser flows, accessibility and visual QA in local Chrome. |

There is no global state library. React context covers the app-wide concerns (services, preferences, auth, toasts), and everything else is local state or URL state.

## 2. Folder structure

```
src/
├── main.tsx                 entry: fonts, CSS, providers, router
├── app/                     application wiring
│   ├── AppProviders.tsx     Preferences → Services+Auth → Toasts
│   ├── contexts.ts          context objects + use* hooks
│   ├── preferencesStore.ts  preferences schema, defaults, persistence key
│   ├── router.tsx           routes; secondary pages lazy-loaded
│   ├── RequireAuth.tsx      auth boundary (enforced in API mode)
│   └── ToastProvider.tsx
├── layouts/                 AppShell, Sidebar, TopBar, CommandPalette, AuthLayout, error pages
├── components/ui/           reusable, domain-agnostic UI (Button, Badge, Panel, Form, Dialog, Table…)
├── features/                one folder per product area
│   ├── workspace/           page, header, toolbar, watchlist
│   ├── chart/               PriceChart, legend, overlay primitive, data adapters, theme
│   ├── opportunity/         AI panel, probability meter, factor list
│   ├── signals/ alerts/ insights/ community/ settings/ auth/
│   └── */schemas.ts         form validation (pure, unit-tested)
├── domain/                  types + pure business rules (instruments, market, opportunity, predictions…)
├── lib/                     format (ONLY place numbers/times become text), indicators, storage, random
├── services/
│   ├── types.ts             service INTERFACES — the UI depends only on these
│   ├── schemas.ts           runtime contracts (zod) for all payloads
│   ├── errors.ts            ApiError + plain-language messages
│   ├── config.ts            env parsing
│   ├── api/                 HTTP client + backend implementation (proposed endpoints)
│   └── demo/                simulated implementation + scenario switch
├── fixtures/                simulated market, opportunities, predictions, sample community content
├── hooks/                   useResource, useLiveCandles/useLiveQuotes, environment hooks
├── styles/                  tokens.css (themes) + index.css (Tailwind mapping, base)
└── test/                    test setup + render helper
e2e/                         Playwright: flows, a11y, visual matrix
scripts/qa-shot.mjs          ad-hoc screenshot tool
```

## 3. Layers and data flow

```
 Page (features/*)  ──uses──▶  hooks (useResource, useLiveCandles)  ──call──▶  Services interface
       │                                                                        │
       ▼                                                                        ├── demo/*  → fixtures/*  (simulated, provenance: 'demo')
 components/ui + lib/format                                                     └── api/*   → http.ts → Laravel   (validated by zod)
```

1. **Domain** (`src/domain`): types and pure functions, such as EV in R, staleness, calibration statistics and the market calendar. There is no React here, and it is fully unit-tested.
2. **Services** (`src/services`): one interface per data area. `createServices(config)` returns either the demo or the API implementation. This is the **Strategy** pattern (interchangeable implementations) with **Adapter** behaviour (each adapts its source to the same domain types). Pages cannot tell the two apart. Swapping to the real backend is a configuration change plus aligning `endpoints.ts`.
3. **Hooks** (`src/hooks`):
   - `useResource(key, loader)` handles loading, success, error, refresh and stale-data-on-refresh-failure. It aborts superseded requests, so a late response for an old instrument can never overwrite the current one.
   - `useLiveCandles` merges stream updates by candle time. Out-of-order or older updates are ignored, and a same-time update replaces the forming bar.
4. **UI**: pages compose `components/ui` primitives. All number and time text goes through `lib/format.ts`.

### Live price updates (SF9)

- **Demo:** `DemoMarket` is an **Observer** subject. One timer, running only while there are subscribers, advances the simulation every second during FX market hours and notifies every chart and watchlist subscriber.
- **API:** `subscribeCandles` polls the latest candle every second as a fallback, because no streaming endpoint is confirmed yet (see API_INTEGRATION.md §4). Each subscription owns exactly one timer and one in-flight request, both cancelled on unsubscribe.
- **Freshness:** `effectiveFeedStatus` combines stream status, browser connectivity and the time since the last update into `live / demo / stale / closed / offline / error`. A feed is stale after 10 seconds without an update.

### Chart rendering

`PriceChart` creates the chart once. Separate effects then handle:

- theme palette
- the main series (rebuilt when the chart type changes)
- indicator series
- data sync
- the opportunity layer

Data sync uses `setData` only when the instrument, timeframe or length changes, and `series.update(lastBar)` for ticks (O(1) per tick).

The AI layer is drawn by `OpportunityOverlay`, a series primitive. It paints the entry/SL/TP zones, the forecast-region tint and the dashed **NOW** boundary *below* the candles, so price data is never hidden.

## 4. Key design decisions

| Decision | Rationale |
| --- | --- |
| Demo fixtures are a separate service implementation, not mock data inside components | Clean replacement later. No `if (demo)` branches in pages. Fixtures can never leak into API mode. |
| Every data object carries `provenance: 'demo' \| 'live'` | The UI labels simulated content from the data itself, not from a global flag a developer could forget. |
| Validate API responses with zod | Contract drift becomes a clear "unexpected format" error instead of `NaN` prices on screen. |
| Forecasts are a separate series, colour and region | A prediction can never be mistaken for an observed price (requirement §3). |
| URL holds Signals filters; localStorage holds preferences and workspaces | Shareable views. Preferences survive reloads. Storage reads are validated and fall back safely. |
| Native `<dialog>` for modals and the drawer | Built-in focus containment, Esc handling and an inert background. Less code, fewer accessibility bugs. |
| No role-based navigation yet | Role permissions come from the use-case diagrams, which the client does not have. Inventing them would be wrong (KNOWN_ISSUES.md). |
| Code-splitting | Workspace (first screen) is eager. Other pages are lazy. React and the chart engine are separate long-cached vendor chunks. |

## 5. Design patterns (as named in the project description)

- **Strategy:** `Services` implementations (demo vs API) chosen at start-up.
- **Observer:** the price feed (`DemoMarket.subscribe`, polling streams) notifying charts and watchlists.
- **Adapter:** service implementations adapt the backend or fixtures to domain types; `chartData.ts` adapts candles to chart series.
- **Repository-like services:** `MarketDataService.getCandles(symbol, timeframe)` matches the `MarketDataRepository.getCandles(pair, timeframe)` example in the project PDF.
- **MVVM-style separation:** hooks act as view-models (state, loading, derived values); components only render.
