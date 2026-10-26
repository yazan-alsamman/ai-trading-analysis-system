"""AI setups for users (B10, docs/risk-management.md#ai-setups): the size of a setup for your
account, "I took this trade", and your taken trades. AI setups are global: whoever may read
signals may use them (``strategy_resolver.may_read_ai_setup``)."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Response, status

from app.ai import explain, follows, sizing, takes
from app.api.deps import CurrentUser, SessionDep, SignalsReader
from app.schemas.ai import (
    AIExplanationRead,
    AISizeInputs,
    AISizeRead,
    AITradeRead,
    FollowIn,
    FollowRead,
    TakeIn,
    TakeRead,
)
from app.schemas.common import Page
from app.services import risk_service

router = APIRouter(tags=["ai"])
SetupId = Annotated[str, Path(max_length=128)]


@router.get(
    "/ai/setups/{setup_id}/size",
    response_model=AISizeRead,
    responses={
        409: {"description": "the setup has no prices (not ARMED or ACTIVE), or no specs"},
        502: {"description": "ai-service answered outside the contract (no fallback)"},
        503: {"description": "ai-service unavailable and AI_SIZE_MODE=remote"},
    },
)
async def setup_size(setup_id: SetupId, principal: SignalsReader, session: SessionDep):
    """The setup sized for your account: by ai-service ``/v1/size`` or, when it is not
    available, by the backend (``source``). The daily-loss and drawdown guards of your taken
    trades apply first. Stored, and reused while the inputs are the same. 404 unknown setup,
    409 when it has no prices (not ARMED or ACTIVE) or its instrument no specs, 422 when your
    risk profile cannot be used, 502 when ai-service answers outside the contract, 503 when it
    is unavailable and no fallback is allowed (``AI_SIZE_MODE=remote``)."""
    user = principal.user
    setup = await takes.get_setup_or_404(session, user, setup_id)
    try:
        result = await sizing.size_setup_for_user(session, setup, user)
    except sizing.SizingError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    profile = await risk_service.get_or_create(session, user)
    sources = risk_service.ai_risk_inputs(profile).sources
    return AISizeRead(
        setup_id=setup_id,
        lots=result.lots,
        risk_amount=result.risk_amount,
        margin_required=result.margin_required,
        feasible=result.feasible,
        warnings=result.warnings,
        source=result.source,
        computed_at=result.computed_at,
        inputs=AISizeInputs(**result.inputs["account"], **result.inputs["risk"], sources=sources),
        taken=await takes.taken(session, user.id, setup_id),
    )


@router.get("/ai/setups/{setup_id}/explanation", response_model=AIExplanationRead)
async def setup_explanation(
    setup_id: SetupId,
    principal: SignalsReader,
    session: SessionDep,
    lang: Annotated[Literal["ar", "en"], Query()] = "en",
):
    """The setup's explanation in ``lang``, when it may be shown: verified by ai-service
    against the setup's numbers, or the fixed template filled with them. Otherwise
    ``explanation`` is null and ``explanation_status`` is ``unavailable`` (show "الشرح غير
    متاح" / "Explanation unavailable"). 404 unknown setup."""
    await takes.get_setup_or_404(session, principal.user, setup_id)
    shown = await explain.stored(session, setup_id, lang)
    return AIExplanationRead(
        setup_id=setup_id, lang=lang, explanation=shown.text, explanation_status=shown.status
    )


@router.post(
    "/ai/setups/{setup_id}/take",
    response_model=TakeRead,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": TakeRead, "description": "already taken (unchanged)"}},
)
async def take_setup(
    setup_id: SetupId,
    user: CurrentUser,
    session: SessionDep,
    response: Response,
    data: TakeIn | None = None,
):
    """I took this trade: only while the setup is ARMED or ACTIVE (409 otherwise). ``lots``
    defaults to your stored size. 201 the first time, 200 with the same take afterwards. The
    result (``realized_r``, ``pnl``) is filled when the setup ends."""
    data = data or TakeIn()
    row, created = await takes.take(
        session, user, setup_id, lots=data.lots, entry_price=data.entry_price
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return row


@router.delete("/ai/setups/{setup_id}/take", status_code=status.HTTP_204_NO_CONTENT)
async def untake_setup(setup_id: SetupId, user: CurrentUser, session: SessionDep):
    """Undo it, while the setup has not ended (409 after; 404 when not taken)."""
    await takes.untake(session, user, setup_id)


@router.get("/me/ai/follows", response_model=list[FollowRead])
async def my_ai_follows(user: CurrentUser, session: SessionDep):
    """The instruments and profiles whose ARMED setups you are alerted about."""
    return await follows.list_follows(session, user)


@router.put("/me/ai/follows/{instrument_id}/{profile}", response_model=FollowRead)
async def follow_ai_setups(
    instrument_id: uuid.UUID,
    profile: Annotated[str, Path(max_length=32)],
    user: CurrentUser,
    session: SessionDep,
    data: FollowIn | None = None,
):
    """Alert me when a setup of this instrument and profile becomes ARMED (optionally only
    from ``min_grade``). Idempotent: calling it again only changes ``min_grade``. 404 unknown
    instrument, 422 unknown profile. After ARMED you hear about a setup only if you took it."""
    data = data or FollowIn()
    return await follows.follow(session, user, instrument_id, profile, data.min_grade)


@router.delete("/me/ai/follows/{instrument_id}/{profile}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_ai_setups(
    instrument_id: uuid.UUID,
    profile: Annotated[str, Path(max_length=32)],
    user: CurrentUser,
    session: SessionDep,
):
    """Stop the ARMED alerts of this instrument and profile (404 when not followed)."""
    await follows.unfollow(session, user, instrument_id, profile)


@router.get("/me/ai/trades", response_model=Page[AITradeRead])
async def my_ai_trades(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Your taken AI setups, newest first, with the setup's state and your result."""
    rows, total = await takes.list_trades(session, user, limit=limit, offset=offset)
    items = [
        AITradeRead(
            **TakeRead.model_validate(t).model_dump(),
            instrument_id=s.instrument_id,
            profile=s.profile,
            direction=s.direction,
            state=s.state,
            entry=s.entry,
            sl=s.sl,
            tp=s.tp,
        )
        for t, s in rows
    ]
    return Page[AITradeRead](items=items, total=total, limit=limit, offset=offset)
