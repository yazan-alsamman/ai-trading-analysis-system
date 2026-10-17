# Testing and QA

## Strategy

| Layer | Tool | What it proves |
| --- | --- | --- |
| Pure logic | Vitest | Formatting, indicators, market calendar, EV/staleness maths, prediction statistics and calibration binning, validation schemas, fixture invariants, HTTP error mapping, feed-status rules |
| Components | Vitest + Testing Library (jsdom) | The AI panel shows probability, band, levels, provenance and the disclaimer; the not-detected, stale and error states; the alert create → validate → delete flow; shell navigation and demo labelling; no execution controls exist |
| Real browser | Playwright + local Google Chrome | Workspace interactions (watchlist, timeframe, chart type, indicators, persistence), ⌘K search, Signals URL filters, demo failure scenario, theme persistence, login validation, 404 |
| Accessibility | `@axe-core/playwright` (WCAG 2.0/2.1 A + AA, incl. colour contrast) + keyboard test | Every route in both themes. Skip link, visible focus, dialog Esc and focus return. |
| Visual / responsive | Playwright matrix | 10 routes × 5 widths (1440, 1280, 1024, 768, 390) × 2 themes. Asserts **no horizontal page overflow** and **no runtime/console errors**. Saves 100 screenshots to `qa-screenshots/matrix/` for review. |

Run them:

```bash
pnpm check   # typecheck + lint + unit/component tests + build
pnpm e2e     # builds, serves on :4173, runs all browser suites in Chrome
```

## Results — round 4 (16 October 2026)

| Check | Result |
| --- | --- |
| Type check / lint | ✅ 0 / 0 |
| Vitest | ✅ **128 / 128** (adds membership config and store, marketing components, journey, gate, FAQ, motion listener cleanup) |
| Build | ✅ |
| Playwright | ✅ **64 / 64**: round-4 flows (landing, scroll sequences, reduced motion, mobile menu, membership journey, SEO), axe on 15 routes × 2 themes, visual matrix 15 routes × 5 widths × 2 themes |

`settle()` now waits for finite animations to end, so axe scans final states.

## Results — round 2 (15 October 2026)

| Check | Result |
| --- | --- |
| Type check / lint | ✅ 0 errors / 0 problems |
| Vitest | ✅ **67 / 67** (adds alert-crossing, sessions, timeframe alignment, notification store) |
| Build | ✅ app 71 KB, React 100 KB, charts 57 KB, CSS 12 KB (gzip) |
| Playwright | ✅ **41 / 41**: 10 flows (adds keyboard shortcuts, alignment strip and notification centre), 20 axe scans with 0 serious/critical violations, keyboard test, 10 visual-matrix runs (0px overflow, 0 console errors) |

Axe caught one regression during the round (`definition-list`: `dt`/`dd` nested two `div`s deep in the new metric grid). It was fixed by flattening the grid.

## Results — round 1 (15 October 2026)

| Check | Result |
| --- | --- |
| `tsc -b` (strict, `noUncheckedIndexedAccess`) | ✅ 0 errors |
| ESLint (typescript-eslint strict, react-hooks) | ✅ 0 errors, 0 warnings |
| Vitest | ✅ **58 / 58 passed**, 7 files |
| Production build | ✅ succeeded. Gzip: app 64 KB, React 100 KB, charts 57 KB, CSS 11 KB. |
| Playwright total | ✅ **39 / 39 passed** |
| — functional flows | ✅ 8 / 8 |
| — axe scans | ✅ 20 / 20, **0 serious or critical violations** (10 routes × dark/light) |
| — keyboard test | ✅ 1 / 1 |
| — visual matrix | ✅ 10 / 10, 0px horizontal overflow, 0 console errors across 100 page renders |

### Defects found by QA and fixed in this delivery

| Found by | Defect | Fix |
| --- | --- | --- |
| Visual review | Header 24h change (−0.42%) differed from the watchlist (−0.46%) for the same pair | Header and watchlist now use the same quote source (`dayStats`) |
| Visual review | Zone labels collided with price-line labels; NOW label hidden by controls | Zone names moved to the axis price-line titles; NOW drawn at the bottom of the pane |
| Visual review | Mobile top bar overflowed: a responsive `hidden` class lost to the component's own `inline-flex` | Responsive visibility moved to wrapper elements |
| Visual review | Form controls ignored explicit widths; chat box 96px tall (class conflicts) | `unless()` helper applies defaults only when the caller has not set them |
| Visual review | Calibration gap shown in red (not a market movement) | Neutral signed text |
| Visual review | 1280px: chart squeezed to ~450px by three columns | Three-column layout from 1440px; tabbed side panel below |
| axe | Contrast 3.7–4.5:1 for badges and up/down text on the selected-row background | `--bg-selected`, `--fg-muted`, up/down/accent/forecast and system tones retuned. All pairs ≥ 4.5:1 (measured). |
| axe | `nested-interactive`: chart container `role="img"` contained the attribution link | Labelled `group` + `aria-describedby` text summary |
| axe | AI panel scroll area not keyboard-focusable | Focusable `region` with a label |
| Keyboard test | Skip link was not the first Tab stop (main received focus on load) | `<main>` receives focus only after client-side navigation |
| Visual matrix | 390px Insights page overflowed by 195px: visually hidden text in wide tables escaped its scroll container | Scroll regions and `<main>` are `position: relative` |
| Unit tests | Calibration bins risked floating-point gaps (0.1 + 0.2) | Integer bin arithmetic, with a test |

## Manual verification guide (for the defence)

1. Run `pnpm dev`, open http://localhost:5173.
2. Point out the **demo banner** and the **Simulated** badges on the chart legend, price header and AI panel.
3. In the Workspace:
   - Pick USD/JPY in the watchlist.
   - Switch 15m → 4h, then Candles → Line.
   - Open *Indicators* and add RSI 14 (new pane).
   - Hover the chart to show the legend.
   - Hover right of **NOW** to show the label "AI forecast (simulated) — not an observed price".
4. Toggle **Zones** and **Forecast** off and on.
5. Press **Ctrl K**, type "gold", then Enter.
6. Open **Settings → Demo controls**:
   - Choose *Request failures*, then open Signals: error state with **Try again**.
   - Choose *Feed interrupted*, then wait 10 s on the Workspace: feed status becomes **Stale**.
   - Choose *Empty data*: empty states.
7. Switch the theme in the top bar. The chart re-themes without a reload.
8. Resize the browser to phone width: the sidebar becomes a drawer, the workspace stacks, and the page never scrolls sideways.
9. Keyboard only:
   - Tab: skip link, then navigation.
   - Alerts: *New price alert*, then Esc returns focus to the button.
