"""B1: the cTrader live feed against the mock server (tools/fake_ctrader): bars from quotes,
price scaling, the session (auth, symbol, backfill of the gap, spots), reconnects, tokens
(refresh before expiry, after an auth error, rotation persisted, encrypted, never logged), the
idle service, and the data-quality gate fed by it.

The mock runs on a clock 60x faster than real time, placed a week ahead (so one real second is
a market minute and no write is "late data" needing an aggregate refresh). The feed uses the
same clock. Sessions are real ones on their own pool (``committed_session_factory``).
"""

import asyncio
import importlib.util
import logging
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.feeds import secrets as box
from app.feeds.ctrader import credentials, store
from app.feeds.ctrader import protocol as p
from app.feeds.ctrader.candles import BarBuilder
from app.feeds.ctrader.service import Feed, backoff
from app.models.candle import Candle
from app.models.feed import FeedCredential
from app.models.instrument import Instrument, MarketType
from app.services import data_health
from tests.market_utils import make_instrument

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "fake_ctrader", ROOT / "tools" / "fake_ctrader" / "fake_ctrader.py"
)
fake_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_module)

T = datetime(2026, 10, 21, 14, 0, tzinfo=UTC)  # a Wednesday
S = timedelta(seconds=1)
GOLD = {
    "contract_size": 100,
    "tick_size": 0.01,
    "lot_step": 0.01,
    "min_lot": 0.01,
    "max_lot": 100,
    "price_basis": "bid",
}


# --- bars from quotes (pure) -------------------------------------------------------------------


def test_ohlc_on_bid_spread_time_weighted_volume_ticks() -> None:
    b = BarBuilder(grace_seconds=3, digits=2)
    assert b.quote(T + 10 * S, bid=2400.00, ask=2400.20) == []
    assert b.quote(T + 20 * S, bid=2402.50, ask=2402.90) == []
    assert b.quote(T + 30 * S, ask=2403.00) == []  # ask only: spread changes, OHLC do not
    assert b.quote(T + 40 * S, bid=2399.10, ask=2399.40) == []
    [bar] = b.quote(T + 61 * S, bid=2401.00, ask=2401.30)  # the next minute closes it
    assert (bar.ts, bar.open, bar.high, bar.low, bar.close) == (T, 2400.0, 2402.5, 2399.1, 2399.1)
    assert bar.volume == 4  # tick count: 4 quotes in the minute
    # 0.20 x 10 s + 0.40 x 10 s + 0.50 x 10 s + 0.30 x 20 s over 50 s = 0.34
    assert bar.spread == pytest.approx(0.34)
    assert b.current.ts == T + timedelta(minutes=1) and b.current.open == 2401.0


def test_minute_boundaries_and_the_grace_timer() -> None:
    b = BarBuilder(grace_seconds=3, digits=2)
    b.quote(T + 59.9 * S, bid=1.0, ask=1.2)
    assert b.due(T + 62.9 * S) == []  # within the grace
    [bar] = b.due(T + 63 * S)  # minute end + 3 s, no tick: closed by the timer
    assert bar.ts == T and bar.spread == pytest.approx(0.2)
    b.quote(T + 60 * S, bid=1.1, ask=1.3)  # exactly 14:01:00 opens the 14:01 bar
    assert b.current.ts == T + timedelta(minutes=1) and b.current.open == 1.1


def test_no_bar_for_minutes_without_ticks() -> None:
    b = BarBuilder(grace_seconds=3)
    b.quote(T + 5 * S, bid=2400.0, ask=2400.3)
    closed = b.quote(T + timedelta(minutes=5, seconds=2), bid=2401.0, ask=2401.3)
    assert [c.ts for c in closed] == [T]  # 14:01..14:04 had no tick: no bars
    assert b.due(T + timedelta(hours=60)) != []  # a weekend later: the open bar closes once
    assert b.due(T + timedelta(hours=61)) == []


def test_late_and_out_of_order_quotes_are_ignored() -> None:
    b = BarBuilder(grace_seconds=3)
    b.quote(T + 10 * S, bid=10.0, ask=10.1)
    b.due(T + 64 * S)
    assert b.quote(T + 50 * S, bid=99.0, ask=99.1) == []  # its minute is closed already
    assert b.current is None


# --- price scaling (the documented examples) ---------------------------------------------------


def test_prices_are_one_hundred_thousandths() -> None:
    """OpenApiMessages.proto, ProtoOASpotEvent.bid: "123000 in protocol means 1.23, 53423782
    means 534.23782"."""
    assert p.price(123000) == 1.23
    assert p.price(53423782) == 534.23782
    assert p.price(240012345, digits=2) == 2400.12


def test_trendbar_decoding() -> None:
    """low + deltaOpen/High/Close over 100000, open time = utcTimestampInMinutes x 60
    (spotware/OpenApiPy samples/jupyter/main.ipynb)."""
    minute = int(T.timestamp() // 60)
    bar = p.trendbar(
        {"volume": 31, "low": 239950000, "deltaOpen": 30000, "deltaHigh": 80000,
         "deltaClose": 55000, "utcTimestampInMinutes": minute},
        digits=2,
    )  # fmt: skip
    assert (bar.ts, bar.open, bar.high, bar.low, bar.close, bar.volume) == (
        T, 2399.8, 2400.3, 2399.5, 2400.05, 31,
    )  # fmt: skip


def test_backoff_is_jittered_exponential_and_capped() -> None:
    assert [backoff(n, lambda a, b: b) for n in range(8)] == [1, 2, 4, 8, 16, 32, 60, 60]
    assert backoff(3, lambda a, b: a) == 4


# --- the session against the mock --------------------------------------------------------------


class Clock:
    """The market's time: ``speed`` times real time from ``start``."""

    def __init__(self, start: datetime, speed: float = 60.0) -> None:
        self.start, self.speed, self.real0 = start.timestamp(), speed, time.time()

    def __call__(self) -> float:
        return self.start + (time.time() - self.real0) * self.speed

    def now(self) -> datetime:
        return datetime.fromtimestamp(self(), UTC)

    def advance(self, seconds: float) -> None:
        self.start += seconds


def _next_wednesday_noon() -> datetime:
    day = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    day += timedelta(days=7)
    return day + timedelta(days=(2 - day.weekday()) % 7)


@pytest.fixture
def clock() -> Clock:
    return Clock(_next_wednesday_noon())


@pytest.fixture
async def fake(clock: Clock) -> AsyncIterator:
    server = fake_module.FakeCTrader(
        tick_rate=10, heartbeat_seconds=0.5, max_bars=1000, clock=clock
    )
    url = await server.start()
    server.url = url
    yield server
    await server.stop()


@pytest.fixture
def factory(committed_session_factory) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    return committed_session_factory


@pytest.fixture
async def linked(factory, fake, monkeypatch: pytest.MonkeyPatch, redis_client: Redis):
    """Settings for the mock, the instrument, and a linked demo account."""
    settings = get_settings()
    for name, value in {
        "ctrader_enabled": True,
        "ctrader_env": "demo",
        "ctrader_client_id": fake_module.CLIENT_ID,
        "ctrader_client_secret": fake_module.CLIENT_SECRET,
        "ctrader_ws_url": fake.url,
        "ctrader_account_id": None,
        "ctrader_backfill_max_days": 1,
        "ctrader_close_grace_seconds": 3.0,
        "ctrader_instrument": "fxpro:XAU/USD",
    }.items():
        monkeypatch.setattr(settings, name, value)
    async with factory() as session:
        instrument = await make_instrument(
            session, "XAU/USD", "fxpro", MarketType.commodity, **GOLD
        )
        issued = fake.issue()
        await credentials.save_link(
            session,
            credentials.Tokens.from_answer(issued, datetime.fromtimestamp(fake.clock(), UTC)),
            [{"account_id": fake_module.ACCOUNT_ID, "is_live": False}],
            fake_module.ACCOUNT_ID,
        )
    await redis_client.delete(store.STATUS_KEY, store.RECONNECTS_KEY)
    yield {"instrument": instrument, "issued": issued}
    async with factory() as session:
        await session.execute(delete(FeedCredential))
        await session.commit()


async def _feed(factory, redis, clock) -> Feed:
    engine = factory.kw["bind"]
    return Feed(factory, redis, engine=engine, now=clock.now, sleep_scale=0.01)


async def _wait(condition, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not met in time")


async def _bars(factory, instrument: Instrument) -> list[Candle]:
    async with factory() as session:
        rows = await session.scalars(
            select(Candle).where(Candle.instrument_id == instrument.id).order_by(Candle.ts)
        )
        return list(rows.all())


async def _live_bars(factory, instrument) -> int:
    return sum(1 for c in await _bars(factory, instrument) if c.spread is not None)


async def test_session_streams_bars_and_backfills_the_gap(
    factory, redis_client, fake, linked, clock
) -> None:
    feed = await _feed(factory, redis_client, clock)
    stop = asyncio.Event()
    task = asyncio.create_task(feed.run(stop))
    try:
        await _wait(lambda: _live_bars(factory, linked["instrument"]), timeout=20)
        await _wait(lambda: _enough_live(factory, linked["instrument"], 3), timeout=20)
    finally:
        stop.set()
        await task
    received = fake.received
    # application auth, account auth, symbols, symbol by id, the gap's trend bars, then the
    # subscription (later trend-bar requests: the first live bar's OHLC)
    order = [t for t in received if t in (2100, 2102, 2114, 2116, 2137, 2127)]
    assert order[:5] == [2100, 2102, 2114, 2116, 2137]
    assert order.index(2127) > order.index(2137)
    bars = await _bars(factory, linked["instrument"])
    backfilled = [b for b in bars if b.spread is None]
    live = [b for b in bars if b.spread is not None]
    assert len(backfilled) >= 1400  # a day of M1 (the mock answers 1000 per request: hasMore)
    assert all(b.source == "fxpro_ctrader" for b in bars)
    # one bar per minute, no hole between the backfill and the live bars
    steps = {(b.ts - a.ts) for a, b in zip(bars, bars[1:], strict=False)}
    assert steps == {timedelta(minutes=1)}
    assert all(0.1 < b.spread < 0.4 for b in live)  # the mock's ask - bid
    status = await store.read_status(redis_client)
    assert status["state"] in ("streaming", "stopped") and status["last_bar"]["spread"]


async def _enough_live(factory, instrument, n: int) -> bool:
    return await _live_bars(factory, instrument) >= n


async def test_reconnect_reauthorises_resubscribes_and_backfills(
    factory, redis_client, fake, linked, clock
) -> None:
    feed = await _feed(factory, redis_client, clock)
    stop = asyncio.Event()
    task = asyncio.create_task(feed.run(stop))
    try:
        await _wait(lambda: _enough_live(factory, linked["instrument"], 2), timeout=20)
        before = len(fake.received)
        fake.drop()
        await _wait(lambda: feed.sessions >= 2, timeout=20)
        await _wait(lambda: _enough_live(factory, linked["instrument"], 5), timeout=30)
    finally:
        stop.set()
        await task
    after = fake.received[before:]
    assert [t for t in after if t in (2100, 2102, 2127)][:3] == [2100, 2102, 2127]
    assert 2137 in after  # the gap since the last stored bar was fetched
    bars = await _bars(factory, linked["instrument"])
    steps = {(b.ts - a.ts) for a, b in zip(bars, bars[1:], strict=False)}
    assert steps == {timedelta(minutes=1)}  # no hole across the drop
    assert (await store.read_status(redis_client))["reconnects_24h"] >= 1


async def test_tokens_refreshed_before_expiry_and_rotation_persisted(
    factory, redis_client, fake, linked, clock, caplog
) -> None:
    caplog.set_level(logging.DEBUG)
    soon = fake.issue(lifetime=2 * 86400)  # two days left: below the 7-day margin
    async with factory() as session:
        await credentials.save_link(
            session,
            credentials.Tokens.from_answer(soon, datetime.fromtimestamp(fake.clock(), UTC)),
            [{"account_id": fake_module.ACCOUNT_ID, "is_live": False}],
            fake_module.ACCOUNT_ID,
        )
    feed = await _feed(factory, redis_client, clock)
    stop = asyncio.Event()
    task = asyncio.create_task(feed.run(stop))
    try:
        await _wait(lambda: _enough_live(factory, linked["instrument"], 1), timeout=20)
    finally:
        stop.set()
        await task
    assert 2173 in fake.received  # ProtoOARefreshTokenReq
    async with factory() as session:
        row = await credentials.load(session)
        stored = credentials.tokens_of(row)
    assert stored.refresh_token != soon["refreshToken"]  # rotated, and persisted
    assert stored.refresh_token in fake.refresh_tokens
    assert stored.access_token != soon["accessToken"] and row.refreshed_at is not None
    # stored encrypted: neither token is in the row as text
    assert (
        row.access_token_enc.startswith("v1:") and stored.access_token not in row.access_token_enc
    )
    assert stored.refresh_token not in row.refresh_token_enc
    # and never logged
    for secret in (soon["accessToken"], soon["refreshToken"], stored.access_token,
                   stored.refresh_token, fake_module.CLIENT_SECRET):  # fmt: skip
        assert secret not in caplog.text


async def test_an_auth_error_triggers_a_refresh(
    factory, redis_client, fake, linked, clock, caplog
) -> None:
    """The stored expiry says 30 days, but cTrader refuses the token: refresh, then again."""
    caplog.set_level(logging.DEBUG)
    fake.expire_tokens()
    feed = await _feed(factory, redis_client, clock)
    stop = asyncio.Event()
    task = asyncio.create_task(feed.run(stop))
    try:
        await _wait(lambda: _enough_live(factory, linked["instrument"], 1), timeout=20)
        # mid-stream: cTrader invalidates the token (event 2147): reconnect with a refresh
        refreshes = fake.received.count(2173)
        fake.expire_tokens()
        await _wait(lambda: fake.received.count(2173) > refreshes, timeout=20)
        await _wait(lambda: feed.sessions >= 2, timeout=20)
    finally:
        stop.set()
        await task
    assert fake.received.count(2173) >= 2
    assert linked["issued"]["accessToken"] not in caplog.text
    assert linked["issued"]["refreshToken"] not in caplog.text


async def test_disabled_feed_idles_and_logs_once(
    factory, redis_client, fake, linked, clock, monkeypatch, caplog
) -> None:
    monkeypatch.setattr(get_settings(), "ctrader_enabled", False)
    caplog.set_level(logging.INFO, logger="feed-ctrader")
    feed = await _feed(factory, redis_client, clock)
    stop = asyncio.Event()
    task = asyncio.create_task(feed.run(stop))
    await asyncio.sleep(0.5)  # ~80 idle checks at sleep_scale 0.01
    stop.set()
    await task
    assert fake.received == []  # never connected
    idle = [r for r in caplog.records if "idle: disabled" in r.getMessage()]
    assert len(idle) == 1  # logged once (an hour)
    assert await _bars(factory, linked["instrument"]) == []
    assert (await store.read_status(redis_client))["state"] in ("disabled", "stopped")


async def test_not_linked_idles(factory, redis_client, fake, linked, clock) -> None:
    async with factory() as session:
        await session.execute(delete(FeedCredential))
        await session.commit()
    feed = await _feed(factory, redis_client, clock)
    assert await feed._ready() == "not_linked"


async def test_live_mock_data_makes_the_gate_ok_and_a_stop_degraded(
    factory, redis_client, fake, linked, clock, monkeypatch
) -> None:
    """The B5 gate on fxpro:XAU/USD: ok while the feed streams (with 3 days backfilled for its
    lookback), degraded once the feed stops for longer than the allowed lag."""
    monkeypatch.setattr(get_settings(), "ctrader_backfill_max_days", 3)
    monkeypatch.setattr(get_settings(), "data_quality_instruments", "fxpro:XAU/USD")
    feed = await _feed(factory, redis_client, clock)
    stop = asyncio.Event()
    task = asyncio.create_task(feed.run(stop))
    try:
        await _wait(lambda: _enough_live(factory, linked["instrument"], 3), timeout=40)
        async with factory() as session:
            [report] = await data_health.compute(session, ["fxpro:XAU/USD"], clock.now())
        assert report.status.value == "ok", [c for c in report.checks if not c.ok]
    finally:
        stop.set()
        await task
    clock.advance(get_settings().data_quality_max_lag_seconds + 120)  # no quote any more
    async with factory() as session:
        [report] = await data_health.compute(session, ["fxpro:XAU/USD"], clock.now())
    assert report.status.value == "degraded"
    assert "freshness" in {c.name for c in report.failed}


# --- backfill never overwrites a live bar -------------------------------------------------------


async def test_backfill_never_overwrites_a_live_bar(session_factory, session: AsyncSession) -> None:
    instrument = await make_instrument(session, "XAU/USD", "fxpro", MarketType.commodity)
    ts = T + timedelta(days=30)  # far from now: no aggregate refresh involved
    live = store.live_candle(
        fake_module_bar(ts, 2400.0, 2401.0, 2399.0, 2400.5, spread=0.27), ts + 61 * S
    )
    await store.write(session_factory, instrument.id, [live], keep_live=False, refresh=False)
    other = ts + timedelta(minutes=1)
    plain = p.Trendbar(other, 1.0, 1.0, 1.0, 1.0, 1)
    await store.write(
        session_factory, instrument.id, [store.backfill_candle(plain, ts)], keep_live=True,
        refresh=False,
    )  # fmt: skip
    backfilled = [
        store.backfill_candle(p.Trendbar(ts, 9.0, 9.0, 9.0, 9.0, 99), ts + 90 * S),
        store.backfill_candle(p.Trendbar(other, 2.0, 2.0, 2.0, 2.0, 5), ts + 90 * S),
        store.backfill_candle(p.Trendbar(other, 2.0, 2.0, 2.0, 2.0, 5), ts + 90 * S),  # again
    ]
    await store.write(session_factory, instrument.id, backfilled, keep_live=True, refresh=False)
    rows = {
        c.ts: c
        for c in await session.scalars(
            select(Candle)
            .where(Candle.instrument_id == instrument.id)
            .execution_options(populate_existing=True)
        )
    }
    assert len(rows) == 2  # no duplicates
    assert (rows[ts].open, rows[ts].close, rows[ts].spread) == (2400.0, 2400.5, 0.27)  # kept
    assert (rows[other].open, rows[other].volume, rows[other].spread) == (2.0, 5, None)
    count = await session.scalar(
        select(func.count()).select_from(Candle).where(Candle.instrument_id == instrument.id)
    )
    assert count == 2


def fake_module_bar(ts, o, h, lo, c, spread):
    from app.feeds.ctrader.candles import ClosedBar  # noqa: PLC0415

    return ClosedBar(ts, o, h, lo, c, 10, spread)


def test_tokens_are_encrypted_with_a_derived_key() -> None:
    sealed = box.encrypt("secret-token")
    assert sealed.startswith("v1:") and "secret-token" not in sealed
    assert box.decrypt(sealed) == "secret-token"
    assert repr(credentials.Tokens("a", "b", T)) == "Tokens(expires_at=2026-10-21T14:00:00+00:00)"


async def test_admin_backfill_task_in_chunks_keeps_live_bars(
    factory, redis_client, fake, linked, clock
) -> None:
    """The manual backfill (Celery task feeds.ctrader_backfill): a day per request, idempotent,
    a live bar (with a spread) is kept."""
    from app.feeds.ctrader import backfill  # noqa: PLC0415

    instrument = linked["instrument"]
    now = clock.now().replace(second=0, microsecond=0)
    start, end = now - timedelta(days=2, hours=6), now - timedelta(hours=1)
    live_ts = start + timedelta(hours=3)
    live = store.live_candle(fake_module_bar(live_ts, 1.0, 2.0, 0.5, 1.5, spread=0.31), now)
    await store.write(factory, instrument.id, [live], keep_live=False, refresh=False)
    await redis_client.delete(backfill.LOCK_KEY)
    engine = factory.kw["bind"]
    result = await backfill.run(
        factory, redis_client, start, end, engine=engine, pause=0, now=clock.now()
    )
    assert result["state"] == "done", result
    trendbar_requests = fake.received.count(2137)
    assert trendbar_requests >= 3  # 2.2 days: three daily chunks (+ hasMore follow-ups)
    bars = await _bars(factory, instrument)
    assert len(bars) == (end - start) // timedelta(minutes=1)
    kept = next(b for b in bars if b.ts == live_ts)
    assert (kept.open, kept.spread) == (1.0, 0.31)
    again = await backfill.run(
        factory, redis_client, start, end, engine=engine, pause=0, now=clock.now()
    )
    assert again["state"] == "done" and len(await _bars(factory, instrument)) == len(bars)
    status = await redis_client.get(backfill.STATUS_KEY)
    assert '"state": "done"' in status
