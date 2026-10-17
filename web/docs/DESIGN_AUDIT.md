# Design & UX audit — premium transformation (round 2)

_Date: 15 October 2026 · Method: source review of every route and component, plus 100 "before" screenshots (10 routes × 5 widths × 2 themes, archived in `qa-screenshots/before/`)._

## 1. Baseline (before changes)

| Check | Result |
| --- | --- |
| `pnpm typecheck` | ✅ 0 errors |
| `pnpm lint` | ✅ 0 problems |
| `pnpm test` | ✅ 58 / 58 |
| `pnpm build` | ✅ |
| `pnpm e2e` (last run) | ✅ 39 / 39, with 0 serious axe violations and 0px overflow |

The foundation is sound: semantic tokens, measured contrast, all interface states handled, honest demo labelling. The weaknesses are about **product quality and information design**, not correctness.

## 2. Findings

Severity: **H** = hurts credibility or task efficiency · **M** = noticeable · **L** = polish.

### 2.1 Visual identity

| # | Sev | Finding | Evidence |
| --- | --- | --- | --- |
| V1 | H | **No recognisable identity.** The brand mark is a generic "trend arrow in a rounded square", and the wordmark is plain text. Nothing would make the product memorable to the committee. | `Sidebar.tsx` `BrandMark`; every screenshot |
| V2 | M | Dark surfaces are neutral grey-blue (`#11161d` / `#0b0f14`). There is little perceptible layering between canvas, surface and raised, so panels read as a flat field. | `tokens.css` |
| V3 | M | Every page uses the same "bordered rounded panel" unit. Signals, Alerts, Insights and Settings look structurally identical, so there is no hierarchy between primary data and secondary controls. | `Panel.tsx` usage |
| V4 | M | Uppercase micro-headings (`SIGNAL`, `LEVELS`, `RISK PROFILE`…) are repeated in the AI panel. They create noise rather than structure. | `OpportunityPanel.tsx` `Section` |
| V5 | L | Volume histogram is tall and saturated; it competes with price. | `PriceChart.tsx` scale margins 0.82 |

### 2.2 Application shell

| # | Sev | Finding |
| --- | --- | --- |
| S1 | H | **No notification centre.** Alerts can be created, but nothing in the shell reports that one fired. Price alerts never trigger, even against the simulated feed. |
| S2 | H | **Market state is only visible on the Workspace.** Other pages show no connection, session or freshness information. |
| S3 | M | No page title or breadcrumb in the top bar. The current location is shown only by the sidebar highlight, which is hidden on mobile. |
| S4 | M | The navigation is a flat list of 5 items, with no task grouping and no shortcut hints. Keyboard shortcuts are limited to ⌘K, and they are undiscoverable. |
| S5 | M | **Vertical budget.** Demo banner (28px) + top bar (48px) + page header (~90px) leave ~190px before content on every list page at 1440×900. |
| S6 | L | The sidebar footer area is empty. It is a natural place for global market-session status. |

### 2.3 Trading Workspace

| # | Sev | Finding |
| --- | --- | --- |
| W1 | H | **The AI panel is a long vertical document.** The decision-critical facts (direction, probability, R:R, where price sits relative to SL/entry/TP) are spread over 4 sections and require scrolling at 900px height. |
| W2 | H | **There is no multi-timeframe view.** The spec defines 15m (detection), 1h (confirmation) and 4h (regime). A trader cannot see whether the timeframes agree without switching three times. |
| W3 | M | **The watchlist is price-only.** It shows no intraday shape and no AI status per pair, so it does not help decide *which* pair to open. |
| W4 | M | **The instrument header wastes width.** It carries only price, change and 24h high/low, with large gaps. There is no visual of where price sits in its 24h range, and no session context. |
| W5 | M | The AI layer toggles use filled violet backgrounds when on. They are the loudest controls in the toolbar despite being secondary. |
| W6 | L | No keyboard shortcuts for timeframe or instrument switching, which experienced traders expect. |

### 2.4 Other routes

| # | Sev | Finding |
| --- | --- | --- |
| R1 | M | **Signals** has no summary (how many long/short, strongest setups). Repetitive "Trend following · Medium" text fills a wide column, and there is no inline detail. |
| R2 | M | **Insights**: the calibration chart sits in a large mostly-empty panel, and there is no view of performance over time. |
| R3 | M | **Community / News**: cards are tall with low information density, and there is no filter by instrument or impact. |
| R4 | M | **Sign in / Register**: a lone card on an empty canvas, with no product identity or value statement. It is the first screen a committee sees. |
| R5 | L | **Inconsistent page widths**: Settings `max-w-5xl`, News `max-w-4xl`, Posts `max-w-3xl`, Signals full width. |
| R6 | L | **Settings** is a single long column; sections are not navigable. |

## 3. Plan (this round)

| Step | Scope | Addresses |
| --- | --- | --- |
| 1 | **Identity & tokens**: midnight-navy layered surfaces, refined light theme, a new geometric brand mark + wordmark, quieter panel headings, and compact page headers | V1–V4, S5 |
| 2 | **Shell**: grouped navigation with shortcut hints; top-bar page title / breadcrumb; global market-status (session + UTC clock + feed); notification centre fed by **real price-alert evaluation** against the active feed; shortcuts dialog (`?`) and `g`-chord navigation; market sessions in the sidebar footer | S1–S6 |
| 3 | **Workspace**: ticker-strip header with a 24h range bar; watchlist with sparklines and per-pair AI status; AI panel rebuilt around a decision summary and a **price ladder** (SL / entry / now / TP to scale); **multi-timeframe confluence strip**; quieter AI toggles; keyboard shortcuts `1/2/3`, `[` `]`; slimmer volume | W1–W6, V5 |
| 4 | Remaining routes, in priority order: Signals summary, Auth identity, Insights performance curve, News filters, consistent page widths | R1–R6 |

Each change preserves the existing architecture: service interfaces, tokens, `format.ts`, and the state components.

## 4. Outcome of this round

| Finding | Status | Implementation |
| --- | --- | --- |
| V1 identity | ✅ | New brand glyph: rising candles + a dashed violet forecast node (`components/brand/BrandMark.tsx`), wordmark, favicon. New sign-in identity panel. |
| V2 surfaces | ✅ | Midnight-navy layered surfaces (`canvas #070b12` → `surface #0d131d` → `raised #131b28`). All text pairs re-measured ≥ 4.5:1. |
| V3 repetitive panels | ✅ partly | `Page` frame (wide/reading widths), summary bands (Signals), gap-px divided metric grids instead of nested cards |
| V4 uppercase headings | ✅ | Sentence-case section labels in the AI panel |
| V5 loud volume | ✅ | Bottom 14% of pane, 0.24 alpha |
| S1 notifications | ✅ | Notification centre + client-side alert monitor (demo) that really fires alerts on crossings |
| S2 market state | ✅ | Top-bar market status (session, UTC clock, demo indicator) + sidebar session board |
| S3 location | ✅ | Breadcrumb (group › page › sub-page) |
| S4 navigation | ✅ | Grouped navigation (Trade / Monitor / Connect), shortcut hints, `?` dialog, `g`-chords, `t` theme |
| S5 vertical budget | ✅ | Demo banner dismissible per session (top-bar "Demo data" + all "Simulated" badges remain) |
| W1 AI panel | ✅ | Verdict block, metric grid, **to-scale trade-plan ladder**, collapsible provenance |
| W2 multi-timeframe | ✅ | Timeframe alignment strip (15m detect · 1h confirm · 4h regime), also summarised in the header |
| W3 watchlist | ✅ | Sparklines (24 × 1h) + per-pair AI direction/probability |
| W4 header | ✅ | Ticker strip: price, change, 24h range bar, session, AI verdict + alignment, freshness |
| W5 loud toggles | ✅ | Selected-surface style with violet icon |
| W6 shortcuts | ✅ | `1/2/3`, `[` `]`, `Z`, `F` |
| R1 Signals | ✅ | Summary band (long/short counts, top probability, mean, all-timeframe-aligned pairs); compact row action |
| R2 Insights | ✅ | Cumulative-result performance chart |
| R3 News | ✅ | Impact + instrument filters, denser items |
| R4 Auth | ✅ | Two-column identity layout with an "observed vs forecast" illustration |
| R5 widths | ✅ | `Page` component everywhere |
| R6 Settings navigation | ⏳ | Not yet — candidate for the next round |

Before/after evidence: `qa-screenshots/before/` vs `qa-screenshots/matrix/` (regenerated by `pnpm e2e`).
