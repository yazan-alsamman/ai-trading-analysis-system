# Public site — content, assistant and footer (round 6)

_17 October 2026 · frontend only. Builds on `CINEMATIC_MOTION_IMPLEMENTATION.md` (round 5)._

The public website explains the platform before sign-in, in this order:
**understand the platform → see how it works → explore the analysis → understand risk and
methodology → membership → next step.**

All product visuals use the platform's own simulated fixtures (`marketing/showcase.ts`, fixed at
14 Oct 2026 14:00 UTC) and say *Simulated*.

---

## 1. Public routes

| Route | Page | Notes |
| --- | --- | --- |
| `/` | Landing | Eager. Scenes listed in §2. |
| `/about` | About | Lazy. Eight sections, §3. |
| `/ai-assistant` | Research assistant (public) | Lazy. §5. |
| `/membership` | Membership | Unchanged in round 6. |
| `/legal/risk-disclosure` | Risk disclosure | Written from the product's real behaviour; flagged as not legally reviewed. |
| `/legal/data-storage` | Data stored in your browser | Every storage key the web client uses (verified in code); no cookies, analytics or trackers. |
| `/login`, `/register`, `/welcome` | Auth (AuthLayout) | Unchanged. |

**Header navigation:** Platform · How it works · Methodology · Assistant · About · Membership
(`PUBLIC_NAV` in `marketing/content.ts`). The FAQ moved to the footer.

`vite.config.ts` lists the public routes for `sitemap.xml`. The sitemap is emitted only with
`VITE_SITE_URL`.

---

## 2. Landing scenes (round 6 additions)

| # | Scene | What it shows |
| --- | --- | --- |
| 05 | **Anatomy of a setup** (`#anatomy`, `sections/AnatomySection.tsx`) | **Signal preview:** instrument, timeframe, direction, generation time ("example time"), validity, entry zone, stop (invalidation), target zone, reward : risk, probability with band, and profile checks. **Entry-zone chart:** history first, then the three zones growing from the signal candle, then the risk and reward distances. **Market context:** sessions at the example time and two items labelled *Sample content*. Notes beside it: an entry zone is not a guaranteed fill; a stop is not a cap on losses; a target may never be reached. |
| 08 | AI assistant scene | A "Try the research assistant" link to `/ai-assistant`. |

The later scene eyebrows were renumbered (06 Risk … 11 FAQ). The risk, signals, methodology and
membership scenes are as in rounds 4–5.

---

## 3. About page (`marketing/pages/AboutPage.tsx`)

| § | Question | Content | Visual and motion |
| --- | --- | --- | --- |
| Hero | Who are we? | "A clearer way to read the markets." A research platform for gold and FX: charts, a model's assessment and your own risk limits in one structured, sourced workflow. It never trades. CTAs: Explore the platform; Read the methodology; View membership. | Licensed footage (trader in profile) with the simulated close line drawing over it; three moments on the line become research notes. Poster on phones and tablets. |
| 01 | What problem? | "Markets don't arrive organised." | Six labelled fragments (context, technicals, events, opinion, timeframes, risk) connect with drawn lines into "One research view" (six ordered steps). |
| 02 | What does it do? | Six capabilities, each with its **real status** from `domain/membership.ts`: charts (Demo data); model signals with zones (Demo data); position sizing (Works now); market context and events (Needs backend: the backend collects news, the web client shows samples); research assistant (Demo data, rule-based); evaluation (Demo data). | A small live preview per capability (candles, zone bars, risk figures, sample items, assistant exchange, calibration line), played when in view. |
| 03 | How does it work? | Seven steps: market context → news and events → technical analysis → signal and zones → risk assessment → structured research → **your decision**. Each step is tagged with where it lives in the product. | Horizontal on desktop: the track grows and one data point travels it once. Vertical on phones. |
| 04 | How do we use AI? | Five principles: evidence before conclusions; observed never mixed with projected; every answer names its sources; honest about what is running (rule-based assistant, browser heuristic for demo signals, provider keys server-side); probabilities, not promises. | Violet scene: inputs (model output, factors, checks, missing) connect into a research summary assembled line by line. Labelled simulated. |
| 05 | Risk and uncertainty | "Uncertainty is information. We show it." | Risk card: the real calculator on the example plan (0.5 / 1 / 2 %) with the exposure gauge. Uncertainty card: point estimate and band on a 0–100 % scale. Transparency card: the provenance labels and their meanings. |
| 06 | Who is it for? | Gold traders who want structure; traders who compare before they commit (FX majors, 15m/1h/4h); anyone who sizes before they act. **Not built for:** copying signals blindly, automated execution, guaranteed returns. | Editorial list with large numerals. |
| Close | Next step | "Discipline is a process. This is the process." CTAs: Explore the platform; View membership; Create an account. States that pricing has not been announced and no payment is taken. | Licensed footage (notes being written), canvas pool behind the copy. |

**Not stated anywhere, because it is not verified:** founders, team, company history, location,
regulation, partnerships, user counts, testimonials, win rates and live performance.

---

## 4. Footer (`marketing/layout/PublicFooter.tsx`)

- **Brand and next step:** "Research first. Then decide.", the description, *Compare plans* and
  *Try the research assistant*.
- **Navigation** (`FOOTER_GROUPS` in `marketing/content.ts`). Every link is an existing route or an
  anchor on one; a unit test checks the routes, and e2e opens every link and anchor.
  - Platform: modules, how it works, anatomy, risk, research assistant, methodology, live demo (demo
    mode only).
  - Company: About, our approach to AI, risk and transparency, FAQ.
  - Membership: plans, compare features, membership FAQ, sign in, create account.
  - Legal: risk disclosure, data stored in your browser.
- **App download.** `src/config/externalLinks.ts` → `APP_STORES` (both `url: null`). The footer shows
  "Android · coming soon / Google Play" and "iOS · coming soon / App Store" as clearly unavailable
  tiles, with no store badges, links, QR code or app IDs. When a store URL is verified, set it there
  and the tile becomes a link that opens in a new tab with `noopener`.
- **Social:** `SOCIAL_LINKS` is empty. The footer says no channels have been announced yet. Add verified
  profiles there; only `http(s)` URLs render (`isSafeExternalUrl`).
- **Legal and trust:** the full risk disclaimer with a link to the disclosure; the footage credit
  (Coverr, Mixkit); "© 2026 AI Trading Assistance · Graduation project"; and a note that terms and a
  privacy policy are in preparation.

**Missing destinations (not created, because they cannot be written accurately yet):**

| Destination | Why it is missing |
| --- | --- |
| Terms of service | Needs a legal entity and legal review |
| Privacy policy (server data) | Needs a legal entity and legal review; browser-side storage is documented at `/legal/data-storage` |
| Contact | No public address configured (`CONTACT_EMAIL = null`) |
| Store listings | `mobile/` holds only a README; no published app |
| Social profiles | None referenced anywhere in the project |
| Cookie policy | Not required: the web client sets no cookies |

---

## 5. Research assistant

**Where it appears:**

- `/ai-assistant`: a full page (console plus "what it is / can / cannot").
- A **floating launcher** on `/` and `/about` only. It appears after the hero (so it never covers the
  hero CTAs), steps aside while the footer is visible, opens a side sheet, and lazy-loads its content.
- Inside the app, `/assistant` and the workspace sheet, as before.

**How it works:**

- The public surfaces use `createShowcaseAssistant()` (`marketing/assistant/showcaseAssistant.ts`).
  It is the **same rule-based composer** as the app (`services/demo/assistant.ts`), behind the same
  `AssistantService` interface. Its clock is fixed at the showcase time, so answers about the example
  setup stay coherent.
- No network request is made and nothing typed leaves the browser.
- **Context:** the simulated XAU/USD 1h setup, plus an optional illustrative $25,000 account at 1 %
  ("Use the example account").
- **One conversation per browser** (`ata.assistant.public.v1`). "Clear conversation" removes it, and
  an empty conversation leaves nothing stored.

**Structured answers** (shared by the app and the public site):

- Each reply carries an optional `kind`: explain, evidence, invalidate, risk, compare, missing,
  glossary or unknown. A remote provider may omit it.
- `ReplyCard` shows:
  - the kind as a header (e.g. *Invalidation conditions*)
  - the answer
  - the simulated-data note as a separate callout
  - time, *rule-based, not a language model*, and what the answer used
  - **Next research step** buttons, which are real suggested prompts
- The empty state groups prompts by task: read the signal; entry, stop and invalidation; risk;
  before you decide.

**Interaction:**

- Enter sends; Shift+Enter adds a new line.
- A pending state reads "Composing an answer from the context…", with a Stop button.
- Errors offer Retry.
- The conversation log is an `aria-live` region.
- The layout is responsive: the sheet is full-width on phones.

**Limits, stated in the UI:**

- It is not a language model.
- It cannot read news, the calendar, order books or the internet, and cannot see live prices.
- It cannot predict beyond the model output, and cannot place trades.

A real provider plugs in through `services/api` (`POST /assistant/replies`, proposed) with keys on
the server.

---

## 6. Tests

- **Unit** (`marketing/round6.test.tsx`, 10 tests):
  - no dead footer or header routes
  - no invented store or social links
  - honest footer states
  - reply kinds, and follow-ups that are real prompts
  - the simulated-note split
  - the showcase assistant (fixed clock, abort)
  - the public assistant flow (prompt → card → Enter → clear)
  - the About page answers its questions in order, with honest statuses and no invented claims
  - legal pages
  - the launcher's scope
- **e2e** (`e2e/round6.spec.ts`, 7 tests):
  - About page sections, the real calculator and its CTA
  - assistant page: prompt → follow-up → Shift+Enter / Enter → clear
  - launcher: show, open, hide at the footer
  - **every footer link and anchor resolves**
  - anatomy scene
  - legal pages are indexable
  - 390 px fit
- The a11y and visual matrices now include `/about`, `/ai-assistant` and both legal pages.
- **Weekend-dependent tests fixed.** The demo market follows real FX hours, so three older tests
  failed every weekend (the round-5 "unconfirmed failures"). They now pin the browser clock to a
  weekday (`atTime(page, WEEKDAY)`), and a new test asserts the weekend "Market closed" state.
