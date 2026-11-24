"""``feeds.ctrader_backfill`` (maintenance queue, the ``worker-backtest`` service): a long M1
backfill from cTrader, asked for by ``POST /admin/feeds/ctrader/backfill``
(app/feeds/ctrader/backfill.py, docs/ctrader-feed.md#backfill)."""

from datetime import datetime

from app.feeds.ctrader import backfill
from app.tasks import celery_app
from app.tasks.signals import run_async


@celery_app.task(
    name="feeds.ctrader_backfill",
    acks_late=True,
    soft_time_limit=3 * 3600,
    time_limit=3 * 3600 + 60,
    ignore_result=True,
)
def ctrader_backfill(start: str, end: str) -> dict:
    return run_async(
        lambda factory, redis: backfill.run(
            factory, redis, datetime.fromisoformat(start), datetime.fromisoformat(end)
        )
    )
