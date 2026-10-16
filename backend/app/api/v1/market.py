import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import MarketReader, SessionDep
from app.models.candle import Timeframe
from app.models.instrument import MarketType
from app.schemas.common import Page
from app.schemas.market import CandleOut, CandleSeries, InstrumentRead
from app.services import market_service

router = APIRouter(prefix="/market", tags=["market"])


def _as_utc(value: datetime | None) -> datetime | None:
    """Naive datetimes in query strings are taken as UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@router.get("/instruments", response_model=Page[InstrumentRead])
async def list_instruments(
    _: MarketReader,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    market: MarketType | None = None,
    source: Annotated[str | None, Query(max_length=32)] = None,
    is_active: bool | None = None,
    q: Annotated[str | None, Query(max_length=32, description="Symbol contains")] = None,
):
    items, total = await market_service.list_instruments(
        session,
        limit=limit,
        offset=offset,
        market=market,
        source=source,
        is_active=is_active,
        q=q,
    )
    return Page[InstrumentRead](
        items=[InstrumentRead.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/instruments/{instrument_id}", response_model=InstrumentRead)
async def get_instrument(instrument_id: uuid.UUID, _: MarketReader, session: SessionDep):
    return await market_service.get_instrument_or_404(session, instrument_id)


@router.get("/instruments/{instrument_id}/candles", response_model=CandleSeries)
async def get_candles(
    instrument_id: uuid.UUID,
    _: MarketReader,
    session: SessionDep,
    timeframe: Timeframe,
    start: Annotated[datetime | None, Query(description="ISO 8601, inclusive")] = None,
    end: Annotated[datetime | None, Query(description="ISO 8601, inclusive")] = None,
    limit: Annotated[int, Query(ge=1, le=market_service.MAX_CANDLES_LIMIT)] = 500,
):
    """Candles ascending by time. With ``start``: the first ``limit`` candles from ``start``;
    otherwise the latest ``limit`` candles (up to ``end`` if given)."""
    start, end = _as_utc(start), _as_utc(end)
    if start is not None and end is not None and start > end:
        raise HTTPException(422, "start must be <= end")
    await market_service.get_instrument_or_404(session, instrument_id)
    rows = await market_service.get_candles(
        session, instrument_id, timeframe, start=start, end=end, limit=limit
    )
    return CandleSeries(
        instrument_id=instrument_id,
        timeframe=timeframe,
        candles=[CandleOut.from_candle(r) for r in rows],
    )
