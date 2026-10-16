"""Notifications API (docs/notifications.md). Preferences are validated by
``app.notifications.preferences.PreferencesIn``."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationType, Platform, Severity
from app.models.user import UserRole


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NotificationRead(BaseModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    body: str
    data: dict[str, Any]
    severity: Severity
    created_at: datetime
    read_at: datetime | None


class UnreadCount(BaseModel):
    count: int


class PreferencesRead(BaseModel):
    matrix: dict[str, dict[str, bool]]
    min_signal_strength: float
    only_valid_plans: bool
    quiet_hours: dict[str, Any] | None
    language: str
    max_per_hour: dict[str, int]
    updated_at: datetime


class ChannelInfo(BaseModel):
    enabled_on_server: bool
    linked: bool | None = None  # telegram
    username: str | None = None  # telegram
    mode: str | None = None  # telegram: polling | webhook
    address: str | None = None  # email
    devices: int | None = None  # push


class ChannelsRead(BaseModel):
    in_app: ChannelInfo
    telegram: ChannelInfo
    email: ChannelInfo
    push: ChannelInfo


class TestRequest(_Strict):
    channel: Literal["in_app", "telegram", "email", "push"]


class DeliveryRead(BaseModel):
    channel: str
    target: str
    status: str
    last_error: str | None = None


class TestResponse(BaseModel):
    notification_id: uuid.UUID
    deliveries: list[DeliveryRead]


class TelegramLinkRead(BaseModel):
    code: str
    deep_link: str | None = Field(description="https://t.me/<bot>?start=<code> (null if unknown)")
    bot_username: str | None
    expires_in: int


class DeviceCreate(_Strict):
    token: str = Field(min_length=10, max_length=512, description="the FCM registration token")
    platform: Platform
    app_version: str | None = Field(default=None, max_length=32)
    locale: str | None = Field(default=None, max_length=16)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: Platform
    token_suffix: str = Field(description="the last 8 characters of the token")
    app_version: str | None
    locale: str | None
    last_seen_at: datetime
    created_at: datetime


class BroadcastRequest(_Strict):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    severity: Severity = Severity.info
    roles: list[UserRole] | None = Field(default=None, description="null = every active user")
    id: uuid.UUID | None = Field(
        default=None, description="broadcast id; sending the same id again changes nothing"
    )


class BroadcastAccepted(BaseModel):
    broadcast_id: uuid.UUID
    recipients: int
