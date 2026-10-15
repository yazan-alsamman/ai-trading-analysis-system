# Design system

The source of truth is `src/styles/tokens.css`, mapped to Tailwind utilities in `src/styles/index.css`. Components use **semantic** names only (`bg-surface`, `text-fg-2`, `text-up`) and never raw hex values. That is why the dark and light themes stay identical in structure.

## 1. Principles

1. **Data first.** Prices, charts and AI output carry the visual weight. The surrounding interface stays quiet: 1px borders, no gradients, no glow.
2. **Colour has meaning, never decoration.**
3. **Observed ≠ predicted.** AI output has its own colour, line style and labels.
4. **Never colour alone.** Every directional value also has a sign (`+` / `−`) and an arrow, and every status has a text label.
5. **Density with rhythm.** Dense where traders scan (tables, watchlist), with more room where they read (AI explanations, news).

## 2. Colour roles

| Token | Role | Rule |
| --- | --- | --- |
| `canvas`, `surface`, `raised`, `inset`, `hover`, `selected` | Surfaces from back to front | Elevation comes from tone + border; shadow (`shadow-float`) only on floating layers |
| `line`, `line-strong` | Dividers, control borders | |
| `fg`, `fg-2`, `fg-3` | Primary, secondary and muted text | `fg-3` is the minimum for any readable text |
| `accent` | Interaction: selection, primary button, focus, links | Not used for market direction |
| `up` / `down` | **Market direction and P/L only** (price change, Long/Short, TP/SL levels, realised R) | Always paired with a sign/arrow/label |
| `forecast` (violet) | **AI model output only**: probabilities, forecast path, "Opportunity detected" | Never used for observed prices |
| `danger` (orange), `warning` (amber), `info` (blue) | System feedback: errors, stale data, notices | Always with an icon + text. Errors are deliberately **not red**, so they are never confused with a falling price. |
| `demo` (amber) | Simulated content badges and the demo banner | |

**Contrast.** Every text/background pair was measured, including the soft badge backgrounds and the selected-row background, in both themes. All pairs are **≥ 4.5:1** (WCAG AA). The axe scan in `e2e/a11y.spec.ts` checks this on every route.

## 3. Typography

| Role | Font / size | Notes |
| --- | --- | --- |
| Page title | Inter 20/28, 600 | One `h1` per page |
| Panel title | Inter 13/20, 600 | `h2` inside `Panel` |
| Body | Inter 14/22 | |
| Labels, metadata | Inter 12/16 | **12px is the floor**: no smaller text anywhere, including SVG chart axes |
| Prices and numbers | JetBrains Mono, `.num` utility | `tabular-nums slashed-zero`, so values keep their width while ticking |
| Hero price | Mono 24/32, 500 | Neutral colour; the change beside it carries the direction |

Fonts are **self-hosted** (Fontsource), not loaded from a CDN. They work offline and behind restrictive networks (SF19).

## 4. Spacing, layout and shape

- **4px grid.** Layout spacing uses Tailwind steps 1–6, 8, 10, 12 (4–48px). The 2px half-steps (0.5, 1.5, 2.5, 3.5) appear only inside compact controls, for optical alignment (badges, segmented controls, icon offsets).
- **App shell:**
  - Sidebar: 224px (64px collapsed).
  - Top bar: 48px.
  - Demo banner: 28px.
- **Panels:** 16px padding, 44px header, 8px radius, 1px border.
- **Table rows:** 36px (comfortable) or 30px (compact), set by the Settings density preference through `--row-h`.
- **Radii:** 4px (inputs, badges), 6px (buttons), 8px (panels, dialogs).
- **Breakpoints:**

| Width | Workspace layout |
| --- | --- |
| ≥ 1440px | Three columns: watchlist, chart, AI panel |
| 1024–1439px | Chart plus a tabbed side panel (AI / watchlist) |
| < 1024px | Stacked; the page scrolls |
| < 1024px (navigation) | The sidebar becomes a drawer |

## 5. Financial formatting (`src/lib/format.ts`)

| Value | Rule | Example |
| --- | --- | --- |
| Price | Instrument precision (5, 3 for JPY, 2 for XAU), thousands separator | `1.08214`, `2,345.67` |
| Change | Always signed, true minus sign U+2212 | `+0.00087`, `−0.42%` |
| Probability | Whole percent, plus a band when the model provides one | `68%` · `61–74%` |
| Expected value | R multiples | `+0.36R` |
| Reward : risk | | `1 : 2.0` |
| Distance | Pips, using the instrument pip size | `12.4 pips away` |
| Missing | Em dash, never `0` or blank | `—` |
| Time | Stored in UTC; displayed in the chosen zone **with the zone label** | `14:30:05 UTC`, `GMT+3` |
| Volume | Labelled *tick volume* when the feed is tick volume | `Tick vol 2K` |

## 6. Components (`src/components/ui`)

| Component | Notes |
| --- | --- |
| `Button`, `IconButton` | `IconButton` **requires** a `label`, which becomes the accessible name and the visible tooltip |
| `Badge`, `DemoBadge` | `DemoBadge` marks simulated content everywhere |
| `Panel`, `PageHeader`, `Stat` | Labelled sections (`section[aria-labelledby]`) |
| `SegmentedControl` | WAI-ARIA radio group; arrow keys move the selection |
| `Field`, `Input`, `Select`, `Textarea`, `Checkbox`, `Switch`, `FormError` | Label, hint and error wired with `aria-describedby` and `aria-invalid` |
| `Dialog`, `ConfirmDialog` | Native `<dialog>`; focus returns to the opener; Cancel is the default focus for destructive confirmations |
| `Popover` | Disclosure pattern; Esc closes and returns focus |
| `TableRegion`, `Th`, `SortableTh`, `Td` | Horizontal scroll only inside a labelled, focusable region; `aria-sort` on sortable headers |
| `EmptyState`, `ErrorState`, `OfflineState`, `Loading`, `Skeleton` | Every async area uses these, so there are no blank areas and no infinite spinners |
| `ChangeText`, `DirectionBadge`, `FeedStatusPill` | Market semantics with non-colour cues and screen-reader wording |
| `RouteTabs` | Tabs are links: shareable and Back-button friendly |

## 7. Chart conventions

| Element | Treatment |
| --- | --- |
| Observed candles / bars | `up` / `down` colours |
| Line and area | Primary text colour |
| Indicators | Neutral series colours `--chart-ind-1/2/3`, never up/down; RSI in its own pane with 70/30 guides |
| Volume | Translucent up/down histogram in the bottom 18% of the price pane |
| AI zones | Translucent bands for TP (up), entry (accent) and SL (down), starting at the signal candle, drawn **under** price |
| Price lines | Dashed, with axis labels `TP`, `Entry`, `SL` |
| Forecast | **Violet dashed line with point markers**, right of a dashed **NOW** boundary, over a faint violet region tint |
| Legend | Shows *"AI forecast (simulated) — not an observed price"* when hovering the forecast |
| Time axis | Labels follow the chosen time zone; the crosshair label shows date and time |
| Controls | Zoom in, zoom out and reset are real buttons, so the chart is keyboard-operable |

## 8. States checklist (applied to every async area)

| State | Treatment |
| --- | --- |
| Loading | Skeleton plus a polite live-region announcement |
| Empty | Explanation and a next action |
| Populated | Normal view |
| Updating | Previous data stays visible; the refresh icon spins |
| Stale | Amber notice with the time of the data |
| Partial failure | Previous data kept, plus an inline error banner |
| Complete failure | `ErrorState` with a plain-language reason and **Try again** |
| Permission denied | `forbidden` maps to "Your account does not have access" |
| Offline | Global banner, plus `Offline` in the feed status |
| Invalid input | Field-level messages in plain language, validated on blur and on submit |

## 9. Motion

Transitions are 150ms colour and transform changes only. There are no pulsing or glowing prices. `prefers-reduced-motion` disables all transitions and animations globally.

## 10. Round 2 additions

| Item | Notes |
| --- | --- |
| Brand glyph (`components/brand/BrandMark.tsx`) | Three rising candles in accent + a dashed violet segment ending in a node: *observed vs forecast* is the identity. Use `BrandGlyph` alone at ≤ 32px. |
| Surfaces | Dark theme is midnight navy: canvas `#070b12`, surface `#0d131d`, raised `#131b28`, selected `#142036`. |
| `Page` | Every route uses it. `wide` (max 1600px) for data pages, `reading` (max 1024px) for forms and text. |
| Divided grids | Metric and summary grids use `gap-px` on a `bg-line` container — crisp 1px dividers at any column count, no nested cards. |
| `Sparkline`, `RangeBar` (`components/ui/MiniCharts.tsx`) | Sparklines are decorative (`aria-hidden`); the same information is present as text. The range bar is neutral grey (position is not direction). |
| `PriceLadder` | Always SL on the left, TP on the right (longs and shorts alike), entry zone in accent, current-price marker; amber when price is outside the plan. |
| `TimeframeConfluence` | Three buttons (15m / 1h / 4h) with direction + probability; pressing one switches the chart. |
| Notification centre | Bell with unread count; items carry provenance ("Simulated"). |
| Keyboard | `?` help · `Ctrl/⌘ K` search · `g` + `w/s/a/i/c/,` navigation · `t` theme · workspace `1/2/3`, `[` `]`, `z`, `f`. Disabled while typing or when a dialog is open; never bound to Ctrl/Alt combinations. |
| Demo banner | Dismissible per browser session; the top-bar "Demo data" indicator and every "Simulated" badge always remain. |
