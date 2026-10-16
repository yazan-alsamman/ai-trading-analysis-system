"""Security events: new sign-in from a new IP/device, password changed, API key created or
revoked, account locked by the login lockout (``critical``: ignores quiet hours and caps).

A sign-in is "new" when ``sha256(user, IP, user agent)`` was never seen for the user. The very
first sign-in of an account is recorded silently (nothing to compare it with).
"""

from __future__ import annotations

import hashlib
import time
import uuid

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import LoginFingerprint, NotificationType, Severity
from app.models.user import User
from app.notifications.service import NotifyItem, notify


def fingerprint(user_id: uuid.UUID, ip: str, user_agent: str) -> str:
    return hashlib.sha256(f"{user_id}|{ip}|{user_agent}".encode()).hexdigest()


def _item(user_id: uuid.UUID, event: str, severity: Severity, dedup: str, **data) -> NotifyItem:
    return NotifyItem(
        user_id=user_id,
        type=NotificationType.security,
        data={"event": event, **data},
        dedup_key=f"security:{event}:{dedup}",
        severity=severity,
    )


async def on_login(session: AsyncSession, user: User, ip: str, user_agent: str) -> None:
    """Record the sign-in fingerprint; notify if it is new and not the first ever."""
    fp = fingerprint(user.id, ip, user_agent)
    stmt = (
        insert(LoginFingerprint)
        .values(user_id=user.id, fingerprint=fp)
        .on_conflict_do_update(
            index_elements=["user_id", "fingerprint"],
            set_={"last_seen": func.clock_timestamp()},
        )
        .returning(literal_column("(xmax = 0)"))  # true for an insert, false for an update
    )
    inserted = bool(await session.scalar(stmt))
    known = await session.scalar(
        select(func.count())
        .select_from(LoginFingerprint)
        .where(LoginFingerprint.user_id == user.id)
    )
    await session.commit()
    if inserted and known > 1:
        item = _item(
            user.id,
            "new_login",
            Severity.warning,
            fp[:32],
            ip=ip,
            user_agent=user_agent[:200],
        )
        await notify(session, item)


async def password_changed(session: AsyncSession, user_id: uuid.UUID) -> None:
    await notify(session, _item(user_id, "password_changed", Severity.warning, uuid.uuid4().hex))


async def api_key(session: AsyncSession, user_id: uuid.UUID, created: bool, name: str, prefix: str):
    event = "api_key_created" if created else "api_key_revoked"
    item = _item(user_id, event, Severity.info, prefix, key_name=name, key_prefix=prefix)
    await notify(session, item)


async def account_locked(session: AsyncSession, email: str, lock_seconds: int, failures: int):
    """Only for existing accounts (the API answers the same either way)."""
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        return
    window = int(time.time() // max(1, lock_seconds))  # one notification per lock period
    item = _item(
        user.id,
        "account_locked",
        Severity.critical,
        str(window),
        minutes=max(1, lock_seconds // 60),
        failures=failures,
    )
    await notify(session, item)
