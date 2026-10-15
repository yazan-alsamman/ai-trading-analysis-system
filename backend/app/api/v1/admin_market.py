import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, AggregateRefresherDep, SessionDep
from app.schemas.market import (
    CandleBatch,
    CandlesWritten,
    InstrumentCreate,
    InstrumentRead,
    InstrumentUpdate,
)
from app.services import market_service

router = APIRouter(prefix="/admin/instruments", tags=["admin"])


@router.post("", response_model=InstrumentRead, status_code=status.HTTP_201_CREATED)
async def create_instrument(data: InstrumentCreate, _: AdminUser, session: SessionDep):
    return await market_service.create_instrument(session, data)


@router.patch("/{instrument_id}", response_model=InstrumentRead)
async def update_instrument(
    instrument_id: uuid.UUID, data: InstrumentUpdate, _: AdminUser, session: SessionDep
):
    instrument = await market_service.get_instrument_or_404(session, instrument_id)
    return await market_service.update_instrument(session, instrument, data)


@router.post("/{instrument_id}/candles", response_model=CandlesWritten)
async def upsert_candles(
    instrument_id: uuid.UUID,
    data: CandleBatch,
    _: AdminUser,
    session: SessionDep,
    refresh_aggregates: AggregateRefresherDep,
):
    """Bulk upsert of 1m candles (max 5,000 per request), e.g. for backfill scripts.

    Batches reaching further back than the refresh policies' window also refresh the
    aggregates for the affected days, so higher timeframes show the backfilled data at once.
    """
    await market_service.get_instrument_or_404(session, instrument_id)
    written = await market_service.upsert_candles(session, instrument_id, data.candles)
    await session.commit()
    if market_service.needs_aggregate_refresh(data.candles):
        await refresh_aggregates(min(c.ts for c in data.candles), max(c.ts for c in data.candles))
    return CandlesWritten(written=written)
