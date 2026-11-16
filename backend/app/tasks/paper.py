"""Paper trading engine (docs/paper-trading.md) on the default queue, next to price alerts.

``paper.tick`` runs every minute (beat) and schedules ``paper.evaluate`` at the boundary + 10 s,
when the closed 1m bar has arrived (the signal engine and price alerts use the same delay)."""

from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.paper import engine
from app.services.market_service import floor_to_bucket
from app.tasks import celery_app
from app.tasks.signals import EVALUATE_DELAY, run_async


@celery_app.task(name="paper.tick")
def tick() -> str:
    boundary = floor_to_bucket(datetime.now(UTC), timedelta(minutes=1))
    if get_settings().paper_trading_enabled:
        evaluate.apply_async(
            eta=boundary + EVALUATE_DELAY, expires=boundary + timedelta(seconds=55)
        )
    return boundary.isoformat()


@celery_app.task(name="paper.evaluate", soft_time_limit=50)
def evaluate() -> dict:
    run = run_async(lambda factory, redis: engine.evaluate(factory, redis))
    return {
        "status": run.status,
        "instruments": run.instruments,
        "filled": run.filled,
        "rejected": run.rejected,
        "closed": run.closed,
        "notifications": run.notifications,
        "errors": run.errors,
        "duration_ms": run.duration_ms,
    }
