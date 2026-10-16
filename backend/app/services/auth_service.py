import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    credentials_exception,
    decode_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair

logger = logging.getLogger(__name__)

INVALID_LOGIN = "Incorrect email or password"


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if not verify_password(password, user.hashed_password if user else None):
        raise credentials_exception(INVALID_LOGIN)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    return user


async def _issue_pair(session: AsyncSession, user: User) -> tuple[TokenPair, RefreshToken]:
    refresh_token, row = await create_refresh_token(session, user)
    pair = TokenPair(
        access_token=create_access_token(user),
        refresh_token=refresh_token,
        expires_in=get_settings().jwt_access_minutes * 60,
    )
    return pair, row


async def login(
    session: AsyncSession, email: str, password: str, client: tuple[str, str] | None = None
) -> TokenPair:
    """``client`` = (IP, user agent): a sign-in from a new one notifies the user (Y15)."""
    user = await authenticate(session, email, password)
    pair, _ = await _issue_pair(session, user)
    await session.commit()
    if client is not None:
        from app.notifications import security  # noqa: PLC0415 - keeps auth imports light

        try:
            await security.on_login(session, user, *client)
        except Exception:  # noqa: BLE001 - never block a sign-in
            logger.exception("Recording the sign-in fingerprint failed")
            await session.rollback()
    return pair


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every still-active refresh token of a user (the caller commits)."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def refresh(session: AsyncSession, token: str) -> TokenPair:
    """Rotate a refresh token. Presenting an already-revoked token revokes all of the user's."""
    payload = decode_token(token, "refresh")
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.id == payload["jti"]).with_for_update()
    )
    if row is None or row.user_id != payload["sub"]:
        raise credentials_exception("Invalid refresh token")
    if row.revoked_at is not None:
        logger.warning("Refresh token reuse detected for user %s", row.user_id)
        await revoke_all_refresh_tokens(session, row.user_id)
        await session.commit()
        raise credentials_exception("Refresh token has been revoked")
    if row.expires_at <= datetime.now(UTC):
        raise credentials_exception("Token has expired")

    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise credentials_exception("Invalid refresh token")

    pair, new_row = await _issue_pair(session, user)
    row.revoked_at = datetime.now(UTC)
    row.replaced_by = new_row.id
    await session.commit()
    return pair


async def logout(session: AsyncSession, user: User, token: str) -> None:
    """Revoke one of the current user's refresh tokens. Idempotent."""
    payload = decode_token(token, "refresh")
    row = await session.get(RefreshToken, payload["jti"])
    if row is None or row.user_id != user.id:
        raise credentials_exception("Invalid refresh token")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await session.commit()
