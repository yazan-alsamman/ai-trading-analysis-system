"""Taken AI setups (B10): a user says they took a setup. The result is filled by
``store.apply_evaluation`` when the setup ends (``_close_takes``)."""

from __future__ import annotations

import uuid

import trading_backtest as tb
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contract import FINAL_STATES
from app.ai.sizing import PRICED
from app.models.ai import AISetup, AISetupSize, AISetupTake
from app.models.instrument import Instrument
from app.models.user import User
from app.services import risk_service, strategy_resolver

FINAL = frozenset(s.value for s in FINAL_STATES)


async def get_setup_or_404(session: AsyncSession, user: User, setup_id: str) -> AISetup:
    row = await session.get(AISetup, setup_id)
    if row is None or not strategy_resolver.may_read_ai_setup(user, row):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Setup not found")
    return row


async def _risk_per_lot(
    session: AsyncSession, setup: AISetup, user: User, stored: AISetupSize | None
) -> float | None:
    """Money lost per lot at the stop, in the user's account currency: from their stored size,
    else from the specs and the stop (None when unknown)."""
    if stored is not None and stored.lots > 0:
        return stored.risk_usd / stored.lots
    instrument = await session.get(Instrument, setup.instrument_id)
    spec = risk_service.contract_spec(instrument) if instrument is not None else None
    if spec is None or setup.entry is None or setup.sl is None:
        return None
    profile = await risk_service.get_or_create(session, user)
    rate, _ = await risk_service.conversion_rate(
        session, instrument, profile.quote_currency, setup.entry
    )
    try:
        per_unit = tb.value_per_price_unit(
            spec.contract_size, spec.quote_currency, profile.quote_currency, rate
        )
    except ValueError:
        return None
    return abs(setup.entry - setup.sl) * per_unit


async def take(
    session: AsyncSession,
    user: User,
    setup_id: str,
    *,
    lots: float | None = None,
    entry_price: float | None = None,
) -> tuple[AISetupTake, bool]:
    """(the take, created). Only while the setup is ARMED or ACTIVE; a second call returns the
    existing take unchanged. ``lots`` defaults to the user's stored size; ``risk_amount`` is
    the risk of those lots at the setup's stop."""
    setup = await get_setup_or_404(session, user, setup_id)
    existing = await session.get(AISetupTake, (setup_id, user.id))
    if existing is not None:
        return existing, False
    if setup.state not in PRICED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"a {setup.state} setup cannot be taken (ARMED or ACTIVE)"
        )
    stored = await session.get(AISetupSize, (setup_id, user.id))
    if lots is None and stored is not None:
        lots = stored.lots
    per_lot = await _risk_per_lot(session, setup, user, stored)
    risk_amount = round(lots * per_lot, 4) if lots is not None and per_lot is not None else None
    await session.execute(
        insert(AISetupTake)
        .values(
            setup_id=setup_id,
            user_id=user.id,
            lots=lots,
            risk_amount=risk_amount,
            entry_price=entry_price,
        )
        .on_conflict_do_nothing(index_elements=["setup_id", "user_id"])
    )
    await session.commit()
    row = await session.get(AISetupTake, (setup_id, user.id), populate_existing=True)
    return row, True


async def untake(session: AsyncSession, user: User, setup_id: str) -> None:
    """Undo a take, only while the setup has not ended."""
    setup = await get_setup_or_404(session, user, setup_id)
    row = await session.get(AISetupTake, (setup_id, user.id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You have not taken this setup")
    if setup.state in FINAL:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"the setup is {setup.state}: its take is final"
        )
    await session.delete(row)
    await session.commit()


async def taken(session: AsyncSession, user_id: uuid.UUID, setup_id: str) -> bool:
    return await session.get(AISetupTake, (setup_id, user_id)) is not None


async def list_trades(
    session: AsyncSession, user: User, *, limit: int, offset: int
) -> tuple[list[tuple[AISetupTake, AISetup]], int]:
    """The user's takes, newest first, with their setups."""
    total = await session.scalar(
        select(func.count()).select_from(AISetupTake).where(AISetupTake.user_id == user.id)
    )
    rows = await session.execute(
        select(AISetupTake, AISetup)
        .join(AISetup, AISetup.setup_id == AISetupTake.setup_id)
        .where(AISetupTake.user_id == user.id)
        .order_by(AISetupTake.taken_at.desc(), AISetupTake.setup_id)
        .limit(limit)
        .offset(offset)
    )
    return [(t, s) for t, s in rows.all()], total or 0
