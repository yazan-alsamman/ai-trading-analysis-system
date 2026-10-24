"""The AI engine tasks (B9, app/ai/evaluate.py and app/ai/explain.py; docs/ai-contract.md).

- ``ai.evaluate_tick`` (beat at each 15m boundary): one ``ai.evaluate`` per instrument and
  profile for the bar that just closed, ``AI_EVALUATE_DELAY_SECONDS`` after the boundary.
  Nothing is scheduled while ``AI_EVALUATE_ENABLED`` is false (the default).
- ``ai.evaluate`` (default queue, the ``worker`` service): one run; a duplicate is a no-op.
- ``ai.explain`` (notifications queue): ``/v1/explain`` for a newly ARMED setup in one
  language; 5xx and timeouts are retried a bounded number of times, a 404 is "unavailable".
"""

import logging
from datetime import UTC, datetime

from app.ai import evaluate as evaluation
from app.ai import explain as explanation
from app.ai.client import AIContractError, AIUnavailableError
from app.core.config import get_settings
from app.tasks import celery_app
from app.tasks.signals import run_async

logger = logging.getLogger(__name__)

EXPLAIN_RETRIES = 2  # after the client's own retries (AI_MAX_RETRIES)
EXPLAIN_RETRY_SECONDS = 60


@celery_app.task(name="ai.evaluate_tick", ignore_result=True)
def evaluate_tick() -> int:
    scheduled = evaluation.schedule(datetime.now(UTC), evaluate.apply_async)
    if scheduled:
        logger.info(
            "ai.evaluate_tick bar_close_ts=%s runs=%d", scheduled[0][3].isoformat(), len(scheduled)
        )
    return len(scheduled)


@celery_app.task(
    name="ai.evaluate",
    acks_late=True,  # redelivered if the worker dies; the run key makes a second run a no-op
    reject_on_worker_lost=True,
    soft_time_limit=110,
    time_limit=120,
    ignore_result=True,
)
def evaluate(source: str, symbol: str, profile: str, bar_close_ts: str) -> dict:
    if not get_settings().ai_evaluate_enabled:  # switched off after it was scheduled
        return {"status": "disabled"}
    when = datetime.fromisoformat(bar_close_ts.replace("Z", "+00:00"))
    result = run_async(
        lambda factory, redis: evaluation.run(factory, redis, source, symbol, profile, when)
    )
    return {
        "status": result.status,
        "reason": result.reason,
        "duration_ms": result.duration_ms,
        "request_bytes": result.request_bytes,
    }


@celery_app.task(
    name="ai.explain",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=EXPLAIN_RETRIES,
    soft_time_limit=150,
    time_limit=160,
    ignore_result=True,
)
def explain(self, setup_id: str, lang: str) -> str:
    try:
        return run_async(lambda factory, _redis: explanation.explain(factory, setup_id, lang))
    except AIUnavailableError as exc:
        if self.request.retries >= EXPLAIN_RETRIES:
            logger.warning("ai explain %s/%s: unavailable, giving up: %s", setup_id, lang, exc)
            return "unavailable"
        raise self.retry(countdown=EXPLAIN_RETRY_SECONDS) from None
    except AIContractError as exc:
        logger.error("ai explain %s/%s: contract error: %s (%s)", setup_id, lang, exc, exc.detail)
        return "contract_error"
