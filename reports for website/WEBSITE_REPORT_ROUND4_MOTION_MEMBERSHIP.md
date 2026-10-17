# AI Trading Assistance — Round 4 Report

**Cinematic public website, motion system, membership experience and account entry**

| | |
| --- | --- |
| Date | 16 October 2026 |
| Scope | **Frontend only** (`web/`). No backend, database, auth service, billing or infrastructure was changed. |
| Branch | `e/web-client`, with `origin/main` merged in (backend PRs #1–#17); pull request opened against `main` |
| Previous round | `WEBSITE_REDESIGN_REPORT.md` (round 3) |

---

## 1. Summary

Before this round, the first thing a visitor saw was the application. The platform now has a **public website** that explains it before any sign-in. It is driven by a **unified motion system** and leads into a **membership experience** and a **plan-aware sign-up journey**.

| Area | Result |
| --- | --- |
| Motion | One runtime (`src/motion/`) and one stylesheet (`styles/motion.css`): tokens, a shared scroll loop, in-view reveals, line-mask headlines, pointer parallax, pinned scroll sequences, view transitions. **No new dependency.** |
| Hero | Editorial headline masks, then copy, then the real simulated gold chart drawing itself (observed → NOW → model levels → projection), then three floating evidence cards. Content visible from first paint; fully staged in ≈ 3.4 s. |
| Storytelling | Five sequences: A overload → structure (pinned) · B seven modules (pinned, synchronised previews) · C chart → research plan (pinned, 6 steps) · D summary → evidence · E membership |
| Product demos | Previews render the **application's own components** (FactorList, CheckList, LimitMeter, Markdown, chart) with the platform's simulated fixtures at a fixed time |
| Honest results | Methodology section: period, sample size, definitions, source, a calibration chart, and "No verified live results exist yet" |
| Membership | `/membership`: three configurable plans, **Pricing to be announced**, comparison (table / phone list), plan-fit helper, confirmation sheet with no checkout, FAQ |
| Journey | Plan → account → review (`/welcome`), with the plan carried through `?plan=`, the auth switch and session state. Demo plan preview inside the app with an upgrade-information gate. |
| Authentication | Animated motif, sliding Sign in / Create account switch, shared-element transition, back-to-site link, journey progress and plan summary |
| SEO | Per-page title/description/Open Graph/canonical; app pages `noindex`; `robots.txt`; `sitemap.xml` built only when `VITE_SITE_URL` is set |

---

## 2. Reference research (motion)

The full write-up is `web/docs/MOTION_DESIGN_DIRECTION.md` §1. goai.global was inspected again in real Chrome, with:

- timed hero frames
- animation inventory
- scroll sampling every 260 px
- hover transitions
- menu animation
- reduced-motion and mobile runs

Findings that shaped the work:

- **No motion library** on the reference: hand-written CSS keyframes plus Web Animations. We matched that and added none.
- **Blank screen for ≈ 2.6 s; the hero is fully staged at ≈ 7 s** (video-driven). We stage in under 1 s and finish in ≈ 3.4 s.
- Reveals use opacity + 16 px rise + blur. Ours use the same family on narrative text only.
- **27 ambient loops** run constantly, and **mobile gets no reduction**. We keep one slow drift, paused off-screen, and on phones and tablets we turn off pinning and parallax.
- **No pinned scroll storytelling** exists on the reference. Ours adds three pinned sequences that explain the product.

Captures are in `screenshots/reference-goai/` (third-party, analysis only).

---

## 3. What was built

### 3.1 Motion system

| File | Responsibility |
| --- | --- |
| `motion/tokens.ts` | Durations, easings, staggers, distances; pure maths (`stickyProgress`, `segment`, `stepAt`, `easeOut`) |
| `motion/runtime.ts` | `subscribeFrames` (one passive listener + rAF), `useInView`, `useScrollProgress`, `useStepProgress`, `usePointerParallax`, `useReducedMotion`, `useCinematic` |
| `motion/Reveal.tsx` | `<Reveal>`, `<RevealText>` |
| `styles/motion.css` | Keyframes, reveal states, layers, accordion, nav underline, slider, view transitions, reduced-motion overrides |

**Performance:**

- Only `transform`, `opacity`, a short `filter` and `stroke-dashoffset` animate.
- Scroll work runs only while a section intersects. Listeners and frames are released on unmount (unit-tested).
- No video, canvas or WebGL.
- The landing page is eager (the hero paints immediately). The workspace and the chart engine are now lazy, so public visitors never download them.

### 3.2 Public website (`/`)

| Section | Content |
| --- | --- |
| Header | Floating capsule; compact glass after 24 px; animated underline; full-screen mobile menu on `<dialog>` with staggered links |
| Hero | As described in §1 |
| Sequence A | Problem fragments → the seven modules (pinned, 230 vh) |
| Sequence B | The platform, seven modules (pinned, 340 vh; tablist; connector; previews) |
| Sequence C | How it works, six steps (pinned, 360 vh) |
| Risk management | Interactive calculator on the demo plan (capital and risk % sliders, real `computeTradeRisk`) |
| Personalised research | Signal checks tick in; the assistant's actual rule-based reply |
| Sequence D | Methodology: summary ⇄ evidence (six facets with drawn connectors), honest results panel, calibration chart, "What we will not show you" |
| Sequence E | Membership: plan cards and confirmation |
| Closing | FAQ (accessible accordion), final CTA, footer with full risk disclaimer |

### 3.3 Membership (frontend only)

Specification: `web/docs/MEMBERSHIP_FRONTEND_SPEC.md`.

- `domain/membership.ts` is the single configuration. Every plan defines every feature; every feature has a status (Works now / Demo data / Needs backend / Planned). Prices are `tba`.
- Essential (gold-first), Professional (+ FX majors, personalisation, alignment, alert delivery), Elite (+ assistant, research history). Risk tools and analytics are in **every** plan.
- There is **no "popular" badge**. The plan-fit helper recommends the smallest plan that covers the visitor's own answers.
- **No checkout and no fake payment.** Activation is shown as unavailable.

### 3.4 Journey and the application

- **Selection.** `/membership` → confirmation sheet → `/register?plan=` or `/login?plan=`. The plan persists for the session; the auth switch forwards it.
- **Registration and sign-in.** Journey progress, plan summary and "Change plan". After sign-in with a plan → `/welcome`.
- **`/welcome`.** Reviews included / not included with status, and states that activation is unavailable. In demo mode, "Preview \<plan\> as a demo" sets a **labelled demo membership**.
- **In the app:**
  - sidebar chip "Demo plan · \<name\>"
  - Settings → Membership (switch or exit the preview)
  - `PlanGate` upgrade information on the assistant (Elite) and personalised signals (Professional+)
  - a workspace notice for Essential on non-gold instruments

  With no demo plan, everything stays open, exactly as before.

### 3.5 Integration with `main`

`origin/main` (14 backend PRs) was merged cleanly into the branch, with no conflicts.

`docs/FRONTEND_BACKEND_DEPENDENCIES.md` now records which existing backend endpoints the frontend can adopt next (workspaces, risk profile, notifications, market data, WebSocket) and which do not exist (membership, payments, assistant, password reset). **No backend code was touched.**

---

## 4. Verification

| Check | Result |
| --- | --- |
| Type check | ✅ 0 errors (`pnpm typecheck`) |
| Lint | ✅ 0 errors, 0 warnings (`pnpm lint`, includes e2e) |
| Unit / component tests | ✅ **128 / 128** in 14 files (was 107). New: membership config and store (11), marketing components, journey, gate, FAQ, motion listener cleanup (10). |
| Production build | ✅ Main app chunk 100 KB gzip (includes the landing page), React 100 KB, CSS 17 KB. The chart engine (57 KB) and the workspace (14 KB) now load only inside the app. Membership 1.7 KB, welcome 1.5 KB. |
| Browser tests (Playwright, local Chrome) | ✅ **64 / 64** (was 54): 17 earlier flows + 6 new round-4 flows (landing, scroll storytelling, reduced motion, mobile menu, full membership journey, SEO), 30 axe scans (15 routes × 2 themes, 0 serious/critical), keyboard test, 10 visual-matrix runs (15 routes × 5 widths × 2 themes, 0 px overflow, 0 console errors) |

**Browser inspection performed in this round** (screenshots in `screenshots/round4/`):

| What | Detail |
| --- | --- |
| Hero timeline | Frames at 0.3 / 0.9 / 1.6 / 5 s |
| Sequence A | Scroll frames at 5 / 45 / 98 % |
| Sequence B | 2 / 40 / 98 % |
| Sequence C | 3 / 30 / 75 / 98 % |
| Other public sections | Every remaining section |
| Membership | Hero, plans, confirmation sheet, comparison |
| Sign-up journey | Registration with plan + validation errors → welcome → app with demo plan → gated assistant → settings → sign-in with plan |
| Light theme | Hero, comparison, registration |
| Mobile (390 px touch) | Hero, menu, sequences, comparison, registration |
| Reduced motion | Hero at 400 ms |

**Defects found by that inspection and fixed:**

| Defect | Fix |
| --- | --- |
| On phones the landing page laid out **999 px wide**: grid columns without an explicit track grew to the chart's intrinsic width, which pushed the header menu off-screen | `grid-cols-[minmax(0,1fr)]` base tracks on every responsive grid; e2e asserts ≤ 390 px |
| `/membership#compare` landed at the top: the lazily loaded page wasn't rendered when the hash scroll ran | Hash scroll retries for up to 60 frames |
| The landing page briefly showed the app's loading skeleton and the footer | Landing page made eager |
| Hero: SL and Entry labels overlapped; a card hid the "Simulated" tag; cards covered the legend | Label relaxation (min 28 px); legend moved to the header; tag moved |
| Sequence A: the two headlines were briefly superimposed mid-scroll | Sequential fade-out → fade-in |
| Fragment numbering didn't match the app's module order | Reordered (04 Risk, 05 Signals) |
| Reduced motion: staged items would stay invisible for their delay | All animation and transition delays are zeroed under reduced motion |
| **Mobile menu links could not be tapped**: the dialog inherited `pointer-events: none` from the floating header. Caught by the new e2e test. | `pointer-events-auto` on the dialog |
| axe: inactive steps in sequence C were dimmed with opacity (contrast below AA) | Muted with text tokens instead of opacity |
| axe could scan entrance animations mid-fade | The e2e `settle()` waits for finite animations to finish |

**Not verified:**

- Behaviour on physical iOS/Android devices (emulated touch only)
- Screen-reader sessions
- Safari and Firefox rendering (Chrome only; the Firefox slider focus style is written but not checked)
- A run against the live FastAPI stack

---

## 5. Status of every feature

| Category | Items |
| --- | --- |
| **Completed and verified in the browser** | Motion system, hero, sequences A–E, risk calculator, methodology, FAQ, header and mobile menu, membership page and comparison, plan fit, confirmation sheet, sign-up journey with plan, welcome step, demo plan preview and gates, auth transitions, reduced-motion behaviour, mobile layouts, SEO meta / robots |
| **Implemented, not fully verified** | View-transition shared elements in Safari/Firefox (Chrome only); `sitemap.xml` (generated only with `VITE_SITE_URL`, which is not set locally); Firefox slider focus style |
| **Demo-only** | Market data and model output on every page (simulated fixtures); the assistant (rule-based); demo sign-in; the demo membership preview and its gating |
| **Requires backend integration** | Subscriptions, entitlements and payments; real sign-up verification; Feature 12 model output; assistant provider; password reset; adopting the existing workspaces, risk-profile, notification, market and WebSocket endpoints |
| **Requires commercial decisions** | Plan prices, billing periods, trials, refunds, support levels; final plan contents (the matrix is a proposal) |

---

## 6. Prioritised next steps

1. **Commercial decisions.** Approve plan contents and prices; then set `price` in `domain/membership.ts`.
2. **Adopt existing backend endpoints.** Workspaces, `/me/risk-profile`, notifications, market data and the WebSocket (frontend adapter work only).
3. **Backend: subscriptions and entitlements.** `/me/subscription`, `/me/entitlements`, then replace the demo gate with server entitlements.
4. **Token refresh.** Run against the VPS stack, with an end-to-end auth test.
5. **Model output.** Feature 12 through the API, so the public demo can switch from fixtures to real (labelled) model output.
6. **Cross-browser and device testing.** Safari and Firefox, real devices and a screen-reader pass.
