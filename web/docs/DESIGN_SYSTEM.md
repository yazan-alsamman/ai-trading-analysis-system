# Design system: "Ink, Aurum and Violet"

_Round 3 (16 October 2026). It replaces the round-2 navy/blue palette. The direction comes from `docs/GOAI_REFERENCE_ANALYSIS.md` §5._

The source of truth is `src/styles/tokens.css`. `src/styles/index.css` maps it to Tailwind utilities.

- Components use **semantic** names only (`bg-surface`, `text-fg-2`, `text-forecast`), never raw hex values.
- The dark and light themes are structurally identical: only the token values differ.

## 1. Principles

1. **A research terminal with an editorial front door.** Narrative surfaces (Overview, sign-in, module openers) use display type and atmosphere. Data surfaces (Workspace, tables, forms) stay dense and quiet.
2. **Colour has one meaning each.**
   - Gold is brand and selection.
   - Violet is the model.
   - Green and red are market direction.
   - Sky is simulated data.
   - Amber and orange are system feedback.
3. **Observed ≠ projected.** Model output has its own colour, line style, label and region, to the right of a **NOW** boundary.
4. **Provenance is always visible.** Every value can be traced to one of six sources (§8), shown with `SourceTag`.
5. **Never colour alone.** Direction has sign and arrow. Every status has an icon and a word.
6. **Density with rhythm.** Dense where traders scan; roomy where they read.

## 2. Colour tokens

### Dark (primary)

| Token | Value | Role |
| --- | --- | --- |
| `canvas` | `#07070a` | Page background (ink, faint violet cast) |
| `surface` / `raised` / `inset` | `#0d0d12` / `#13131a` / `#0a0a0e` | Panels; floating layers; wells (inputs, code) |
| `hover` / `selected` | `#17171f` / `#1c1b26` | Interaction states |
| `line` / `line-strong` | `#1e1d28` / `#2f2e3d` | Hairlines; control borders |
| `fg` / `fg-2` / `fg-3` | `#f2f1f6` / `#b0afbf` / `#8f8ea0` | Text, from one lavender-grey family |
| `primary` / `primary-fg` | `#f2f1f6` / `#0a0a0e` | **Inverted primary action** (one per view) |
| `accent` | `#e2bd72` (aurum) | Brand, active navigation, focus ring, selection, links, entry level |
| `forecast` | `#b9a0ff` (violet) | **Model output only** |
| `up` / `down` | `#2fc68f` / `#ff6f77` | **Market direction only**, always with sign or arrow |
| `demo` = `info` | `#6cbcff` (sky) | Simulated-data labels (dashed outline) and notices |
| `warning` / `danger` | `#f2a541` / `#ff8a4c` | Stale/caution; errors and limit breaches (never red, so never mistaken for a falling price) |

### Light ("paper")

| Token | Value |
| --- | --- |
| `canvas` / `surface` / `inset` | `#f4f3ef` / `#ffffff` / `#f8f7f4` |
| `selected` | `#f2ede1` (warm gold tint) |
| `fg` / `fg-2` / `fg-3` | `#141318` / `#4a4853` / `#5e5c67` |
| `primary` | `#141318` (ink button, white text) |
| `accent` | `#7c540d` (deep gold) |
| `forecast` / `up` / `down` | `#6534c8` / `#066b47` / `#b3262f` |
| `demo` = `info` | `#0b5a96` |
| `warning` / `danger` | `#7f4700` / `#a33c0b` |

### Measured contrast

The pairs were computed with the WCAG formula by `scripts/contrast.mjs`. Every text tone was checked on every surface. Minimum values:

| Pair | Dark | Light |
| --- | --- | --- |
| `fg-3` (weakest body text) on `selected` | 5.30 | 5.61 |
| `accent` text on `selected` | 9.53 | 5.13 |
| Tone text on its own soft badge background | ≥ 5.17 | ≥ 4.76 |
| Primary button label | 17.9 | 16.7 |

All pairs that the interface actually renders are ≥ 4.5:1 (WCAG AA). The script also tests every text tone on every tone's soft background. One cell is below the threshold: `fg-3` on an `fg-3`-tinted badge over `selected`, 4.40 in dark. No component uses that combination, because there is no `fg-3` badge tone. axe (`e2e/a11y.spec.ts`) re-checks every route in both themes.

**Why sky for demo?** The round-2 amber `demo` collided with amber `warning` and, now, with the gold accent. Sky is unique in the palette, and demo badges also use a **dashed** outline plus a flask icon, so they are recognisable without colour.

## 3. Typography

| Role | Face / size | Where |
| --- | --- | --- |
| Display | **Instrument Serif** 400, `text-d1` 64/64 · `text-d2` 44/46 · `text-d3` 32/36, `.display` | Overview hero, section openers, sign-in. **Never** inside dense panels. The muted second clause uses `<em>` (italic, `fg-2`). |
| Eyebrow | JetBrains Mono 12/16, 500, uppercase, tracking 0.16em, `.eyebrow` | Before sections and page titles: `04 · RISK MANAGEMENT` |
| Page title | Inter 24/32, 600 | One `h1` per page (`PageHeader`) |
| Panel title | Inter 13–16, 600 | |
| Body | Inter 14/22 | |
| Labels, metadata | Inter 12/16 | **12px is the floor** everywhere, including SVG axes and eyebrows |
| Numbers | JetBrains Mono, `.num` (tabular, slashed zero) | Every price, money value, percentage and time |

All fonts are self-hosted through Fontsource; no CDN is involved. Instrument Serif is OFL-1.1 and is listed in `THIRD_PARTY_NOTICES.md`.

## 4. Space, layout, shape, elevation

| Item | Value |
| --- | --- |
| Grid | 4px steps; 2px half-steps only inside compact controls |
| Shell | Sidebar 232px (64px collapsed) · top bar 52px · `--row-h` 36/30px (density) |
| Content widths | `--content-wide` 1600px (data pages) · `--content-reading` 1024px (forms, text) · Overview and Assistant 1400px |
| Radii | 4 (badges, inputs) · 6 (buttons) · 8 (dense panels) · **12–16 (narrative cards)** · **full (pills: primary CTAs, auth switch, view tabs)** |
| Elevation | Tone + hairline. `shadow-float` only on floating layers (dialogs, sheets, popovers, hero research card) |
| Atmosphere | `.atmosphere` = 48px grid + two radial glows (aurum, violet). **Overview hero and the auth panel only.** |

### Breakpoints

| Width | Behaviour |
| --- | --- |
| < 640px | Single column; Signals render as **cards**; full-width side sheets |
| 640–1023px | Stacked workspace; navigation drawer |
| 1024–1439px | Chart + tabbed side panel; sidebar visible |
| ≥ 1440px | Three-column workspace (watchlist · chart · AI panel) |

## 5. Motion

| Token | Value | Use |
| --- | --- | --- |
| `--dur-fast` | 150ms | Hover, colour, focus offset |
| `--dur-base` | 220ms | Side sheet slide-in |
| `--dur-slow` | 420ms | `.reveal` entrance (opacity + 6px rise), staggered with `.reveal-1…4` |
| `--ease-out` | `cubic-bezier(.22,1,.36,1)` | All of the above |

Rules:

- No motion on prices, tables or charts.
- No pulsing or glowing values. The only loop is the assistant's three-dot "composing" indicator.
- `prefers-reduced-motion` disables every animation and transition (`index.css`).

## 6. Chart series

| Element | Treatment |
| --- | --- |
| Observed candles / bars | `up` / `down` |
| Line / area, Overview research chart | `fg` line with an `fg` → transparent area |
| Indicators | `--chart-ind-1/2/3` (sky, copper, grey), never up/down |
| Model zones | Translucent TP (`up`), **entry (`accent` gold)**, SL (`down`), under price |
| Projection | **Violet dashed line + point markers**, only for points the model supplied, right of a dashed **NOW** line over a faint violet region |
| Confidence band | Drawn **only** when supplied; never synthesised |

## 7. Components (`src/components/ui`)

| Component | Notes |
| --- | --- |
| `Button` | Variants: `primary` (inverted), `secondary`, `ghost`, `danger`. Sizes `sm`/`md`/`lg`. `shape="pill"` for narrative CTAs. Supports `trailingIcon`. `buttonClasses()` styles links identically. |
| `IconButton` | `label` is required (accessible name + tooltip) |
| `Badge`, `DemoBadge` | Demo tone has a dashed outline |
| **`SourceTag`** (new) | `live` · `historical` · `model` · `user` · `demo` · `unavailable`, each with an icon, word and tooltip definition |
| `Panel`, `Page`, `PageHeader` (+ `eyebrow`), **`SectionHeading`** (new) | `SectionHeading` = eyebrow + display title + muted clause |
| `Field`, `Input`, `Select`, `Checkbox`, `Switch` | `Input` height and width are defaults the caller may override |
| `Dialog` (sm/md/**lg**), **`SideSheet`** (new) | Native `<dialog>`; focus containment; Esc; focus returns to the opener |
| **`Markdown`** (new) | Safe renderer for assistant replies: React elements only, never `innerHTML` |
| `TableRegion`, `SortableTh` | Unchanged |
| `EmptyState`, `ErrorState`, `Loading`, `Skeleton` | Unchanged; used by every new module |
| `ChangeText`, `DirectionBadge`, `FeedStatusPill` | Unchanged |
| Feature-level: `LimitMeter` | Used vs this trade (hatched) vs limit marker; status in words + icon |
| Feature-level: `ResearchChart`, `PasswordInput`, `PasswordStrength` | |

## 8. Provenance vocabulary

| Kind | Label | Meaning |
| --- | --- | --- |
| `live` | Live | Verified data from the connected backend feed |
| `historical` | Historical | Recorded past data |
| `model` | Model output | Produced by the AI model: a probabilistic estimate |
| `user` | Your input | Entered by the user; not verified |
| `demo` | Simulated | Generated in the browser |
| `unavailable` | Not connected | Needs a backend service that does not exist yet |

## 9. States checklist

Every async area handles these states:

- loading (skeleton + polite announcement)
- empty (explanation + next action)
- updating (previous data kept)
- stale (amber notice)
- partial failure (inline banner)
- failure (`ErrorState` + Try again)
- offline
- invalid input (field messages)
- demo (labelled)

New in round 3:

| Area | State |
| --- | --- |
| Risk | **Incomplete**: lists every missing input and calculates nothing. **Invalid**: e.g. a target on the wrong side of the entry. |
| Signals | "Nothing fits your profile" is treated as a valid answer, not an error |
| Assistant | Composing (with Stop) · error (with Retry) · context partly unavailable (with Retry) |

## 10. Keyboard

| Shortcut | Action |
| --- | --- |
| `?` | Help |
| `Ctrl/⌘ K` | Search |
| `g o` | Overview |
| `g w` | Workspace |
| `g s` | Signals |
| `g p` | Assistant |
| `g r` | Capital & risk |
| `g a` | Alerts |
| `g i` | Insights |
| `g c` | Community |
| `g ,` | Settings |
| `t` | Theme |
| Workspace: `1/2/3`, `[` `]`, `z`, `f` | Timeframe, previous/next instrument, zones, forecast |
| Assistant: `Enter` / `Shift+Enter` | Send / new line |

## 11. Round 4: motion system and public website

The full specification is in `docs/MOTION_DESIGN_DIRECTION.md`. **This section supersedes §5.**

### Motion tokens

Defined in `src/motion/tokens.ts`, mirrored as CSS custom properties in `src/styles/motion.css`.

| Token | Value |
| --- | --- |
| Durations | `instant` 120 · `fast` 180 · `base` 260 · `slow` 600 · `cinematic` 1100 ms |
| Easing | `out` `(.22,1,.36,1)` · `in` `(.55,0,1,.45)` · `inOut` `(.65,0,.35,1)` · `spring` `(.34,1.4,.64,1)`, plan selection only |
| Stagger | lines 110 · items 70 · candles 12 ms |
| Rise | 18 px (10 px under 768 px) |
| Parallax | ±14 px maximum |

### Runtime

`src/motion/runtime.ts` provides:

- **one** shared scroll/resize frame loop, used only while sections intersect
- `useInView`
- `useScrollProgress` / `useStepProgress`, which write `--p` with no per-frame re-render
- `usePointerParallax` (fine pointers only)
- `useReducedMotion`
- `useCinematic` (≥ 1024 px wide and ≥ 600 px tall, motion allowed)

### Primitives

| Primitive | Purpose |
| --- | --- |
| `<Reveal variant>` | In-view entrance |
| `<RevealText lines>` | Line-mask headline (`trigger="mount"` for the hero) |
| `.m-in`, `.m-in-blur`, `.m-stage`, `.m-draw`, `.m-grow-x/-y`, `.m-pop` | Keyframes with an `--at` delay |
| `[data-play="false"]` | Holds an animation until its container is in view |
| `[data-layer][data-on]` | Step-driven layers in pinned sequences |
| `.accordion-panel[data-open]` | Grid-rows accordion |
| `.parallax` with `--depth` | Pointer parallax layer |

Page transitions use the View Transitions API through React Router `viewTransition`: root cross-fade plus a shared `brand` and `auth-card`.

### Reduced motion

- Animation **and transition delays are zeroed**.
- Reveals, layers, masks and parallax are forced to their final state.
- Pinned sequences render as static layouts.
- View transitions are disabled.

### New components

| Component | Purpose |
| --- | --- |
| `marketing/components/ShowcaseChart` | Intro or step mode; the projection appears only from supplied points |
| `ModulePreviews` | Renders the app's own components with showcase data |
| `PlanCard` / `PlanGrid` / `CompareTable` / `PlanFit` / `PlanConfirmSheet` | Membership |
| `JourneySteps` / `PlanSummary` | Sign-up journey |
| `features/membership/PlanGate` | Demo upgrade information |
| `.range` | Slider with a gold fill and a visible focus ring |

### Rules kept

- Prices and figures never animate as if live.
- Observed data draws as a solid line up to **NOW**. The projection is violet, dashed, after NOW, and only drawn when the model supplied it.
- Simulated content always carries `SourceTag kind="demo"`.
