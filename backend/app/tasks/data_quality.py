"""``data_quality.check`` (beat, every minute, ~15 s after the boundary, default queue): the
data-quality report of every instrument in ``DATA_QUALITY_INSTRUMENTS``, stored in Redis for
``GET /api/v1/health/data`` (app/services/data_health.py, docs/data-quality.md)."""

from app.services import data_health
from app.tasks import celery_app
from app.tasks.signals import run_async


@celery_app.task(name="data_quality.check", soft_time_limit=40)
def check() -> dict[str, str]:
    if not data_health.monitored():
        return {}
    reports = run_async(lambda factory, redis: data_health.run(factory, redis))
    return {r.instrument: r.status.value for r in reports}
