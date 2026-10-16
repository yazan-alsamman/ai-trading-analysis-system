"""Operational counters and markers in Redis, read by ``GET /admin/system/status``.

- ``ops:errors:<unix minute>``: unhandled API errors (5xx) and failed Celery tasks per minute
  (kept 2 hours);
- ``ops:worker:<hostname>``: a Celery worker's heartbeat (queues, pid), refreshed every 30 s,
  expires after 90 s;
- ``ops:task:last_ok`` / ``ops:task:last_fail``: per task name, the time of the last success /
  failure (so the beat tasks' last runs are visible);
- ``ops:daily_summary``: the last daily summary line.

Celery processes are synchronous: they use a small sync client. Every helper swallows Redis
errors: observability must never break the work it observes.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import UTC, datetime

import redis as redis_sync
from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ERRORS_PREFIX = "ops:errors:"
WORKER_PREFIX = "ops:worker:"
TASK_OK = "ops:task:last_ok"
TASK_FAIL = "ops:task:last_fail"
DAILY_SUMMARY = "ops:daily_summary"
HEARTBEAT_SECONDS = 30
STARTED_AT = time.time()

_sync: redis_sync.Redis | None = None


def sync_client() -> redis_sync.Redis:
    global _sync
    if _sync is None:
        _sync = redis_sync.Redis.from_url(
            get_settings().redis_url, decode_responses=True, socket_timeout=2
        )
    return _sync


def _minute_key(ts: float | None = None) -> str:
    return f"{ERRORS_PREFIX}{int((ts or time.time()) // 60)}"


async def count_error(redis: Redis) -> None:
    try:
        key = _minute_key()
        pipe = redis.pipeline(transaction=False)
        pipe.incr(key)
        pipe.expire(key, 7200)
        await pipe.execute()
    except Exception:  # noqa: BLE001
        pass


def count_error_sync() -> None:
    try:
        key = _minute_key()
        client = sync_client()
        client.incr(key)
        client.expire(key, 7200)
    except Exception:  # noqa: BLE001
        pass


async def errors_last_hour(redis: Redis) -> int:
    now = int(time.time() // 60)
    values = await redis.mget([f"{ERRORS_PREFIX}{m}" for m in range(now - 59, now + 1)])
    return sum(int(v) for v in values if v)


def task_finished(name: str, ok: bool) -> None:
    try:
        sync_client().hset(TASK_OK if ok else TASK_FAIL, name, datetime.now(UTC).isoformat())
    except Exception:  # noqa: BLE001
        pass


def start_worker_heartbeat(hostname: str, queues: list[str]) -> None:
    """A daemon thread in the worker's main process writing ``ops:worker:<hostname>``."""

    def beat() -> None:
        payload = json.dumps({"queues": queues, "pid": os.getpid()})
        while True:
            try:
                sync_client().set(f"{WORKER_PREFIX}{hostname}", payload, ex=90)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(HEARTBEAT_SECONDS)

    threading.Thread(target=beat, name="ops-heartbeat", daemon=True).start()
    logger.info("ops heartbeat started for %s (%s)", hostname, ",".join(queues))
