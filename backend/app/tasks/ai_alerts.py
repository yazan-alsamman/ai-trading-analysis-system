"""``ai_alerts.dispatch`` (notifications queue; beat every 30 s, and ``ai.alerts.kick()`` after
an evaluation): sends the AI setup alerts of ``ai_setup_outbox`` (app/ai/alerts.py,
docs/notifications.md#ai-setup-alerts). Idle, it is one indexed query."""

from app.ai import alerts
from app.tasks import celery_app
from app.tasks.signals import run_async


@celery_app.task(name="ai_alerts.dispatch", soft_time_limit=50, time_limit=60, ignore_result=True)
def dispatch() -> dict:
    return run_async(lambda factory, redis: alerts.dispatch(factory, redis))
