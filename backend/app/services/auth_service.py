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
from app.realtime import auth_events
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


async def _issue_pair(
    session: AsyncSession, user: User, family_id: uuid.UUID | None = None
) -> tuple[TokenPair, RefreshToken]:
    """A refresh token (a new session, or ``family_id``'s on rotation) and an access token
    whose ``sid`` is that session."""
    refresh_token, row = await create_refresh_token(session, user, family_id)
    pair = TokenPair(
        access_token=create_access_token(user, row.family_id),
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
    """End every session of a user (the caller commits, then publishes the ``user_id`` auth
    event): every still-active refresh token is revoked, and ``sessions_revoked_at`` is set so
    the WebSockets of older access tokens without a session id close too."""
    now = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.execute(update(User).where(User.id == user_id).values(sessions_revoked_at=now))


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
        await auth_events.publish(user_id=row.user_id)  # every session's WebSockets close
        raise credentials_exception("Refresh token has been revoked")
    if row.expires_at <= datetime.now(UTC):
        raise credentials_exception("Token has expired")

    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise credentials_exception("Invalid refresh token")

    pair, new_row = await _issue_pair(session, user, row.family_id or row.id)
    row.revoked_at = datetime.now(UTC)
    row.replaced_by = new_row.id
    await session.commit()
    return pair


async def logout(session: AsyncSession, user: User, token: str) -> None:
    """End the session of one of the current user's refresh tokens. Idempotent.

    The whole family is revoked, not only the presented row, so the session cannot be
    refreshed from an older sibling; then the session's WebSockets close (``session_id`` auth
    event, after the commit). The user's other sessions (other devices) are untouched."""
    payload = decode_token(token, "refresh")
    row = await session.get(RefreshToken, payload["jti"])
    if row is None or row.user_id != user.id:
        raise credentials_exception("Invalid refresh token")
    family = row.family_id or row.id
    ended = await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            (RefreshToken.family_id == family) | (RefreshToken.id == row.id),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    if ended.rowcount:
        await auth_events.publish(session_id=family)
