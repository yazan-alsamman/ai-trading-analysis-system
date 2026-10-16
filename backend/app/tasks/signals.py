"""Celery tasks of the live signal engine (see app/services/signal_engine.py).

``signals.tick`` runs every minute (beat). It finds the (instrument, timeframe) pairs whose bar
just closed and schedules one ``signals.evaluate`` per pair for ``boundary + EVALUATE_DELAY``,
so the last 1m candle of the bar has arrived.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.candle import Timeframe
from app.services import signal_engine
from app.services.market_service import floor_to_bucket
from app.tasks import celery_app

logger = logging.getLogger(__name__)

EVALUATE_DELAY = timedelta(seconds=10)


def run_async[T](fn: Callable[[async_sessionmaker[AsyncSession], Redis], Awaitable[T]]) -> T:
    """Run ``fn(session_factory, redis)`` in a fresh event loop with its own connections (each
    Celery task gets a new loop, and asyncpg/redis connections cannot cross loops)."""
    settings = get_settings()

    async def runner() -> T:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            return await fn(async_sessionmaker(engine, expire_on_commit=False), redis)
        finally:
            await redis.aclose()
            await engine.dispose()

    return asyncio.run(runner())


@celery_app.task(name="signals.tick")
def tick() -> int:
    now = datetime.now(UTC)
    boundary = floor_to_bucket(now, timedelta(minutes=1))

    async def jobs(session_factory, _redis):
        async with session_factory() as session:
            due = await signal_engine.due_jobs(session, now)
            # custom setups of every due job, resolved in one batch for this beat run
            return due, await signal_engine.custom_snapshots(session, due)

    due, custom = run_async(jobs)
    eta = boundary + EVALUATE_DELAY
    for job in due:
        args = (str(job.instrument_id), job.timeframe.value, job.bar_time.isoformat())
        snapshots = custom.get((job.instrument_id, job.timeframe))
        evaluate.apply_async(args, {"custom": snapshots} if snapshots else None, eta=eta)
    closed = [tf.value for tf, _ in signal_engine.closed_bars(now)]
    logger.info(
        "signals.tick boundary=%s closed=%s jobs=%d", boundary.isoformat(), closed, len(due)
    )
    return len(due)


@celery_app.task(
    name="signals.evaluate",
    bind=True,
    acks_late=True,  # redelivered if the worker dies mid-run (the lock + unique key dedupe)
    reject_on_worker_lost=True,
    max_retries=6,
)
def evaluate(
    self, instrument_id: str, timeframe: str, bar_time: str, custom: dict | None = None
) -> dict:
    """``custom``: custom setups resolved by the tick (key -> snapshot); others are resolved
    here."""
    job = signal_engine.Job(
        uuid.UUID(instrument_id), Timeframe(timeframe), datetime.fromisoformat(bar_time)
    )

    async def go(session_factory, redis):
        return await signal_engine.evaluate(session_factory, redis, job, custom)

    result = run_async(go)
    if result.status == "locked":  # another worker is on it; check again once it is done
        raise self.retry(countdown=30)
    return {
        "status": result.status,
        "inserted": result.inserted,
        "errors": len(result.errors),
    }
