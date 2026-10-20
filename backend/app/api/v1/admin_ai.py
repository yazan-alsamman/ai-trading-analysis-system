"""AI engine records for admins (B8, docs/ai-contract.md): setups stored from ai-service
responses with their events, and the model registry. User-facing reads come with B9/B11."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import select

from app.ai import store
from app.ai.contract import SetupState
from app.api.deps import AdminUser, SessionDep
from app.models.ai import AIModelVersion, AISetup, AISetupEvent
from app.schemas.ai import AIModelIn, AIModelRead, AISetupDetail, AISetupEventRead, AISetupRead

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
    """A setup with its last payload and every state event (oldest first)."""
    row = await session.get(AISetup, setup_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Setup not found")
    events = await session.scalars(
        select(AISetupEvent)
        .where(AISetupEvent.setup_id == setup_id)
        .order_by(AISetupEvent.at, AISetupEvent.id)
    )
    return AISetupDetail.model_validate(
        {
            **AISetupRead.model_validate(row).model_dump(),
            "evidence": row.evidence,
            "features": row.features,
            "last_payload": row.last_payload,
            "events": [AISetupEventRead.model_validate(e) for e in events],
        }
    )


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
