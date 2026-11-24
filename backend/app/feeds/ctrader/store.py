"""Writing the feed's bars and its status (B1, docs/ctrader-feed.md).

Bars go through the one insert path, ``market_service.upsert_candles``, then
``market_events.publish_candle_updates_safely``:

- live bars (built from quotes) carry the spread and overwrite whatever is stored for that
  minute (the live value wins);
- backfilled bars (M1 trend bars) have ``spread = null`` and are written with ``keep_live``:
  a stored bar that has a spread is never overwritten. Bars older than an hour are also
  re-materialized in the continuous aggregates (``refresh_aggregates``).

The status lives in Redis (``STATUS_KEY``, a JSON object) for ``GET /admin/feeds/ctrader`` and
``/admin/system/status``; reconnects are a sorted set of times (the last 24 h are counted).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.feeds.ctrader import protocol as p
from app.feeds.ctrader.candles import ClosedBar
from app.models.candle import Candle
from app.schemas.market import CandleIn
from app.services import market_events, market_service

logger = logging.getLogger(__name__)

SOURCE = "fxpro_ctrader"
STATUS_KEY = "feeds:ctrader:status"
RECONNECTS_KEY = "feeds:ctrader:reconnects"
DAY = 24 * 3600


def live_candle(bar: ClosedBar, received_at: datetime) -> CandleIn:
    return CandleIn(
        ts=bar.ts,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,  # tick count: cTrader quotes carry no traded volume
        spread=bar.spread,
        source=SOURCE,
        received_at=received_at,
    )


def backfill_candle(bar: p.Trendbar, received_at: datetime) -> CandleIn:
    return CandleIn(
        ts=bar.ts,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,  # "Bar volume in ticks."
        spread=None,  # trend bars carry no spread
        source=SOURCE,
        received_at=received_at,
    )


async def write(
    factory: async_sessionmaker[AsyncSession],
    instrument_id: uuid.UUID,
    candles: Sequence[CandleIn],
    *,
    keep_live: bool,
    engine: AsyncEngine | None = None,
    refresh: bool = True,
) -> int:
    if not candles:
        return 0
    async with factory() as session:
        written = await market_service.upsert_candles(
            session, instrument_id, candles, keep_live=keep_live
        )
        await session.commit()
        if refresh and market_service.needs_aggregate_refresh(candles):
            await market_service.refresh_aggregates(
                min(c.ts for c in candles), max(c.ts for c in candles), engine
            )
        await market_events.publish_candle_updates_safely(session, instrument_id, candles)
    return written


async def last_feed_bar(
    factory: async_sessionmaker[AsyncSession], instrument_id: uuid.UUID
) -> datetime | None:
    """The newest 1m bar this feed wrote (live or backfilled)."""
    async with factory() as session:
        return await session.scalar(
            select(Candle.ts)
            .where(Candle.instrument_id == instrument_id, Candle.source == SOURCE)
            .order_by(Candle.ts.desc())
            .limit(1)
        )


def gap(last: datetime | None, now: datetime, max_days: int) -> tuple[datetime, datetime] | None:
    """The range to backfill: from the minute after the last stored bar (at most
    ``max_days`` back) to the last closed minute."""
    end = now.astimezone(UTC).replace(second=0, microsecond=0)
    floor = end - timedelta(days=max_days)
    start = floor if last is None else max(floor, last + timedelta(minutes=1))
    return (start, end) if start < end else None


# --- status ---------------------------------------------------------------------------------------


async def set_status(redis: Redis, **fields: Any) -> None:
    """Merge ``fields`` into the stored status (never tokens). Never raises."""
    try:
        raw = await redis.get(STATUS_KEY)
        status = json.loads(raw) if raw else {}
        status.update(fields, updated_at=_iso(datetime.now(UTC)))
        await redis.set(STATUS_KEY, json.dumps(status, default=_iso))
    except Exception:  # noqa: BLE001 - the feed keeps running without its status
        logger.warning("cTrader feed: writing the status failed", exc_info=True)


async def count_reconnect(redis: Redis) -> None:
    try:
        now = time.time()
        await redis.zadd(RECONNECTS_KEY, {f"{now:.6f}": now})
        await redis.zremrangebyscore(RECONNECTS_KEY, 0, now - DAY)
    except Exception:  # noqa: BLE001
        logger.warning("cTrader feed: counting a reconnect failed", exc_info=True)


async def read_status(redis: Redis) -> dict[str, Any]:
    raw = await redis.get(STATUS_KEY)
    status = json.loads(raw) if raw else {}
    now = time.time()
    status["reconnects_24h"] = await redis.zcount(RECONNECTS_KEY, now - DAY, now)
    return status


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)
