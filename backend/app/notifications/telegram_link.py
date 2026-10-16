"""Linking a Telegram chat to an account, and the bot's commands.

1. ``POST /me/notifications/telegram/link`` stores a one-time code in Redis for 10 minutes and
   returns ``https://t.me/<bot>?start=<code>``.
2. The user opens the link; Telegram sends ``/start <code>`` to the bot, which links the chat
   (a chat belongs to one account; linking it again moves it) and replies.
3. ``/stop`` in the bot or ``DELETE /me/notifications/telegram`` unlinks; so does a 403 from
   Telegram when the user blocked the bot.

:func:`handle_update` is used by the polling service (``app.notifications.telegram_bot``) and by
the webhook endpoint; sending notifications is done by the Celery tasks, not here.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models.notification import NotificationPreference, TelegramLink
from app.models.user import User
from app.notifications.channels import ChannelError
from app.notifications.channels.telegram import TelegramClient
from app.notifications.preferences import Prefs
from app.notifications.templates import t

logger = logging.getLogger(__name__)

CODE_TTL = 600
client_factory = TelegramClient  # replaced in tests
CODE_KEY = "notif:tg:link:{code}"
USERNAME_KEY = "notif:tg:username"


async def create_code(redis: Redis, user_id: uuid.UUID) -> str:
    code = secrets.token_urlsafe(12)  # 16 characters of [A-Za-z0-9_-], valid in ?start=
    await redis.set(CODE_KEY.format(code=code), str(user_id), ex=CODE_TTL)
    return code


async def bot_username(redis: Redis, client: TelegramClient | None = None) -> str | None:
    configured = get_settings().telegram_bot_username.lstrip("@")
    if configured:
        return configured
    cached = await redis.get(USERNAME_KEY)
    if cached:
        return cached if isinstance(cached, str) else cached.decode()
    try:
        me = await (client or client_factory()).get_me()
    except ChannelError:
        logger.warning("telegram: getMe failed, the deep link cannot be built")
        return None
    username = me.get("username")
    if username:
        await redis.set(USERNAME_KEY, username, ex=86_400)
    return username


async def link(
    session: AsyncSession, user_id: uuid.UUID, chat_id: int, username: str | None
) -> None:
    # one chat per account and one account per chat: drop older links of either
    await session.execute(
        delete(TelegramLink).where(
            (TelegramLink.chat_id == chat_id) | (TelegramLink.user_id == user_id)
        )
    )
    session.add(TelegramLink(user_id=user_id, chat_id=chat_id, username=username))
    await session.commit()


async def _language(session: AsyncSession, user_id: uuid.UUID | None) -> str:
    if user_id is None:
        return "ar"
    return Prefs.of(await session.get(NotificationPreference, user_id)).language


async def handle_update(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    update: dict[str, Any],
    client: TelegramClient | None = None,
) -> str | None:
    """Handle one Telegram update; returns what happened (for logs and tests)."""
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None or not text.startswith("/"):
        return None
    client = client or client_factory()
    command, _, arg = text.partition(" ")
    command = command.split("@", 1)[0].lower()  # /start@MyBot
    username = (message.get("from") or {}).get("username")
    async with factory() as session:
        current = await session.scalar(select(TelegramLink).where(TelegramLink.chat_id == chat_id))
        if command == "/start" and arg.strip():
            raw = await redis.getdel(CODE_KEY.format(code=arg.strip()))
            if raw is None:
                outcome, key, user_id = "bad_code", "bot.bad_code", None
            else:
                user_id = uuid.UUID(raw if isinstance(raw, str) else raw.decode())
                await link(session, user_id, chat_id, username)
                outcome, key = "linked", "bot.linked"
            reply = t(await _language(session, user_id), key)
        elif command == "/stop":
            if current is not None:
                await session.execute(delete(TelegramLink).where(TelegramLink.chat_id == chat_id))
                await session.commit()
                outcome = "unlinked"
                reply = t(await _language(session, current.user_id), "bot.unlinked")
            else:
                outcome, reply = "not_linked", t("ar", "bot.not_linked")
        elif command == "/status":
            if current is None:
                outcome, reply = "not_linked", t("ar", "bot.not_linked")
            else:
                user = await session.get(User, current.user_id)
                email = user.email if user else "?"
                masked = email[:2] + "***@" + email.split("@", 1)[-1] if "@" in email else "***"
                outcome = "status"
                reply = t(await _language(session, current.user_id), "bot.status", email=masked)
        else:
            outcome, reply = "help", t("ar", "bot.help") + "\n\n" + t("en", "bot.help")
    try:
        await client.send_message(chat_id, reply)
    except ChannelError as exc:
        logger.warning("telegram: reply failed: %s", exc.message)
    logger.info("telegram-bot: %s %s", command, outcome)
    return outcome
