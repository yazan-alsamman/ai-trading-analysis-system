"""Paper trading: a simulated account with virtual USD (docs/paper-trading.md). JWT only."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.paper import service
from app.schemas.common import Page
from app.schemas.paper import (
    PaperAccountRead,
    PaperLevelsUpdate,
    PaperLeverageUpdate,
    PaperOrderCreate,
    PaperOrderRead,
    PaperPositionRead,
    PaperReset,
)

router = APIRouter(prefix="/me/paper", tags=["paper-trading"])


async def _account_view(session, user):
    account = await service.get_account(session, user.id)
    view = await service.summary(session, account)
    await session.commit()  # a first read creates the account
    return view


@router.get("/account", response_model=PaperAccountRead)
async def get_account(user: CurrentUser, session: SessionDep):
    """The portfolio (created on first use with PAPER_INITIAL_BALANCE USD and the default
    leverage): balance, equity, open and realized P/L, margin, today's P/L."""
    service.require_enabled()
    return await _account_view(session, user)


@router.patch("/account", response_model=PaperAccountRead)
async def update_account(data: PaperLeverageUpdate, user: CurrentUser, session: SessionDep):
    """Change the leverage (applies to new positions)."""
    service.require_enabled()
    await service.set_leverage(session, user, data.leverage)
    return await _account_view(session, user)


@router.post("/account/reset", response_model=PaperAccountRead)
async def reset_account(user: CurrentUser, session: SessionDep, data: PaperReset | None = None):
    """Delete every order and position and start again (optionally with another balance)."""
    service.require_enabled()
    await service.reset(session, user, data.initial_balance if data else None)
    return await _account_view(session, user)


@router.post(
    "/orders",
    response_model=PaperOrderRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {
            "description": "`market_closed`, `no_price`, `too_many_positions`, `too_many_orders`"
        },
        422: {
            "description": "`invalid_lots`, `invalid_price`, `invalid_stop_loss`, "
            "`invalid_take_profit`, `insufficient_margin`, `no_contract_spec`, "
            "`unsupported_currency`, `inactive_instrument`"
        },
    },
)
async def place_order(data: PaperOrderCreate, user: CurrentUser, session: SessionDep):
    """A market order fills at once at the latest 1m close (status `filled`, `position_id`
    set). A limit / stop order is `pending` until the engine fills it on a closed 1m bar.
    Optional stop loss and take profit are copied to the position."""
    service.require_enabled()
    return await service.place_order(session, user, data)


@router.get("/orders", response_model=Page[PaperOrderRead])
async def list_orders(
    user: CurrentUser,
    session: SessionDep,
    status_: Annotated[
        Literal["pending", "filled", "cancelled", "rejected"] | None, Query(alias="status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await service.list_orders(
        session, user, status_=status_, limit=limit, offset=offset
    )
    return Page[PaperOrderRead](items=items, total=total, limit=limit, offset=offset)


@router.delete("/orders/{order_id}", response_model=PaperOrderRead)
async def cancel_order(order_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Cancel a pending order (409 `not_pending` otherwise)."""
    return await service.cancel_order(session, user, order_id)


@router.get("/positions", response_model=Page[PaperPositionRead])
async def list_positions(
    user: CurrentUser,
    session: SessionDep,
    status_: Annotated[Literal["open", "closed"] | None, Query(alias="status")] = "open",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Open positions (default) with the current price and open P/L, or the closed ones
    (history, newest first)."""
    items, total = await service.list_positions(
        session, user, status_=status_, limit=limit, offset=offset
    )
    return Page[PaperPositionRead](items=items, total=total, limit=limit, offset=offset)


@router.patch("/positions/{position_id}", response_model=PaperPositionRead)
async def update_position(
    position_id: uuid.UUID, data: PaperLevelsUpdate, user: CurrentUser, session: SessionDep
):
    """Move (or remove with null) the stop loss and take profit of an open position."""
    return await service.update_levels(session, user, position_id, data)


@router.post("/positions/{position_id}/close", response_model=PaperPositionRead)
async def close_position(position_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Close at the latest 1m close (409 `market_closed` when there is no live price)."""
    service.require_enabled()
    return await service.close_position(session, user, position_id)
