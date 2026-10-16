"""Risk management (docs/risk-management.md): your risk profile, the schema and templates, the
position-size calculator and the trade plans of your live signals."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep, StrategiesReader
from app.models.candle import Timeframe
from app.schemas.common import Page
from app.schemas.risk import (
    PositionSizeRequest,
    PositionSizeResponse,
    RiskProfileRead,
    RiskProfileUpdate,
    RiskSchema,
    SignalPlanRead,
)
from app.schemas.strategies import SignalRead
from app.services import risk_service as service

router = APIRouter(tags=["risk"])


@router.get("/risk/schema", response_model=RiskSchema)
async def risk_schema(_: StrategiesReader):
    """JSON Schema of a risk config (stop, trailing, take_profit, sizing, guards, fee_bps) and
    the normalised templates (conservative, balanced, aggressive)."""
    return service.schema()


@router.post("/risk/position-size", response_model=PositionSizeResponse)
async def position_size(
    data: PositionSizeRequest, principal: StrategiesReader, session: SessionDep
):
    """A trade plan on the last closed bar: stop, targets, quantity, money at risk and R:R.
    ``entry`` / ``stop`` default to the close and the stop rule; ``config`` and
    ``account_size`` to your risk profile."""
    return await service.position_size(session, principal.user, data)


@router.get("/me/risk-profile", response_model=RiskProfileRead)
async def get_risk_profile(user: CurrentUser, session: SessionDep):
    """Created with the ``balanced`` template and 10,000 USDT on first read."""
    return service.read(await service.get_or_create(session, user))


@router.put("/me/risk-profile", response_model=RiskProfileRead)
async def put_risk_profile(data: RiskProfileUpdate, user: CurrentUser, session: SessionDep):
    """``{account_size, quote_currency, config}`` or ``{template}``; 422 lists every config
    error with its path (e.g. ``stop.multiplier``)."""
    return service.read(await service.update(session, user, data))


@router.get("/me/signal-plans", response_model=Page[SignalPlanRead])
async def my_signal_plans(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    instrument_id: uuid.UUID | None = None,
    timeframe: Timeframe | None = None,
    strategy_key: Annotated[str | None, Query(max_length=64)] = None,
    since: Annotated[datetime | None, Query(description="bar_time >= since (ISO 8601)")] = None,
):
    """The trade plans of your live signals (one per signal and activation), newest bar first."""
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    rows, total = await service.list_plans(
        session,
        user,
        limit=limit,
        offset=offset,
        instrument_id=instrument_id,
        timeframe=timeframe,
        strategy_key=strategy_key,
        since=since,
    )
    items = [
        SignalPlanRead(
            id=p.id,
            user_strategy_id=p.user_strategy_id,
            plan=p.plan,
            created_at=p.created_at,
            signal=SignalRead.model_validate(s),
        )
        for p, s in rows
    ]
    return Page[SignalPlanRead](items=items, total=total, limit=limit, offset=offset)
