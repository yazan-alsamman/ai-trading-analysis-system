"""Conversations and messages between an expert and a subscriber.

Rights: a subscriber with the ``chat`` perk opens the conversation and writes; the expert can
always reply; when the subscription ends the conversation is read-only for the subscriber
(history stays). A blocked conversation takes no new messages from either side. Admins can
read every conversation.

Sending is idempotent per sender on ``client_id``. After the commit the message is published on
``chat:{conversation_id}``; the recipient gets a ``chat_message`` notification only when none of
their connections is looking at the conversation (presence), and at most one external
notification per conversation every ``CHAT_NOTIFY_COLLAPSE_MINUTES``: within that window the
inbox row is updated instead ("N new messages from X").
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import presence
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.chat import Conversation, ConversationStatus, Message
from app.models.expert import ExpertProfile
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.notifications import preferences as prefs_mod
from app.notifications import service as notifications
from app.notifications import templates
from app.payments.entitlements import entitlements
from app.realtime import publisher
from app.realtime.topics import chat_topic, user_topic
from app.schemas.chat import MessageCreate
from app.social import service as social
from app.social.notify import display_name

logger = logging.getLogger(__name__)

HISTORY_MAX = 100


def _404() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")


def is_participant(conv: Conversation, user: User) -> bool:
    return user.id in (conv.expert_id, conv.user_id)


# --- conversations -------------------------------------------------------------------------------


async def open_conversation(
    session: AsyncSession, user: User, expert_id: uuid.UUID
) -> tuple[Conversation, bool]:
    """(conversation, created). The subscriber starts it; needs the ``chat`` perk."""
    expert = await session.get(User, expert_id)
    profile = await session.get(ExpertProfile, expert_id)
    if expert is None or profile is None or expert.role != UserRole.expert or not expert.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expert not found")
    if expert_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot chat with yourself")
    existing = await session.scalar(
        select(Conversation).where(
            Conversation.expert_id == expert_id, Conversation.user_id == user.id
        )
    )
    if existing is not None:
        return existing, False
    if not profile.chat_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This expert does not take chats")
    if not (await entitlements(session, user, expert_id))["chat"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chat is for subscribers with the chat perk")
    await session.execute(
        insert(Conversation)
        .values(expert_id=expert_id, user_id=user.id)
        .on_conflict_do_nothing(constraint="uq_conversations_pair")
    )
    await session.commit()
    conv = await session.scalar(
        select(Conversation).where(
            Conversation.expert_id == expert_id, Conversation.user_id == user.id
        )
    )
    return conv, True


async def conversation_for(
    session: AsyncSession, user: User, conversation_id: uuid.UUID
) -> Conversation:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or not (is_participant(conv, user) or user.role == UserRole.admin):
        raise _404()
    return conv


async def send_right(session: AsyncSession, conv: Conversation, user: User) -> str | None:
    """None if ``user`` may send now, else the reason."""
    if not is_participant(conv, user):
        return "admins read conversations but do not write in them"
    if conv.status == ConversationStatus.blocked:
        return "the conversation is blocked"
    if conv.status == ConversationStatus.closed:
        return "the conversation is closed"
    if user.id == conv.user_id and not (await entitlements(session, user, conv.expert_id))["chat"]:
        return "your subscription with chat has ended (read only)"
    return None


async def block(session: AsyncSession, user: User, conv: Conversation, on: bool) -> Conversation:
    """Either side blocks (no new messages); the side that blocked (or an admin) unblocks."""
    if not is_participant(conv, user) and user.role != UserRole.admin:
        raise _404()
    if on:
        conv.status, conv.blocked_by = ConversationStatus.blocked, user.id
    else:
        if conv.status != ConversationStatus.blocked:
            return conv
        if conv.blocked_by != user.id and user.role != UserRole.admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the side that blocked can unblock")
        conv.status, conv.blocked_by = ConversationStatus.open, None
    await session.commit()
    await session.refresh(conv)
    return conv


# --- messages ------------------------------------------------------------------------------------


async def _rate_limit(redis: Redis, user_id: uuid.UUID, now: datetime) -> None:
    """``CHAT_MESSAGES_PER_MINUTE`` and ``CHAT_MESSAGES_PER_DAY`` per sender (fixed windows,
    one Redis round trip; fails open when Redis is down)."""
    settings = get_settings()
    minute = f"chat:rl:{user_id}:m:{now:%Y%m%d%H%M}"
    day = f"chat:rl:{user_id}:d:{now:%Y%m%d}"
    try:
        pipe = redis.pipeline(transaction=False)
        pipe.incr(minute)
        pipe.expire(minute, 70)
        pipe.incr(day)
        pipe.expire(day, 90_000)
        per_minute, _, per_day, _ = await pipe.execute()
    except (RedisError, OSError):
        logger.warning("chat rate limit unavailable (allowed)")
        return
    if per_minute > settings.chat_messages_per_minute:
        retry = 60 - now.second
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"At most {settings.chat_messages_per_minute} messages per minute",
            headers={"Retry-After": str(retry)},
        )
    if per_day > settings.chat_messages_per_day:
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"At most {settings.chat_messages_per_day} messages per day",
            headers={"Retry-After": str(int((midnight - now).total_seconds()) + 1)},
        )


async def send(
    session: AsyncSession, redis: Redis | None, user: User, conv: Conversation, data: MessageCreate
) -> tuple[Message, bool]:
    """(message, created). A repeated ``client_id`` returns the first message (no new one,
    no rate-limit cost)."""
    redis = redis or get_redis()
    existing = await session.scalar(
        select(Message).where(Message.sender_id == user.id, Message.client_id == data.client_id)
    )
    if existing is not None:
        if existing.conversation_id != conv.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "client_id already used elsewhere")
        return existing, False
    reason = await send_right(session, conv, user)
    if reason:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You cannot send: {reason}")
    now = datetime.now(UTC)
    await _rate_limit(redis, user.id, now)
    attachments = await social.validate_attachments(session, user, data.attachments)
    message_id = await session.scalar(
        insert(Message)
        .values(
            conversation_id=conv.id,
            sender_id=user.id,
            body=data.body,
            attachments=attachments,
            client_id=data.client_id,
        )
        .on_conflict_do_nothing(constraint="uq_messages_sender_client")
        .returning(Message.id)
    )
    if message_id is None:  # a concurrent retry won the race
        await session.rollback()
        first = await session.scalar(
            select(Message).where(Message.sender_id == user.id, Message.client_id == data.client_id)
        )
        return first, False
    message = await session.get(Message, message_id)
    await session.execute(
        update(Conversation)
        .where(Conversation.id == conv.id)
        .values(
            **{"last_message_at": message.created_at, _read_column(conv, user): message.created_at}
        )
    )
    await session.commit()
    await session.refresh(conv)
    await publish_message(redis, message, "chat_message", user, session)
    recipient = conv.expert_id if user.id == conv.user_id else conv.user_id
    try:
        await notify_recipient(session, redis, conv, message, user, recipient)
    except Exception:  # noqa: BLE001 - the message is delivered anyway
        logger.exception("chat notification for %s failed", message.id)
    return message, True


def _read_column(conv: Conversation, user: User) -> str:
    return "expert_last_read_at" if user.id == conv.expert_id else "user_last_read_at"


async def own_message(session: AsyncSession, user: User, message_id: uuid.UUID) -> Message:
    message = await session.get(Message, message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    conv = await session.get(Conversation, message.conversation_id)
    if not is_participant(conv, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    if message.sender_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the sender can change a message")
    return message


async def edit(session: AsyncSession, redis, user: User, message: Message, body: str) -> Message:
    if message.deleted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The message was deleted")
    window = timedelta(minutes=get_settings().chat_edit_window_minutes)
    if datetime.now(UTC) - message.created_at > window:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Messages can be edited within {get_settings().chat_edit_window_minutes} minutes",
        )
    message.body, message.edited_at = body, datetime.now(UTC)
    await session.commit()
    await session.refresh(message)
    await publish_message(redis, message, "chat_message_updated", user, session)
    return message


async def delete(session: AsyncSession, redis, user: User, message: Message) -> None:
    """Tombstone: the row stays (body erased, ``deleted_at`` set) so the history keeps its
    place."""
    if message.deleted_at is None:
        message.body, message.deleted_at = "", datetime.now(UTC)
        message.attachments = []
        await session.commit()
        await session.refresh(message)
        await publish_message(redis, message, "chat_message_updated", user, session)


async def history(
    session: AsyncSession,
    viewer: User,
    conv: Conversation,
    *,
    before: uuid.UUID | None,
    limit: int,
) -> tuple[list[dict], uuid.UUID | None]:
    """Newest first. ``before``: a message id (exclusive cursor). Returns (items, next cursor)."""
    where = [Message.conversation_id == conv.id]
    if before is not None:
        anchor = await session.get(Message, before)
        if anchor is None or anchor.conversation_id != conv.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown 'before' message")
        where.append(
            or_(
                Message.created_at < anchor.created_at,
                and_(Message.created_at == anchor.created_at, Message.id < anchor.id),
            )
        )
    rows = list(
        await session.scalars(
            select(Message)
            .where(*where)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return await serialize(session, viewer, rows), (rows[-1].id if more and rows else None)


async def serialize(session: AsyncSession, viewer: User, messages: list[Message]) -> list[dict]:
    resolved = await social.resolve_attachments(session, viewer, messages)
    return [wire(m, viewer.id, resolved.get(m.id, [])) for m in messages]


def wire(message: Message, viewer_id: uuid.UUID | None, attachments: list) -> dict[str, Any]:
    deleted = message.deleted_at is not None
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "body": None if deleted else message.body,
        "attachments": [] if deleted else attachments,
        "client_id": message.client_id if message.sender_id == viewer_id else None,
        "edited_at": message.edited_at,
        "deleted": deleted,
        "created_at": message.created_at,
    }


def _json(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def publish_message(
    redis: Redis | None,
    message: Message,
    type_: str,
    sender: User | None = None,
    session: AsyncSession | None = None,
) -> None:
    """``chat_message`` / ``chat_message_updated`` on the conversation topic (never raises).
    Attachments are summarised as every user may see them (a private strategy or signal is
    ``available: false`` here; the history endpoint resolves them per viewer); ``client_id`` is
    included so the sender's other devices can match their optimistic copy."""
    try:
        attachments: list = []
        if message.attachments and message.deleted_at is None and sender and session:
            # the topic reaches both participants (and admins): only what everyone may see
            attachments = (await social.resolve_attachments(session, None, [message]))[message.id]
        payload = _json(wire(message, message.sender_id, attachments))
        await publisher.publish(
            chat_topic(message.conversation_id),
            {"type": type_, "conversation_id": str(message.conversation_id), "message": payload},
            redis,
        )
    except Exception:  # noqa: BLE001
        logger.exception("publishing chat message %s failed", message.id)


async def mark_read(
    session: AsyncSession,
    redis: Redis | None,
    user: User,
    conv: Conversation,
    message_id: uuid.UUID | None,
) -> datetime:
    if not is_participant(conv, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only participants have read markers")
    at = datetime.now(UTC)
    if message_id is not None:
        message = await session.get(Message, message_id)
        if message is None or message.conversation_id != conv.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown message")
        at = message.created_at
    column = _read_column(conv, user)
    current = getattr(conv, column)
    if current is None or at > current:  # markers only move forward
        setattr(conv, column, at)
        await session.commit()
    else:
        at = current
    await publisher.publish(
        chat_topic(conv.id),
        {
            "type": "chat_read",
            "conversation_id": str(conv.id),
            "user_id": str(user.id),
            "read_at": at.isoformat(),
        },
        redis,
    )
    return at


async def list_conversations(session: AsyncSession, user: User) -> list[dict]:
    """The caller's conversations, most recent first, with the other side, the last message,
    the unread count and whether the caller can send."""
    convs = list(
        await session.scalars(
            select(Conversation)
            .where(or_(Conversation.user_id == user.id, Conversation.expert_id == user.id))
            .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.created_at)
        )
    )
    return [await read_conversation(session, user, c) for c in convs]


async def read_conversation(session: AsyncSession, viewer: User, conv: Conversation) -> dict:
    as_expert = viewer.id == conv.expert_id
    other_id = conv.user_id if as_expert else conv.expert_id
    if not is_participant(conv, viewer):  # an admin
        other_id = conv.user_id
    other = await session.get(User, other_id)
    mine = conv.expert_last_read_at if as_expert else conv.user_last_read_at
    theirs = conv.user_last_read_at if as_expert else conv.expert_last_read_at
    unread_where = [
        Message.conversation_id == conv.id,
        Message.sender_id != viewer.id,
        Message.deleted_at.is_(None),
    ]
    if mine is not None:
        unread_where.append(Message.created_at > mine)
    unread = await session.scalar(select(func.count()).select_from(Message).where(*unread_where))
    last = await session.scalar(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    reason = await send_right(session, conv, viewer)
    return {
        "id": conv.id,
        "expert_id": conv.expert_id,
        "user_id": conv.user_id,
        "other": {"id": other.id, "display_name": display_name(other), "role": other.role},
        "my_role": "expert"
        if as_expert
        else ("subscriber" if is_participant(conv, viewer) else "admin"),
        "status": conv.status,
        "blocked_by_me": conv.blocked_by == viewer.id,
        "can_send": reason is None,
        "read_only_reason": reason,
        "unread": unread or 0 if is_participant(conv, viewer) else 0,
        "last_message": (
            {
                "id": last.id,
                "sender_id": last.sender_id,
                "excerpt": None if last.deleted_at else templates.excerpt(last.body, 120),
                "created_at": last.created_at,
            }
            if last
            else None
        ),
        "last_message_at": conv.last_message_at,
        "other_last_read_at": theirs,
        "created_at": conv.created_at,
    }


async def admin_conversations(
    session: AsyncSession, *, status_: ConversationStatus | None, limit: int, offset: int
) -> tuple[list[dict], int]:
    where = [] if status_ is None else [Conversation.status == status_]
    total = await session.scalar(select(func.count()).select_from(Conversation).where(*where))
    rows = list(
        await session.scalars(
            select(Conversation)
            .where(*where)
            .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.id)
            .limit(limit)
            .offset(offset)
        )
    )
    out = []
    for c in rows:
        expert = await session.get(User, c.expert_id)
        user = await session.get(User, c.user_id)
        out.append(
            {
                "id": c.id,
                "status": c.status,
                "blocked_by": c.blocked_by,
                "expert": {
                    "id": expert.id,
                    "display_name": display_name(expert),
                    "role": expert.role,
                },
                "user": {"id": user.id, "display_name": display_name(user), "role": user.role},
                "last_message_at": c.last_message_at,
                "created_at": c.created_at,
            }
        )
    return out, total or 0


# --- notifications -------------------------------------------------------------------------------


async def notify_recipient(
    session: AsyncSession,
    redis: Redis,
    conv: Conversation,
    message: Message,
    sender: User,
    recipient_id: uuid.UUID,
) -> str:
    """``present`` (nothing), ``notified`` (a new notification, external channels included) or
    ``collapsed`` (the window's inbox row updated: "N new messages", in-app only)."""
    if await presence.present(redis, conv.id, recipient_id):
        return "present"
    window = get_settings().chat_notify_collapse_minutes * 60
    key = f"chat:notify:{conv.id}:{recipient_id}"
    data = {
        "conversation_id": str(conv.id),
        "message_id": str(message.id),
        "sender_id": str(sender.id),
        "sender_name": display_name(sender),
        "excerpt": templates.excerpt(message.body, 160),
        "count": 1,
    }
    if await redis.set(key, "", nx=True, ex=window):
        prepared = await notifications.prepare(
            session,
            redis,
            [
                notifications.NotifyItem(
                    user_id=recipient_id,
                    type=NotificationType.chat_message,
                    data=data,
                    dedup_key=f"chat:{conv.id}:{message.id}",
                )
            ],
        )
        await session.commit()
        if prepared.notifications:
            await redis.set(key, str(prepared.notifications[0]["id"]), xx=True, keepttl=True)
        await notifications.after_commit(redis, prepared)
        return "notified"
    note_id = await redis.get(key)
    if not note_id:
        return "collapsed"  # the first notification of the window is still being stored
    note = await session.get(Notification, uuid.UUID(note_id))
    if note is None:
        return "collapsed"
    count = int((note.data or {}).get("count") or 1) + 1
    lang = (await prefs_mod.load(session, [recipient_id]))[recipient_id].language
    data["count"] = count
    title, body = templates.inbox(NotificationType.chat_message, data, lang)
    note.title, note.body, note.data, note.read_at = title[:200], body, data, None
    await session.commit()
    await session.refresh(note)
    await publisher.publish(
        user_topic(recipient_id),
        {"type": "notification", "notification": notifications.wire(note)},
        redis,
    )
    return "collapsed"
