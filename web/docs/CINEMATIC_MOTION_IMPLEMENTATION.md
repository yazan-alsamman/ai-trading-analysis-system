# Cinematic motion — implementation (round 5)

Scope: the public website (`/`, plus the plan → sign-up hand-off). **Frontend only.** No backend, API,
auth, payment, infrastructure or deployment file was changed. Builds on the round-4 motion system
(`docs/MOTION_DESIGN_DIRECTION.md`).

The brief asked for a cinematic, immersive site: real footage in the hero, a chart that draws itself,
a floating 3D laptop running the product, eight distinct scenes, ambient life, page transitions and a
mobile recomposition. It had to do this without inventing data, without fake motion on stills, without
unlicensed or hot-linked assets, and while respecting reduced motion, Save-Data and accessibility.

---

## 1. Architecture

| Layer | File | Responsibility |
| --- | --- | --- |
| Footage player | `src/motion/CinematicVideo.tsx` | Muted, looping, inline, decorative `<video>`. Plays only while on screen **and** while the tab is visible; `preload="none"` until it nears the viewport (except `priority`). It shows the poster `<img>` alone under reduced motion, under Save-Data, on phones for secondary scenes (`phone="poster"`), or when playback is refused or fails. It exposes `data-video-state` (`idle` / `playing` / `paused` / `poster`) for tests. |
| Footage inventory | `src/marketing/media.ts` | One entry per clip: local file, poster, phone rendition, subject, source, title, exact download URL, licence. |
| Media hooks | `src/motion/runtime.ts` | Added `useSmallScreen` (< 48 rem), `useSingleColumn` (< 64 rem) and `prefersSaveData()` (`navigator.connection.saveData` or `prefers-reduced-data`). |
| Styles | `src/styles/cinematic.css` (imported by `index.css`) | Footage masks and veils (themed); the CSS-3D laptop; the depth stage; the data packet; the exposure gauge; plan tilt-reveal and spotlight; the violet scene; reply blocks and typing indicator; reduced-motion overrides. |
| Chart | `src/marketing/components/ShowcaseChart.tsx` | Intro sequence extended: grid → time axis → line → swing points → NOW (+ pulse) → levels → projection. New `scan` prop: an ambient crosshair with an OHLC readout labelled *simulated*. |
| Product screen | `src/marketing/components/WorkspaceScreen.tsx` | The research workspace as shown inside the laptop: the app's navigation items, `ShowcaseChart`, `DirectionBadge`, `SourceTag`, evidence bars and the risk plan. All of it uses the showcase (simulated) data. Authored at 1000 × 625 px and scaled with `--s`. |
| Asset build | `scripts/build-media.sh` | Reproducible: cuts each licensed source into a seamless loop, bakes the grade, encodes H.264 without audio, writes WebP posters. |

**Rendering rules (unchanged from round 4, enforced here):**

- Only `transform`, `opacity`, `stroke-dashoffset` (and one short `filter` on reveals) animate.
- Scroll work goes through the single `subscribeFrames` loop and runs only while a scene intersects.
- No runtime CSS filters on video: grades are baked into the files. No `backdrop-filter` over playing
  video: panels over footage use near-opaque surfaces instead.
- No WebGL, no canvas, **no new dependency**.

**Loop budget.** A loop is anything that keeps animating at rest:

| Loop | Where | Off-screen |
| --- | --- | --- |
| Footage | one clip per scene | paused (IntersectionObserver), also paused when the tab is hidden |
| Hero crosshair | hero chart, one step every 1.5 s | stopped (`scan` = hero visible && !reduced) |
| NOW pulse | hero chart | paused (`data-paused` on the hero) |
| Aurum drift | hero glow (round 4) | paused |

At any scroll position, at most one or two clips are playing.

---

## 2. Scene inventory

| # | Scene | Section id | Technique | What moves | Reduced motion | Phones |
| --- | --- | --- | --- | --- | --- | --- |
| — | **Hero** | (top) | **Video** + **SVG** + app components | A trader's desk at night (licensed) dissolves in behind the headline. The chart lays its grid and time axis, the line draws, swing points pop as it reaches them, then NOW (with a slow pulse), entry/stop/target and the projection appear. Three cards float in. Then the crosshair steps through the history with a readout ("… · simulated"). Pointer parallax on fine pointers. | Poster; finished chart; no scan | Footage becomes a band above the copy (also on tablets < 64 rem); small 720 px rendition |
| A | **Problem** | `problem` | **Video** + CSS 3D depth | Fragments start at different depths (`translateZ` −300…+170 px in a perspective stage) and settle into an ordered list. The out-of-focus quote board recedes (`--k`) as order appears. | Static two-column list, poster | Static list, poster |
| — | **Workspace (3D laptop)** | `workspace` | **CSS 3D** + app components | Pinned (260 vh). The lid opens from closed (−82°) to 4°, the machine tilts from above to the working angle and turns slowly (ry −22° → +10°). Three panels (model output, loss at the stop, checks) come forward in depth. The screen shows the real workspace UI. | Still, open laptop | Still, open laptop |
| B | **Platform, seven modules** | `platform` | DOM + CSS | Round 4's scroll-linked tablist, plus a **data packet** that travels along the connector to each newly selected module. | No packet | Static tabs |
| C | **Chart → research plan** | `how-it-works` | **SVG** + app components, **video** header | Seven steps: observed history → NOW → projection → levels → evidence and your checks → sized to your capital → a **structured research plan** (thesis, levels, size, checks, invalidation, missing, "research, not advice"). Only the active step's explanation opens. A workflow clip (hands at a laptop) plays beside the heading. | All layers and cards shown | All shown; poster hidden < 48 rem |
| D | **Risk** | `risk` | **SVG** + real calculation | An **exposure gauge** (0–3 % of capital, with a mark at the 1 % example limit; turns amber above it) and a cause → effect chain (`budget = capital × risk %`, `÷ distance to stop`, `= position`). Every figure comes from `computeTradeRisk`, and a unit test asserts that the chain is consistent. | Instant | Same, stacked |
| — | **Personalised signals** | `signals` | App components | Checks tick in one by one against the saved profile. | Instant | Same |
| E | **AI assistant** | `assistant` | **Video** + **SVG** + app components | A violet scene. A screen reflected in glasses (licensed; graded violet). The question is asked; the context the answer may use lights up and **connectors draw** from each item into the reply; a typing indicator gives way to the reply **block by block**. It stays labelled *Rule-based demo* and *Rule-based, not a language model*. | Reply shown at once | Poster hidden; chat only |
| F | **Methodology** | `methodology` | **Video** band + **SVG** | A hand writing notes (licensed) behind the heading. A **reliability diagram** draws its axes, the dashed "perfect calibration" diagonal, then the observed line and points sized by sample count. "No verified live results exist yet" is unchanged, and an sr-only list gives the numbers. | Drawn at once | Poster |
| G | **Membership** | `membership` | CSS 3D | Plan cards **tilt up** into place (`rotateX(16deg)` → 0) and a soft **spotlight** follows the mouse. *Pricing to be announced*; no checkout. | No tilt | No spotlight (touch) |
| H | **Closing** | (final CTA) | **Video** + **SVG** | A trader in profile at the screen (licensed); the simulated price line draws across the full width; the CTA sits on a canvas-coloured pool. | Poster, line drawn | Poster |

**Page transitions.** The selected plan card and the sign-up page's plan summary now share
`view-transition-name: selected-plan`, so the card morphs into the summary when the visitor continues
to `/register?plan=…` (and back via "Change plan"). The round-4 `brand` and `auth-card` shared elements
are kept. No transition adds a delay before navigation; unsupported browsers navigate instantly.

**What is real and what is simulated.** Footage shows people and screens for atmosphere only. The
charts in the footage belong to the stock clips and are **never** presented as the platform's data. All
product visuals (hero chart, laptop screen, plan, gauge, calibration) use the platform's own simulated
fixtures and say *Simulated*.

---

## 3. Mobile and tablet recomposition

- **< 64 rem (phones and tablets).** Hero footage moves into a band above the copy, masked clear under
  the header and fading out above the eyebrow. Pinned scenes become static layouts (round-4 rule), and the
  laptop is shown still and open.
- **< 48 rem (phones).** Only the hero plays video, using the 720 px rendition (155 KB). Every other
  scene shows its poster, and posters hidden by layout (`md:block`) are never requested (lazy `<img>`).
  The e2e suite asserts that a phone fetches exactly `hero-trader-desk-sm.mp4`.
- No horizontal overflow at 390, 834 and 1440 px: sampled during QA, and asserted at 390 px in e2e.
  The full visual matrix (incl. 1024 px) has not completed in this round.

---

## 4. Asset inventory

All clips were downloaded once as 1080p sources and processed locally by `scripts/build-media.sh` (a
ping-pong loop for clips with a camera move; a 1 s cross-fade loop for near-static clips; grade baked
in; H.264 `yuv420p`, `+faststart`, no audio track). They are **self-hosted** in `public/media/`, with
nothing hot-linked.

| File | Size | Dimensions | Loop | Source (title) | Licence | Used in |
| --- | --- | --- | --- | --- | --- | --- |
| `hero-trader-desk.mp4` | 469 KB | 1280 × 720 | 12 s ping-pong | Coverr, "A broker works with a cryptocurrency candlestick chart" | Coverr licence | Hero (desktop) |
| `hero-trader-desk-sm.mp4` | 155 KB | 720 × 406 | 12 s ping-pong | same | Coverr licence | Hero (phones, tablets) |
| `overload-price-board.mp4` | 168 KB | 960 × 540 | 12 s ping-pong | Coverr, "A screen showing financial analysis of a cryptocurrency" | Coverr licence | Scene A |
| `workflow-laptop-chart.mp4` | 296 KB | 960 × 540 | 10 s ping-pong | Coverr, "A businessman working on a stock market trading platform" | Coverr licence | Scene C header |
| `assistant-reflection.mp4` | 178 KB | 960 × 540 | 8 s cross-fade, violet grade | Mixkit, "Reflection of a screen in glasses" (#221) | Mixkit **Stock Video Free License** | Scene E |
| `method-notebook.mp4` | 238 KB | 960 × 540 | 12 s ping-pong | Coverr, "A trader writing analytical data in a notebook" | Coverr licence | Scene F |
| `closing-trader-profile.mp4` | 344 KB | 1280 × 720 | 8 s cross-fade | Coverr, "A man analyzing the stock market" | Coverr licence | Scene H |
| `*.webp` posters | 7–21 KB each | as above | first frame | — | — | All |

Total: **1.9 MB of video** (2.0 MB with posters). A desktop visitor who scrolls the whole page
downloads at most the clips that came near the viewport. A phone downloads 155 KB.

Exact download URLs are recorded in `src/marketing/media.ts` (`sourceUrl`).

**Licence notes (checked on the providers' licence pages during this round):**

- **Coverr licence:** free for commercial and non-commercial use; no attribution required. Not allowed:
  redistributing the clips as a competing stock service, or using them to train AI. Model releases are
  held by Coverr; trademarks and brands visible in a clip are not cleared, and none are prominent in the
  clips used.
- **Mixkit Stock Video *Free* License:** free for commercial use. Mixkit also publishes clips under a
  *Restricted* licence that **excludes** commercial and advertising use. Every clip with that label
  (e.g. #47214, #47012, #47016) was rejected. #221 is under the Free licence.
- Pexels and Pixabay could not be reached from this machine (HTTP 403), so none of their clips was used.

A short credit line is in the site footer although neither licence requires one.

---

## 5. Accessibility

- Videos and posters are `aria-hidden`, have no audio, and carry no information; there is nothing to
  caption. The 3D laptop is `aria-hidden` and is described by an `sr-only` paragraph with the same
  figures. The calibration diagram has an `sr-only` list of its bins.
- `prefers-reduced-motion`: posters only (no `<video>` element at all), no pinning, no scan, no pulse,
  no packet, no tilt; all delays are zeroed (round 4), so staged content is visible immediately.
- **Contrast over footage.** Copy never sits directly on raw video:
  - The hero dissolve is masked away from the copy, and from under the transparent header.
  - In the light theme the dissolve starts later (`--fr-start` / `--fr-end`), because dark footage under
    dark copy fails contrast.
  - Secondary footage is scaled by a per-theme `--footage-strength` (0.6 dark, 0.32 light).
  - Scene A's fragment labels have a canvas backing.
  - The closing CTA sits on a canvas-coloured pool.

---

## 6. Decisions

| Decision | Why |
| --- | --- |
| Real licensed footage, cut into seamless loops | The brief asks for a real trader video and forbids fake motion on photos. Ping-pong avoids a visible jump on clips with a camera move; a cross-fade is used where the camera is static. |
| Grades baked into the files | Runtime `filter` on video is expensive, and its results differ by browser. |
| CSS 3D instead of WebGL / Three.js | No dependency, crisp DOM text, real app components on the screen, and graceful reduction. |
| No particles | The footage already provides ambient life; each extra loop costs battery and needs a pause path. |
| No AI-generated or stock "fintech" renders | Unclear licensing, and they would imply product data that does not exist. |
| One clip per scene, posters on phones | Cinematic on desktop; light on mobile data and battery. |
| Section 05 split into Signals and Assistant scenes | The assistant needed its own violet scene; the eyebrow numbers were renumbered 01–10. |

---

## 7. Tests

- **Unit** (`src/marketing/cinematic.test.tsx`, 14 tests):
  - `CinematicVideo` attributes; play on screen and pause off screen; priority preload; reduced-motion
    poster; Save-Data poster; phone behaviour; fallback when playback is refused
  - footage inventory is local and licensed
  - chart scan starts after the intro, is labelled *simulated*, and stops
  - laptop is decorative and described
  - research-plan card contents
  - risk chain is consistent with the sizing
  - assistant stays labelled as rule-based
- **e2e** (`e2e/round5.spec.ts`, 9 tests):
  - hero footage plays muted, and below-fold clips are not fetched up front
  - hero pauses off-screen while the methodology clip plays
  - reduced motion makes no video request
  - phones fetch only the small hero clip, with no overflow
  - laptop opens with scroll (`--lid`) in `preserve-3d`
  - Step 7 of 7 shows the research plan
  - assistant labelled as rule-based
  - shared `selected-plan` view-transition name
  - media files are local, `video/mp4`, < 600 KB
- **Round-4 e2e updated deliberately:** the section list includes `workspace` and `assistant`, and
  sequence C has seven steps.

---

## 8. Compatibility and known limits

- `mask-composite: intersect` (Chrome 120+, Firefox 53+, Safari 15.4+) with `-webkit-mask-composite:
  source-in` for older WebKit. Where masks are unsupported, the footage shows unmasked under its veil.
- View transitions: Chrome/Edge 111+ and Safari 18+. Elsewhere, navigation is instant.
- `color-mix()` (fragment backing): Chrome 111+, Safari 16.2+, Firefox 113+.
- iOS Low Power Mode and some data-saver modes refuse autoplay. `play()` rejects → the poster stays
  (unit-tested). Not checked on a physical device.
- Text inside 3D-transformed layers can rasterise slightly soft while the laptop turns. It is crisp at rest.
- During QA, two headless screenshots captured partly rasterised frames mid-scroll (DOM state verified
  correct; re-captures were clean). Real-device smoothness on low-end hardware has not been measured.
- Not verified: Safari and Firefox rendering, physical iOS/Android devices, screen-reader session.

## 9. Remaining work

1. Test on Safari (masks, 3D, view transitions) and on physical phones (autoplay, battery).
2. Consider AV1/WebM renditions (≈ 30–40 % smaller), behind a `<source>` list, once Safari support is
   confirmed for the target audience.
3. Replace stock footage with commissioned footage of the actual product in use, when available.
4. When real model output is available through the API, switch the showcase fixtures to labelled real
   output. The scenes are data-driven and need no redesign.
