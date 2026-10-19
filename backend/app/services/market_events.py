"""Live candle updates for WebSocket clients, published after 1m candles are committed."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.candle import AGGREGATE_TIMEFRAMES, Timeframe
from app.realtime import protocol, publisher
from app.realtime.topics import candles_topic, channel_for
from app.schemas.market import CandleIn, CandleOut
from app.services import market_service

logger = logging.getLogger(__name__)

# Only candles this recent are pushed live; backfills must not spam the sockets.
LIVE_WINDOW = timedelta(hours=2)


async def publish_candle_updates(
    session: AsyncSession,
    instrument_id: uuid.UUID,
    candles: Sequence[CandleIn],
    *,
    redis: Redis | None = None,
    now: datetime | None = None,
) -> list[Timeframe]:
    """Publish the newest 1m candle and, for higher timeframes that have subscribers anywhere,
    the current bucket (read through real-time aggregation). At most one message per
    (instrument, timeframe). Returns the timeframes published. Call after the commit."""
    now = now or datetime.now(UTC)
    recent = [c for c in candles if c.ts >= now - LIVE_WINDOW]
    if not recent:
        return []
    redis = redis or get_redis()
    newest = max(recent, key=lambda c: c.ts)

    published = [Timeframe.m1]
    await publisher.publish(
        candles_topic(instrument_id, Timeframe.m1),
        protocol.candle_event(
            instrument_id, Timeframe.m1, CandleOut.from_candle(newest).model_dump(exclude_none=True)
        ),
        redis,
    )

    channels = {tf: channel_for(candles_topic(instrument_id, tf)) for tf in AGGREGATE_TIMEFRAMES}
    counts = dict(await redis.pubsub_numsub(*channels.values()))
    for tf in AGGREGATE_TIMEFRAMES:
        if not counts.get(channels[tf]):
            continue  # nobody listens: skip the aggregate query
        latest = await market_service.get_latest_candle(session, instrument_id, tf)
        if latest is None:
            continue
        await publisher.publish(
            candles_topic(instrument_id, tf),
            protocol.candle_event(
                instrument_id, tf, CandleOut.from_candle(latest).model_dump(exclude_none=True)
            ),
            redis,
        )
        published.append(tf)
    return published


async def publish_candle_updates_safely(
    session: AsyncSession,
    instrument_id: uuid.UUID,
    candles: Sequence[CandleIn],
    **kwargs,
) -> list[Timeframe]:
    """Like publish_candle_updates, but logs failures instead of raising: a Redis outage must
    never fail a candle write that is already committed."""
    try:
        return await publish_candle_updates(session, instrument_id, candles, **kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("Publishing live candle updates for %s failed", instrument_id)
        return []
