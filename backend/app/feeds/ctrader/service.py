"""The feed-ctrader service (B1, docs/ctrader-feed.md): XAU/USD quotes from the cTrader Open API
into 1m bars of ``CTRADER_INSTRUMENT``.

``Feed.run`` never crash-loops:

- **Idle** while the feed is disabled (``CTRADER_ENABLED=false``, the default), the app
  credentials are missing, no account is linked, or the instrument does not exist: it looks
  again every minute and logs the reason once an hour.
- **A session**: connect (JSON over WebSocket, the host of ``CTRADER_ENV``), application auth,
  token refresh when less than 7 days are left (or after a token error), account auth, the
  symbol and its ``digits``, the **gap backfill** (M1 trend bars since the last stored bar, at
  most ``CTRADER_BACKFILL_MAX_DAYS``), subscribe to spots, then build bars from the quotes
  (candles.py) and write each closed bar at once. A heartbeat goes out every 10 s; after 30 s
  without any message a version request checks the connection.
- **Any failure** ends the session: reconnect after a jittered exponential backoff (1 s,
  doubling, at most 60 s, times 0.5..1), then everything above again (auth, backfill of the
  gap, subscription). A session that lasted 5 minutes resets the backoff.

The first bar of a session starts mid-minute; once it closes its OHLC is taken from the M1 trend
bar of that minute (the spread stays the live one), and the minutes that passed while the gap
backfill ran are fetched with it. A bar still open when a session ends is dropped: the next
session's gap backfill fetches that minute.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.feeds.ctrader import api, credentials, store
from app.feeds.ctrader import protocol as p
from app.feeds.ctrader.candles import BarBuilder, ClosedBar
from app.feeds.ctrader.connection import Connection, CTraderError, Disconnected, TokenError
from app.feeds.secrets import CredentialDecryptError
from app.models.instrument import Instrument
from app.services import market_service

logger = logging.getLogger("feed-ctrader")

IDLE_CHECK_SECONDS = 60.0
IDLE_LOG_SECONDS = 3600.0
SILENCE_SECONDS = 30.0  # then a version request checks the connection
BACKOFF_BASE, BACKOFF_CAP = 1.0, 60.0
STABLE_SECONDS = 300.0  # a session that lasted this long resets the backoff
TOKEN_CHECK_SECONDS = 3600.0
VERSION_REQ = 2104  # PROTO_OA_VERSION_REQ (ProtoOAPayloadType): a cheap liveness probe


class Reconnect(Exception):  # noqa: N818 - a signal, not an error
    """End the session and connect again (e.g. after a token refresh)."""


@dataclass
class Ready:
    instrument_id: uuid.UUID
    account_id: int
    tokens: credentials.Tokens


def backoff(attempt: int, rng: Callable[[float, float], float] = random.uniform) -> float:
    return min(BACKOFF_CAP, BACKOFF_BASE * 2**attempt) * rng(0.5, 1.0)


class Feed:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        redis: Redis,
        *,
        engine: AsyncEngine | None = None,
        connection: Callable[..., Connection] = Connection,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep_scale: float = 1.0,
    ) -> None:
        self.factory = factory
        self.redis = redis
        self.engine = engine
        self.connection = connection
        self.now = now
        self.sleep_scale = sleep_scale  # tests shrink the waits
        self.attempt = 0
        self.force_refresh = False
        self.sessions = 0
        self._idle_logged: dict[str, float] = {}

    # --- the loop -------------------------------------------------------------------------------

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            ready = await self._ready()
            if isinstance(ready, str):
                await self._idle(ready, stop)
                continue
            started = time.monotonic()
            error: str | None = None
            try:
                await self._session(ready, stop)
            except Reconnect as exc:
                error = f"reconnect: {exc}"
            except TokenError as exc:
                self.force_refresh = True
                error = f"token: {exc.code}"
            except CredentialDecryptError as exc:
                error = f"credentials: {exc}"
            except (CTraderError, Disconnected, OSError, TimeoutError) as exc:
                error = f"{type(exc).__name__}: {exc}"
            except Exception as exc:  # noqa: BLE001 - never crash-loop
                logger.exception("cTrader feed: session failed")
                error = f"{type(exc).__name__}"
            if stop.is_set():
                break
            if time.monotonic() - started >= STABLE_SECONDS:
                self.attempt = 0
            delay = backoff(self.attempt) * self.sleep_scale
            self.attempt += 1
            logger.warning("cTrader feed: %s; reconnecting in %.1f s", error, delay)
            await store.count_reconnect(self.redis)
            await store.set_status(self.redis, state="backoff", connected=False, last_error=error)
            await _wait(stop, delay)
        await store.set_status(self.redis, state="stopped", connected=False)

    async def _ready(self) -> Ready | str:
        """What the feed needs, or why it idles."""
        settings = get_settings()
        if not settings.ctrader_enabled:
            return "disabled"
        if not settings.ctrader_client_id or not settings.ctrader_client_secret:
            return "no_app_credentials"
        key = settings.ctrader_instrument_key
        async with self.factory() as session:
            instrument = (
                await session.scalar(
                    select(Instrument).where(
                        Instrument.source == key[0], Instrument.symbol == key[1]
                    )
                )
                if key
                else None
            )
            row = await credentials.load(session)
        if instrument is None:
            return "instrument_missing"
        if row is None:
            return "not_linked"
        if row.env != settings.ctrader_env:
            return "env_mismatch"
        account_id = settings.ctrader_account_id or row.account_id
        if account_id is None:
            return "no_account"
        try:
            tokens = credentials.tokens_of(row)
        except CredentialDecryptError:
            return "relink_required"
        return Ready(instrument.id, int(account_id), tokens)

    async def _idle(self, reason: str, stop: asyncio.Event) -> None:
        last = self._idle_logged.get(reason)
        if last is None or time.monotonic() - last >= IDLE_LOG_SECONDS:
            logger.info("cTrader feed idle: %s (checked every minute, logged once an hour)", reason)
            self._idle_logged[reason] = time.monotonic()
        await store.set_status(self.redis, state=reason, connected=False)
        await _wait(stop, IDLE_CHECK_SECONDS * self.sleep_scale)

    # --- one session ----------------------------------------------------------------------------

    async def _session(self, ready: Ready, stop: asyncio.Event) -> None:
        settings = get_settings()
        events: asyncio.Queue[tuple[int, dict[str, Any], datetime]] = asyncio.Queue()
        url = p.ws_url(settings.ctrader_env, settings.ctrader_ws_url)

        def on_event(payload_type: int, payload: dict[str, Any]) -> None:
            events.put_nowait((payload_type, payload, self.now()))

        await store.set_status(self.redis, state="connecting", connected=False)
        async with self.connection(url, on_event) as conn:
            self.sessions += 1
            await api.authorize_app(
                conn, settings.ctrader_client_id, settings.ctrader_client_secret
            )
            tokens = ready.tokens
            if self.force_refresh or credentials.needs_refresh(tokens, self.now()):
                tokens = await self._refresh(conn, tokens)
            try:
                await api.authorize_account(conn, ready.account_id, tokens.access_token)
            except TokenError:
                tokens = await self._refresh(conn, tokens)
                await api.authorize_account(conn, ready.account_id, tokens.access_token)
            self.force_refresh = False
            symbol = await api.find_symbol(conn, ready.account_id, settings.ctrader_symbol)
            backfilled_until = await self._backfill_gap(conn, ready, symbol)
            await conn.request(p.subscribe_spots(ready.account_id, symbol.symbol_id))
            await store.set_status(
                self.redis,
                state="streaming",
                connected=True,
                env=settings.ctrader_env,
                account_id=ready.account_id,
                symbol=symbol.name,
                symbol_id=symbol.symbol_id,
                digits=symbol.digits,
                token_expires_at=tokens.expires_at,
                last_error=None,
            )
            logger.info(
                "cTrader feed streaming %s (id %s, %d digits) on %s",
                symbol.name,
                symbol.symbol_id,
                symbol.digits,
                settings.ctrader_env,
            )
            await self._stream(conn, ready, symbol, tokens, events, stop, backfilled_until)

    async def _refresh(self, conn: Connection, tokens: credentials.Tokens) -> credentials.Tokens:
        fresh = await api.refresh(conn, tokens.refresh_token)
        async with self.factory() as session:
            await credentials.save_refreshed(session, fresh)  # the old pair is dead already
        logger.info("cTrader feed: access token refreshed (expires %s)", fresh.expires_at)
        return fresh

    async def _backfill_gap(self, conn: Connection, ready: Ready, symbol: api.Symbol) -> datetime:
        """Fetch and store the gap; returns where it ends (the minute the backfill stopped at)."""
        now = self.now()
        last = await store.last_feed_bar(self.factory, ready.instrument_id)
        window = store.gap(last, now, get_settings().ctrader_backfill_max_days)
        if window is None:
            return now.astimezone(UTC).replace(second=0, microsecond=0)
        # a day at a time (fetched, written, released): the memory stays small (128m service)
        written = fetched = 0
        start, end = window
        while start < end:
            upto = min(start + timedelta(days=1), end)
            bars = await api.fetch_m1(
                conn, ready.account_id, symbol, start, upto, pause=0.25 * self.sleep_scale
            )
            fetched += len(bars)
            written += await store.write(
                self.factory,
                ready.instrument_id,
                [store.backfill_candle(b, self.now()) for b in bars],
                keep_live=True,
                engine=self.engine,
                refresh=False,
            )
            start = upto
        if fetched and window[0] < datetime.now(UTC) - market_service.LATE_DATA_THRESHOLD:
            await market_service.refresh_aggregates(window[0], window[1], self.engine)
        logger.info(
            "cTrader feed: backfilled %d of %d M1 bars from %s to %s",
            written,
            fetched,
            window[0].isoformat(),
            window[1].isoformat(),
        )
        return window[1]

    async def _stream(
        self,
        conn: Connection,
        ready: Ready,
        symbol: api.Symbol,
        tokens: credentials.Tokens,
        events: asyncio.Queue,
        stop: asyncio.Event,
        backfilled_until: datetime,
    ) -> None:
        builder = BarBuilder(get_settings().ctrader_close_grace_seconds, symbol.digits)
        first = True
        next_heartbeat = time.monotonic() + p.HEARTBEAT_SECONDS
        next_token_check = time.monotonic() + TOKEN_CHECK_SECONDS
        last_tick: datetime | None = None
        while not stop.is_set():
            if conn.closed.is_set():
                raise Disconnected("connection closed")
            if time.monotonic() - conn.last_received > SILENCE_SECONDS:
                await conn.request((VERSION_REQ, {}), timeout=15)  # Disconnected if no answer
            closed: list[ClosedBar] = []
            try:
                payload_type, payload, at = await asyncio.wait_for(events.get(), timeout=0.5)
            except TimeoutError:
                payload_type = None
            if (
                payload_type == p.SPOT_EVENT
                and int(payload.get("symbolId", -1)) == symbol.symbol_id
            ):
                when = _spot_time(payload, at)
                bid = p.price(payload["bid"], symbol.digits) if "bid" in payload else None
                ask = p.price(payload["ask"], symbol.digits) if "ask" in payload else None
                closed += builder.quote(when, bid, ask)
                last_tick = when
            elif payload_type == p.ACCOUNTS_TOKEN_INVALIDATED_EVENT:
                self.force_refresh = True
                raise TokenError("ACCOUNTS_TOKEN_INVALIDATED", str(payload.get("reason") or ""))
            elif payload_type in (p.CLIENT_DISCONNECT_EVENT, p.ACCOUNT_DISCONNECT_EVENT):
                raise Disconnected(f"disconnected by cTrader ({payload.get('reason') or ''})")
            elif payload_type in (p.ERROR_RES, p.OA_ERROR_RES):
                code = str(payload.get("errorCode") or "")
                if code in p.TOKEN_ERRORS:
                    self.force_refresh = True
                    raise TokenError(code, str(payload.get("description") or ""))
                logger.warning("cTrader feed: error event %s", code)
            closed += builder.due(self.now())
            for bar in closed:
                await self._write_live(
                    conn, ready, symbol, bar, backfilled_until if first else None
                )
                first = False
            if time.monotonic() >= next_heartbeat:
                await conn.send(*p.heartbeat())
                next_heartbeat = time.monotonic() + p.HEARTBEAT_SECONDS
                await store.set_status(self.redis, connected=True, last_tick_at=last_tick)
            if time.monotonic() >= next_token_check:
                next_token_check = time.monotonic() + TOKEN_CHECK_SECONDS
                if credentials.needs_refresh(tokens, self.now()):
                    self.force_refresh = True
                    raise Reconnect("the access token expires within 7 days: refreshing")

    async def _write_live(
        self,
        conn: Connection,
        ready: Ready,
        symbol: api.Symbol,
        bar: ClosedBar,
        since: datetime | None,
    ) -> None:
        """Store a closed live bar. ``since`` (the session's first bar): the trend bars from where
        the gap backfill stopped up to this bar are fetched too: the minutes that passed while
        the backfill ran are stored as backfill, and this bar, which began mid-minute, takes its
        OHLC and ticks from its trend bar (the spread stays the live one)."""
        received = self.now()
        candle = store.live_candle(bar, received)
        if since is not None:
            try:
                bars = await api.fetch_m1(
                    conn,
                    ready.account_id,
                    symbol,
                    min(since, bar.ts),
                    bar.ts + timedelta(minutes=1),
                    pause=0,
                )
            except CTraderError:
                bars = []
            earlier = [b for b in bars if b.ts < bar.ts]
            if earlier:
                await store.write(
                    self.factory,
                    ready.instrument_id,
                    [store.backfill_candle(b, received) for b in earlier],
                    keep_live=True,
                    engine=self.engine,
                )
            same = [b for b in bars if b.ts == bar.ts]
            if same:
                tb = same[0]
                candle = candle.model_copy(
                    update={
                        "open": tb.open,
                        "high": tb.high,
                        "low": tb.low,
                        "close": tb.close,
                        "volume": tb.volume,
                    }
                )
        await store.write(self.factory, ready.instrument_id, [candle], keep_live=False)
        await store.set_status(
            self.redis,
            last_bar={"ts": bar.ts, "close": candle.close, "spread": candle.spread},
            last_bar_written_at=received,
        )


def _spot_time(payload: dict[str, Any], received: datetime) -> datetime:
    """The quote's time: the server's ``timestamp`` (ms; we subscribe with
    ``subscribeToSpotTimestamp``), else when it arrived."""
    raw = payload.get("timestamp")
    return datetime.fromtimestamp(int(raw) / 1000, UTC) if raw else received


async def _wait(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), max(0.0, seconds))
    except TimeoutError:
        pass
