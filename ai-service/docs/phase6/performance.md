# P6 task 8: production image and performance

Measured 2026-10-25 on Fadi's laptop (Docker 29.4.1, 16 logical CPUs): image `ai-service:p6`
built from `Dockerfile` (`python:3.12-slim`, runtime dependencies only: fastapi, uvicorn,
pydantic, numpy 2.5.4, pandas 3.1.0, pyarrow 26.0.0; no scikit-learn, LightGBM or matplotlib),
run with the production limits:

    docker run --memory 512m --memory-swap 512m --cpus 0.5 -p 8011:8001 ai-service:p6
    python -m app live bench --url http://localhost:8011 --sizes 1000 5000 --n 40

Requests: the last XAUUSD 15m bars of the walk-forward period from the store, one bar later on
each call, HTTP from the host (`app/live/replay.py`, `bench`).

| 15m bars | Body (KB) | Calls | p50 (ms) | p95 (ms) | max (ms) |
| --- | --- | --- | --- | --- | --- |
| 1,000 (proposed `AI_BARS_15M`) | 107 | 40 | 289 | 377 | 387 |
| 5,000 (contract maximum) | 543 | 40 | 747 | 923 | 976 |

| | Value |
| --- | --- |
| Image size | 674 MB |
| Memory at start | 81 MiB |
| Peak memory over both runs (cgroup `memory.peak`) | 113 MiB of 512 MiB |
| OOM kills, restarts | none |

**Gate (< 10 s at 512 MB / 0.5 CPU): passed.** p95 is 0.38 s for the proposed request and 0.92 s
for the largest the contract allows, against the backend's 10 s timeout per attempt.
