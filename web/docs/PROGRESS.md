# Progress

_Last updated: 16 October 2026 (round 4: cinematic public website, motion system, membership)_

## Current stage

| Round | Status |
| --- | --- |
| **Round 1** — Phases 1–6: foundation, workspace, core features, integration readiness, QA | ✅ Complete |
| **Round 2** — premium product transformation | ✅ §1 audit, §2 identity, §3A shell and §3B workspace implemented and verified; the remaining routes improved |
| **Round 3** — GO AI-inspired product experience | ✅ Reference research, new identity, Overview, Capital & risk, Personalised signals, AI assistant (demo boundary), auth redesign, FastAPI auth alignment. Results: `../reports for website/WEBSITE_REDESIGN_REPORT.md` |

The round-2 brief was received **truncated** (it ends inside §3B). The rest of the brief (further sections and feature expansion) has not yet been received.

## Backend integration (18 October 2026)

| Area | Delivered |
| --- | --- |
| Sync | `main` fast-forwarded to `07b3d11`; branch `e/backend-integration` |
| API layer | Verified endpoints (29 REST + WebSocket), backend schemas and mappers, token manager (rotation-safe refresh), shared WebSocket, same-origin config + dev proxy |
| Connected | Auth and session restore, profile and password, candles and streaming, strategy signals, risk profile sync and server cross-check, price alerts, notification inbox, news, posts, comments, experts, chat |
| Not available (backend) | AI model output, prediction history, assistant provider, platform membership, password reset (gap analysis) |
| Docs | `BACKEND_INTEGRATION_REPORT.md`, `BACKEND_INTEGRATION_SETUP.md`, `BACKEND_INTEGRATION_GAP_ANALYSIS.md` |
| Tests | 198 unit/contract · 98 Playwright (89 demo + 9 backend-mode vs contract mock) · **live**: 29 API checks + 12 browser tests against the running backend; backend suite 655/655 |

## Round 6 — About, public content, assistant, footer (17 October 2026)

| Area | Delivered |
| --- | --- |
| Integration | Merged `origin/main` (backend PRs #18–#25); one CI-workflow conflict resolved by keeping all jobs |
| About | `/about`: eight sections from the real product (status-labelled capabilities, workflow, approach to AI, risk/uncertainty, audience) |
| Landing | New "Anatomy of a setup" scene (signal, entry/stop/target zones in context, checks, labelled sample market context) |
| Assistant | Public `/ai-assistant` page + floating launcher (rule-based showcase assistant); structured reply cards with next research steps, shared with the app |
| Footer | Complete footer: CTAs, four link groups (all verified), app-download "coming soon", social state, legal links, credits; `src/config/externalLinks.ts` |
| Legal | `/legal/risk-disclosure`, `/legal/data-storage` |
| Docs | `docs/PUBLIC_SITE_CONTENT.md`; dependencies updated for the new backend news / expert-subscription services |
| Tests | 152 unit · **89 / 89 Playwright** (run in chunks; weekend-dependent tests fixed) |

## Round 5 — cinematic motion (17 October 2026)

| Area | Delivered |
| --- | --- |
| Footage | Six licensed loops (Coverr, Mixkit Free), 1.9 MB, self-hosted; `CinematicVideo` (on-screen only, posters for reduced motion, Save-Data and phones); `scripts/build-media.sh` |
| Scenes | Hero with real footage and a self-drawing chart with ambient scan; A in depth; CSS-3D workspace laptop; B data packet; C ends in a structured research plan; D exposure gauge and cause → effect; E violet assistant scene; F reliability diagram; G tilt and spotlight; H cinematic close |
| Transitions | Selected plan → sign-up summary shared element |
| Docs | `docs/CINEMATIC_MOTION_IMPLEMENTATION.md`; report `../reports for website/WEBSITE_REPORT_ROUND5_CINEMATIC.md` |
| Tests | 142 unit/component (all green). Playwright run stopped for low memory: 60 passed (incl. 9/9 new), 3 unconfirmed failures in untouched app routes, visual matrix incomplete. **Re-run needed.** |

## Round 4 — delivered (16 October 2026)

| Area | Delivered |
| --- | --- |
| Motion system | `src/motion/` + `styles/motion.css` (no new dependency); `docs/MOTION_DESIGN_DIRECTION.md` |
| Public website `/` | Cinematic hero, pinned sequences A–C, risk demo, signals + assistant, evidence + methodology, membership preview, FAQ, final CTA, footer |
| Membership | `/membership`, `/welcome`, plan journey through auth, demo plan preview + `PlanGate`; `docs/MEMBERSHIP_FRONTEND_SPEC.md` |
| Auth | Animated motif, sliding switch, view transitions, plan summary and progress |
| SEO | Per-page meta / OG / canonical, app pages `noindex`, `robots.txt`, conditional `sitemap.xml` |
| Integration | Merged `origin/main`; `docs/FRONTEND_BACKEND_DEPENDENCIES.md` |
| Tests | 128 unit/component · 64 Playwright (all green) |

## Round 3 — delivered (16 October 2026)

| Area | Delivered |
| --- | --- |
| Research | `docs/GOAI_REFERENCE_ANALYSIS.md`: goai.global inspected in real Chrome (desktop, mobile, menus, calculator, module pages, login) |
| Identity | "Ink, Aurum and Violet" tokens (both themes, contrast measured), Instrument Serif display type, mono eyebrows, inverted pill primary, `SourceTag` provenance vocabulary, `SideSheet`, `Markdown` |
| Overview (new, landing) | Editorial hero, live gold research card (observed / NOW / model levels / projection only if supplied), seven-module workflow with honest status, "today" cards with sources and definitions |
| Capital & risk (new) | Position size, money at risk, reward, R : R, notional, limit meters (per trade, daily, aggregate, positions), remaining permitted risk. Missing inputs are named, never guessed. Model plan can be loaded. |
| Personalised signals | Saved signal profile, "For you" / "All", per-signal checks, provenance sheet, sizing link, phone card layout |
| AI assistant (new) | Provider-agnostic service; rule-based demo labelled as such; context chips; share-risk toggle; cancel / retry / clear; workspace side sheet |
| Workspace | AI panel: "What could invalidate it", "What is missing", "Size this trade", "Ask about it" |
| Auth | Editorial split layout, password visibility, Caps Lock warning, strength meter matching backend rules, honest password-recovery note; API adapter aligned with the FastAPI `/api/v1` auth contract |
| Insights | Module eyebrow; metric definitions (meaning, calculation, source, window) |
| Tests | 107 unit/component tests (from 67); new e2e flows for Overview, Risk, Signals, Assistant, Workspace, Register; three new routes in the axe and visual matrices |

## Round 2 — delivered

### Audit

`docs/DESIGN_AUDIT.md` lists 21 findings, each with evidence, from the source and 100 baseline screenshots (archived in `qa-screenshots/before/`).

### Identity

| Area | Delivered |
| --- | --- |
| Brand | New brand glyph and wordmark ("observed candles → violet forecast"), favicon |
| Surfaces | Midnight-navy layered dark theme; contrast re-measured |
| Page frame | Shared `Page` frame and compact page headers |

### Shell

| Area | Delivered |
| --- | --- |
| Navigation | Grouped by task (Trade / Monitor / Connect) with shortcut hints |
| Top bar | Breadcrumb; global market status (session, UTC clock, demo indicator) |
| Sidebar | Session board for the four major FX sessions |
| Notification centre | Fed by a **working demo alert monitor**: alerts fire when the simulated price crosses them, are marked triggered, raise a toast and can be re-armed |
| Keyboard | `?` dialog, `g`-chords, `t` theme |
| Demo banner | Dismissible per session; the persistent labels remain |

### Workspace

| Area | Delivered |
| --- | --- |
| Header | Ticker strip with 24h range bar, session, AI verdict and timeframe agreement |
| Watchlist | Sparklines and per-pair AI direction/probability |
| AI panel | Rebuilt: verdict, metric grid, to-scale trade-plan ladder, **timeframe alignment** (15m / 1h / 4h), collapsible provenance |
| Toolbar & chart | Quieter AI toggles; slimmer volume |
| Keyboard | `1/2/3`, `[` `]`, `z`, `f` |

### Other routes

| Route | Delivered |
| --- | --- |
| Signals | Summary band (long/short, top probability, mean, all-timeframe-aligned pairs) |
| Insights | Cumulative-result chart |
| News | Filters |
| Sign in / Register | Identity panel |
| All | Consistent page widths |

### Verification (final run)

| Check | Result |
| --- | --- |
| Type check | 0 errors |
| Lint | 0 problems |
| Unit / component tests | **67 / 67** |
| Build | ✅ app 71 KB gzip |
| Playwright | **41 / 41**: 10 flows, 21 accessibility (0 serious/critical), 10 visual-matrix runs with 0 overflow and 0 console errors |
| Defects caught by QA this round | Invalid `dl` nesting in the metric grid (axe) — fixed |

## Next steps

1. Run the client against the live FastAPI stack (`docker compose up`) and use `/auth/refresh` before access-token expiry.
2. Backend endpoints for the risk/signal profiles and `/assistant/replies` (API_INTEGRATION.md §7).
3. Settings in-page section navigation (DESIGN_AUDIT R6).
3. Backend integration (API_INTEGRATION.md §4 and §6) — still blocked on the backend team.
4. Trader testing per the work plan.

## Blockers

| Blocker | Waiting on |
| --- | --- |
| Real data, auth, server notifications, chat, workspace sync | Backend API |
| Final Feature 12 output fields | AI team |
| Role permissions | Use-case diagrams |
