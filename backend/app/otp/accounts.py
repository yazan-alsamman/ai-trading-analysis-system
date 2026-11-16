"""Phone verification and sign-in with a WhatsApp code (docs/otp.md)."""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import credentials_exception
from app.models.user import User
from app.otp import service
from app.otp.service import Purpose
from app.schemas.auth import TokenPair
from app.services import auth_service


def _phone_taken() -> HTTPException:
    return service.error(
        status.HTTP_409_CONFLICT, "phone_taken", "This number belongs to another account"
    )


async def _owner(session: AsyncSession, phone: str) -> User | None:
    return await session.scalar(select(User).where(User.phone_e164 == phone))


async def request_verification(
    session: AsyncSession, redis: Redis, user: User, phone: str
) -> dict[str, Any]:
    """Send a code to ``phone`` to prove that the signed-in user owns it."""
    owner = await _owner(session, phone)
    if owner is not None and owner.id != user.id:
        raise _phone_taken()
    return await service.send_code(redis, Purpose.verify_phone, phone, user_id=user.id)


async def confirm(session: AsyncSession, redis: Redis, user: User, phone: str, code: str) -> User:
    """Check the code and save the number on the account (replacing a previous one)."""
    await service.check_code(redis, Purpose.verify_phone, phone, code, user_id=user.id)
    owner = await _owner(session, phone)
    if owner is not None and owner.id != user.id:
        raise _phone_taken()
    user.phone_e164 = phone
    user.phone_verified_at = datetime.now(UTC)
    try:
        await session.commit()
    except IntegrityError as exc:  # verified by another account at the same moment
        await session.rollback()
        raise _phone_taken() from exc
    await session.refresh(user)
    return user


async def remove(session: AsyncSession, user: User) -> None:
    user.phone_e164 = None
    user.phone_verified_at = None
    await session.commit()


async def request_login_code(session: AsyncSession, redis: Redis, phone: str) -> dict[str, Any]:
    """Same answer whether or not an account has this verified number."""
    owner = await _owner(session, phone)
    deliver = owner is not None and owner.is_active and owner.phone_verified_at is not None
    return await service.send_code(redis, Purpose.login, phone, deliver=deliver)


async def login(
    session: AsyncSession,
    redis: Redis,
    phone: str,
    code: str,
    client: tuple[str, str] | None = None,
) -> TokenPair:
    await service.check_code(redis, Purpose.login, phone, code)
    owner = await _owner(session, phone)
    if owner is None or owner.phone_verified_at is None:
        raise credentials_exception("Invalid code")
    if not owner.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    return await auth_service.sign_in(session, owner, client)
