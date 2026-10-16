from celery import Celery
from celery.schedules import crontab
from celery.signals import after_setup_logger

from app.core.config import get_settings
from app.core.logging import quiet_http_clients

settings = get_settings()

celery_app = Celery(
    "trading",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.signals",
        "app.tasks.housekeeping",
        "app.tasks.backtests",
        "app.tasks.notifications",
    ],
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
    # notifications on their own queue, consumed by the worker service next to "celery"
    task_routes={
        "backtests.*": {"queue": "backtests"},
        "notifications.*": {"queue": "notifications"},
    },
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
        # digests of held notifications (quiet hours, hourly cap) and circuit-held retries
        "notifications-digests": {"task": "notifications.digests", "schedule": crontab(minute="*")},
        # inbox retention: read > 90 days, unread > 180 days
        "notifications-cleanup": {
            "task": "notifications.cleanup",
            "schedule": crontab(hour=3, minute=30),
        },
    },
)

quiet_http_clients()


@after_setup_logger.connect
def _quiet(**_kwargs) -> None:
    quiet_http_clients()  # httpx would log Telegram URLs, which contain the bot token


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"
