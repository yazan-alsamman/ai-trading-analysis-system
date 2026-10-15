import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminUser, SessionDep
from app.core import rate_limit
from app.core.redis import get_redis
from app.models.api_key import ApiKey
from app.schemas.api_keys import AdminApiKeyRead, ApiKeyRead
from app.schemas.common import Page
from app.services import api_key_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/api-keys", response_model=Page[AdminApiKeyRead])
async def list_api_keys(
    _: AdminUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    user_id: uuid.UUID | None = None,
    revoked: bool | None = None,
):
    rows, total = await api_key_service.list_all(
        session, limit=limit, offset=offset, user_id=user_id, revoked=revoked
    )
    items = [
        AdminApiKeyRead(
            **ApiKeyRead.model_validate(key).model_dump(), user_id=key.user_id, owner_email=email
        )
        for key, email in rows
    ]
    return Page[AdminApiKeyRead](items=items, total=total, limit=limit, offset=offset)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, _: AdminUser, session: SessionDep) -> None:
    row = await session.get(ApiKey, key_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    await api_key_service.revoke(session, row)


@router.get("/rate-limits/stats")
async def rate_limit_stats(_: AdminUser) -> dict:
    """429s of the last hour by tier and route group (all API processes, from Redis), and the
    requests let through while Redis was unreachable (this API process only)."""
    return {
        "window_minutes": rate_limit.STATS_WINDOW_MINUTES,
        "rejected": await rate_limit.rejection_stats(get_redis()),
        "fail_open": {
            "process_total": rate_limit.fail_open.total,
            "process_last_hour": rate_limit.fail_open.last_hour(),
        },
    }
