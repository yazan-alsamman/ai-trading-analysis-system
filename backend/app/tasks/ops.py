"""``ops.daily_summary`` (beat, 00:05 UTC, maintenance queue): one log line with the last 24
hours (signals, notification deliveries sent/failed, new users, active subscriptions), also kept
in Redis for ``GET /admin/system/status`` and grepped by the read-only server inspection."""

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core import ops
from app.models.expert import Subscription
from app.models.notification import DeliveryStatus, Notification, NotificationDelivery
from app.models.strategy import Signal
from app.models.user import User
from app.payments.entitlements import entitled_clause
from app.tasks import celery_app
from app.tasks.signals import run_async

logger = logging.getLogger(__name__)


async def summary(factory, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    since = now - timedelta(days=1)

    async def count(query) -> int:
        async with factory() as session:
            return int(await session.scalar(query) or 0)

    deliveries = select(func.count()).select_from(NotificationDelivery)
    return {
        "window_start": since.isoformat(timespec="minutes"),
        "signals": await count(
            select(func.count()).select_from(Signal).where(Signal.created_at >= since)
        ),
        "notifications": await count(
            select(func.count()).select_from(Notification).where(Notification.created_at >= since)
        ),
        "deliveries_sent": await count(
            deliveries.where(
                NotificationDelivery.status == DeliveryStatus.sent,
                NotificationDelivery.created_at >= since,
            )
        ),
        "deliveries_failed": await count(
            deliveries.where(
                NotificationDelivery.status == DeliveryStatus.failed,
                NotificationDelivery.created_at >= since,
            )
        ),
        "new_users": await count(
            select(func.count()).select_from(User).where(User.created_at >= since)
        ),
        "active_subscriptions": await count(
            select(func.count()).select_from(Subscription).where(entitled_clause(now))
        ),
    }


@celery_app.task(name="ops.daily_summary")
def daily_summary() -> dict:
    result = run_async(lambda factory, _redis: summary(factory))
    line = " ".join(f"{k}={v}" for k, v in result.items())
    logger.info("daily_summary %s", line)
    try:
        ops.sync_client().set(
            ops.DAILY_SUMMARY,
            json.dumps({**result, "at": datetime.now(UTC).isoformat()}),
            ex=3 * 86400,
        )
    except Exception:  # noqa: BLE001
        pass
    return result
