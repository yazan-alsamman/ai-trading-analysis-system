# Motion design direction

_Round 4 · 16 October 2026 · Implemented in `src/motion/`, `src/styles/motion.css` and `src/marketing/`._

## 1. Reference interactions actually inspected (goai.global, real Chrome)

Captured with `scratchpad/goai/motion.cjs`:

- timed hero frames at 0.4 / 0.9 / 1.6 / 2.6 / 4 / 7 s
- `document.getAnimations()` sampling
- scroll sampling every 260 px over the 7,665 px page
- hover transitions
- the nav dropdown animation
- `prefers-reduced-motion: reduce`
- a 390 px touch device

| Observation | Measured | What we learn |
| --- | --- | --- |
| Motion libraries | **None.** No GSAP, ScrollTrigger, Lenis, Locomotive, AOS or Framer. Hand-written CSS keyframes (≈50) plus Web Animations for menus. | A premium feel does not need a heavy library |
| Hero timeline | **Blank screen until ≈ 2.6 s**, then nav (≈ 4 s), eyebrow, then headline + copy fading up with blur, then the age timeline. Fully staged at ≈ 7 s. | Staging is strong; first paint is far too late. We stage in < 1 s and finish in ≈ 3.4 s. |
| Reveal style | Opacity 0 → 1, `translateY(16px)` → 0, `blur(8px)` → 0, triggered on entering the viewport | We use opacity + rise + a light blur on narrative text only |
| Ambient motion | 27 infinite loops at rest: aurora drifts 28–40 s, gradient drift 40 s, marquees 38 s, pulses 1.6–3.2 s, a full-screen fixed particle canvas, 4 videos (one autoplaying) | Atmosphere comes from many slow layers. We keep **one** slow layer and pause it off-screen. |
| Scroll-linked motion | A background video scales 1.03 → 1.01 with scroll. **No pinned scroll-storytelling.** `scroll-behavior: smooth` on `html`. | Our pinned sequences are a step beyond the reference |
| Menu | Dropdown: opacity, 450 ms, `cubic-bezier(.16,1,.3,1)` | Matches our `ease-out` family |
| Hover | Links: colour 200 ms. CTAs: `transform` + `box-shadow` 200 ms. | Same register as our interface tokens |
| Pricing | Third card highlighted with a bright hairline border + glow; "Compare all features" table toggled by Show/Hide | We highlight only by *user selection*; no unexplained "popular" badge |
| Reduced motion | **0 running animations, videos stopped.** Good. | We match it |
| Mobile (390 px touch) | **Still 27 running animations and 4 videos.** No mobile reduction. | We go further: no pinning, no parallax and fewer layers on touch/small screens |

## 2. Motion language: "Evidence assembling"

The story of the product is information becoming **structured, sourced evidence**. Motion therefore shows things **assembling, connecting and resolving into focus**, never decoration for its own sake.

| Principle | In practice |
| --- | --- |
| **Assemble** | Scattered fragments settle into an ordered workflow (sequence A); a chart builds layer by layer (sequence C) |
| **Connect** | Connectors draw between modules; a marker travels along the workflow (sequence B) |
| **Resolve** | Summary → evidence: details unfold from a single result card (sequence D) |
| **Observed ≠ projected, in motion too** | Observed price draws as a **solid** line from left to right and stops at **NOW**. The model projection appears **after** NOW, dashed and violet, point by point, and only when the model supplied it. Prices never "tick" in marketing previews. |
| **Calm at rest** | When the intro is over nothing loops, except one slow (60 s) atmospheric drift that pauses off-screen and under reduced motion |

## 3. Tokens (`src/motion/tokens.ts`, mirrored in `styles/motion.css`)

### Duration

| Token | ms | Use |
| --- | --- | --- |
| `instant` | 120 | Hover, press, focus |
| `fast` | 180 | Tabs, toggles, chips |
| `base` | 260 | Menus, dialogs, sheets, accordion |
| `slow` | 600 | Section reveals, cards, plan selection |
| `cinematic` | 1100 | Headline masks, chart drawing, hero staging |

### Easing

| Token | Curve | Use |
| --- | --- | --- |
| `out` | `cubic-bezier(.22,1,.36,1)` | Default for entering |
| `in` | `cubic-bezier(.55,0,1,.45)` | Leaving |
| `inOut` | `cubic-bezier(.65,0,.35,1)` | On-screen movement |
| `spring` | `cubic-bezier(.34,1.4,.64,1)` | Plan selection only |

### Stagger and distance

| Token | Value |
| --- | --- |
| Stagger: headline lines | 110 ms |
| Stagger: list items | 70 ms |
| Stagger: chart candles | 12 ms |
| Rise | 18 px (10 px on compact screens) |
| Pointer parallax | ±14 px maximum |

## 4. Specifications

### 4.1 Hero (`marketing/sections/Hero.tsx`)

The whole sequence is CSS-driven (`animation-delay`) and starts on first paint.

| t (ms) | Element | Motion |
| --- | --- | --- |
| 0 | Eyebrow | Fade + rise, 600 |
| 80 / 190 / 300 | Headline lines 1–3 | Mask reveal: line slides up from `translateY(105%)` inside `overflow: hidden`, 1100 `out` |
| 520 | Supporting paragraph | Fade + rise + blur 4 → 0 px, 600 |
| 700 | Product stage frame | Fade + rise + scale .985 → 1, 900 |
| 900 → 2200 | Observed price line | `stroke-dashoffset` draw, left → right, 1300 `inOut`; area fades in under it |
| 2150 | NOW boundary | Draws top → bottom, 260 |
| 2300 | Model levels (TP / entry / SL) | `scaleX` 0 → 1 from the signal candle, staggered 90 |
| 2550 | Model projection (only if supplied) | Points appear one by one (120 each) after the dashed path draws |
| 1100 | CTAs | Fade + rise; available early, never delayed behind the visual |
| 2700 / 2850 / 3000 | Floating cards (model output, risk plan, evidence) | Fade + rise + scale; then rest |
| after | Pointer parallax | Layers at depths 0.3 / 0.6 / 1.0, max 14 px. Fine pointers only; off under reduced motion. |

### 4.2 Scroll sequences

All use **one** shared scroll manager (`motion/scrollManager.ts`):

- one passive `scroll` + `resize` listener, coalesced to one `requestAnimationFrame`
- sections subscribe **only while intersecting** (`IntersectionObserver`), so off-screen sections cost nothing
- progress writes to a CSS custom property or directly to `transform` / `opacity`; no React re-render per frame
- React state changes only when a *step* changes

| Sequence | Desktop (≥ 1024 px, fine pointer, motion allowed) | Compact / touch / reduced motion |
| --- | --- | --- |
| A · Overload → structure | Pinned stage, 220 vh. 7 scattered "fragments" (rotated, offset) travel to ordered rows (0.15 → 0.75 of progress, staggered windows) while their labels cross-fade into the 7 modules. | Two static lists, "before" and "after", with in-view reveals |
| B · Platform comes together | Pinned, 320 vh, 7 steps. The rail fills; the active module highlights; a connector marker moves along the diagram; the preview panel cross-fades (260 ms). The tabs remain clickable and scroll to their step. | Accessible tablist; the same previews, switched by tap |
| C · Chart → research plan | Pinned, 360 vh, 6 steps: candles (12 ms stagger) → NOW → projection → levels → risk card → evidence and uncertainty | All six layers shown, with numbered captions |
| D · Understand the evidence | In-view: the summary card resolves, then six facets reveal (70 ms stagger) with connectors drawing; a "Summary ⇄ Evidence" toggle | Same, without connectors |
| E · Membership | Section reveal; plan cards rise in sequence; selection uses `spring` scale 1 → 1.015 and a gold hairline | Same, smaller travel |

Pinned sections never trap the user:

- scroll speed is native
- every step is reachable by keyboard and by tabs
- total pinned length on the home page is ≈ 9 viewport heights, split across three sequences

### 4.3 Interface motion

| Element | Spec |
| --- | --- |
| Route changes | View Transitions API through React Router `viewTransition`: root cross-fade 260 ms plus a 6 px rise. Shared elements: brand mark, auth card. No API → instant navigation. |
| Header | Transparent → compact glass after 24 px of scroll: height 72 → 56, 260 ms |
| Mobile menu | Native `<dialog>`; panel slides 24 px + fades (260); links stagger 40 ms |
| Accordion (FAQ) | `grid-template-rows: 0fr → 1fr`, 260 `out`; chevron rotates |
| Plan selection | `spring` 380 ms; check badge scales in |
| Compare table | Rows reveal with a 40 ms stagger; highlighted column tint 260 |
| Side sheets / dialogs | Existing 220 slide + fade |
| Auth | Card rises 600; motif draws itself (line 1300, projection after); Sign in ↔ Create account share the card via a view transition |

## 5. Desktop vs mobile

| Feature | Desktop | Mobile / tablet (< 1024 px or coarse pointer) |
| --- | --- | --- |
| Hero staging | Full sequence | Same sequence, shorter travel; floating cards stack under the chart |
| Pointer parallax | On | Off |
| Pinned sequences | On | Off: static, readable layouts with in-view reveals |
| Atmospheric drift | One layer, 60 s | Off |

## 6. Performance constraints

- Only `transform`, `opacity` and SVG `stroke-dashoffset` animate continuously. The accordion is the one layout animation, and it is user-initiated and short.
- No video, no WebGL, no new motion dependency (0 KB added). The decision is recorded in §8.
- Off-screen sections unsubscribe from scroll. The atmospheric layer uses `animation-play-state: paused` when off-screen.
- Listeners, observers and rAF handles are removed on unmount (tested).
- Pinned stages have fixed dimensions (no layout shift). Charts use fixed `viewBox` ratios.

## 7. Accessibility

`prefers-reduced-motion: reduce` turns off:

- the hero sequence (content is shown at its final state)
- parallax and pinning
- view transitions
- drawing animations

Every sequence then shows its complete, final state.

Other requirements:

- No content is hidden behind motion. Without JavaScript or `IntersectionObserver`, everything renders visible (`data-motion` is opt-in progressive enhancement).
- No flashing. Nothing exceeds one cycle per second, and nothing loops at rest except the 60 s drift.
- Pinned steps are mirrored as focusable tabs with `aria-selected`. Captions are real text, not canvas.

## 8. Library decision

GO AI reaches its result without a motion library. Our needs are:

- entrance staging
- in-view reveals
- scroll progress
- parallax
- route transitions

Each of these is a few dozen lines on top of CSS, `IntersectionObserver`, `requestAnimationFrame` and the View Transitions API, which React Router 7 already supports.

Adding Motion/Framer (≈ 30–50 KB gzip) or GSAP would duplicate these capabilities and add a second animation system. **No dependency was added.**

## 9. Implementation plan (executed)

1. `motion/`: tokens, scroll manager, `useInView`, `useScrollProgress`, `usePointerParallax`, `useReducedMotion`, `<Reveal>`, `<RevealText>`, `<PinnedStage>`
2. `styles/motion.css`: keyframes, reveal states, view-transition rules, reduced-motion overrides
3. Public site: header, hero, sequences A–E, risk demo, methodology, membership teaser, FAQ, final CTA, footer
4. Membership page, onboarding, auth transitions
5. Browser QA:
   - frames during the hero
   - scroll-step screenshots per sequence
   - reduced-motion and mobile runs
   - e2e flows
