import logging

from app.services import housekeeping
from app.tasks import celery_app
from app.tasks.signals import run_async

logger = logging.getLogger(__name__)


@celery_app.task(name="housekeeping.cleanup")
def cleanup() -> dict:
    """Daily at 03:00 UTC (beat): see app.services.housekeeping.cleanup."""

    async def go(session_factory, _redis):
        async with session_factory() as session:
            return await housekeeping.cleanup(session)

    result = run_async(go)
    logger.info(
        "housekeeping.cleanup deleted refresh_tokens=%d api_keys=%d",
        result.refresh_tokens,
        result.api_keys,
    )
    return {"refresh_tokens": result.refresh_tokens, "api_keys": result.api_keys}
