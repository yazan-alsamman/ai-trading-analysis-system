"""Notifications (Y15): the in-app inbox, external deliveries (Telegram, email, push), user
preferences, Telegram links, mobile devices and known login fingerprints."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationType(StrEnum):
    signal = "signal"
    backtest_completed = "backtest_completed"
    backtest_failed = "backtest_failed"
    security = "security"
    system = "system"
    # Y18 (migration 0011 adds them to the existing enum type)
    new_post = "new_post"
    comment_reply = "comment_reply"
    post_liked = "post_liked"  # in-app only, batched per post and day
    content_hidden = "content_hidden"
    price_alert = "price_alert"
    # Y19 (migration 0012)
    chat_message = "chat_message"
    subscription_started = "subscription_started"
    subscription_renewed = "subscription_renewed"
    subscription_payment_failed = "subscription_payment_failed"
    subscription_canceled = "subscription_canceled"
    new_subscriber = "new_subscriber"


class Severity(StrEnum):
    info = "info"
    success = "success"
    warning = "warning"
    critical = "critical"


class Channel(StrEnum):
    telegram = "telegram"
    email = "email"
    push = "push"


class DeliveryStatus(StrEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


class Platform(StrEnum):
    android = "android"
    ios = "ios"
    web = "web"


def _enum(cls, name: str) -> SAEnum:
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Notification(Base):
    """One event for one user: the inbox row and the source of every external delivery.
    ``dedup_key`` (unique per user) makes producing an event idempotent."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedup_key", name="uq_notifications_user_dedup"),
        Index("ix_notifications_user_created", "user_id", text("created_at DESC")),
        Index(
            "ix_notifications_user_unread",
            "user_id",
            text("created_at DESC"),
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(_enum(NotificationType, "notification_type"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    severity: Mapped[Severity] = mapped_column(_enum(Severity, "notification_severity"))
    dedup_key: Mapped[str] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class NotificationDelivery(Base):
    """One notification on one channel to one target (chat id, email, device id; never a
    secret). ``hold``: why a pending delivery waits (``quiet_hours``, ``hourly_cap`` -> digest;
    ``circuit_open`` -> re-sent) until ``release_at``."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "notification_id", "channel", "target", name="uq_notification_deliveries_target"
        ),
        Index(
            "ix_notification_deliveries_due",
            "release_at",
            postgresql_where=text("status = 'pending' AND hold IS NOT NULL"),
        ),
        Index("ix_notification_deliveries_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("notifications.id", ondelete="CASCADE")
    )
    channel: Mapped[Channel] = mapped_column(_enum(Channel, "notification_channel"))
    target: Mapped[str] = mapped_column(String(320))
    status: Mapped[DeliveryStatus] = mapped_column(
        _enum(DeliveryStatus, "delivery_status"),
        default=DeliveryStatus.pending,
        server_default=DeliveryStatus.pending.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(String(300))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    hold: Mapped[str | None] = mapped_column(String(16))
    release_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(Base):
    """One per user, created on first use (see ``notifications.preferences`` for defaults)."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint(
            "min_signal_strength BETWEEN 0 AND 1", name="ck_notification_preferences_strength"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    matrix: Mapped[dict[str, Any]] = mapped_column(JSONB)  # event type -> channel -> bool
    min_signal_strength: Mapped[float] = mapped_column(
        Double, default=0.0, server_default=text("0")
    )
    only_valid_plans: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    quiet_hours: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # {start, end, tz}
    language: Mapped[str] = mapped_column(String(2), default="ar", server_default="ar")
    max_per_hour: Mapped[dict[str, Any]] = mapped_column(JSONB)  # channel -> int
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )


class TelegramLink(Base):
    __tablename__ = "telegram_links"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(64))
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class UserDevice(Base):
    """An FCM registration token of the mobile (or web) app. Tokens FCM reports as invalid are
    deleted."""

    __tablename__ = "user_devices"
    __table_args__ = (Index("ix_user_devices_user", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    platform: Mapped[Platform] = mapped_column(_enum(Platform, "device_platform"))
    token: Mapped[str] = mapped_column(String(512), unique=True)
    app_version: Mapped[str | None] = mapped_column(String(32))
    locale: Mapped[str | None] = mapped_column(String(16))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class LoginFingerprint(Base):
    """``sha256(user, IP, user agent)`` of every login seen, to tell a new IP/device."""

    __tablename__ = "login_fingerprints"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
