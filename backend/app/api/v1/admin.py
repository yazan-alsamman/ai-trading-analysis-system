import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, SessionDep
from app.models.user import UserRole
from app.schemas.common import Page
from app.schemas.user import RoleUpdate, StatusUpdate, UserRead
from app.services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=Page[UserRead])
async def list_users(
    _: AdminUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    role: UserRole | None = None,
    is_active: bool | None = None,
    q: Annotated[str | None, Query(max_length=320, description="Email contains")] = None,
):
    items, total = await user_service.list_users(
        session, limit=limit, offset=offset, role=role, is_active=is_active, q=q
    )
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in items], total=total, limit=limit, offset=offset
    )


@router.patch("/users/{user_id}/role", response_model=UserRead)
async def update_role(user_id: uuid.UUID, data: RoleUpdate, admin: AdminUser, session: SessionDep):
    return await user_service.set_role(session, admin, user_id, data.role)


@router.patch("/users/{user_id}/status", response_model=UserRead)
async def update_status(
    user_id: uuid.UUID, data: StatusUpdate, admin: AdminUser, session: SessionDep
):
    return await user_service.set_status(session, admin, user_id, data.is_active)
