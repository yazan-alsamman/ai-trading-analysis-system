# Implementation plan

## Scope

**In scope (website surface):**

| Area | Software Features (SF) |
| --- | --- |
| Notifications and channels | SF2, SF7, SF16 |
| Chart | SF3, SF4, SF5, SF8, SF9 |
| Themes | SF10 |
| Community | SF11, SF12, SF13 |
| Prediction statistics | SF14, SF15 |
| Security boundary | SF17 (client side) |
| Workspaces | SF18 |
| Offline / degraded handling | SF19 |
| AI output shown | AI Feature 12 |

**Cancelled. Not implemented and not in the backlog:**

- AI 13: automated trade closing
- AI 18: AI-driven custom experience
- AI 19: automated trading
- SF1: subscribe to trades on demand
- SF6: custom indicator code

Normal preferences (theme, density, workspaces) and choosing from the fixed indicator list remain in scope.

## Phases

| # | Phase | Deliverables | Acceptance criteria | Status |
| --- | --- | --- | --- | --- |
| 1 | Foundation | Vite + React + TS strict, Tailwind, tokens (dark/light), app shell, UI components, formatting library | Builds; both themes switch at runtime; shell keyboard-navigable | ✅ Done |
| 2 | Trading Workspace | Chart (4 types, 3 timeframes, 5 indicators, crosshair legend, zoom), watchlist, AI opportunity panel, zones, forecast, freshness | Usable with no backend; every simulated value labelled; forecast visually distinct; all states handled | ✅ Done |
| 3 | Core features | Signals, Alerts (CRUD + opportunity prefs), Insights, Community (news/comments, posts, experts), Settings, Auth screens | Every visible control works or is clearly marked unavailable; forms validated | ✅ Done |
| 4 | Integration readiness | Service interfaces, HTTP client, zod contracts, proposed endpoints, env config, auth boundary | Switching `VITE_DATA_SOURCE=api` needs no UI changes; contracts documented | ✅ Done (backend not available to test against) |
| 5 | Responsive & accessibility QA | 5 widths × 2 themes, axe on all routes, keyboard checks | 0 horizontal overflow; 0 serious/critical axe violations | ✅ Done |
| 6 | Final verification | typecheck, lint, unit, e2e, build | All green | ✅ Done |
| 7 | Backend integration | Align endpoints, run against Laravel, streaming prices, auth | Real data end-to-end; demo labels disappear automatically (`provenance: live`) | ⏳ Blocked on backend |
| 8 | Trader testing & polish | Feedback from professional and intermediate traders (work plan, Oct–Nov 2026) | Feedback items triaged and fixed | ⏳ Next |
| 9 | Publish | GitHub remote, CI running `pnpm check` + `pnpm e2e`, deployment | Reproducible build from a clean clone | ⏳ When instructed |

## Feature → implementation map

| Requirement | Where |
| --- | --- |
| SF2 opportunity notifications | `features/alerts/OpportunityNotifications.tsx` |
| SF3 chart display types | `features/workspace/ChartToolbar.tsx`, `features/chart/PriceChart.tsx` |
| SF4 timeframes | same as SF3 |
| SF5 indicators (fixed list) | `domain/indicators.ts`, `lib/indicators.ts` |
| SF7 channels | `features/settings/SettingsPage.tsx` (`ChannelsSection`) |
| SF8 AI on chart | `features/chart/OpportunityOverlay.ts` + forecast series |
| SF9 live updates | `hooks/useMarketData.ts`, `services/demo/demoMarket.ts`, `services/api/index.ts` (`pollingStream`) |
| SF10 themes | `styles/tokens.css`, `app/AppProviders.tsx` |
| SF11 / SF12 / SF13 | `features/community/*` |
| SF14 / SF15 | `features/insights/*`, `domain/predictions.ts` |
| SF16 price alerts | `features/alerts/*` |
| SF17 auth boundary | `app/RequireAuth.tsx`, `services/api/http.ts` |
| SF18 workspaces | `features/settings/WorkspacesSection.tsx`, top-bar switcher |
| SF19 offline / low bandwidth | offline banner, `offline` feed state, self-hosted fonts, cached last data |
| AI Feature 12 | `features/opportunity/*`, `features/signals/SignalsPage.tsx` |
