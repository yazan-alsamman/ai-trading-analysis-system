"""``subscriptions.renew`` (beat, hourly, default queue): renewals and trial ends, failed
charges -> past_due, past_due past the grace period -> expired, canceled subscriptions ended
at period end, abandoned checkouts expired (app/payments/service.py)."""

import logging

from app.payments import service
from app.tasks import celery_app
from app.tasks.signals import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="subscriptions.renew", soft_time_limit=300)
def renew() -> dict:
    counts = run_async(lambda factory, redis: service.renew_due(factory, redis))
    if counts:
        logger.info("subscriptions.renew %s", counts)
    return counts
