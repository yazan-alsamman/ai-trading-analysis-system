# AI Trading Assistance — Web Client

The website for **AI Trading Assistance**, a graduation project: an AI-assisted Forex analysis and decision-support platform for experienced traders.

> **Analysis only.** The platform shows market data, AI opportunity analysis, prediction statistics and community features. It is **not a broker**, never places, modifies or closes trades, and never promises profit.

Owner (website): **Elias**. Backend: Yazan & Rami (FastAPI). AI: Yazan, Rami, Fadi. Mobile: Batoul.

---

## Quick start

Requirements: **Node.js ≥ 20** (developed on 24) and **pnpm 10**.

```bash
pnpm install        # install dependencies
pnpm dev            # http://localhost:5173 — demo mode, no backend needed
```

The app opens in **demo mode**:

- Prices, AI opportunities, statistics and community content are generated in the browser.
- All of it is labelled **Simulated / Demo / Sample** in the UI.

Copy `.env.example` to `.env.local` to change the configuration (see below).

## Commands

| Command | What it does |
| --- | --- |
| `pnpm dev` | Development server with hot reload (port 5173) |
| `pnpm build` | Type-check (`tsc -b`) and production build into `dist/` |
| `pnpm preview` | Serve the production build (port 4173) |
| `pnpm typecheck` | Strict TypeScript check only |
| `pnpm lint` | ESLint (TypeScript strict rules + React hooks) |
| `pnpm test` | Unit and component tests (Vitest + Testing Library) |
| `pnpm e2e` | Browser tests in local Google Chrome: flows, accessibility (axe), visual matrix |
| `pnpm check` | typecheck + lint + test + build — run before every commit |
| `node scripts/qa-shot.mjs workspace 390,1440 dark,light` | Screenshot one route at the given widths and themes (needs `pnpm dev` running) |
| `node scripts/qa-page.mjs overview,risk 1440,390 dark,light` | Whole-page screenshots (grows the viewport to the content height); `BASE_URL`, `PREFS_PATCH` |
| `node scripts/contrast.mjs` | WCAG contrast table for the palette |

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_DATA_SOURCE` | `demo` | `demo` = simulated fixtures, `api` = FastAPI backend (auth live; other endpoints proposed) |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Backend REST base URL (API mode only) |
| `VITE_API_TIMEOUT_MS` | `10000` | Request timeout |

Invalid values fall back to demo mode, with a console warning.

## What is implemented

| Area | Route | Requirements covered |
| --- | --- | --- |
| **Public website** (no sign-in): cinematic hero, scroll-driven story (sequences A–E), risk demo, methodology, FAQ | `/` | Marketing |
| **Membership**: three configurable plans (pricing to be announced), comparison, plan fit, selection → sign-up journey, demo preview | `/membership`, `/welcome` | Membership (frontend only) |
| **Overview** (first app page): 7-module workflow with honest status, gold research card, today at a glance | `/overview` | — |
| Trading workspace: chart, watchlist, AI research panel (evidence, invalidation, missing data), assistant side sheet | `/workspace` | SF3, SF4, SF5, SF8, SF9, SF18 · AI Feature 12 |
| **Capital & risk**: position sizing, money at risk, limit checks (pure, unit-tested; no guessed broker specs) | `/risk` | Risk management |
| Personalised signals: saved profile, per-signal preference + risk checks, provenance sheet | `/signals` | AI Feature 12 |
| **AI assistant**: provider-agnostic boundary; rule-based demo answering only from visible context | `/assistant` | Assistant |
| Alerts: price alerts (CRUD) and opportunity notifications | `/alerts` | SF16, SF2, SF7 |
| Insights: prediction statistics, calibration, history | `/insights` | SF14, SF15 |
| Community: news + comments, posts, experts | `/community/*` | SF11, SF12, SF13 |
| Settings: theme, density, time zone, channels, workspaces | `/settings` | SF10, SF7, SF18 |
| Sign in / Register | `/login`, `/register` | SF17 (client boundary) |

These features are **cancelled** and deliberately not implemented: AI 13 (automated trade closing), AI 18 (AI-driven custom experience), AI 19 (automated trading), SF1 (subscribe to trades on demand) and SF6 (custom indicator code).

## Documentation

| Document | Content |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Folder structure, layers, data flow, design decisions |
| [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) | "Ink, Aurum and Violet": tokens, measured contrast, typography, motion, components, provenance vocabulary |
| [docs/GOAI_REFERENCE_ANALYSIS.md](docs/GOAI_REFERENCE_ANALYSIS.md) | Reference-site research (goai.global) and the resulting design direction |
| [docs/MOTION_DESIGN_DIRECTION.md](docs/MOTION_DESIGN_DIRECTION.md) | Motion language, tokens, sequences, performance and accessibility rules |
| [docs/MEMBERSHIP_FRONTEND_SPEC.md](docs/MEMBERSHIP_FRONTEND_SPEC.md) | Plan schema, feature matrix, selection flow, demo gating, future contracts |
| [docs/FRONTEND_BACKEND_DEPENDENCIES.md](docs/FRONTEND_BACKEND_DEPENDENCIES.md) | What is integrated, what exists on the backend but is not used yet, what is missing |
| [docs/API_INTEGRATION.md](docs/API_INTEGRATION.md) | Proposed endpoint contracts and backend dependencies |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Phases, features, acceptance criteria |
| [docs/PROGRESS.md](docs/PROGRESS.md) | What is done, current stage, next steps |
| [docs/TESTING_AND_QA.md](docs/TESTING_AND_QA.md) | Test strategy and actual results |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Local run, production build, hosting |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | Real limitations and open dependencies |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | Licence attributions |

## Development workflow

1. Work on a feature branch.
2. Run `pnpm check` (and `pnpm e2e` for UI changes).
3. Update `docs/PROGRESS.md`, and `docs/API_INTEGRATION.md` if a contract changed.
4. Never commit `.env*` files except `.env.example`.

This client lives in the `web/` folder of the project monorepo. Run every command above from `web/`. Branch and PR rules: [../docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md).
