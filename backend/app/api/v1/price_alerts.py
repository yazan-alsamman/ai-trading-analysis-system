"""Price alerts (docs/price-alerts.md). JWT only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.alerts import service
from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import Page
from app.schemas.price_alerts import (
    PriceAlertCreate,
    PriceAlertCreated,
    PriceAlertRead,
    PriceAlertTrigger,
    PriceAlertUpdate,
)

router = APIRouter(prefix="/me/price-alerts", tags=["price-alerts"])


@router.get("", response_model=Page[PriceAlertRead])
async def list_alerts(
    user: CurrentUser,
    session: SessionDep,
    instrument_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await service.list_alerts(
        session, user, limit=limit, offset=offset, instrument_id=instrument_id, is_active=is_active
    )
    return Page[PriceAlertRead](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=PriceAlertCreated, status_code=status.HTTP_201_CREATED)
async def create_alert(data: PriceAlertCreate, user: CurrentUser, session: SessionDep):
    """``would_trigger_now``: an above/below alert the latest price already meets (it is
    created anyway and fires on the next closed 1m bar). 400 over your role's limit."""
    return await service.create(session, user, data)


@router.get("/history", response_model=Page[PriceAlertTrigger])
async def alert_history(
    user: CurrentUser,
    session: SessionDep,
    alert_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """The last triggers with their prices, newest first (from your notifications)."""
    items, total = await service.history(
        session, user, limit=limit, offset=offset, alert_id=alert_id
    )
    return Page[PriceAlertTrigger](items=items, total=total, limit=limit, offset=offset)


@router.patch("/{alert_id}", response_model=PriceAlertRead)
async def update_alert(
    alert_id: uuid.UUID, data: PriceAlertUpdate, user: CurrentUser, session: SessionDep
):
    alert = await service.own(session, user, alert_id)
    return await service.update(session, user, alert, data)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    await service.remove(session, await service.own(session, user, alert_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
