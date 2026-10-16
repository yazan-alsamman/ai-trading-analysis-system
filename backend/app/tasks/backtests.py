"""Backtest tasks, routed to the ``backtests`` queue (own worker service, so long backtests
never delay the live signal engine)."""

import logging
import uuid

from celery.exceptions import SoftTimeLimitExceeded
from celery.signals import worker_ready

from app.core.config import get_settings
from app.services import backtest_service
from app.tasks import celery_app
from app.tasks.signals import run_async

logger = logging.getLogger(__name__)

TIME_LIMIT = get_settings().backtest_time_limit_seconds


@celery_app.task(
    name="backtests.run",
    soft_time_limit=TIME_LIMIT,
    time_limit=TIME_LIMIT + 30,  # hard kill if the soft limit could not stop it
)
def run(backtest_id: str) -> str:
    """Not acks_late: a backtest lost with its worker is failed by ``backtests.recover``
    instead of being retried (a crash often repeats)."""
    target = uuid.UUID(backtest_id)
    try:
        result = run_async(lambda factory, redis: backtest_service.execute(factory, redis, target))
    except SoftTimeLimitExceeded:  # raised outside the coroutine's own handler
        message = backtest_service.time_limit_message(TIME_LIMIT)
        run_async(lambda factory, redis: backtest_service.fail(factory, redis, target, message))
        return "failed"
    return result.value if result else "skipped"


@celery_app.task(name="backtests.recover")
def recover() -> int:
    """Fail backtests left ``running`` by a dead worker (beat, every 5 minutes, and on start)."""
    return run_async(lambda factory, redis: backtest_service.recover_stuck(factory, redis))


@worker_ready.connect
def recover_on_start(sender=None, **_kwargs) -> None:
    """A restarted worker cleans up after the one that died (routed to the backtests queue)."""
    try:
        celery_app.send_task("backtests.recover")
    except Exception:  # noqa: BLE001 - only housekeeping
        logger.exception("Could not schedule backtests.recover on worker start")
