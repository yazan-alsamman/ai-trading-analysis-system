"""``GET /admin/system/status``: one view of the running platform (read-only, cheap queries).

Every section is collected on its own: a failing one reports ``{"error": ...}`` instead of
failing the whole answer.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import evaluate as evaluation
from app.calendar import service as calendar_service
from app.core import ops
from app.core.config import get_settings
from app.notifications import breaker
from app.notifications.channels import enabled_channels
from app.services import data_health

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
    "data_quality.check",
    "calendar.refresh",
    "ai_alerts.dispatch",
    "notifications.sweep",
    "ai.evaluate_tick",
    "ai.evaluate",
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


async def _data_quality(session: AsyncSession, redis: Redis) -> list[dict[str, Any]]:
    """The data-quality report of every monitored instrument (B5, docs/data-quality.md)."""
    return [r.model_dump(mode="json") for r in await data_health.current(session, redis)]


async def _calendar(session: AsyncSession, redis: Redis) -> dict[str, Any]:
    """The economic-calendar refresh (B6): last success, last error, back-off, stored rows."""
    return {**await calendar_service.state(redis), **await calendar_service.table_stats(session)}


async def _ai_alerts(session: AsyncSession) -> dict[str, Any]:
    """The AI setup alert outbox (B11): rows by status, and how long the oldest pending one has
    waited."""
    rows = await session.execute(
        text("SELECT status, count(*) FROM ai_setup_outbox GROUP BY status")
    )
    oldest = await session.scalar(
        text(
            "SELECT extract(epoch FROM clock_timestamp() - min(created_at)) "
            "FROM ai_setup_outbox "
            "WHERE status = 'pending'"
        )
    )
    counts = {"pending": 0, "done": 0, "skipped": 0, "failed": 0, **dict(rows.all())}
    return {
        "outbox": counts,
        "oldest_pending_seconds": round(float(oldest), 1) if oldest is not None else None,
    }


async def _ai_evaluate(session: AsyncSession, redis: Redis) -> dict[str, Any]:
    """The periodic evaluation (B9): enabled, the last run of every instrument and profile
    (time, status, reason, duration, request size, bars sent), the last contract error."""
    return await evaluation.status(session, redis)


async def _notifications(redis: Redis) -> dict[str, Any]:
    server = enabled_channels()
    return {
        name: {"enabled_on_server": server[name], "circuit": await breaker.state(redis, name)}
        for name in server
    }


async def _websocket(redis: Redis, hub) -> dict[str, Any]:
    """WebSocket clients of every API process (uvicorn workers report every 30 s through
    Redis), plus the live numbers of the process serving this request."""
    stats = hub.stats() if hub is not None else {}
    out: dict[str, Any] = {
        "process_clients": stats.get("clients"),
        "process_subscriptions": stats.get("subscriptions"),
    }
    try:
        processes = await ops.api_processes(redis)
    except Exception:  # noqa: BLE001
        logger.exception("system status: API processes failed")
        processes = []
    kinds: Counter[str] = Counter()
    for p in processes:
        kinds.update(p.get("topics_by_kind") or {})
    out.update(
        api_processes=len(processes),
        clients=sum(p.get("clients", 0) for p in processes),
        subscriptions=sum(p.get("subscriptions", 0) for p in processes),
        topics_by_kind=dict(kinds),
        processes=[
            {k: p.get(k) for k in ("host", "pid", "clients", "subscriptions")} for p in processes
        ],
        note="clients/subscriptions: all API processes, reported every 30 s; process_*: "
        "the process that served this request, live",
    )
    return out


async def collect(session: AsyncSession, redis: Redis, hub) -> dict[str, Any]:
    settings = get_settings()
    now = time.time()
    out: dict[str, Any] = {
        "version": settings.app_version,
        "environment": settings.environment,
        "public_hostname": settings.public_hostname or None,
        "time": datetime.now(UTC).isoformat(),
        "uptime_seconds": round(now - ops.STARTED_AT),
    }
    sections = {
        "database": lambda: _database(session),
        "redis": lambda: _redis(redis),
        "celery": lambda: _celery(redis, now),
        "market_data": lambda: _market(session, now),
        "data_quality": lambda: _data_quality(session, redis),
        "calendar": lambda: _calendar(session, redis),
        "ai_alerts": lambda: _ai_alerts(session),
        "ai_evaluate": lambda: _ai_evaluate(session, redis),
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
    out["websocket"] = await _websocket(redis, hub)
    try:
        raw = await redis.get(ops.DAILY_SUMMARY)
        out["daily_summary"] = json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        out["daily_summary"] = None
    return out
