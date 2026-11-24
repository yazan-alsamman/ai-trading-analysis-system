import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.refresh_token import RefreshToken
from app.models.user import User

TokenType = Literal["access", "refresh"]

password_hash = PasswordHash.recommended()

# Verified against when the email is unknown, so login timing does not reveal which emails exist.
_DUMMY_HASH = password_hash.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str | None) -> bool:
    if hashed_password is None:
        password_hash.verify(password, _DUMMY_HASH)
        return False
    return password_hash.verify(password, hashed_password)


def _encode(claims: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user: User, session_id: uuid.UUID | None = None) -> str:
    """``session_id``: the login session (the refresh-token family), as the ``sid`` claim. A
    token without one (issued before B12 part 2, or minted by scripts) has no session."""
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=get_settings().jwt_access_minutes),
    }
    if session_id is not None:
        claims["sid"] = str(session_id)
    return _encode(claims)


async def create_refresh_token(
    session: AsyncSession, user: User, family_id: uuid.UUID | None = None
) -> tuple[str, RefreshToken]:
    """Issue a refresh token and add its row to the session (the caller commits).
    ``family_id``: the session it continues (a rotation); None starts one (a login)."""
    now = datetime.now(UTC)
    row_id = uuid.uuid4()
    row = RefreshToken(
        id=row_id,
        user_id=user.id,
        expires_at=now + timedelta(days=get_settings().jwt_refresh_days),
        family_id=family_id or row_id,
    )
    session.add(row)
    await session.flush()
    token = _encode(
        {
            "sub": str(user.id),
            "jti": str(row.id),
            "type": "refresh",
            "iat": now,
            "exp": row.expires_at,
        }
    )
    return token, row


def credentials_exception(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise credentials_exception("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise credentials_exception() from exc
    if payload.get("type") != expected_type:
        raise credentials_exception()
    try:
        payload["sub"] = uuid.UUID(payload["sub"])
        if expected_type == "refresh":
            payload["jti"] = uuid.UUID(payload["jti"])
        else:
            payload["sid"] = uuid.UUID(payload["sid"]) if payload.get("sid") else None
    except (KeyError, TypeError, ValueError) as exc:
        raise credentials_exception() from exc
    return payload
