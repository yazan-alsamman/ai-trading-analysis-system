"""Daily cleanup of rows that are no longer useful (run by Celery beat, app/tasks)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIEvaluationRun
from app.models.api_key import ApiKey
from app.models.refresh_token import RefreshToken

REFRESH_TOKEN_GRACE = timedelta(days=7)
API_KEY_GRACE = timedelta(days=90)
AI_RUN_RETENTION = timedelta(days=90)  # ai_evaluation_runs (B9): ~96 rows a day per key


@dataclass(frozen=True)
class CleanupResult:
    refresh_tokens: int
    api_keys: int
    ai_evaluation_runs: int = 0


async def cleanup(session: AsyncSession, now: datetime | None = None) -> CleanupResult:
    """Delete refresh tokens that expired or were revoked more than 7 days ago, API keys
    revoked more than 90 days ago (their usage counters in Redis expire on their own) and AI
    evaluation runs older than 90 days."""
    now = now or datetime.now(UTC)
    token_cutoff = now - REFRESH_TOKEN_GRACE
    tokens = await session.execute(
        delete(RefreshToken).where(
            or_(RefreshToken.expires_at < token_cutoff, RefreshToken.revoked_at < token_cutoff)
        )
    )
    keys = await session.execute(delete(ApiKey).where(ApiKey.revoked_at < now - API_KEY_GRACE))
    runs = await session.execute(
        delete(AIEvaluationRun).where(AIEvaluationRun.finished_at < now - AI_RUN_RETENTION)
    )
    await session.commit()
    return CleanupResult(
        refresh_tokens=tokens.rowcount, api_keys=keys.rowcount, ai_evaluation_runs=runs.rowcount
    )
