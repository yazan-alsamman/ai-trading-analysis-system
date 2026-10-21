"""Follows of AI setups (B11): a user asks for the ARMED alerts of an instrument and profile.
Nobody follows anything until they ask (no automatic follow)."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIAlertFollow
from app.models.instrument import Instrument
from app.models.user import User

# The profiles ai-service evaluates (the contract's ``profile``; to extend with Fadi)
PROFILES = frozenset({"intraday"})


async def list_follows(session: AsyncSession, user: User) -> list[AIAlertFollow]:
    rows = await session.scalars(
        select(AIAlertFollow)
        .where(AIAlertFollow.user_id == user.id)
        .order_by(AIAlertFollow.created_at, AIAlertFollow.instrument_id, AIAlertFollow.profile)
    )
    return list(rows.all())


async def follow(
    session: AsyncSession,
    user: User,
    instrument_id: uuid.UUID,
    profile: str,
    min_grade: str | None,
) -> AIAlertFollow:
    """Idempotent: a second call only changes ``min_grade``."""
    if profile not in PROFILES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown profile {profile!r} (one of: {', '.join(sorted(PROFILES))})",
        )
    if await session.get(Instrument, instrument_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrument not found")
    await session.execute(
        insert(AIAlertFollow)
        .values(user_id=user.id, instrument_id=instrument_id, profile=profile, min_grade=min_grade)
        .on_conflict_do_update(
            index_elements=["user_id", "instrument_id", "profile"], set_={"min_grade": min_grade}
        )
    )
    await session.commit()
    return await session.get(
        AIAlertFollow, (user.id, instrument_id, profile), populate_existing=True
    )


async def unfollow(
    session: AsyncSession, user: User, instrument_id: uuid.UUID, profile: str
) -> None:
    result = await session.execute(
        delete(AIAlertFollow).where(
            AIAlertFollow.user_id == user.id,
            AIAlertFollow.instrument_id == instrument_id,
            AIAlertFollow.profile == profile,
        )
    )
    if not result.rowcount:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not followed")
    await session.commit()
