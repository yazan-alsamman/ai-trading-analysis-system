"""Backtests (docs/backtesting.md). Creating, cancelling/deleting and comparing need a JWT;
reading also works with an API key that has the ``backtests:read`` scope."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import BacktestsReader, CurrentUser, SessionDep
from app.api.limits import EXPENSIVE
from app.core.redis import get_redis
from app.models.backtest import BacktestStatus
from app.schemas.backtests import (
    BacktestAccepted,
    BacktestCreate,
    BacktestRead,
    BacktestSummary,
    CompareRequest,
    CompareResponse,
    TradeRead,
)
from app.schemas.common import Page
from app.services import backtest_service as service

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post(
    "",
    response_model=BacktestAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra=EXPENSIVE,
)
async def create_backtest(data: BacktestCreate, user: CurrentUser, session: SessionDep):
    """Queue a backtest; follow it on the WebSocket user topic (``backtest_progress``,
    ``backtest_completed`` / ``backtest_failed``) or poll ``GET /backtests/{id}``."""
    row = await service.create(session, user, data)
    await service.submit(session, row)
    return BacktestAccepted(id=row.id, status=row.status)


@router.get("", response_model=Page[BacktestSummary])
async def list_backtests(
    principal: BacktestsReader,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_: Annotated[BacktestStatus | None, Query(alias="status")] = None,
    strategy_key: Annotated[str | None, Query(max_length=64)] = None,
    instrument_id: uuid.UUID | None = None,
):
    """Your backtests, newest first, with headline metrics once completed."""
    items, total = await service.list_backtests(
        session,
        principal.user,
        limit=limit,
        offset=offset,
        status_=status_,
        strategy_key=strategy_key,
        instrument_id=instrument_id,
    )
    return Page[BacktestSummary](items=items, total=total, limit=limit, offset=offset)


@router.post("/compare", response_model=CompareResponse)
async def compare_backtests(data: CompareRequest, user: CurrentUser, session: SessionDep):
    """2–6 of your completed backtests: metrics side by side, equity normalised to 100."""
    return await service.compare(session, user, data.ids)


@router.get("/{backtest_id}", response_model=BacktestRead)
async def get_backtest(backtest_id: uuid.UUID, principal: BacktestsReader, session: SessionDep):
    """Everything a results page needs: config, status/progress, metrics, equity and drawdown
    curves (Lightweight Charts points, at most 2,000) and entry/exit markers."""
    row = await service.get_own_or_404(session, principal.user, backtest_id)
    return await service.read(session, row)


@router.get("/{backtest_id}/trades", response_model=Page[TradeRead])
async def list_trades(
    backtest_id: uuid.UUID,
    principal: BacktestsReader,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    row = await service.get_own_or_404(session, principal.user, backtest_id)
    trades, total = await service.trades_page(session, row, limit, offset)
    return Page[TradeRead](
        items=[TradeRead.model_validate(t) for t in trades],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{backtest_id}/trades.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_trades(backtest_id: uuid.UUID, principal: BacktestsReader, session: SessionDep):
    """All trades as CSV (one header row, ISO 8601 UTC times)."""
    row = await service.get_own_or_404(session, principal.user, backtest_id)
    body = service.trades_csv(await service.all_trades(session, row.id))
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="backtest-{row.id}-trades.csv"'},
    )


@router.delete("/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backtest(backtest_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Cancel a queued/running backtest (it stops at its next checkpoint), otherwise delete
    it with its trades."""
    await service.cancel_or_delete(session, get_redis(), user, backtest_id)
