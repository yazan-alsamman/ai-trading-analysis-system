"""Experts directory, expert profiles and plans, the subscribers' signals feed, earnings
(docs/subscriptions.md). JWT only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.experts import service
from app.schemas.common import Page
from app.schemas.experts import (
    EarningsRead,
    ExpertCard,
    ExpertDetail,
    ExpertProfileIn,
    ExpertProfileRead,
    PlanIn,
    PlanRead,
    PlanUpdate,
)

router = APIRouter(tags=["experts"])


@router.get("/experts", response_model=Page[ExpertCard])
async def list_experts(
    user: CurrentUser,
    session: SessionDep,
    market: Annotated[str | None, Query(max_length=32)] = None,
    language: Annotated[str | None, Query(max_length=8)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Listed experts, most subscribed first. ``rating`` is a placeholder (null)."""
    items, total = await service.directory(
        session, user, market=market, language=language, q=q, limit=limit, offset=offset
    )
    return Page[ExpertCard](items=items, total=total, limit=limit, offset=offset)


@router.get("/experts/{expert_id}", response_model=ExpertDetail)
async def get_expert(expert_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    return await service.detail(session, user, expert_id)


@router.get("/experts/{expert_id}/signals")
async def expert_signals(
    expert_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Signals of the expert's public custom strategies that the expert runs, with the
    expert's trade plan. Subscribers with the ``signals_feed`` perk (403 otherwise)."""
    items, total = await service.signals_feed(session, user, expert_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/me/expert-profile", response_model=ExpertProfileRead)
async def get_my_profile(user: CurrentUser, session: SessionDep):
    return await service.own_profile(session, user)


@router.put("/me/expert-profile", response_model=ExpertProfileRead)
async def put_my_profile(data: ExpertProfileIn, user: CurrentUser, session: SessionDep):
    """Experts only (403 otherwise). Created on the first PUT."""
    return await service.upsert_profile(session, user, data)


@router.get("/me/plans", response_model=list[PlanRead])
async def my_plans(user: CurrentUser, session: SessionDep):
    service.require_expert(user)
    return await service.list_plans(session, user.id, active_only=False)


@router.post("/me/plans", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
async def create_plan(data: PlanIn, user: CurrentUser, session: SessionDep):
    """At most 3 active plans (409)."""
    return await service.create_plan(session, user, data)


@router.patch("/me/plans/{plan_id}", response_model=PlanRead)
async def update_plan(plan_id: uuid.UUID, data: PlanUpdate, user: CurrentUser, session: SessionDep):
    """A new price applies to new subscriptions and from each subscription's next renewal."""
    plan = await service.own_plan(session, user, plan_id)
    return await service.update_plan(session, user, plan, data)


@router.delete("/me/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_plan(plan_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    """Plans are never deleted (subscriptions refer to them): this deactivates it. Existing
    subscriptions keep renewing at their price."""
    plan = await service.own_plan(session, user, plan_id)
    plan.is_active = False
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/earnings", response_model=EarningsRead)
async def my_earnings(user: CurrentUser, session: SessionDep):
    return await service.earnings(session, user)
