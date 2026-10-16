"""The ``telegram-bot`` service: long polling of ``getUpdates`` for /start, /stop and /status.

    python -m app.notifications.telegram_bot

Polling needs no domain or HTTPS (the server has none yet). With ``TELEGRAM_MODE=webhook`` the
updates arrive at ``POST /api/v1/telegram/webhook/{secret}`` instead and this service idles.
Without ``TELEGRAM_BOT_TOKEN`` it also idles (it does not exit: the deploy waits for every
service to be running). Notifications themselves are sent by the Celery tasks.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.notifications.channels import ChannelError, RateLimited
from app.notifications.channels.telegram import TelegramClient
from app.notifications.telegram_link import handle_update

logger = logging.getLogger("telegram-bot")

OFFSET_KEY = "notif:tg:offset"


async def _idle(stop: asyncio.Event, reason: str) -> None:
    logger.info("telegram-bot idle: %s", reason)
    await stop.wait()


async def poll(stop: asyncio.Event) -> None:
    settings = get_settings()
    client = TelegramClient()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    delay = 1.0
    try:
        with contextlib.suppress(ChannelError):
            await client.delete_webhook()  # getUpdates refuses to work while a webhook is set
        logger.info("telegram-bot polling started")
        while not stop.is_set():
            offset = await redis.get(OFFSET_KEY)
            try:
                updates = await client.get_updates(int(offset) if offset else None)
                delay = 1.0
            except RateLimited as exc:
                await asyncio.sleep(exc.retry_after)
                continue
            except ChannelError as exc:
                logger.warning(
                    "telegram-bot: getUpdates failed (%s), retrying in %.0fs", exc, delay
                )
                await asyncio.sleep(delay)
                delay = min(60.0, delay * 2)
                continue
            for update in updates:
                try:
                    await handle_update(factory, redis, update, client)
                except Exception:  # noqa: BLE001 - one bad update must not stop the bot
                    logger.exception("telegram-bot: update %s failed", update.get("update_id"))
                await redis.set(OFFSET_KEY, int(update["update_id"]) + 1)
    finally:
        await redis.aclose()
        await engine.dispose()


async def main() -> None:
    configure_logging()
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):  # Windows
            loop.add_signal_handler(sig, stop.set)
    if not settings.telegram_bot_token:
        await _idle(stop, "TELEGRAM_BOT_TOKEN is empty (Telegram disabled)")
    elif settings.telegram_mode != "polling":
        await _idle(stop, f"TELEGRAM_MODE={settings.telegram_mode} (updates come by webhook)")
    else:
        runner = asyncio.create_task(poll(stop))
        await stop.wait()
        runner.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await runner
    logger.info("telegram-bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
