"""``python -m app.feeds.ctrader``: the feed-ctrader service (docs/ctrader-feed.md)."""

import asyncio
import contextlib
import logging
import signal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import set_redis
from app.feeds.ctrader.service import Feed

logger = logging.getLogger("feed-ctrader")


async def main() -> None:
    configure_logging()
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):  # Windows
            loop.add_signal_handler(sig, stop.set)
    # one bar a minute: two connections are plenty (the aggregate refresh takes its own)
    engine = create_async_engine(settings.database_url, pool_size=2, max_overflow=1)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    set_redis(redis)  # the candle publisher uses the shared client
    try:
        await Feed(async_sessionmaker(engine, expire_on_commit=False), redis, engine=engine).run(
            stop
        )
    finally:
        await redis.aclose()
        await engine.dispose()
    logger.info("feed-ctrader stopped")


if __name__ == "__main__":
    asyncio.run(main())
