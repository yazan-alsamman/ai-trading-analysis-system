"""A long backfill by hand (``POST /admin/feeds/ctrader/backfill``, the Celery task
``feeds.ctrader_backfill`` on the maintenance queue; docs/ctrader-feed.md#backfill).

Fadi needs about a year of D1 and 20 days of 15m: M1 trend bars for the range, a day per
request (at most 4 history requests a second), written day by day with ``keep_live`` (a bar
built live, with a spread, is never overwritten), then the continuous aggregates are
re-materialized once for the whole range. Idempotent: running it again rewrites the same bars.

It opens its own connection with the stored tokens. While the live feed is enabled it never
refreshes them (the feed owns the refresh: two refreshers would invalidate each other's
refresh token); with the feed disabled it may.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.feeds.ctrader import api, credentials, store
from app.feeds.ctrader import protocol as p
from app.feeds.ctrader.connection import Connection, TokenError
from app.models.instrument import Instrument
from app.services import market_service

logger = logging.getLogger(__name__)

LOCK_KEY = "feeds:ctrader:backfill-lock"
STATUS_KEY = "feeds:ctrader:backfill"
MAX_RANGE = timedelta(days=400)
DAY = timedelta(days=1)


class BackfillError(Exception):
    pass


async def run(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    start: datetime,
    end: datetime,
    *,
    engine: AsyncEngine | None = None,
    connection=Connection,
    pause: float = 1 / p.HISTORY_REQUESTS_PER_SECOND,
    now: datetime | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    start, end = start.astimezone(UTC), min(end.astimezone(UTC), now or datetime.now(UTC))
    if not await redis.set(LOCK_KEY, "1", nx=True, ex=4 * 3600):
        return {"status": "busy"}
    progress: dict[str, Any] = {
        "state": "running",
        "from": start.isoformat(),
        "to": end.isoformat(),
        "written": 0,
        "bars": 0,
    }
    try:
        async with factory() as session:
            key = settings.ctrader_instrument_key
            instrument = await session.scalar(
                select(Instrument).where(Instrument.source == key[0], Instrument.symbol == key[1])
            )
            row = await credentials.load(session)
        if instrument is None or row is None:
            raise BackfillError("no instrument or no linked account")
        account_id = settings.ctrader_account_id or row.account_id
        if account_id is None:
            raise BackfillError("no account chosen")
        tokens = credentials.tokens_of(row)
        url = p.ws_url(settings.ctrader_env, settings.ctrader_ws_url)
        async with connection(url) as conn:
            await api.authorize_app(
                conn, settings.ctrader_client_id, settings.ctrader_client_secret
            )
            try:
                await api.authorize_account(conn, account_id, tokens.access_token)
            except TokenError:
                if settings.ctrader_enabled:
                    raise BackfillError(
                        "the access token was refused; the live feed refreshes it: try later"
                    ) from None
                tokens = await api.refresh(conn, tokens.refresh_token)
                async with factory() as session:
                    await credentials.save_refreshed(session, tokens)
                await api.authorize_account(conn, account_id, tokens.access_token)
            symbol = await api.find_symbol(conn, account_id, settings.ctrader_symbol)
            day = start
            while day < end:
                upto = min(day + DAY, end)
                bars = await api.fetch_m1(conn, account_id, symbol, day, upto, pause=pause)
                received = datetime.now(UTC)
                progress["written"] += await store.write(
                    factory,
                    instrument.id,
                    [store.backfill_candle(b, received) for b in bars],
                    keep_live=True,
                    refresh=False,
                )
                progress["bars"] += len(bars)
                progress["done_until"] = upto.isoformat()
                await _progress(redis, progress)
                day = upto
        if progress["bars"]:
            await market_service.refresh_aggregates(start, end, engine)
        progress["state"] = "done"
        logger.info(
            "cTrader backfill %s..%s: %d bars, %d written",
            start.isoformat(),
            end.isoformat(),
            progress["bars"],
            progress["written"],
        )
        return progress
    except Exception as exc:
        progress.update(state="failed", error=f"{type(exc).__name__}: {exc}"[:300])
        logger.warning("cTrader backfill failed: %s", progress["error"])
        return progress
    finally:
        await _progress(redis, progress)
        await redis.delete(LOCK_KEY)


async def _progress(redis: Redis, progress: dict[str, Any]) -> None:
    try:
        await redis.set(STATUS_KEY, json.dumps(progress), ex=7 * 24 * 3600)
    except Exception:  # noqa: BLE001
        logger.warning("cTrader backfill: writing the progress failed")


def check_range(start: datetime, end: datetime, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if start.tzinfo is None or end.tzinfo is None:
        raise BackfillError("from and to need a time zone (e.g. 2026-01-01T00:00:00Z)")
    if start >= end:
        raise BackfillError("from must be before to")
    if start >= now:
        raise BackfillError("from must be in the past")
    if end - start > MAX_RANGE:
        raise BackfillError("at most 400 days per backfill")
