"""``calendar.refresh`` (beat, every 15 minutes, default queue): the ForexFactory weekly
calendar, fetched at most once per ``CALENDAR_FETCH_INTERVAL_MINUTES`` (default 240) under a
Redis lock, never during the back-off after a 429/403 (app/calendar/service.py,
docs/economic-calendar.md). A run that is not due costs two Redis reads and no request."""

import logging

from app.calendar import service
from app.core.config import get_settings
from app.tasks import celery_app
from app.tasks.signals import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="calendar.refresh", soft_time_limit=45, time_limit=60, ignore_result=True)
def refresh() -> dict:
    if not get_settings().calendar_enabled:
        return {"status": "disabled"}
    return run_async(lambda factory, redis: service.refresh(factory, redis))
