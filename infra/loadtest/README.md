# Load test (C2)

k6 against the **local** compose stack with the production `mem_limit` / `cpus`. Never run it
against the production server: `run.sh` starts k6 in a container on this machine's compose
network, where it can only reach the local Nginx, and it refuses a remote `DOCKER_HOST`.

```bash
NGINX_PORT=8080 PYTHON=backend/.venv/Scripts/python infra/loadtest/run.sh
# VUS=200 WS_CLIENTS=200 HOLD_SECONDS=150; KEEP_LIMITS=1 / KEEP_USERS=1 skip the clean-up;
# EXTRA_COMPOSE=other.yml adds one more override (to try other limits)
```

| file | what |
|---|---|
| `compose.limits.yml` | the production limits on the dev stack, the production worker command (`--concurrency 2`), and the per-IP WebSocket connection limit raised for the run (all clients share one IP) |
| `make_users.py` | runs in the backend container: 200 analyst accounts `load-NNN@example.com` (300 requests/min each, so the rate limiter is not what is measured) with access tokens, plus the instruments that have candles |
| `load.js` | scenario `api`: ramp to 200 users in 30 s, hold, ramp down in 15 s; each picks candles 35% (1m/5m/15m/1h/4h, 500 bars), indicators 20% (rsi, ema, macd, bollinger, atr on 500 bars), signals 15%, news 15%, posts feed 15%, with 0.5-2 s think time. Scenario `ws`: 200 clients connect over 20 s, subscribe to BTC/USDT 1m candles and their user topic and stay connected; fan-out delay = receive time - the publisher's `sent_at` |
| `summarize.py` | p50/p95/p99, errors and 429s per endpoint, WebSocket numbers, `docker stats` peaks vs the production limits |

During the run `simulate-live` rewrites the BTC/USDT 1m candle every second (live signal
engine, price alerts and WebSocket fan-out all work), and `docker stats` is sampled about every
2 s for this stack's containers only. Afterwards the `load-` accounts are purged and the normal
dev stack is restored (Nginx alone first: it has a fixed address).

## Results (2026-10-16, 16-CPU Windows host, Docker Desktop, production limits)

Two runs at 200 API users + 200 WebSocket clients, 150 s hold. Run 1 is before the fix below,
run 2 after it.

**Run 2** (pool timeout 10 s, 503 when the pool is exhausted):

| endpoint | requests | p50 ms | p95 ms | p99 ms | max ms | errors | 429 |
|---|---:|---:|---:|---:|---:|---:|---:|
| candles | 2582 | 3197 | 10100 | 10408 | 10777 | 161 | 0 |
| indicators | 1540 | 3176 | 10110 | 10386 | 11027 | 102 | 0 |
| signals | 1184 | 3116 | 10078 | 10313 | 10531 | 69 | 0 |
| news | 1125 | 3261 | 10085 | 10378 | 11128 | 74 | 0 |
| posts | 1130 | 3166 | 10090 | 10335 | 10566 | 69 | 0 |

7,561 requests (38.7/s), 6.28% failed. The errors are the pool timeout (latency is capped at
about 10 s, the timeout); the backend logs of this run were lost when the containers were
recreated, so their status (503 expected) was not checked. WebSocket: 182 of 200 connected (handshake p50 2.8 s,
max 10.5 s; the 18 failures are most likely the authentication step waiting for the same
exhausted pool, not verified), 24,940 candle messages, 0 error frames, fan-out delay p50 60 ms,
p95 162 ms, p99 298 ms, max 422 ms.

**Run 1** (default pool timeout 30 s): 6,937 requests (35.3/s), 0.09% failed (six 500s: SQLAlchemy
`QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00`); p50
3.2-3.5 s, p95 11.0-11.6 s, p99 16.9-18.4 s, max 28.5-30.4 s on every endpoint; WebSocket 200 of
200 connected, fan-out p50 56 ms, p95 185 ms, p99 301 ms.

| service | peak memory (run 1 / run 2) MiB | prod limit MiB | peak CPU % | prod cpus |
|---|---:|---:|---:|---:|
| backend | 240 / 266 | 384 | 104 / 105 | 1.0 |
| db | 279 / 282 | 768 | 109 / 108 | 1.0 |
| worker | 237 / 238 | 384 | 61 / 11 | 0.75 |
| worker-backtest | 230 / 228 | 512 | 12 / 29 | 1.0 |
| beat | 117 / 119 | 192 | 3 / 25 | 0.25 |
| redis | 5 / 7 | 192 | 9 / 8 | 0.5 |
| nginx | 25 / 24 | 64 | 9 / 10 | 0.25 |
| telegram-bot | 57 / 57 | 128 | 0 / 0 | 0.25 |
| ai-service | 39 / 39 | 256 | 0 / 0 | 0.5 |

No container was OOM-killed and no 429 was returned.

## What it shows

- **CPU, not memory, is the limit.** The backend (one uvicorn process, 1 CPU) and the database
  (1 CPU) both sit at their CPU limit; together they serve about 35-39 requests/s of this mix.
  200 users asking every 1.25 s on average want about 4 times that, so requests queue: p50 about
  3.2 s on every endpoint, cheap ones (signals, news) as slow as the expensive ones, because they
  wait in the same queue.
- **Under overload the pool decides what users see.** With the default 30 s pool timeout,
  requests hung up to 30 s and then failed as unhandled 500s. Now (`DB_POOL_TIMEOUT=10`, handler
  in `app/main.py`) they wait at most about 10 s and get `503` with `Retry-After: 2`: shorter
  hangs, more of them refused, a status clients can back off from.
- **WebSocket fan-out holds up**: about 125 candle messages/s to 200 clients stayed under 0.5 s
  even with the API saturated (the publisher and the hub do not wait for the database).
- **Memory has headroom everywhere**: the largest share is backend 69%, beat 62%, worker 62%.
- The dev worker (Celery default concurrency = one process per CPU) does not fit 384m and was
  OOM-killed in a first smoke run; production runs `--concurrency 2`, which the override copies.

## Recommendations

Not tested (the run with these limits was stopped by the host running low on memory, so
measure before changing production), and only if the server has the CPU to spare next to the
other projects it hosts:

- backend: `cpus: 2.0` with `uvicorn --workers 2`, `mem_limit: 640m` (two processes of about
  250 MiB under load);
- db: `cpus: 2.0`; memory is fine at 768m (peak 282 MiB);
- everything else: keep the current limits.

To try them locally: an override with those values as `EXTRA_COMPOSE=...` for `run.sh`.
