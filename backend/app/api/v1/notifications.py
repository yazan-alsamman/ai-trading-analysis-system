"""Notifications (docs/notifications.md): the inbox, preferences, channels (Telegram link,
devices for push), a test message, admin broadcast and stats, and the Telegram webhook.

Everything under /me is JWT only (API keys get 403)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, select, update

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.api.limits import COST_KEY
from app.core.config import get_settings
from app.core.redis import get_redis
from app.db.session import SessionLocal
from app.models.notification import (
    Notification,
    NotificationType,
    TelegramLink,
    UserDevice,
)
from app.models.user import User
from app.notifications import preferences as prefs
from app.notifications import service, telegram_link
from app.notifications.channels import enabled_channels
from app.notifications.preferences import PreferencesIn
from app.schemas.common import Page
from app.schemas.notifications import (
    BroadcastAccepted,
    BroadcastRequest,
    ChannelInfo,
    ChannelsRead,
    DeviceCreate,
    DeviceRead,
    NotificationRead,
    PreferencesRead,
    TelegramLinkRead,
    TestRequest,
    TestResponse,
    UnreadCount,
)

router = APIRouter(tags=["notifications"])
admin_router = APIRouter(prefix="/admin/notifications", tags=["notifications"])
webhook_router = APIRouter(tags=["notifications"])

TEST_COST = {COST_KEY: get_settings().notification_test_cost}


async def _own_or_404(session, user: User, notification_id: uuid.UUID) -> Notification:
    row = await session.get(Notification, notification_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return row


# --- inbox ---------------------------------------------------------------------------------------


@router.get("/me/notifications", response_model=Page[NotificationRead])
async def list_notifications(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    type: NotificationType | None = None,  # noqa: A002 - the API field name
    unread: bool | None = None,
):
    """Your notifications, newest first (``unread=true`` for unread only)."""
    rows, total = await service.list_inbox(
        session, user, limit=limit, offset=offset, type_=type, unread=unread
    )
    items = [NotificationRead(**service.wire(r)) for r in rows]
    return Page[NotificationRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/me/notifications/unread-count", response_model=UnreadCount)
async def unread_count(user: CurrentUser, session: SessionDep):
    return UnreadCount(count=await service.unread_count(session, user))


@router.post("/me/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(user: CurrentUser, session: SessionDep) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    await session.commit()


@router.post("/me/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_one(notification_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    row = await _own_or_404(session, user, notification_id)
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await session.commit()


# --- preferences and channels --------------------------------------------------------------------


@router.get("/me/notification-preferences", response_model=PreferencesRead)
async def get_preferences(user: CurrentUser, session: SessionDep):
    """Created with the defaults on first read."""
    return prefs.read(await prefs.get_or_create(session, user.id))


@router.put("/me/notification-preferences", response_model=PreferencesRead)
async def put_preferences(data: PreferencesIn, user: CurrentUser, session: SessionDep):
    """The whole document: missing fields take their defaults; 422 lists errors with paths."""
    return prefs.read(await prefs.update(session, user.id, data))


@router.get("/me/notifications/channels", response_model=ChannelsRead)
async def channels(user: CurrentUser, session: SessionDep):
    """What each channel can do for you: configured on this server, linked, devices."""
    server = enabled_channels()
    link = await session.get(TelegramLink, user.id)
    devices = await session.scalar(
        select(func.count()).select_from(UserDevice).where(UserDevice.user_id == user.id)
    )
    return ChannelsRead(
        in_app=ChannelInfo(enabled_on_server=True),
        telegram=ChannelInfo(
            enabled_on_server=server["telegram"],
            linked=link is not None,
            username=link.username if link else None,
            mode=get_settings().telegram_mode,
        ),
        email=ChannelInfo(enabled_on_server=server["email"], address=user.email),
        push=ChannelInfo(enabled_on_server=server["push"], devices=devices or 0),
    )


@router.post(
    "/me/notifications/test",
    response_model=TestResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=TEST_COST,
)
async def test_notification(data: TestRequest, user: CurrentUser, session: SessionDep):
    """A test message on one channel, ignoring preferences, quiet hours and caps (not the
    server configuration: a channel disabled there gives a ``skipped`` delivery)."""
    if data.channel == "telegram" and await session.get(TelegramLink, user.id) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Telegram is not linked")
    if data.channel == "push":
        count = await session.scalar(
            select(func.count()).select_from(UserDevice).where(UserDevice.user_id == user.id)
        )
        if not count:
            raise HTTPException(status.HTTP_409_CONFLICT, "No device registered for push")
    item = service.NotifyItem(
        user_id=user.id,
        type=NotificationType.system,
        data={"test": True, "channel": data.channel},
        dedup_key=f"test:{uuid.uuid4()}",
        channels=() if data.channel == "in_app" else (data.channel,),
    )
    prepared = await service.notify(session, item)
    if not prepared.notifications:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not create the test")
    return TestResponse(
        notification_id=prepared.notifications[0]["id"],
        deliveries=[
            {"channel": str(d["channel"]), "target": d["target"], "status": str(d["status"])}
            for d in prepared.deliveries
        ],
    )


# --- telegram ------------------------------------------------------------------------------------


@router.post("/me/notifications/telegram/link", response_model=TelegramLinkRead)
async def telegram_link_code(user: CurrentUser):
    """A one-time code (10 minutes): open ``deep_link`` in Telegram, or send
    ``/start <code>`` to the bot."""
    if not enabled_channels()["telegram"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Telegram is not configured on this server")
    redis = get_redis()
    code = await telegram_link.create_code(redis, user.id)
    username = await telegram_link.bot_username(redis)
    return TelegramLinkRead(
        code=code,
        deep_link=f"https://t.me/{username}?start={code}" if username else None,
        bot_username=username,
        expires_in=telegram_link.CODE_TTL,
    )


@router.delete("/me/notifications/telegram", status_code=status.HTTP_204_NO_CONTENT)
async def telegram_unlink(user: CurrentUser, session: SessionDep) -> None:
    await session.execute(delete(TelegramLink).where(TelegramLink.user_id == user.id))
    await session.commit()


@router.delete("/me/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    row = await _own_or_404(session, user, notification_id)
    await session.delete(row)
    await session.commit()


@webhook_router.post("/telegram/webhook/{secret}", include_in_schema=False)
async def telegram_webhook(
    secret: str,
    request: Request,
    token: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
):
    """Webhook mode (``TELEGRAM_MODE=webhook``, behind HTTPS). Unknown secrets get 404, so the
    endpoint does not exist for anyone else."""
    settings = get_settings()
    expected = settings.telegram_webhook_secret
    if (
        settings.telegram_mode != "webhook"
        or not settings.telegram_bot_token
        or not expected
        or secret != expected
        or token != expected
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    update_ = await request.json()
    await telegram_link.handle_update(SessionLocal, get_redis(), update_)
    return {"ok": True}


# --- devices -------------------------------------------------------------------------------------


def _device(row: UserDevice) -> DeviceRead:
    return DeviceRead(
        id=row.id,
        platform=row.platform,
        token_suffix=row.token[-8:],
        app_version=row.app_version,
        locale=row.locale,
        last_seen_at=row.last_seen_at,
        created_at=row.created_at,
    )


@router.post("/me/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def register_device(
    data: DeviceCreate, user: CurrentUser, session: SessionDep, response: Response
):
    """Register an FCM token, or refresh it (200): call on every app start and whenever FCM
    rotates the token. A token signed in to another account moves to this one."""
    row = await session.scalar(select(UserDevice).where(UserDevice.token == data.token))
    if row is None:
        row = UserDevice(user_id=user.id, **data.model_dump())
        session.add(row)
    else:
        response.status_code = status.HTTP_200_OK
        row.user_id, row.platform = user.id, data.platform
        row.app_version, row.locale = data.app_version, data.locale
        row.last_seen_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return _device(row)


@router.get("/me/devices", response_model=list[DeviceRead])
async def list_devices(user: CurrentUser, session: SessionDep):
    rows = await session.scalars(
        select(UserDevice).where(UserDevice.user_id == user.id).order_by(UserDevice.created_at)
    )
    return [_device(r) for r in rows]


@router.delete("/me/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    row = await session.get(UserDevice, device_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    await session.delete(row)
    await session.commit()


# --- admin ---------------------------------------------------------------------------------------


@admin_router.post(
    "/broadcast", response_model=BroadcastAccepted, status_code=status.HTTP_202_ACCEPTED
)
async def broadcast(data: BroadcastRequest, _: AdminUser, session: SessionDep):
    """A ``system`` notification to every active user (or the given roles), sent in batches by
    a task. Sending the same ``id`` again creates nothing new."""
    broadcast_id = data.id or uuid.uuid4()
    query = select(func.count()).select_from(User).where(User.is_active.is_(True))
    if data.roles:
        query = query.where(User.role.in_(data.roles))
    recipients = await session.scalar(query) or 0
    service.enqueue_broadcast(
        broadcast_id, data.title, data.body, data.severity, data.roles or None
    )
    return BroadcastAccepted(broadcast_id=broadcast_id, recipients=recipients)


@admin_router.get("/stats")
async def notification_stats(_: AdminUser, session: SessionDep) -> dict:
    """Last 24 h: deliveries per channel and status, circuit breakers, held deliveries and the
    queue length."""
    return await service.stats(session, get_redis())
