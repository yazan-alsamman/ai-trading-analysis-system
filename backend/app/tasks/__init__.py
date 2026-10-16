from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "trading",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.signals", "app.tasks.housekeeping", "app.tasks.backtests"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    # unacked messages of a dead worker are redelivered after this (default: 1 hour)
    broker_transport_options={"visibility_timeout": 300},
    worker_prefetch_multiplier=1,
    # backtests run on their own queue / worker service (docker-compose: worker-backtest)
    task_routes={"backtests.*": {"queue": "backtests"}},
    task_ignore_result=True,
    beat_schedule={
        # every minute; the evaluations themselves are scheduled ~10 s after the boundary
        "signals-tick": {"task": "signals.tick", "schedule": crontab(minute="*")},
        # refresh tokens and revoked API keys past their grace period
        # backtests a dead worker left "running"
        "backtests-recover": {"task": "backtests.recover", "schedule": crontab(minute="*/5")},
        "housekeeping-cleanup": {
            "task": "housekeeping.cleanup",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"
