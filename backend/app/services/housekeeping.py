"""Daily cleanup of rows that are no longer useful (run by Celery beat, app/tasks)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.refresh_token import RefreshToken

REFRESH_TOKEN_GRACE = timedelta(days=7)
API_KEY_GRACE = timedelta(days=90)


@dataclass(frozen=True)
class CleanupResult:
    refresh_tokens: int
    api_keys: int


async def cleanup(session: AsyncSession, now: datetime | None = None) -> CleanupResult:
    """Delete refresh tokens that expired or were revoked more than 7 days ago, and API keys
    revoked more than 90 days ago (their usage counters in Redis expire on their own)."""
    now = now or datetime.now(UTC)
    token_cutoff = now - REFRESH_TOKEN_GRACE
    tokens = await session.execute(
        delete(RefreshToken).where(
            or_(RefreshToken.expires_at < token_cutoff, RefreshToken.revoked_at < token_cutoff)
        )
    )
    keys = await session.execute(delete(ApiKey).where(ApiKey.revoked_at < now - API_KEY_GRACE))
    await session.commit()
    return CleanupResult(refresh_tokens=tokens.rowcount, api_keys=keys.rowcount)
