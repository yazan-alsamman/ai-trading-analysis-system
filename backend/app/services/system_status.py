"""``GET /admin/system/status``: one view of the running platform (read-only, cheap queries).

Every section is collected on its own: a failing one reports ``{"error": ...}`` instead of
failing the whole answer.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import ops
from app.core.config import get_settings
from app.notifications import breaker
from app.notifications.channels import enabled_channels

logger = logging.getLogger(__name__)

QUEUES = ("celery", "notifications", "backtests", "maintenance")
BEAT_TASKS = (
    "signals.tick",
    "alerts.tick",
    "alerts.evaluate",
    "news.fetch",
    "notifications.digests",
    "subscriptions.renew",
    "ops.daily_summary",
)


def _age(iso: str | None, now: float) -> float | None:
    if not iso:
        return None
    return round(now - datetime.fromisoformat(iso).timestamp(), 1)


async def _database(session: AsyncSession) -> dict[str, Any]:
    size = await session.scalar(text("SELECT pg_database_size(current_database())"))
    connections = dict(
        (
            await session.execute(
                text(
                    "SELECT coalesce(state, 'unknown'), count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() GROUP BY 1"
                )
            )
        ).all()
    )
    revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
    out: dict[str, Any] = {
        "size_mb": round((size or 0) / 1024 / 1024, 1),
        "connections": connections,
        "migration": revision,
        "slowest_queries": None,
    }
    has_statements = await session.scalar(
        text("SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'")
    )
    if has_statements:
        rows = await session.execute(
            text(
                "SELECT left(query, 160), calls, round(mean_exec_time::numeric, 2) "
                "FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5"
            )
        )
        out["slowest_queries"] = [
            {"query": q, "calls": c, "mean_ms": float(m)} for q, c, m in rows.all()
        ]
    return out


async def _redis(redis: Redis) -> dict[str, Any]:
    info = await redis.info("memory")
    return {
        "used_memory": info.get("used_memory_human"),
        "max_memory": info.get("maxmemory_human"),
        "keys": await redis.dbsize(),
    }


async def _celery(redis: Redis, now: float) -> dict[str, Any]:
    pipe = redis.pipeline(transaction=False)
    for queue in QUEUES:
        pipe.llen(queue)
    lengths = await pipe.execute()
    workers = []
    async for key in redis.scan_iter(match=f"{ops.WORKER_PREFIX}*", count=100):
        raw, ttl = await redis.get(key), await redis.ttl(key)
        data = json.loads(raw) if raw else {}
        workers.append(
            {
                "name": key.removeprefix(ops.WORKER_PREFIX),
                "queues": data.get("queues", []),
                "seen_seconds_ago": max(0, 90 - ttl) if ttl and ttl > 0 else None,
            }
        )
    last_ok = await redis.hgetall(ops.TASK_OK)
    last_fail = await redis.hgetall(ops.TASK_FAIL)
    return {
        "queues": dict(zip(QUEUES, lengths, strict=True)),
        "workers": sorted(workers, key=lambda w: w["name"]),
        "tasks": {
            name: {
                "last_ok": last_ok.get(name),
                "seconds_ago": _age(last_ok.get(name), now),
                "last_failure": last_fail.get(name),
            }
            for name in BEAT_TASKS
        },
    }


async def _market(session: AsyncSession, now: float) -> list[dict[str, Any]]:
    rows = await session.execute(
        text(
            "SELECT i.symbol, i.source, c.ts FROM instruments i "
            "LEFT JOIN LATERAL (SELECT ts FROM candles_1m WHERE instrument_id = i.id "
            "ORDER BY ts DESC LIMIT 1) c ON true WHERE i.is_active ORDER BY i.source, i.symbol"
        )
    )
    return [
        {
            "symbol": symbol,
            "source": source,
            "last_candle": ts.isoformat() if ts else None,
            "lag_seconds": round(now - ts.timestamp()) if ts else None,
        }
        for symbol, source, ts in rows.all()
    ]


async def _notifications(redis: Redis) -> dict[str, Any]:
    server = enabled_channels()
    return {
        name: {"enabled_on_server": server[name], "circuit": await breaker.state(redis, name)}
        for name in server
    }


async def collect(session: AsyncSession, redis: Redis, hub) -> dict[str, Any]:
    settings = get_settings()
    now = time.time()
    out: dict[str, Any] = {
        "version": settings.app_version,
        "environment": settings.environment,
        "time": datetime.now(UTC).isoformat(),
        "uptime_seconds": round(now - ops.STARTED_AT),
    }
    sections = {
        "database": lambda: _database(session),
        "redis": lambda: _redis(redis),
        "celery": lambda: _celery(redis, now),
        "market_data": lambda: _market(session, now),
        "notifications": lambda: _notifications(redis),
        "errors_last_hour": lambda: ops.errors_last_hour(redis),
    }
    for name, fn in sections.items():
        try:
            out[name] = await fn()
        except Exception as exc:  # noqa: BLE001 - one broken section must not hide the others
            logger.exception("system status: %s failed", name)
            out[name] = {"error": f"{type(exc).__name__}"}
            await session.rollback()
    stats = hub.stats() if hub is not None else {}
    out["websocket"] = {
        "process_clients": stats.get("clients"),
        "process_subscriptions": stats.get("subscriptions"),
        "topics_by_kind": stats.get("topics_by_kind"),
        "note": "this API process only",
    }
    try:
        raw = await redis.get(ops.DAILY_SUMMARY)
        out["daily_summary"] = json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        out["daily_summary"] = None
    return out
