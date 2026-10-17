# Backend integration — setup

How to run the web client against the FastAPI backend in this monorepo, locally and in production.
The design and its evidence: `BACKEND_INTEGRATION_REPORT.md`. What is not connected yet:
`BACKEND_INTEGRATION_GAP_ANALYSIS.md`.

## 1. Prerequisites

| Part | Needs |
| --- | --- |
| Web client (`web/`) | Node 24, pnpm 10.28 (`corepack enable`) |
| Backend stack (repo root) | Docker with Compose (PostgreSQL, Redis, backend, workers, Nginx). Without Docker: Python 3.12+, PostgreSQL and Redis, as in the root `README.md` ("التطوير بدون Docker"). |

## 2. Environment variables

### Web client (`web/.env.local`, from `web/.env.example`)

Everything prefixed `VITE_` is **compiled into the public bundle**. Never put a secret there.

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_DATA_SOURCE` | `demo` | `demo` = simulated data, no backend. `api` = the backend. |
| `VITE_API_BASE_URL` | `/api/v1` | REST base. Same-origin by default; an absolute URL (`https://api.example.org/api/v1`) also works. |
| `VITE_WS_URL` | derived | Market WebSocket. Default: `/ws/market` on the API's host (`ws://` or `wss://` to match). |
| `VITE_API_TIMEOUT_MS` | `10000` | Per-request timeout |
| `VITE_SITE_URL` | empty | Public origin for canonical URLs and `sitemap.xml` |
| `BACKEND_URL` | `http://localhost:8000` | **Dev machine only** (no `VITE_` prefix, never in the bundle): where `pnpm dev`/`pnpm preview` proxy `/api` and `/ws` |

### Backend (repo root `.env`, from `.env.example`). Owned by the backend team

The variables that matter for the web client:

| Variable | Why it matters to the web client |
| --- | --- |
| `CORS_ORIGINS` | Only needed when the web client is served from a **different** origin than the API. It must list exact origins; `*` is rejected by the backend. Not needed with the Vite proxy or behind one Nginx. |
| `JWT_ACCESS_MINUTES` (30) / `JWT_REFRESH_DAYS` (14) | Access-token lifetime. The client refreshes 60 s before expiry and on any 401. |
| `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` | First admin account (needed to add instruments) |
| `RATE_LIMIT_*`, `AUTH_*_PER_MINUTE`, `LOGIN_LOCKOUT_*` | The client shows 429 as "Too many requests" and never retries automatically |
| `API_DOCS_ENABLED` | Swagger UI on or off (off in production) |

Secrets such as `JWT_SECRET`, `POSTGRES_PASSWORD`, `SMTP_*` and `TELEGRAM_BOT_TOKEN` stay on the server. The web
client never needs them.

## 3. Local development

```bash
# 1. Backend stack (repo root)
cp .env.example .env            # set FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD
docker compose up --build       # API on http://localhost:8000 (health: /api/v1/health/ready)

# 2. Instruments and test candles (backend team's CLI). The candles are SYNTHETIC demo data.
docker compose exec backend python -m app.cli seed-instruments
docker compose exec backend python -m app.cli seed-demo-candles --symbol XAU/USD --source twelvedata --days 30
docker compose exec backend python -m app.cli seed-demo-candles --symbol EUR/USD --source twelvedata --days 30

# 3. Web client in backend mode (web/)
cp .env.example .env.local      # then set VITE_DATA_SOURCE=api
pnpm install
pnpm dev                        # http://localhost:5173 → proxies /api and /ws to BACKEND_URL
```

The browser talks only to `localhost:5173`; Vite forwards `/api/*` and `/ws/*` to the backend. No CORS
configuration is needed. Database migrations and seeds belong to the backend (`alembic`, `app.cli`).

### 3.1 Without Docker (Windows, no admin rights), as used for the live verification

The backend needs **PostgreSQL 16 with TimescaleDB** (its migrations create hypertables and continuous
aggregates) and **Redis** (rate limits, login lockout, the WebSocket hub, Celery). The steps below are the
exact ones used on 18 October 2026; every component is local, bound to `127.0.0.1`, and outside the repository.

```bash
# PostgreSQL 16 + TimescaleDB 2.17.2 (the version the backend CI uses), as a private copy
cp -r "/c/Program Files/PostgreSQL/16/"{bin,lib,share} $LIVE/pg16/
#   official build: github.com/timescale/timescaledb/releases/download/2.17.2/timescaledb-postgresql-16-windows-amd64.zip
cp timescaledb/*.dll $LIVE/pg16/lib/ && cp timescaledb/timescaledb.control timescaledb/*.sql $LIVE/pg16/share/extension/
$LIVE/pg16/bin/initdb -D $LIVE/pgdata -U ata --auth=trust -E UTF8 --locale=C
printf "shared_preload_libraries='timescaledb'\nlisten_addresses='127.0.0.1'\nport=55432\n" >> $LIVE/pgdata/postgresql.conf
$LIVE/pg16/bin/postgres -D $LIVE/pgdata &
psql -h 127.0.0.1 -p 55432 -U ata -d postgres -c "CREATE DATABASE trading;" -c "CREATE DATABASE trading_test;"

# Redis (portable Windows build of Redis 8.10.2, SHA-256 verified; no persistence)
redis-server --bind 127.0.0.1 --port 6390 --save "" --appendonly no &

# Backend (Python 3.12 via uv, as in CI), then migrations, seeds and the API
python -m uv venv --python 3.12 $LIVE/venv
python -m uv pip install --python $LIVE/venv/Scripts/python.exe -e ../libs/indicators -e ../libs/strategies -e ../libs/backtest
python -m uv pip install --python $LIVE/venv/Scripts/python.exe -e ".[dev]"       # in backend/
export DATABASE_URL=postgresql+asyncpg://ata@127.0.0.1:55432/trading REDIS_URL=redis://127.0.0.1:6390/0 \
       JWT_SECRET=<random> FIRST_ADMIN_EMAIL=admin@example.com FIRST_ADMIN_PASSWORD=<random>
python -m alembic upgrade head
python -m app.cli seed-instruments
python -m app.cli seed-demo-candles --symbol EUR/USD --source twelvedata --days 7    # SYNTHETIC prices
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m app.cli simulate-live --symbol EUR/USD --source twelvedata --interval 2    # optional: live WS updates (demo prices)
celery -A app.tasks worker -P solo -Q celery,notifications ; celery -A app.tasks beat   # signal engine, alerts, notifications
```

On Windows Celery needs `-P solo` (the default prefork pool is not supported there).

To use a backend on another host without the proxy, set `VITE_API_BASE_URL=https://host/api/v1`, and ask
for `http://localhost:5173` to be added to that backend's `CORS_ORIGINS`.

## 4. Production

The team's deployment (`.github/workflows/deploy.yml`, `web/Dockerfile`, `infra/nginx/default.conf`)
serves the static build at `/` and the API at `/api` and `/ws` from **one Nginx**, so the client uses
same-origin paths.

| Setting | Value for backend mode |
| --- | --- |
| `VITE_DATA_SOURCE` | `api` (currently `demo` in `deploy.yml`, not changed by this work) |
| `VITE_API_BASE_URL` | `/api/v1` (the Dockerfile's `ARG` default is `http://localhost:8000/api/v1`, so it **must** be passed) |
| `VITE_SITE_URL` | the public origin, e.g. `http://187.127.76.76:8080` |
| TLS | Required before real users sign in. Tokens are sent with every request, and the WebSocket token is in its URL. |

With `VITE_DATA_SOURCE=api` the app requires sign-in, and the panels listed in the gap analysis (G1–G6)
show "Not available yet".

## 5. Verifying connectivity

1. `curl http://<host>/api/v1/health/ready` → `{"status":"ok","checks":{"database":"ok","redis":"ok"}}`.
2. Open the app, sign in. In DevTools → Network:
   - `POST /api/v1/auth/login` → 200
   - `GET /api/v1/users/me` with `Authorization: Bearer …` → 200
   - Settings → Data source shows "Backend" and the API URL
3. Open the Workspace:
   - `GET /api/v1/market/instruments` and `…/instruments/{id}/candles?timeframe=15m` → 200
   - WS `/ws/market?token=…` sends `subscribe`
   - the chart status reads **Streaming**, with the **Backend feed** label
4. Signals: the "Strategy-engine signals" panel lists `GET /api/v1/signals`.
5. Leave a tab idle more than 30 minutes, then act. One `POST /auth/refresh` happens, then the request
   succeeds; you are not signed out.

## 6. Tests

```bash
pnpm typecheck && pnpm lint && pnpm test && pnpm build      # static checks + unit/contract tests
pnpm e2e --project=demo --workers=1                          # browser tests, demo build (port 4173)
pnpm e2e --project=api-mode --workers=1                      # browser tests, backend-mode build vs contract mock (port 4174)

# LIVE: the backend-mode build against a REAL running backend (no mocking), port 4175
LIVE_BACKEND_URL=http://127.0.0.1:8000 pnpm exec playwright test -c playwright.live.config.ts
```

The live suite registers accounts (`live-e2e-…@example.com`) and creates data. Run it only against a
local or test backend, never production. It registers and signs in more accounts per minute than the
production limits allow, so the test backend needs higher limits: `AUTH_REGISTER_IP_PER_MINUTE=200`,
`AUTH_LOGIN_IP_PER_MINUTE=200`, `AUTH_LOGIN_EMAIL_PER_MINUTE=50`, `AUTH_REFRESH_IP_PER_MINUTE=200`. Clean up
with `python -m app.cli purge-demo --prefix live-e2e- --yes` (and `live-smoke-`).

- `src/services/api/contract.test.ts` parses the backend's **recorded real responses**
  (`../docs/postman/tools/examples.json`) with the client schemas and mappers. When the backend team
  regenerates those recordings, contract drift fails here.
- `e2e/api-mode.spec.ts` runs the real backend-mode bundle against `e2e/mockBackend.ts`. That mock serves the
  same recordings and enforces bearer auth and refresh rotation. It proves the client follows the contract,
  not that a given server is up. Use §5 against a real stack for that.
- On a memory-constrained machine run the e2e projects (or files) separately, with `--workers=1`.

## 7. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Every page says "Could not reach the server" | Backend not running, or `BACKEND_URL` / `VITE_API_BASE_URL` wrong. Check §5 step 1. |
| CORS error in the console | The site and API are on different origins. Use the proxy or one Nginx, or add the site's origin to `CORS_ORIGINS`. |
| Signed out after a while in several tabs | Should not happen: refreshes are coordinated across tabs (Web Locks). If it does, check that the clock is right and `JWT_REFRESH_DAYS` has not passed. |
| "XAU/USD is not available on the backend yet" | Instrument not seeded: `app.cli seed-instruments` |
| Chart empty, status "Streaming" | Instrument exists but has no candles: seed them or connect a collector. |
| Panels say "Not available yet" | Expected for capabilities the backend does not provide (gap analysis G1–G6). |
| `429 Too many requests` | Backend rate limit. The client never auto-retries. Wait, or adjust `RATE_LIMIT_*` for development. |
