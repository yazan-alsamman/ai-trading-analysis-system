"""News tasks on the default queue (the ``worker`` service).

- ``news.fetch`` (beat, every 5 minutes): the RSS feeds whose interval is due, fetched
  concurrently; every feed has a 10 s deadline and a 2 MB cap, and the task a 60 s hard limit,
  so it never holds a worker slot the signal engine needs for long.
- ``news.cleanup`` (beat, daily): retention (``NEWS_RETENTION_DAYS``).
"""

import logging

from app.core.config import get_settings
from app.news import service
from app.tasks import celery_app
from app.tasks.signals import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="news.fetch", soft_time_limit=45, time_limit=60, ignore_result=True)
def fetch() -> dict:
    if not get_settings().news_rss_enabled:
        return {"disabled": True}
    report = run_async(lambda factory, redis: service.fetch_due(factory, redis))
    if report:
        logger.info("news.fetch %s", report)
    return report


@celery_app.task(name="news.cleanup")
def cleanup() -> int:
    deleted = run_async(lambda factory, _redis: service.cleanup(factory))
    logger.info("news.cleanup deleted=%d", deleted)
    return deleted
