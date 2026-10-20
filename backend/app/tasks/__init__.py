from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    after_setup_logger,
    after_setup_task_logger,
    task_failure,
    task_success,
    worker_ready,
)

from app.core import ops as ops_state
from app.core.config import get_settings
from app.core.logging import ContextFilter, JsonFormatter, quiet_http_clients, use_json

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
        "app.tasks.alerts",
        "app.tasks.news",
        "app.tasks.subscriptions",
        "app.tasks.ops",
        "app.tasks.data_quality",
        "app.tasks.calendar",
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
    # Queues (consumers in docker-compose.yml and infra/deploy/docker-compose.prod.yml):
    # - celery (default) + notifications -> "worker": the live path (signal engine, price
    #   alerts, notification sends) that must never wait;
    # - backtests + maintenance -> "worker-backtest": heavy or non-urgent work (backtests, RSS,
    #   retention, cleanups, subscription renewals, the daily summary).
    # Exact task names are matched before the patterns below them.
    task_routes={
        "notifications.cleanup": {"queue": "maintenance"},
        "backtests.*": {"queue": "backtests"},
        "notifications.*": {"queue": "notifications"},
        "news.*": {"queue": "maintenance"},
        "housekeeping.*": {"queue": "maintenance"},
        "subscriptions.*": {"queue": "maintenance"},
        "ops.*": {"queue": "maintenance"},
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
        # data-quality reports (B5), ~15 s after the boundary when the 1m bar has arrived;
        # a run that has not started within the minute is dropped (the next one replaces it)
        "data-quality-check": {
            "task": "data_quality.check",
            "schedule": crontab(minute="*"),
            "options": {"countdown": 15, "expires": 55},
        },
        # economic calendar (B6): checked every 15 minutes, one ForexFactory request per
        # CALENDAR_FETCH_INTERVAL_MINUTES at most (the task skips the runs that are not due)
        "calendar-refresh": {
            "task": "calendar.refresh",
            "schedule": crontab(minute="7,22,37,52"),
            "options": {"expires": 600},
        },
        # price alerts on the 1m bar that just closed (evaluated ~10 s after the boundary)
        "alerts-tick": {"task": "alerts.tick", "schedule": crontab(minute="*")},
        # RSS feeds whose interval is due (NEWS_RSS_ENABLED)
        "news-fetch": {"task": "news.fetch", "schedule": crontab(minute="*/5")},
        # news retention (NEWS_RETENTION_DAYS)
        "news-cleanup": {"task": "news.cleanup", "schedule": crontab(hour=3, minute=45)},
        # renewals, trial ends, grace periods and expired checkouts (Y19), every 10 minutes
        # one log line a day: signals, notifications, users, subscriptions (maintenance queue)
        "ops-daily-summary": {"task": "ops.daily_summary", "schedule": crontab(hour=0, minute=5)},
        "subscriptions-renew": {
            "task": "subscriptions.renew",
            "schedule": crontab(minute="*/10"),
        },
    },
)

quiet_http_clients()


@after_setup_logger.connect
@after_setup_task_logger.connect
def _setup_logging(logger=None, **_kwargs) -> None:
    quiet_http_clients()  # httpx would log Telegram URLs, which contain the bot token
    if logger is not None and use_json():
        for handler in logger.handlers:
            handler.setFormatter(JsonFormatter())
            handler.addFilter(ContextFilter())


@worker_ready.connect
def _heartbeat(sender=None, **_kwargs) -> None:
    try:
        queues = sorted(q.name for q in sender.task_consumer.queues)
    except Exception:  # noqa: BLE001
        queues = []
    ops_state.start_worker_heartbeat(getattr(sender, "hostname", "worker"), queues)


@task_success.connect
def _task_ok(sender=None, **_kwargs) -> None:
    ops_state.task_finished(getattr(sender, "name", "?"), True)


@task_failure.connect
def _task_failed(sender=None, **_kwargs) -> None:
    ops_state.task_finished(getattr(sender, "name", "?"), False)
    ops_state.count_error_sync()


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"
