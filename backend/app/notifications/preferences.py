"""Notification preferences: defaults, validation, and the decisions applied to every external
delivery, in this order: event enabled for the channel -> signal filters -> quiet hours ->
hourly cap. The in-app inbox always stores every event."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Channel, NotificationPreference, NotificationType

EXTERNAL = (Channel.telegram, Channel.email, Channel.push)
DEFAULT_MATRIX: dict[str, dict[str, bool]] = {
    NotificationType.signal: {"telegram": True, "email": False, "push": True},
    NotificationType.backtest_completed: {"telegram": False, "email": False, "push": True},
    NotificationType.backtest_failed: {"telegram": False, "email": False, "push": True},
    NotificationType.security: {"telegram": False, "email": True, "push": False},
    NotificationType.system: {"telegram": True, "email": False, "push": True},
    # Y18
    NotificationType.new_post: {"telegram": False, "email": False, "push": True},
    NotificationType.comment_reply: {"telegram": False, "email": False, "push": True},
    NotificationType.content_hidden: {"telegram": False, "email": True, "push": True},
    NotificationType.price_alert: {"telegram": True, "email": False, "push": True},
    # Y19
    NotificationType.chat_message: {"telegram": True, "email": False, "push": True},
    NotificationType.subscription_started: {"telegram": False, "email": True, "push": True},
    NotificationType.subscription_renewed: {"telegram": False, "email": True, "push": False},
    NotificationType.subscription_payment_failed: {"telegram": True, "email": True, "push": True},
    NotificationType.subscription_canceled: {"telegram": False, "email": True, "push": True},
    NotificationType.new_subscriber: {"telegram": False, "email": True, "push": True},
}
# Events that never leave the app (no matrix entry, cannot be switched on): likes are batched
# into one inbox row per post and day ("N people liked your post").
IN_APP_ONLY = frozenset({NotificationType.post_liked})
DEFAULT_MAX_PER_HOUR = {"telegram": 30, "email": 30, "push": 30}
DEFAULT_LANGUAGE = "ar"
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def default_matrix() -> dict[str, dict[str, bool]]:
    return {str(t): dict(channels) for t, channels in DEFAULT_MATRIX.items()}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuietHours(_Strict):
    start: str = Field(description='"HH:MM" local time', examples=["23:00"])
    end: str = Field(description='"HH:MM" local time; before start = across midnight')
    tz: str = Field(default="Asia/Damascus", description="IANA time zone")

    @field_validator("start", "end")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        if not HHMM.match(v):
            raise ValueError('must be "HH:MM" (00:00-23:59)')
        return v

    @field_validator("tz")
    @classmethod
    def _tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown time zone {v!r}") from None
        return v

    @model_validator(mode="after")
    def _distinct(self) -> QuietHours:
        if self.start == self.end:
            raise ValueError("start and end must differ")
        return self


ChannelSwitches = dict[Literal["telegram", "email", "push"], bool]


class PreferencesIn(_Strict):
    """``PUT /me/notification-preferences`` (missing fields take their defaults; missing matrix
    entries keep the default for that event and channel)."""

    matrix: dict[NotificationType, ChannelSwitches] = Field(
        default_factory=dict, description="event type -> channel -> on/off (in-app is always on)"
    )
    min_signal_strength: float = Field(default=0.0, ge=0, le=1)
    only_valid_plans: bool = False
    quiet_hours: QuietHours | None = None
    language: Literal["ar", "en"] = DEFAULT_LANGUAGE
    max_per_hour: dict[Literal["telegram", "email", "push"], int] = Field(default_factory=dict)

    @field_validator("matrix")
    @classmethod
    def _external_only(cls, v: dict[NotificationType, ChannelSwitches]):
        for event in v:
            if event in IN_APP_ONLY:
                raise ValueError(f"{event} is in-app only and has no channel switches")
        return v

    @field_validator("max_per_hour")
    @classmethod
    def _caps(cls, v: dict[str, int]) -> dict[str, int]:
        for channel, cap in v.items():
            if not 1 <= cap <= 1000:
                raise ValueError(f"{channel}: must be between 1 and 1000")
        return v

    def stored(self) -> dict[str, Any]:
        matrix = default_matrix()
        for event, switches in self.matrix.items():
            matrix[str(event)].update(switches)
        return {
            "matrix": matrix,
            "min_signal_strength": self.min_signal_strength,
            "only_valid_plans": self.only_valid_plans,
            "quiet_hours": self.quiet_hours.model_dump() if self.quiet_hours else None,
            "language": self.language,
            "max_per_hour": {**DEFAULT_MAX_PER_HOUR, **self.max_per_hour},
        }


@dataclass(frozen=True)
class Prefs:
    """Preferences of one user as the senders use them (defaults when there is no row)."""

    matrix: dict[str, dict[str, bool]]
    min_signal_strength: float = 0.0
    only_valid_plans: bool = False
    quiet_hours: dict[str, Any] | None = None
    language: str = DEFAULT_LANGUAGE
    max_per_hour: dict[str, int] | None = None

    @classmethod
    def default(cls) -> Prefs:
        return cls(matrix=default_matrix(), max_per_hour=dict(DEFAULT_MAX_PER_HOUR))

    @classmethod
    def of(cls, row: NotificationPreference | None) -> Prefs:
        if row is None:
            return cls.default()
        matrix = default_matrix()
        for event, switches in (row.matrix or {}).items():
            if event in matrix:
                matrix[event].update({k: bool(v) for k, v in switches.items()})
        return cls(
            matrix=matrix,
            min_signal_strength=row.min_signal_strength,
            only_valid_plans=row.only_valid_plans,
            quiet_hours=row.quiet_hours,
            language=row.language,
            max_per_hour={**DEFAULT_MAX_PER_HOUR, **(row.max_per_hour or {})},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix": self.matrix,
            "min_signal_strength": self.min_signal_strength,
            "only_valid_plans": self.only_valid_plans,
            "quiet_hours": self.quiet_hours,
            "language": self.language,
            "max_per_hour": self.max_per_hour or dict(DEFAULT_MAX_PER_HOUR),
        }

    # --- decisions ---------------------------------------------------------------------------

    def wants(self, event: str, channel: str) -> bool:
        return bool(self.matrix.get(event, {}).get(channel, False))

    def passes_filters(self, event: str, data: dict[str, Any]) -> bool:
        """Signal filters: minimum strength and, optionally, a valid trade plan."""
        if event != NotificationType.signal:
            return True
        strength = (data.get("signal") or {}).get("strength") or 0.0
        if strength < self.min_signal_strength:
            return False
        if self.only_valid_plans:
            plan = data.get("plan")
            if not plan or plan.get("invalid_reason") is not None:
                return False
        return True

    def cap(self, channel: str) -> int:
        return int((self.max_per_hour or DEFAULT_MAX_PER_HOUR).get(channel, 30))

    def quiet_until(self, now: datetime) -> datetime | None:
        """End of the current quiet period (UTC), or None when not in quiet hours."""
        return quiet_until(self.quiet_hours, now)


def _hm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


def quiet_until(quiet: dict[str, Any] | None, now: datetime) -> datetime | None:
    """``quiet`` = ``{start, end, tz}`` in local time; a start after the end spans midnight
    (23:00-07:00). Returns when the quiet period containing ``now`` ends, in UTC."""
    if not quiet:
        return None
    tz = ZoneInfo(quiet.get("tz") or "UTC")
    local = now.astimezone(tz)
    start, end = _hm(quiet["start"]), _hm(quiet["end"])
    t = local.time().replace(second=0, microsecond=0)
    if start < end:
        inside = start <= t < end
        end_day = local.date()
    else:  # across midnight
        inside = t >= start or t < end
        end_day = local.date() + timedelta(days=1) if t >= start else local.date()
    if not inside:
        return None
    end_local = datetime.combine(end_day, end, tzinfo=tz)
    return end_local.astimezone(UTC)


async def load(session: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, Prefs]:
    """Preferences of many users at once (defaults for users without a row)."""
    from sqlalchemy import select

    rows = {}
    if user_ids:
        result = await session.scalars(
            select(NotificationPreference).where(NotificationPreference.user_id.in_(user_ids))
        )
        rows = {r.user_id: r for r in result}
    return {uid: Prefs.of(rows.get(uid)) for uid in user_ids}


async def get_or_create(session: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    row = await session.get(NotificationPreference, user_id)
    if row is not None:
        return row
    defaults = PreferencesIn().stored()
    await session.execute(
        insert(NotificationPreference)
        .values(user_id=user_id, **defaults)
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    await session.commit()
    return await session.get(NotificationPreference, user_id, populate_existing=True)


async def update(
    session: AsyncSession, user_id: uuid.UUID, data: PreferencesIn
) -> NotificationPreference:
    row = await get_or_create(session, user_id)
    for name, value in data.stored().items():
        setattr(row, name, value)
    await session.commit()
    await session.refresh(row)
    return row


def read(row: NotificationPreference) -> dict[str, Any]:
    return {**Prefs.of(row).to_dict(), "updated_at": row.updated_at}


def next_hour(now: datetime) -> datetime:
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
