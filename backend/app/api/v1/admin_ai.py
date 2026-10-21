"""AI engine records for admins (B8, docs/ai-contract.md): setups stored from ai-service
responses with their events, and the model registry. User-facing reads come with B9/B11."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import func, select

from app.ai import alerts, store
from app.ai.contract import SetupState
from app.api.deps import AdminUser, SessionDep
from app.models.ai import (
    AIModelVersion,
    AISetup,
    AISetupEvent,
    AISetupOutbox,
    AISetupSize,
    AISetupTake,
)
from app.schemas.ai import (
    AIModelIn,
    AIModelRead,
    AISetupDetail,
    AISetupEventRead,
    AISetupRead,
    AISetupSizeBrief,
    OutboxRead,
)
from app.schemas.common import Page

router = APIRouter(prefix="/admin/ai", tags=["admin"])


@router.get("/setups", response_model=list[AISetupRead])
async def list_setups(
    _: AdminUser,
    session: SessionDep,
    state: SetupState | None = None,
    instrument_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Newest first."""
    query = select(AISetup).order_by(AISetup.created_at.desc(), AISetup.setup_id).limit(limit)
    if state is not None:
        query = query.where(AISetup.state == state.value)
    if instrument_id is not None:
        query = query.where(AISetup.instrument_id == instrument_id)
    return list((await session.scalars(query)).all())


@router.get("/setups/{setup_id}", response_model=AISetupDetail)
async def get_setup(
    setup_id: Annotated[str, Path(max_length=128)], _: AdminUser, session: SessionDep
):
    """A setup with its last payload, every state event (oldest first), the stored per-user
    sizes, how many users took it, and its alerts (outbox)."""
    row = await session.get(AISetup, setup_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Setup not found")
    events = await session.scalars(
        select(AISetupEvent)
        .where(AISetupEvent.setup_id == setup_id)
        .order_by(AISetupEvent.at, AISetupEvent.id)
    )
    sizes = await session.scalars(
        select(AISetupSize)
        .where(AISetupSize.setup_id == setup_id)
        .order_by(AISetupSize.computed_at.desc(), AISetupSize.user_id)
    )
    takes_count = await session.scalar(
        select(func.count()).select_from(AISetupTake).where(AISetupTake.setup_id == setup_id)
    )
    outbox = await session.scalars(
        select(AISetupOutbox).where(AISetupOutbox.setup_id == setup_id).order_by(AISetupOutbox.id)
    )
    return AISetupDetail.model_validate(
        {
            **AISetupRead.model_validate(row).model_dump(),
            "evidence": row.evidence,
            "features": row.features,
            "last_payload": row.last_payload,
            "events": [AISetupEventRead.model_validate(e) for e in events],
            "sizes": [AISetupSizeBrief.model_validate(r) for r in sizes],
            "takes_count": takes_count,
            "outbox": [OutboxRead.model_validate(r) for r in outbox],
        }
    )


@router.get("/outbox", response_model=Page[OutboxRead])
async def list_outbox(
    _: AdminUser,
    session: SessionDep,
    status_: Annotated[
        Literal["pending", "done", "skipped", "failed"] | None, Query(alias="status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """The AI setup alerts (B11), newest first, with attempts and errors."""
    filters = [AISetupOutbox.status == status_] if status_ else []
    total = await session.scalar(select(func.count()).select_from(AISetupOutbox).where(*filters))
    rows = await session.scalars(
        select(AISetupOutbox)
        .where(*filters)
        .order_by(AISetupOutbox.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page[OutboxRead](
        items=[OutboxRead.model_validate(r) for r in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post("/outbox/{row_id}/retry", response_model=OutboxRead)
async def retry_outbox(row_id: int, _: AdminUser, session: SessionDep):
    """A ``failed`` alert back to ``pending``, due now (``attempts`` kept). 409 otherwise."""
    row = await session.get(AISetupOutbox, row_id, with_for_update=True)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outbox row not found")
    if row.status != "failed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"the row is {row.status}, not failed")
    row.status, row.next_attempt_at = "pending", datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    alerts.kick()
    return row


@router.get("/models", response_model=list[AIModelRead])
async def list_models(_: AdminUser, session: SessionDep):
    """The registry, newest first (the active model is flagged)."""
    rows = await session.scalars(
        select(AIModelVersion).order_by(AIModelVersion.created_at.desc(), AIModelVersion.model_id)
    )
    return list(rows.all())


@router.post("/models", response_model=AIModelRead)
async def register_model(data: AIModelIn, _: AdminUser, session: SessionDep):
    """Register a model (inactive), or update the description of a known one."""
    return await store.register_model(
        session,
        data.model_id,
        training_from=data.training_from,
        training_to=data.training_to,
        data_hash=data.data_hash,
        metrics=data.metrics,
        notes=data.notes,
    )


@router.post("/models/{model_id}/activate", response_model=AIModelRead)
async def activate_model(
    model_id: Annotated[str, Path(max_length=128)], _: AdminUser, session: SessionDep
):
    """Make this model the only active one."""
    row = await store.activate_model(session, model_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    return row
