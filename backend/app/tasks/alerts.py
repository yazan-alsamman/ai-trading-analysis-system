"""Price alert tasks on the default queue (the ``worker`` service), next to the signal engine.

``alerts.tick`` runs every minute (beat) and schedules ``alerts.evaluate`` for the 1m bar that
just closed at ``boundary + 10 s``, when its last candle has arrived (the signal engine uses
the same delay). The evaluation is skipped quickly when no alert is active.
"""

import logging
from datetime import UTC, datetime, timedelta

from app.alerts import engine
from app.services.market_service import floor_to_bucket
from app.tasks import celery_app
from app.tasks.signals import EVALUATE_DELAY, run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="alerts.tick")
def tick() -> str:
    boundary = floor_to_bucket(datetime.now(UTC), timedelta(minutes=1))
    bar_time = boundary - timedelta(minutes=1)
    evaluate.apply_async((bar_time.isoformat(),), eta=boundary + EVALUATE_DELAY)
    return bar_time.isoformat()


@celery_app.task(
    name="alerts.evaluate",
    acks_late=True,  # redelivered if the worker dies; the lock and dedup keys make it safe
    reject_on_worker_lost=True,
    soft_time_limit=50,
)
def evaluate(bar_time: str) -> dict:
    run = run_async(
        lambda factory, redis: engine.evaluate(factory, redis, datetime.fromisoformat(bar_time))
    )
    return {
        "status": run.status,
        "alerts": run.alerts,
        "fired": run.fired,
        "notifications": run.notifications,
        "duration_ms": run.duration_ms,
    }
