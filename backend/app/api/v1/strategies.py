import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

import trading_strategies as ts
from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, SessionDep, SignalsReader, StrategiesReader
from app.api.limits import EXPENSIVE
from app.models.candle import Timeframe
from app.schemas.common import Page
from app.schemas.strategies import (
    SignalRead,
    StrategyPreviewRequest,
    UserStrategyCreate,
    UserStrategyRead,
    UserStrategyUpdate,
)
from app.services import strategy_service

router = APIRouter(tags=["strategies"])


@router.get("/strategies")
async def strategy_catalog(_: StrategiesReader) -> list[dict]:
    """The global strategies: description, params (type, default, min, max), the indicator
    lines to draw with each one, and the history (bars) it needs before its first signal."""
    return ts.catalog()


@router.post("/strategies/{key}/preview", openapi_extra=EXPENSIVE)
async def preview_strategy(
    key: str, data: StrategyPreviewRequest, _: StrategiesReader, session: SessionDep
) -> Response:
    """Run a strategy over the same candle window ``GET .../candles`` returns. Response:
    ``signals`` (time, side, strength, price, reason, details), Lightweight Charts ``markers``
    and the strategy's ``indicators`` lines (same format as the indicators endpoint)."""
    result = await strategy_service.preview(session, key, data)
    body = json.dumps(result, separators=(",", ":"), allow_nan=False)
    return Response(content=body, media_type="application/json")


@router.get("/me/strategies", response_model=list[UserStrategyRead])
async def my_strategies(user: CurrentUser, session: SessionDep):
    return await strategy_service.list_user_strategies(session, user)


@router.post("/me/strategies", response_model=UserStrategyRead, status_code=status.HTTP_201_CREATED)
async def activate_strategy(data: UserStrategyCreate, user: CurrentUser, session: SessionDep):
    return await strategy_service.create_user_strategy(session, user, data)


@router.patch("/me/strategies/{user_strategy_id}", response_model=UserStrategyRead)
async def update_strategy(
    user_strategy_id: uuid.UUID, data: UserStrategyUpdate, user: CurrentUser, session: SessionDep
):
    row = await strategy_service.get_user_strategy_or_404(session, user, user_strategy_id)
    return await strategy_service.update_user_strategy(session, row, data)


@router.delete("/me/strategies/{user_strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(user_strategy_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    row = await strategy_service.get_user_strategy_or_404(session, user, user_strategy_id)
    await strategy_service.delete_user_strategy(session, row)


@router.get("/signals", response_model=Page[SignalRead])
async def list_signals(
    principal: SignalsReader,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    instrument_id: uuid.UUID | None = None,
    timeframe: Timeframe | None = None,
    strategy_key: Annotated[str | None, Query(max_length=64)] = None,
    since: Annotated[datetime | None, Query(description="bar_time >= since (ISO 8601)")] = None,
    mine: Annotated[bool, Query(description="only signals of my active strategies")] = False,
):
    """Signals, newest bar first."""
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)  # naive = UTC, like everywhere else
    rows, total = await strategy_service.list_signals(
        session,
        principal.user,
        limit=limit,
        offset=offset,
        instrument_id=instrument_id,
        timeframe=timeframe,
        strategy_key=strategy_key,
        since=since,
        mine=mine,
    )
    return Page[SignalRead](
        items=[SignalRead.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )
