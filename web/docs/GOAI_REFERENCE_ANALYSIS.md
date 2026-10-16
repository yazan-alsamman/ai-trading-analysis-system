# GO AI reference analysis

_Date: 16 October 2026 · Reference: https://goai.global/ · Purpose: learn product-design principles for **AI Trading Assistance**. This is not a brief to copy GO AI. We do not reuse its names, content, imagery, branding or commercial model._

## 1. What was actually inspected

All observations come from a real Chrome browser driven by Playwright (`scratchpad/goai/*.cjs` scripts, not committed). We captured screenshots and read computed styles from the live DOM.

| Page / interaction | Viewport(s) | Method | Result |
| --- | --- | --- | --- |
| Home `/` (full scroll, 9 viewport captures) | 1440×900, 390×844 | Scroll capture + `getComputedStyle` on headings, paragraphs, buttons and sections; `document.fonts`; colour census of 4,000 nodes | ✅ |
| "Platform" mega-menu | 1440 | Hover | ✅ dropdown with 4 module entries, each with a one-line purpose |
| Hero age timeline (20 / 30 / 50 / 85) | 1440 | Click | ✅ changes the background video; it is decorative storytelling |
| "Calculate Your Future" calculator | 1440 | Click, then keyboard `ArrowRight` on a range input | ✅ modal with 3 range inputs (age, monthly amount, target age). Outputs update live. The assumption is stated under the result ("Assumes 10% annual return…") |
| "Four Systems. One Outcome." module cards | 1440 | Scroll + hover | ✅ 4 cards that reveal in a staggered sequence on scroll. Captured mid-animation |
| Before/after comparison, testimonials carousel, stats pills, world map, pricing table, final CTA, footer | 1440 | Scroll capture | ✅ |
| Module pages `/go-intel`, `/go-os`, `/go-lab`, `/go-library` | 1440 | First 3 viewports each | ✅ |
| `/about`, `/membership` | 1440 | First 3 viewports | ✅ |
| Login `/my-account` | 1440 | Capture | ✅ |
| Mobile menu | 390 (touch) | Tap "Toggle menu" | ✅ full-height sheet: grouped links + pill CTAs |
| Keyboard focus | 1440 | 4 × Tab | ✅ visible 2px outline (`rgb(71 63 96)`); skip link exists |
| `prefers-reduced-motion` | — | Searched stylesheet rules | ✅ rules present |

**Limitations (stated, not hidden)**

- Registration, checkout and the member dashboard require an account. They were **not** inspected.
- Video content was observed only as poster/frames.
- Hover states were inspected on the module cards and nav only. Other card hovers are inferred from CSS transitions.
- First load took ~46 s to reach network idle (heavy video/media). This is noted as a pattern to avoid.

## 2. Observed patterns

### 2.1 Visual identity

| Aspect | Observation (measured) |
| --- | --- |
| Canvas | Near-black with a violet cast: `body` `rgb(3 0 7)`. Atmosphere comes from faint star particles and very soft radial violet glows behind key sections. |
| Text colour | A single lavender-grey `rgb(216 217 238)` used at many alpha steps (0.4 / 0.55 / 0.65 / 0.7 / 0.75 / 0.85). Headlines are pure white. Hierarchy comes from **opacity of one hue**, not from many greys. |
| Display type | Manrope / SF Pro, weight 500–800, **negative tracking −0.045em**, line-height 1.0. Sizes 58–86px on desktop. |
| Two-tone headlines | The second clause is set in muted grey: "The Gap Isn't Access. *It's Structure.*", "Know your *future.*" The emphasis is created by reducing, not adding. |
| Eyebrows | Orbitron (geometric mono-like) uppercase, ~12px, letter-spacing ≈ 0.18em, muted: "THE PLATFORM", "THE PROOF", "THE THESIS". Each major section starts with one. |
| Numerals | Orbitron is also used for big numbers (`$669K`, `10,000+`). Numbers get their own typographic voice. |
| Buttons | Pills (`radius 999px`). Primary = **white fill, near-black text, weight 700**. Secondary = transparent with a `rgba(216 217 238 / 0.16–0.22)` hairline. Heights 42–61px. |
| Cards | Radius 18–24px, `1px rgba(216 217 238 / 0.14)` hairline, almost transparent fill. **No heavy shadows**. Elevation comes from the hairline and a slight fill lift. |
| Navigation | Floating capsule nav (rounded-full, blurred dark fill) that stays fixed while scrolling. Primary CTA on the right. |
| Accent colour | Violet appears only in glows, map light and a few highlights. Most of the page is monochrome. |

### 2.2 Storytelling and structure (home page order)

1. **Promise**: "Know your future." plus a one-sentence value statement.
2. **Problem**: "The Most Expensive Investment Is Confusion."
3. **Diagnosis**: "The World Doesn't Need More Information. It Needs Better Decisions." A list of the fragmented sources investors bounce between, pulled into one hub.
4. **System**: "Four Systems. One Outcome." Four modules, each one line long, each with *Explore ↗*.
5. **Proof**: countries, community events, testimonials, stats pills.
6. **Contrast**: a before/after list (✗ Random tips / ✓ Clear frameworks).
7. **Offer**: plans, plus an expandable "Compare all features" table (progressive disclosure).
8. **Thesis + final CTA**: "The Gap Isn't Access. It's Structure." with *Get Started Today* / *Watch Demo*.

Every section answers one question and ends by pointing at the next action. Module pages repeat the structure at a smaller scale: a promise headline, then 2–3 capability cards, each pairing a short text card (numbered `01`) with a large illustrative panel.

### 2.3 Interaction design

| Element | Genuine or decorative |
| --- | --- |
| Platform dropdown, mobile menu sheet, plan "Hide/Show" comparison, testimonial carousel, calculator sliders | **Genuine.** They change the content. |
| Hero age timeline | Mostly **decorative**. It swaps the video. |
| Scroll-staggered card reveal, star particles, glowing ring | **Decorative motion** |
| "Toronto, Canada — Subscription started" toast | Social-proof ticker. We would not adopt it: unverifiable "live activity". |
| Calculator | Genuine, and **it states its assumption** under the result. This is the single most relevant interaction for us. |

### 2.4 Product architecture

GO AI presents four modules (Library = knowledge, Intel = awareness, Lab = execution tools, OS = decision) as **one operating system**. The same four names appear in:

- the nav dropdown, where each has a one-line purpose
- the "Four Systems" section
- the module pages
- the pricing comparison table
- the footer

The consistency of naming everywhere is what makes the ecosystem feel coherent.

## 3. Patterns worth adapting

| # | Pattern | How we translate it |
| --- | --- | --- |
| A1 | **Problem → system → proof → next action** narrative | A new **Overview** route (first screen after sign-in): what the platform does, which decisions it supports, the 7-step research workflow, the live state of the data and the next action |
| A2 | **Named modules presented as one system** | Our real modules, named consistently in nav, overview, command palette and page headers: Market Intelligence · Chart Analysis · AI Research · Risk Management · Personalised Signals · Performance Insights · AI Assistant |
| A3 | **One hue at many opacities** for text hierarchy | Ink-violet neutrals: one lavender-grey family for `fg-2`/`fg-3`, all measured ≥ 4.5:1 |
| A4 | **Editorial display type with a muted second clause** | A display serif (Instrument Serif, self-hosted) for hero/auth/section titles only, **never** inside dense trading panels |
| A5 | **Eyebrow labels** before major sections | Mono uppercase eyebrows (JetBrains Mono, 12px, tracked). We already self-host this font |
| A6 | **Hairline cards, large radius, no heavy shadow** | Hairline `line` borders; 12–16px radius for narrative surfaces; 8px stays for dense panels |
| A7 | **Primary CTA = inverted pill** (white on dark / ink on light) | `Button variant="primary"` becomes the inverted neutral; gold is reserved for brand and selection |
| A8 | **Calculator that states its assumptions** | The Capital & Risk module shows every formula input, the conversion rule and missing metadata next to the result |
| A9 | **Progressive disclosure** ("Compare all features") | Signal provenance drawer, "Why / What could invalidate it / What is missing" sections, collapsible model details |
| A10 | **Floating capsule nav and full-height mobile sheet** | Mobile navigation sheet with grouped modules, plus the existing collapsible sidebar on desktop |
| A11 | **Number typography as its own voice** | Tabular mono numerals for every price and metric (already a rule) plus larger mono "hero numbers" on the Overview |

## 4. Patterns that do not suit a trading research platform

| Pattern | Why we reject it |
| --- | --- |
| Full-screen background video, people photography, 46 s load | Traders need speed and focus. Our first meaningful paint must stay fast; no autoplay media. |
| Testimonials, "47 countries", "10,000+ members", live "subscription started" ticker | We cannot verify such claims, and fabricated social proof is explicitly forbidden. |
| "Profit using GO OS, $16k in 3 months" style outcome claims | We never promise profit. Every model output is a probability with its limitations. |
| "92% confidence" chips without definitions | Every probability we show is defined ("TP before SL within horizon") and labelled demo when simulated. |
| Pricing/membership tiers, "Book a call" | Out of scope for a graduation research platform. |
| "Frictionless execution" / BUY buttons | The platform **never executes trades** (AI 19 cancelled). No execution controls anywhere. |
| Scroll-jacked, staggered reveal on data screens | Motion must not delay reading prices. Motion stays on narrative surfaces only and respects reduced-motion. |
| Huge 80px headlines everywhere | Large display type only on the Overview hero and auth. Workspace and data pages stay dense. |

## 5. Design direction: "Ink, Aurum and Violet"

A research terminal with an editorial front door.

- **Ink.** Near-black canvas with a faint violet cast (`#07070a`). The light theme is "paper": warm off-white `#f4f3ef` with ink text.
- **Aurum (gold).** The brand and selection accent: active navigation, focus ring, links and brand mark. It fits a gold-first research product and is distinct from every market colour.
- **Violet.** **Exclusively AI/model output**: probabilities, projections and "model" chips. This rule already existed and is kept.
- **Up / Down.** Green/red, only for market direction and P/L, always with sign and arrow.
- **Sky.** Demo/simulated labelling and info. It moves away from amber so that demo labels are never confused with warnings or with the gold accent.
- **Typography.** Instrument Serif for display; Inter for interface; JetBrains Mono for numbers and eyebrows.
- **Shape.** Pills for primary CTAs on narrative surfaces; 6–8px radii in dense tools.
- **Motion.** 150–250ms opacity/translate on narrative surfaces only; none on prices; `prefers-reduced-motion` disables all.

Measured contrast for the full palette is recorded in `docs/DESIGN_SYSTEM.md`.

## 6. Prioritised implementation plan

| Priority | Work | Reference pattern |
| --- | --- | --- |
| P0 | Design foundation: tokens (ink/aurum/violet/sky), display + eyebrow type, primary pill CTA, brand mark | A3–A7 |
| P0 | Shell: module-based navigation (7 modules), Overview as the first screen | A1, A2, A10 |
| P0 | **Capital & Risk module** with validated, unit-tested calculations; no guessed contract/pip values | A8 |
| P1 | **Personalised signals**: saved profile, per-signal checks (preferences + risk), provenance drawer | A9 |
| P1 | **AI Assistant**: provider-agnostic service, honest demo (rule-based evidence composer), workspace side panel | A2, A9 |
| P1 | Sign-in / registration redesign: editorial identity panel, password visibility + strength, recovery honestly marked pending; align the API adapter with the real FastAPI auth contract | A4, A7 |
| P1 | Workspace: contextual "what could invalidate this / what is missing", links to Risk and Assistant | A9 |
| P2 | Overview analytics: verified/defined metrics, data freshness, model-quality snapshot with definitions | A1, A11 |
| P2 | Responsive and motion polish; screenshot QA in both themes and at 5 widths | — |
