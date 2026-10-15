import uuid
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import PasswordChange, UserCreate, UserUpdate
from app.services import auth_service


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.lower()))


async def get_or_404(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


async def register(session: AsyncSession, data: UserCreate) -> User:
    """Self-registration: always creates a trader, whatever the client sends."""
    if await get_by_email(session, data.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole.trader,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:  # concurrent registration with the same email
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from exc
    await session.refresh(user)
    return user


async def update_profile(session: AsyncSession, user: User, data: UserUpdate) -> User:
    if "full_name" in data.model_fields_set:
        user.full_name = data.full_name
    await session.commit()
    await session.refresh(user)
    return user


async def change_password(session: AsyncSession, user: User, data: PasswordChange) -> None:
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.hashed_password = hash_password(data.new_password)
    await auth_service.revoke_all_refresh_tokens(session, user.id)
    await session.commit()


async def list_users(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    role: UserRole | None = None,
    is_active: bool | None = None,
    q: str | None = None,
) -> tuple[Sequence[User], int]:
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active == is_active)
    if q:
        escaped = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filters.append(User.email.like(f"%{escaped}%", escape="\\"))
    total = await session.scalar(select(func.count()).select_from(User).where(*filters))
    rows = await session.scalars(
        select(User).where(*filters).order_by(User.created_at, User.id).limit(limit).offset(offset)
    )
    return rows.all(), total or 0


async def set_role(session: AsyncSession, actor: User, user_id: uuid.UUID, role: UserRole) -> User:
    user = await get_or_404(session, user_id)
    if user.id == actor.id and role != UserRole.admin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Admins cannot demote themselves")
    user.role = role
    await session.commit()
    await session.refresh(user)
    return user


async def set_status(
    session: AsyncSession, actor: User, user_id: uuid.UUID, is_active: bool
) -> User:
    user = await get_or_404(session, user_id)
    if user.id == actor.id and not is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Admins cannot deactivate themselves")
    user.is_active = is_active
    if not is_active:
        await auth_service.revoke_all_refresh_tokens(session, user.id)
    await session.commit()
    await session.refresh(user)
    return user


async def admin_exists(session: AsyncSession) -> bool:
    admin_id = await session.scalar(select(User.id).where(User.role == UserRole.admin).limit(1))
    return admin_id is not None


async def ensure_admin(session: AsyncSession, email: str, password: str) -> tuple[User, bool]:
    """Create an admin, or promote (and reactivate) an existing user. Returns (user, created).

    An existing user's password is left unchanged.
    """
    user = await get_by_email(session, email)
    created = user is None
    if user is None:
        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            role=UserRole.admin,
        )
        session.add(user)
    else:
        user.role = UserRole.admin
        user.is_active = True
    await session.commit()
    await session.refresh(user)
    return user, created
