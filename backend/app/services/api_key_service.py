"""API keys for external programs: format, hashing, authentication and CRUD.

Format ``tk_<prefix>_<secret>``: ``prefix`` is 8 random [a-z0-9] characters (unique, shown in
lists, used to find the row) and ``secret`` is ``secrets.token_urlsafe(32)`` (256 bits). Only
``sha256(full key)`` is stored. A fast hash is right here, unlike for passwords: the input is
already uniformly random with 256 bits of entropy, so there is nothing to brute-force or look
up in a dictionary, and a slow KDF (argon2) would only add ~50 ms of CPU to every API call.
"""

import hashlib
import hmac
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import get_settings
from app.core.security import credentials_exception
from app.models.api_key import MAX_KEYS_PER_ROLE, ApiKey
from app.models.user import User
from app.schemas.api_keys import ApiKeyCreate, ApiKeyUpdate

KEY_TYPE = "tk"
PREFIX_LENGTH = 8
PREFIX_ALPHABET = string.ascii_lowercase + string.digits

# compared against when the prefix is unknown, so both failures cost the same
_DUMMY_HASH = hashlib.sha256(b"no-such-api-key").hexdigest()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_key() -> tuple[str, str]:
    """(prefix, full key)."""
    prefix = "".join(secrets.choice(PREFIX_ALPHABET) for _ in range(PREFIX_LENGTH))
    return prefix, f"{KEY_TYPE}_{prefix}_{secrets.token_urlsafe(32)}"


def parse_prefix(key: str) -> str | None:
    parts = key.split("_", 2)  # the secret itself may contain "_"
    if len(parts) != 3 or parts[0] != KEY_TYPE or len(parts[1]) != PREFIX_LENGTH or not parts[2]:
        return None
    return parts[1]


def is_usable(row: ApiKey, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return row.revoked_at is None and (row.expires_at is None or row.expires_at > now)


# --- authentication ------------------------------------------------------------------------


async def authenticate(session: AsyncSession, redis: Redis, key: str) -> tuple[User, ApiKey]:
    """The owner and the key, or 401 (unknown, revoked, expired) / 403 (owner inactive)."""
    prefix = parse_prefix(key)
    row = None
    if prefix is not None:
        row = await session.scalar(select(ApiKey).where(ApiKey.prefix == prefix))
    expected = row.key_hash if row is not None else _DUMMY_HASH
    if not hmac.compare_digest(hash_key(key), expected) or row is None:
        raise credentials_exception("Invalid API key")
    now = datetime.now(UTC)
    if row.revoked_at is not None:
        raise credentials_exception("API key has been revoked")
    if row.expires_at is not None and row.expires_at <= now:
        raise credentials_exception("API key has expired")
    user = await session.get(User, row.user_id)
    if user is None:
        raise credentials_exception("Invalid API key")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    await touch(session, redis, row, now)
    return user, row


async def touch(session: AsyncSession, redis: Redis, row: ApiKey, now: datetime) -> bool:
    """Set ``last_used_at``, at most once per interval per key: a Redis ``SET NX EX`` decides,
    so reads do not turn into a DB write each. Without Redis the stored value decides."""
    interval = get_settings().api_key_last_used_interval_seconds
    try:
        due = bool(await redis.set(rate_limit.key("used", row.id), "1", nx=True, ex=interval))
    except (RedisError, OSError):
        due = row.last_used_at is None or now - row.last_used_at >= timedelta(seconds=interval)
    if due:
        row.last_used_at = now
        await session.commit()
    return due


# --- CRUD ----------------------------------------------------------------------------------


def _check_rate_limit(user: User, value: int | None) -> None:
    tier = get_settings().tier_limit(user.role.value)
    if value is not None and value > tier:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"rate_limit_per_minute must be <= {tier} (your tier)",
        )


async def count_usable(session: AsyncSession, user: User) -> int:
    now = datetime.now(UTC)
    return await session.scalar(
        select(func.count())
        .select_from(ApiKey)
        .where(
            ApiKey.user_id == user.id,
            ApiKey.revoked_at.is_(None),
            (ApiKey.expires_at.is_(None)) | (ApiKey.expires_at > now),
        )
    )


async def create(session: AsyncSession, user: User, data: ApiKeyCreate) -> tuple[ApiKey, str]:
    """The new row and the full key (returned to the user once, never stored)."""
    _check_rate_limit(user, data.rate_limit_per_minute)
    maximum = MAX_KEYS_PER_ROLE[user.role]
    if await count_usable(session, user) >= maximum:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"At most {maximum} active API keys for your role"
        )
    prefix, key = generate_key()
    row = ApiKey(
        user_id=user.id,
        name=data.name,
        prefix=prefix,
        key_hash=hash_key(key),
        scopes=sorted(data.scopes),
        rate_limit_per_minute=data.rate_limit_per_minute,
        expires_at=(
            datetime.now(UTC) + timedelta(days=data.expires_in_days)
            if data.expires_in_days
            else None
        ),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row, key


async def list_for_user(session: AsyncSession, user: User) -> list[ApiKey]:
    rows = await session.scalars(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
    )
    return list(rows.all())


async def get_own_or_404(session: AsyncSession, user: User, key_id: uuid.UUID) -> ApiKey:
    row = await session.get(ApiKey, key_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    return row


async def update(session: AsyncSession, user: User, row: ApiKey, data: ApiKeyUpdate) -> ApiKey:
    if row.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "API key has been revoked")
    fields = data.model_dump(exclude_unset=True)
    if "name" in fields:
        row.name = data.name
    if "scopes" in fields:
        row.scopes = sorted(data.scopes)
    if "rate_limit_per_minute" in fields:
        _check_rate_limit(user, data.rate_limit_per_minute)
        row.rate_limit_per_minute = data.rate_limit_per_minute
    await session.commit()
    return row


async def revoke(session: AsyncSession, row: ApiKey) -> None:
    """Idempotent."""
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await session.commit()


async def list_all(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    user_id: uuid.UUID | None = None,
    revoked: bool | None = None,
) -> tuple[list[tuple[ApiKey, str]], int]:
    """(key, owner email) pairs for admins, newest first."""
    conditions = []
    if user_id is not None:
        conditions.append(ApiKey.user_id == user_id)
    if revoked is not None:
        revoked_at = ApiKey.revoked_at
        conditions.append(revoked_at.is_not(None) if revoked else revoked_at.is_(None))
    total = await session.scalar(select(func.count()).select_from(ApiKey).where(*conditions))
    rows = await session.execute(
        select(ApiKey, User.email)
        .join(User, User.id == ApiKey.user_id)
        .where(*conditions)
        .order_by(ApiKey.created_at.desc(), ApiKey.id)
        .limit(limit)
        .offset(offset)
    )
    return [(key, email) for key, email in rows.all()], total
