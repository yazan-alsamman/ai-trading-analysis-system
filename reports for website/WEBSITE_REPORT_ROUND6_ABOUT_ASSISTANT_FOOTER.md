# AI Trading Assistance — Round 6 Report

**About page, public-site content, research assistant and complete footer**

| | |
| --- | --- |
| Date | 17 October 2026 |
| Scope | **Frontend only** (`web/`). No backend, API, database, auth, payment, AI-provider, infrastructure or deployment change. |
| Branch | `e/web-client`, with `origin/main` merged (backend PRs #18–#25); pushed, which updates PR #4 |
| Technical write-up | `web/docs/PUBLIC_SITE_CONTENT.md` |
| Previous round | `WEBSITE_REPORT_ROUND5_CINEMATIC.md` |

---

## 1. Summary

| Outcome | Result |
| --- | --- |
| **About page** (`/about`) | Eight sections that answer, in order: who we are, the problem, what the platform does, how it works, how AI is used, risk and uncertainty, who it is for, and what to do next. The copy is written from the real product. Every capability shows its real status (Works now / Demo data / Needs backend). |
| **Public website** | A new landing scene, **Anatomy of a setup**: a structured signal preview, entry, stop and target zones shown in their price structure, profile checks, and a market-context panel with clearly labelled sample items. Navigation now includes About and Assistant. |
| **Research assistant** | A public page (`/ai-assistant`) and a floating launcher on the story pages. Answers are **structured cards** (kind, answer, a separate simulated-data callout, what was used, next research steps), shared with the in-app assistant. It is still the **rule-based demo** and says so everywhere. |
| **Footer** | Brand and calls to action, four groups of verified links, an app-download area ("coming soon" — no app is published), an honest social state (no accounts exist), the risk disclaimer, footage credits and two new legal pages. |

---

## 2. What is real, and what is not claimed

Established by inspecting the repository before writing any copy:

| Topic | Finding | How the site handles it |
| --- | --- | --- |
| Mobile apps | `mobile/` contains only a README; no app, store listing or app ID | "Android · coming soon", "iOS · coming soon". No badges, links or QR code. One config file to update (`src/config/externalLinks.ts`). |
| Social accounts | None referenced anywhere | "None announced yet." Nothing is linked. |
| Contact, terms, privacy | None exist | Not linked. The footer says terms and privacy are in preparation. A data-storage page documents what the browser keeps. |
| News | The backend now ingests RSS news (`GET /news`); the web client is not connected | Market context shows items labelled **Sample content**, and the page explains why |
| Assistant | A rule-based composer; no LLM, no provider | Labelled *Rule-based demo — not a language model*. It runs only in the browser. |
| Performance | No verified live results | Unchanged: "No verified live results exist yet" |
| Company facts | No founders, history, location or regulation in the project | None stated. The About page explains the platform, not an invented company. |
| New backend subscriptions | Expert subscriptions with **demo payments**, not platform membership | Membership still shows "Pricing to be announced"; the dependencies doc explains the difference |

---

## 3. Files

**New:**

- Pages:
  - `marketing/pages/AboutPage.tsx`
  - `marketing/pages/AssistantPublicPage.tsx`
  - `marketing/pages/LegalPages.tsx` (risk disclosure, data storage)
- Assistant:
  - `marketing/assistant/showcaseAssistant.ts`
  - `marketing/assistant/PublicAssistant.tsx`
  - `marketing/assistant/AssistantLauncher.tsx`
  - `features/assistant/ReplyCard.tsx`
  - `features/assistant/replyText.ts`
- Landing and footer:
  - `marketing/sections/AnatomySection.tsx`
  - `marketing/layout/PublicFooter.tsx`
  - `config/externalLinks.ts`
- Tests:
  - `marketing/round6.test.tsx`
  - `e2e/round6.spec.ts`
- Docs: `web/docs/PUBLIC_SITE_CONTENT.md`

**Changed:**

- Assistant:
  - `domain/assistant.ts`: reply `kind`, prompt groups, next steps
  - `services/demo/assistant.ts`: sets `kind`
  - `features/assistant/useAssistantThread.ts`: injectable service and storage key; an empty thread leaves nothing stored
  - `features/assistant/AssistantPanel.tsx`: grouped prompts, reply cards, configurable share switch
- Public site:
  - `marketing/content.ts`: navigation and footer groups
  - `marketing/layout/PublicLayout.tsx`: new footer and launcher
  - `app/router.tsx`: four public routes
  - `vite.config.ts`: sitemap routes
  - `marketing/pages/LandingPage.tsx`, `sections/AssistantScene.tsx`, `sections/RiskSection.tsx` (gauge exported), and eyebrow renumbering
  - `styles/cinematic.css`: workflow travelling point
- Tests:
  - `e2e/fixtures.ts`: new routes, `atTime` / `WEEKDAY` / `WEEKEND`
  - `e2e/app.spec.ts`, `e2e/round3.spec.ts`
- Docs:
  - `web/docs/FRONTEND_BACKEND_DEPENDENCIES.md`
  - `web/docs/KNOWN_ISSUES.md` (#42–47)
  - `web/docs/PROGRESS.md`
- Repo: `.github/workflows/ci.yml` (merge resolution: the `web`, `api-contract` and `e2e` jobs are all kept)

---

## 4. Verification

| Check | Result |
| --- | --- |
| Type check | ✅ 0 errors |
| Lint | ✅ 0 errors, 0 warnings |
| Unit / component | ✅ **152 / 152** in 16 files (was 142). New: 10 in `round6.test.tsx`. |
| Build | ✅ Main chunk 113 KB gzip (was 108: the anatomy scene and footer). The launcher's assistant loads only when opened. About 9.3 KB, legal 3.3 KB and the assistant page 2 KB, all lazy. |
| **Playwright** | ✅ **89 / 89**, run in four chunks on one worker to stay within memory |

**Playwright results by spec:**

| Spec | Result |
| --- | --- |
| a11y (19 routes × 2 themes + keyboard) | 39 / 39 |
| visual matrix (19 routes × 5 widths × 2 themes; overflow and console errors) | 10 / 10 |
| app | 11 / 11 |
| round 3 | 7 / 7 |
| round 4 | 6 / 6 |
| round 5 | 9 / 9 |
| round 6 | 7 / 7 |

**Round 5's three unexplained failures are resolved.** They were not caused by memory. The demo market
follows real FX hours, and both runs happened on a **Saturday**: the app correctly showed "Market
closed (weekend)" with no live signals, and three older tests assumed a weekday. Those tests now pin
the browser clock to a weekday, and a new test asserts the weekend behaviour.

**Browser QA.** Screenshots are in `screenshots/round6/`. Covered:

- the About page at every section
- the assistant (empty, pending, answer, follow-up thread)
- the launcher sheet
- the anatomy scene
- the footer and the legal pages
- dark and light themes, 1440 and 390 px, and reduced motion

Results: all 22 footer links resolve to real pages and anchors; 0 console errors, 0 failed requests,
0 overflow.

**Defects found and fixed this round:**

| Defect | Fix |
| --- | --- |
| New pages had doubled titles ("About · AI Trading Assistance · AI Trading Assistance") | `useDocumentMeta` already adds the brand; titles corrected |
| Anatomy chart: zones squeezed into the right edge; the "risk" label collided with "Entry" | History takes 70 % of the width; zones extend after the signal candle; labels relaxed |
| "Clear conversation" left an empty list in storage | An empty conversation now removes its key |
| The launcher put the whole assistant into the first paint | Its content is lazy-loaded |
| The footer's "coming soon" tiles used `aria-label` on a plain `span` | Visible text plus screen-reader text |

---

## 5. Remaining work

1. **Legal:** terms of service and a privacy policy (needs a legal entity and review).
2. **Publish the apps,** then set `APP_STORES` URLs; add official social profiles and a contact address
   when they exist.
3. **Connect `/news`** to the market-context panel and Community → News, replacing the sample items.
4. **A real assistant provider** behind `POST /assistant/replies`. The UI, reply kinds and boundary
   are ready.
5. Safari, Firefox and physical-device testing (carried over).
