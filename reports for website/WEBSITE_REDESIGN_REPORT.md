# AI Trading Assistance — Website Redesign Report (Round 3)

**GO AI-inspired product experience for the gold & FX research platform**

| | |
| --- | --- |
| Date | 16 October 2026 |
| Scope | `web/` (React 19 + TypeScript, Vite, Tailwind 4) in the project monorepo, branch `e/web-client` |
| Reference | https://goai.global/ (inspected in a real browser; analysis in `web/docs/GOAI_REFERENCE_ANALYSIS.md`) |
| State of the work | Implemented and verified locally. **Nothing committed, pushed or deployed.** |

> **Where the work was done.** The brief named `Desktop/SENIOR/website`. That folder and this monorepo's `web/` are identical copies (only the README differs). `SENIOR/website` has no commits, while `web/` is the version-controlled copy on the active branch, where this session runs, and next to this `reports for website` folder. The work was therefore done in `web/`; `SENIOR/website` was left untouched. To keep using the old copy, copy `web/src`, `web/docs`, `web/e2e`, `web/scripts`, `package.json` and `pnpm-lock.yaml` across.

---

## Contents

1. Executive summary
2. Reference research (GO AI)
3. Design direction and design system
4. What changed, module by module
5. Implementation report (files)
6. Verification results
7. Before / after screenshots
8. Honesty rules: demo-only vs real
9. Known limitations and backend dependencies
10. Prioritised next steps

---

## 1. Executive summary

The site had a sound engineering base:

- strict TypeScript
- a demo/API service boundary
- provenance labels
- axe and visual-matrix tests

Visually, though, it read as a generic dark dashboard, and three areas the brief asks for were missing: **an introduction/overview, capital & risk management, and an AI assistant**.

This round delivered:

| | Delivered |
| --- | --- |
| **Identity** | A new visual identity, **"Ink, Aurum and Violet"**: ink canvas, gold brand accent, violet reserved for the AI model, an editorial serif for narrative moments and mono eyebrows. Light and dark themes, contrast measured. |
| **Overview** (new landing page) | Explains what the platform does, shows a research card built from real (simulated) gold data, and presents the **seven modules as one workflow**, each with an honest status ("Fully working", "Simulated prices", "Rule-based demo"…) |
| **Capital & risk** (new, fully working) | Validated, unit-tested position sizing and limit checks that **never guess** contract size, pip value, leverage or currency conversion |
| **Personalised signals** | A saved profile. Every signal shows what the model returned, which preferences applied, which risk checks passed, the evidence and its timing. |
| **AI assistant** (new) | A provider-agnostic service boundary plus an **openly rule-based demo** that answers only from the context it is shown. It is also available as a side sheet in the Workspace. |
| **Sign-in and registration** | Redesigned. The API adapter was **corrected to the real FastAPI auth contract** in this monorepo; it previously targeted a non-existent Laravel API. |
| **Workspace AI panel** | Now states what could invalidate the analysis and what data is missing |

| Verification | Before | After |
| --- | --- | --- |
| Unit / component tests | 67 | **107** |
| Playwright tests | 41 | **54 / 54 passing** |
| Routes in the axe and visual matrices | 10 | 13 |
| Type errors / lint problems | 0 / 0 | 0 / 0 |

---

## 2. Reference research (GO AI)

**Method.** Real Chrome was driven by Playwright, with no reliance on search summaries:

- home page at 1440 and 390px
- Platform menu, "Calculate Your Future" modal, Four Systems cards
- before/after section, pricing
- module pages (Intel, OS, Lab, Library), About, Membership, Login
- mobile menu, keyboard focus, reduced-motion rules

Computed styles were read from the live DOM: fonts, sizes, letter-spacing, colours and button metrics. Full write-up: `web/docs/GOAI_REFERENCE_ANALYSIS.md`. Reference captures (third-party, for analysis only) are in `screenshots/reference-goai/`.

**What we took** (principles, not content):

| GO AI pattern (measured) | Our translation |
| --- | --- |
| One lavender-grey text colour at many opacities; near-black violet canvas `rgb(3,0,7)` | Ink neutrals from one family; canvas `#07070a` |
| Display type with tight tracking; muted second clause ("The Gap Isn't Access. *It's Structure.*") | Instrument Serif display with an italic muted clause ("Read the market. Weigh the model. *Size the risk.*") |
| Orbitron uppercase eyebrows ("THE PLATFORM") | JetBrains Mono eyebrows ("04 · RISK MANAGEMENT") linking every page to the workflow |
| White pill primary CTA, hairline secondary | `Button variant="primary"` is the inverted neutral; `shape="pill"` on narrative surfaces |
| "Four Systems. One Outcome." module cards with consistent names everywhere | "Seven modules. *One research workflow.*", named identically in nav, Overview, page eyebrows and search |
| Calculator that states its assumption under the result | Risk module shows the formula, the conversion rule and every missing input |
| "Compare all features" progressive disclosure | Signal provenance sheet; "What is missing"; "How this is calculated" |

**What we rejected:**

- background video and portraits (46 s to network idle)
- unverifiable social proof ("47 countries", live "subscription started" toasts)
- profit testimonials
- undefined "92% confidence" chips
- BUY buttons and "frictionless execution"
- scroll-jacked reveals on data screens

---

## 3. Design direction and design system

Full specification: `web/docs/DESIGN_SYSTEM.md`.

- **Colour roles.** Each colour has one meaning:

  | Colour | Meaning |
  | --- | --- |
  | Gold (aurum) | Brand, selection, focus |
  | Violet | Model output only |
  | Green / red | Market direction only, always with sign and arrow |
  | Sky + dashed outline | Simulated data |
  | Amber | Caution |
  | Orange | Errors and limit breaches |

  Demo moved from amber to sky so it can never be confused with a warning or with the gold accent.
- **Contrast.** Every rendered text/background pair is ≥ 4.5:1 in both themes, measured by `web/scripts/contrast.mjs` and re-checked by axe on every route.
- **Typography.** Instrument Serif (display, narrative only), Inter (UI), JetBrains Mono (numbers and eyebrows). The 12px floor is kept. All fonts are self-hosted.
- **Shape and elevation.** Hairline borders, 12–16px radii for narrative cards, pills for primary actions, shadows only on floating layers. Grid-and-glow atmosphere only on the Overview hero and the auth panel.
- **Motion.** 150 / 220 / 420ms with one easing curve; entrance reveals and the side-sheet slide only. Nothing animates on prices. `prefers-reduced-motion` disables everything.
- **New primitives:**
  - `SourceTag`: six provenance kinds — Live, Historical, Model output, Your input, Simulated, Not connected
  - `SectionHeading`
  - `SideSheet` (native `<dialog>`)
  - `Markdown`: safe; no `innerHTML`
  - `Button` `pill` / `lg` / `trailingIcon`, and `buttonClasses()` for links

---

## 4. What changed, module by module

### 4.1 Application shell and navigation

**Changed:**

- Navigation is regrouped by workflow:
  - **Overview**
  - Research: Workspace, Signals, Assistant
  - Risk & monitoring: Capital & risk, Alerts
  - Review: Insights
  - Market intelligence: Community
- New brand glyph: gold observed candles plus a violet dashed forecast node. Tagline "Gold & FX research".
- Shortcuts `g o`, `g r`, `g p` were added. The command palette and help dialog pick them up automatically.
- Top bar at 1024–1439px: the market status collapses to a compact "Demo data" pill, so the demo indicator stays visible at every width.
- Gold (XAU/USD, 1h) is now the default instrument for **new** workspaces. Existing saved workspaces are untouched.

### 4.2 Overview: new landing page (`/overview`; `/` redirects here)

- **Hero.** Editorial headline, one-paragraph purpose, primary CTA "Open XAU/USD workspace", secondary "Plan a trade". A status line shows data source, feed state, FX session and the UTC clock.
- **Research card.** A live-updating chart of the last 72 gold closes (simulated in demo mode and labelled so). It shows:
  - the **NOW** boundary
  - the model's TP / entry / SL levels
  - the projected path **only if the model supplied one**, never extended beyond its points

  The direction, probability and R : R are shown under the chart.
- **Seven modules.** Numbered cards: name, the question each answers, summary, and an **honest status** derived from the data source. An eighth card states "What it never does".
- **Where things stand. With sources.** Four cards, each tagged with its provenance:
  - gold across 15m/1h/4h
  - your risk budget (remaining permitted risk + daily-limit meter, or an explanation that no capital is set)
  - signals matching your profile
  - model track record (hit rate, Brier score, with definitions and sample size)

### 4.3 Workspace

- The AI panel gains:
  - **What could invalidate it**: the stop zone, horizon expiry, validity window, timeframes that disagree, factors already against the setup
  - **What is missing** (collapsible): simulated model, no confidence band, no projected path, no EV, stale data, no news/calendar…
- **Size this trade** opens Capital & risk with the model plan (zone midpoints) prefilled and labelled "Model output".
- **Ask about it** (or the bot icon) opens the assistant in a right-hand side sheet with the workspace's live context, including the feed status.
- These notes come from `domain/research.ts`, shared with the assistant, so the panel and the assistant never contradict each other.

### 4.4 Capital & risk (new, `/risk`): fully working

**Inputs.** All are user-owned and saved in the browser:

- account capital and currency (8 currencies)
- max risk per trade, daily loss limit, max aggregate open risk, max concurrent positions
- current exposure, **reported by the user**: open risk, loss realised today, open positions. The platform never tracks trades.
- optional broker specification: contract size per instrument, volume step

**Planner.** Instrument, entry, stop-loss, optional target, risk %. "Use model plan" loads the current model output for a chosen timeframe. State lives in the URL, so links prefill it.

**Outputs:**

- position size in **base units** (ounces of gold, currency units), which needs no broker data
- **lots** only when the user has entered a contract size, rounded **down** to their volume step; money at risk is recomputed for the rounded size
- money at risk and % of capital; potential reward; R : R; stop distance
- notional value; margin is deliberately not shown because it needs leverage
- a to-scale stop → entry → target ladder with money at each end
- "How this is calculated", with the actual numbers

**Currency conversion without guessing:**

| Case | Rule |
| --- | --- |
| Quote currency = account currency | No conversion |
| Base currency = account currency | Exact conversion at the exit price (stop or target) |
| Otherwise | The user must enter the rate; sizing is withheld until they do |

**Limits.** Four meters: used → with this trade → limit. Status is always given in words + icon (Within limit / Near limit ≥ 80 % / Breach). "Remaining permitted risk" names the binding limit.

**States:**

- **Incomplete:** nothing is calculated; every missing input is listed
- **Invalid:** e.g. target on the wrong side, stop = entry, risk > 100 %
- First-time users on phones see the profile form first

**Worked example (verified in the browser and in e2e).** Capital $25,000, 1 % risk:

1. Gold entry 2,240, stop 2,228 → budget $250 ÷ $12 = 20.83 oz = 0.2083 lots → **0.20 lots → 20 oz → $240 at risk (0.96 %)**.
2. Reward to 2,270 = **$600**, R : R 1 : 2.5.
3. Daily check: 120 + 300 + 240 = 660 of a 750 limit → **Near limit**.

### 4.5 Personalised signals (`/signals`)

- **For you / All analyses** tabs with counts; "For you" is the default. 16 of 24 demo analyses fall outside the default profile, and that is shown.
- **Saved profile** (edit dialog):
  - instruments, timeframes, directions
  - minimum probability (the model's defined P(TP before SL))
  - minimum R : R
  - "only show setups that fit my risk limits"
- **Checks per signal.** Data quality (detected, within validity) · preferences (each with the actual values: "Model probability 55% vs your minimum 60%") · risk (sizable; within daily / aggregate / position limits). Risk checks are "not evaluated", never guessed, until capital is set.
- **Provenance sheet** with five numbered steps: what the model returned → your preferences → your risk limits → data quality → evidence → timing and model version. Actions: open in workspace, size this trade, ask the assistant.
- An empty "For you" list is presented as a valid answer, not an error.
- **Phones:** card layout (resolves known issue #13). **1280px:** secondary columns move into the sheet so row actions stay visible.

### 4.6 AI assistant (new, `/assistant` + workspace side sheet)

- **Provider-agnostic boundary.** `AssistantService.reply(messages, context)`.
  - The API implementation posts to the proposed `/assistant/replies`.
  - The backend owns the model and its keys; **no secret reaches the browser**.
- **The context is explicit.** Chips show exactly what the assistant may use (instrument/timeframe, last price, model output, other timeframes, risk profile). Sharing the risk profile is a switch: on by default in demo mode, off in API mode.
- **Demo = rule-based evidence composer, labelled as such** on the badge and on every reply ("rule-based, not a language model"). It answers seven question types only from the context:
  - explain the analysis
  - what would invalidate it
  - size the risk (with the same domain code as the Risk page)
  - compare timeframes
  - summarise the evidence
  - what is missing
  - define a term

  Anything else gets an honest list of what it can do.
- **UX.** Suggested prompts (always available as chips) · Markdown tables · "composing" state with **Stop** · error with **Retry** · **Clear** · history kept in this browser.

### 4.7 Sign-in and registration

- **Layout.** Editorial split: "Evidence before *conviction.*", a restrained market motif labelled "Illustration — not market data", three principles. The form side has a pill switch between Sign in and Create account (real links, so Back works).
- **Fields.** 44px inputs, password **visibility toggle**, **Caps Lock** warning, inline validation.
- **Registration.** **Strength meter** whose required rules mirror the backend exactly (8–128 characters, a letter and a digit), plus advice-only rules. Terms acknowledgement.
- **"Forgot password?"** says honestly that recovery is not available: no reset endpoint exists; demo mode has no stored password.
- **Real backend alignment** (`services/api`):
  - login → `TokenPair` → `GET /users/me`
  - register (`full_name`) → login
  - logout revokes the refresh token
  - FastAPI `{detail}` errors are parsed; 409 becomes an email field error
  - wrong credentials are no longer reported as "session expired"
  - default base URL is `/api/v1`
  - all of this is unit-tested against the backend's exact shapes

### 4.8 Insights

- Module eyebrow.
- New "How these metrics are defined" panel covering predictions, hit rate, mean predicted, calibration gap, Brier score and realised R, with source and time window.

---

## 5. Implementation report (files)

**New (32 files)**

| Layer | Files |
| --- | --- |
| Domain (pure, tested) | `src/domain/risk.ts`, `risk.test.ts`, `signalProfile.ts`, `research.ts`, `assistant.ts` |
| Services | `src/services/demo/assistant.ts` (+ `assistant.test.ts`) |
| Features | `features/overview/{OverviewPage,ResearchChart}.tsx` · `features/risk/{RiskPage,TradePlanner,ProfileForm,LimitMeter}.tsx`, `limitStatus.ts`, `parse.ts` (+ test) · `features/assistant/{AssistantPage,AssistantPanel}.tsx`, `useAssistantThread.ts`, `useAssistantContext.ts` · `features/signals/{SignalDetail,SignalProfileDialog}.tsx` · `features/auth/PasswordInput.tsx` |
| UI primitives | `components/ui/{SourceTag,SideSheet,Markdown}.tsx`, `buttonClasses.ts`, `markdownParser.ts` |
| Tests and tools | `e2e/round3.spec.ts`, `scripts/qa-page.mjs`, `scripts/contrast.mjs` |
| Docs | `docs/GOAI_REFERENCE_ANALYSIS.md` |

**Modified (54 files)**

| Area | Files |
| --- | --- |
| Tokens and global CSS | `tokens.css`, `index.css` |
| Fonts | `main.tsx` + one new dependency `@fontsource/instrument-serif` (OFL-1.1) |
| Shell | `navigation.ts`, `Sidebar.tsx`, `TopBar.tsx`, `AuthLayout.tsx`, `BrandMark.tsx`, `router.tsx` |
| UI | `Button.tsx`, `Badge.tsx`, `Dialog.tsx`, `Form.tsx`, `Panel.tsx` |
| Preferences | `preferences.ts`, `preferencesStore.ts` (backward-compatible defaults), `contexts.ts`, `AppProviders.tsx` |
| Pages | Signals, Workspace, OpportunityPanel, Insights, Login, Register, AuthCard, auth `schemas.ts` |
| Services | `types.ts`, `demo/index.ts`, `api/index.ts`, `api/http.ts`, `api/endpoints.ts`, `schemas.ts`, `errors.ts`, `config.ts` |
| Formatting | `format.ts` (+ money, units and percent formatters) |
| Tests | `services.test.ts`, `format.test.ts`, `validation.test.ts`, `e2e/app.spec.ts`, `e2e/fixtures.ts` |
| Docs | README, ARCHITECTURE, DESIGN_SYSTEM, API_INTEGRATION, KNOWN_ISSUES, PROGRESS, DEPLOYMENT, IMPLEMENTATION_PLAN, THIRD_PARTY_NOTICES, `.env.example` |

**Architecture preserved:**

- The UI depends only on service interfaces.
- Business rules live in `domain/` with no React.
- Demo and API remain interchangeable strategies.
- No `any`, no disabled lint rules and no deleted tests.

**Deliberate behaviour changes:**

- `/` → `/overview`; sign-in/registration land on `/overview`. Two e2e expectations were updated to match.
- Default instrument for new workspaces: XAU/USD 1h.

---

## 6. Verification results

Final run on 16 October 2026: Windows 11, Node 24.15, pnpm 10.28, local Google Chrome. Commands run from `web/`.

| Check | Command | Result |
| --- | --- | --- |
| Baseline before changes | `pnpm typecheck / lint / test / build` | 0 errors · 0 problems · 67 / 67 · build OK |
| Type check | `pnpm typecheck` | ✅ 0 errors (strict, `noUncheckedIndexedAccess`) |
| Lint | `pnpm lint` | ✅ 0 errors, 0 warnings |
| Unit and component tests | `pnpm test` | ✅ **107 / 107** in 12 files (was 67 / 67). New: risk/limits/signal checks (20), assistant composer + Markdown (11), FastAPI auth contract (4), input parsing (3), password rules, money formatting. |
| Production build | `pnpm build` | ✅ Built in 15 s. Gzip: main 90 KB (was 71 KB: shell + workspace now include the side sheet and assistant panel), React 100 KB, charts 57 KB. New lazy chunks: Overview 5.8 KB, Risk 7.4 KB, Signals 7.7 KB. |
| Browser tests (flows + axe WCAG 2.1 AA in both themes + visual matrix: 13 routes × 5 widths × 2 themes, asserting no horizontal overflow and no console errors) | `pnpm e2e` | ✅ **54 / 54** in 3.6 min: 10 original flows + 7 new round-3 flows, 26 axe scans (13 routes × 2 themes, 0 serious/critical), keyboard test, 10 visual-matrix runs (0 px overflow, 0 console errors) |
| Contrast | `node scripts/contrast.mjs` | All rendered pairs ≥ 4.5:1 (§3) |

**Defects found by QA during this round and fixed:**

| Found by | Defect | Fix |
| --- | --- | --- |
| axe | Overview "Model track record" placed a `<p>` inside a `<dl>` (`definition-list`) | Moved outside the list |
| Visual review | Risk profile column was sticky but taller than the viewport, so its bottom could not be reached | Sticky removed |
| Visual review | At 1024–1280px the top bar crowded ("Sign in" wrapped) | Market status from 1440px; compact demo pill below that |
| Visual review | Signals row actions clipped at 1280px | Entry zone, setup and meter move to ≥ 1440px / the sheet |
| Visual review | Mobile signal profile badges overflowed | Grid layout with truncating badges |
| Visual review | Signals "7/8 passed" read like a failure when one check was merely not evaluated | Now "Passed · risk n/a" |
| Code review | `Input` hard-coded `h-9`, so caller heights conflicted | Height became an overridable default |
| Code review | Block-quote parser in the Markdown renderer could loop forever | Index advances; covered by tests |
| Unit test | My own test expected 50 where 0 was correct (daily limit already exceeded) | Test corrected; code was right |
| Contract review | API mode showed "session expired" for a wrong password, ignored FastAPI `{detail}` errors, used the wrong base path | Adapter and error parser fixed, with tests |

**Not run, stated plainly:**

- **No end-to-end run against a live FastAPI + Postgres + Redis stack.** The Docker stack was not started. Auth is verified by contract tests using the backend's exact schemas.
- **No screen-reader session** (NVDA / VoiceOver). Accessibility is covered by axe, keyboard tests and semantic markup only.

---

## 7. Before / after screenshots

| Folder | Contents |
| --- | --- |
| `screenshots/before/` | Round-2 state, same code as this branch's starting point. Captured 15 Oct by the previous QA run. |
| `screenshots/after/` | This round. Captured 16 Oct from the running app, demo mode, with an example risk profile (capital $25,000). |
| `screenshots/reference-goai/` | Third-party reference captures, for analysis only. **Not our product.** |

| Screen | Before | After |
| --- | --- | --- |
| Landing / overview | — (redirected to workspace) | `after/dark-01-overview-hero.png`, `dark-02-overview-full.png`, `light-01…`, `light-02…` |
| Workspace | `before/dark-1440_workspace.png`, `light-1440_workspace.png` | `after/dark-03-workspace.png`, `light-03-workspace.png`, `dark-04-workspace-assistant-sheet.png` |
| Capital & risk | — (did not exist) | `after/dark-05-risk.png`, `light-05-risk.png` |
| Signals | `before/dark-1440_signals.png` | `after/dark-06-signals.png`, `dark-07-signal-provenance.png`, `light-06-signals.png` |
| AI assistant | — (did not exist) | `after/dark-08-assistant.png`, `light-08-assistant.png` |
| Insights | `before/dark-1440_insights.png` | `after/dark-09-insights.png` |
| Settings | `before/dark-1440_settings.png` | `after/dark-10-settings.png` |
| Sign in | `before/dark-1440_login.png`, `light-1440_login.png` | `after/dark-11-sign-in.png`, `light-11-sign-in.png` |
| Register | `before/dark-1440_register.png` | `after/dark-12-register.png` |
| Mobile | `before/dark-390_workspace.png`, `dark-390_signals.png` | `after/mobile-01…07` (overview, navigation, workspace, risk, signals, assistant, sign-in) |

The full automated matrix (130 screenshots) is regenerated by `pnpm e2e` into `web/qa-screenshots/matrix/`, which is git-ignored.

---

## 8. Honesty rules: demo-only vs real

| Feature | Status |
| --- | --- |
| Capital & risk calculations and limit checks | **Real and complete.** Pure client-side maths on the user's own inputs, unit-tested. Exposure figures are user-reported. |
| Personalised filtering and checks | **Real logic.** In demo mode it runs on simulated model outputs. |
| Prices, candles, quotes | **Simulated** in demo mode (labelled everywhere) |
| Model outputs: opportunities, factors, projections | **Simulated** by a browser heuristic (labelled; "not SHAP output of the real model") |
| Prediction history and statistics | **Simulated** outcomes (explicit banner on Insights) |
| AI assistant | **Demo: rule-based, not a language model** (labelled on every reply). No LLM is connected. |
| Sign-in / registration | **Demo session** in demo mode. API mode is aligned with the real FastAPI auth but was not run live this round. |
| Password recovery | **Not available.** No backend endpoint; stated in the UI. |
| Risk / signal profiles, assistant history | Stored **in this browser only** |
| Trade execution | **Never.** No execution controls exist anywhere. |

---

## 9. Known limitations and backend dependencies

Details are in `web/docs/KNOWN_ISSUES.md` #23–31.

**Backend needed:**

- market data, model outputs and prediction-history endpoints (proposed)
- `POST /assistant/replies` plus a server-side model provider
- `/me/risk-profile` and `/me/signal-profile`
- `/instruments` with broker specifications

**Auth:**

- `/auth/refresh` is not used yet, so the session ends at the 30-minute access-token expiry
- tokens sit in localStorage; an HttpOnly-cookie flow would be safer

**Design limitations, by intent:**

- lots need a user-entered contract size
- cross-currency sizing needs a user-entered rate
- margin is not computed
- the daily-loss check is a stated worst case

**Pre-existing:**

- DST is not modelled in sessions
- the canvas chart has a text summary but no data-table alternative

---

## 10. Prioritised next steps

1. **Run against the live backend.** `docker compose up`, `VITE_DATA_SOURCE=api`. Then add silent token refresh via `/auth/refresh`, or move to HttpOnly cookies.
2. **Connect a real assistant.** Implement `POST /assistant/replies` on the backend with a provider and the context contract in `API_INTEGRATION.md` §7; consider SSE streaming. The UI needs no change.
3. **Persist profiles server-side** (`/me/risk-profile`, `/me/signal-profile`). Optionally serve broker specifications from `/instruments`, so lots work without user input.
4. **Model integration.** Real Feature 12 outputs. The confidence band and projection render automatically when supplied.
5. **Notifications from the signal profile.** Reuse `evaluateSignal()` for SF2 notifications, so alerts match "For you" exactly.
6. **Polish:**
   - Settings in-page navigation (R6)
   - chart data-table alternative for screen readers
   - a moderated user test with traders
