import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.core import rate_limit
from app.core.redis import get_redis
from app.schemas.api_keys import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRead,
    ApiKeyUpdate,
    ApiKeyUsageDay,
)
from app.services import api_key_service

# JWT only (CurrentUser): an API key cannot manage keys.
router = APIRouter(prefix="/me/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(data: ApiKeyCreate, user: CurrentUser, session: SessionDep):
    """Create a key. The full key is in this response only; it cannot be shown again."""
    row, key = await api_key_service.create(session, user, data)
    return ApiKeyCreated(**ApiKeyRead.model_validate(row).model_dump(), key=key)


@router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(user: CurrentUser, session: SessionDep):
    return await api_key_service.list_for_user(session, user)


@router.patch("/{key_id}", response_model=ApiKeyRead)
async def update_api_key(
    key_id: uuid.UUID, data: ApiKeyUpdate, user: CurrentUser, session: SessionDep
):
    row = await api_key_service.get_own_or_404(session, user, key_id)
    return await api_key_service.update(session, user, row, data)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    row = await api_key_service.get_own_or_404(session, user, key_id)
    await api_key_service.revoke(session, row)


@router.get("/{key_id}/usage", response_model=list[ApiKeyUsageDay])
async def api_key_usage(key_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Requests (allowed) and rejected (429) per UTC day, the last 7 days, oldest first."""
    row = await api_key_service.get_own_or_404(session, user, key_id)
    return await rate_limit.daily_usage(get_redis(), row.id)
