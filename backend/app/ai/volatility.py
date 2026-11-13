"""The day's expected move (B13, contract 0.3.0 ``EvaluateResponse.volatility``): what the
web and mobile apps show as "توقع حركة اليوم". The first ``ok`` answer of each New York trading
day is stored by ``store.store_volatility`` and never changes; this module reads it."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contract import NEW_YORK, VOLATILITY_WINDOW, d1_close, d1_open
from app.models.ai import AIVolatilityDaily

WINDOW_OPENS = (2, 0)  # 02:00 New York: the day's value is known from then


def trading_day(now: datetime) -> date:
    """The New York trading day of ``now`` (17:00 to 17:00, named after its close)."""
    return d1_close(d1_open(now)).astimezone(NEW_YORK).date()


def pending_reason(now: datetime) -> str:
    """Why today's value is not there: ``weekend`` (a Saturday or Sunday trading day),
    ``before_window`` (before 02:00 New York; after 17:00 the next day has begun), else
    ``not_received`` (no ``ok`` answer yet)."""
    day = trading_day(now)
    local = now.astimezone(NEW_YORK)
    if day.weekday() >= 5:
        return "weekend"
    if local.date() != day or (local.hour, local.minute) < WINDOW_OPENS:
        return "before_window"
    return "not_received"


async def today(session: AsyncSession, instrument_id: uuid.UUID, now: datetime) -> dict[str, Any]:
    """Today's stored row (``status`` as stored, ``ok``), or ``status: pending`` with why."""
    day = trading_day(now)
    row = await session.get(AIVolatilityDaily, (instrument_id, day))
    if row is not None:
        return {"row": row, "reason": None}
    return {
        "row": None,
        "instrument_id": instrument_id,
        "day": day,
        "status": "pending",
        "reason": pending_reason(now),
        "window": VOLATILITY_WINDOW,
    }
