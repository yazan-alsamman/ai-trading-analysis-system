"""``predictions.resolve_signals`` (maintenance queue, worker-backtest; beat every
``PREDICTION_RESOLVE_INTERVAL_SECONDS``): resolves due strategy signals into
``signal_outcomes``, at most ``PREDICTION_RESOLVE_BATCH`` per run (app/services/
prediction_resolver.py, docs/predictions.md). Idle, it is a few indexed queries."""

from app.services import prediction_resolver
from app.tasks import celery_app
from app.tasks.signals import run_async


@celery_app.task(
    name="predictions.resolve_signals", soft_time_limit=240, time_limit=270, ignore_result=True
)
def resolve_signals() -> int:
    result = run_async(lambda factory, redis: prediction_resolver.run(factory, redis))
    return result.resolved
