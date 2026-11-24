"""Live candle publishing (market_events), the ingest hook and the simulate-live command."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import simulate_live
from app.models.candle import Timeframe
from app.realtime import publisher
from app.realtime.topics import candles_topic, channel_for
from app.schemas.market import CandleOut
from app.services import market_events, market_service
from tests.market_utils import candle_json, known_candles, make_instrument

NOW = datetime.now(UTC).replace(second=0, microsecond=0)


@pytest.fixture
async def instrument(session: AsyncSession):
    return await make_instrument(session)


@pytest.fixture
async def listener(redis_client: Redis) -> AsyncIterator[PubSub]:
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    yield pubsub
    await pubsub.aclose()


async def _listen(pubsub: PubSub, instrument_id, *timeframes: Timeframe) -> None:
    await pubsub.subscribe(*(channel_for(candles_topic(instrument_id, tf)) for tf in timeframes))


async def _messages(pubsub: PubSub, wait: float = 0.3) -> list[dict]:
    out = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait
    while loop.time() < deadline:
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.05)
        if msg is not None:
            out.append(json.loads(msg["data"]))
    return out


async def test_only_1m_without_subscribers(
    session: AsyncSession, instrument, listener: PubSub
) -> None:
    candles = known_candles(NOW - timedelta(minutes=4), 5)
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    await _listen(listener, instrument.id, Timeframe.m1)

    published = await market_events.publish_candle_updates(session, instrument.id, candles, now=NOW)
    assert published == [Timeframe.m1]
    [msg] = await _messages(listener)
    newest = candles[-1]
    assert msg["type"] == "candle" and msg["timeframe"] == "1m"
    assert msg["topic"] == candles_topic(instrument.id, Timeframe.m1)
    assert msg["instrument_id"] == str(instrument.id)
    assert msg["candle"] == CandleOut.from_candle(newest).model_dump(exclude_none=True)
    # exactly the CandleOut shape; spread only when the candle has one
    assert set(msg["candle"]) == set(CandleOut.model_fields) - {"spread"}
    assert abs(msg["sent_at"] - datetime.now(UTC).timestamp() * 1000) < 5000


async def test_higher_timeframes_only_with_subscribers(
    session: AsyncSession, instrument, listener: PubSub
) -> None:
    candles = known_candles(NOW - timedelta(minutes=4), 5)
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    await _listen(listener, instrument.id, Timeframe.m1, Timeframe.h1, Timeframe.d1)

    published = await market_events.publish_candle_updates(session, instrument.id, candles, now=NOW)
    assert published == [Timeframe.m1, Timeframe.h1, Timeframe.d1]
    by_tf = {m["timeframe"]: m for m in await _messages(listener)}
    assert set(by_tf) == {"1m", "1h", "1d"}
    for tf in (Timeframe.h1, Timeframe.d1):
        latest = await market_service.get_latest_candle(session, instrument.id, tf)
        assert by_tf[tf.value]["candle"] == CandleOut.from_candle(latest).model_dump(
            exclude_none=True
        )


async def test_one_message_per_timeframe_per_call(
    session: AsyncSession, instrument, listener: PubSub
) -> None:
    candles = known_candles(NOW - timedelta(minutes=59), 60)
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    await _listen(listener, instrument.id, Timeframe.m1, Timeframe.m5)
    await market_events.publish_candle_updates(session, instrument.id, candles, now=NOW)
    messages = await _messages(listener)
    assert sorted(m["timeframe"] for m in messages) == ["1m", "5m"]
    assert messages[0]["candle"]["time"] == int(NOW.timestamp())  # the newest 1m candle


async def test_old_candles_are_not_published(
    session: AsyncSession, instrument, listener: PubSub
) -> None:
    candles = known_candles(NOW - timedelta(hours=3), 5)
    await _listen(listener, instrument.id, Timeframe.m1, Timeframe.h1)
    assert await market_events.publish_candle_updates(session, instrument.id, candles) == []
    assert await _messages(listener) == []
    # in a mixed batch only the recent part counts
    mixed = candles + known_candles(NOW - timedelta(minutes=1), 1)
    await market_service.upsert_candles(session, instrument.id, mixed)
    await session.commit()
    published = await market_events.publish_candle_updates(session, instrument.id, mixed, now=NOW)
    assert Timeframe.m1 in published


# --- ingest endpoint -------------------------------------------------------------------------


def _ingest(instrument_id) -> str:
    return f"/api/v1/admin/instruments/{instrument_id}/candles"


async def test_ingest_publishes_after_commit(
    client: AsyncClient, admin_headers, instrument, listener: PubSub
) -> None:
    await _listen(listener, instrument.id, Timeframe.m1)
    body = {"candles": [candle_json(NOW - timedelta(minutes=1)), candle_json(NOW, close=10.7)]}
    res = await client.post(_ingest(instrument.id), json=body, headers=admin_headers)
    assert res.status_code == 200 and res.json() == {"written": 2}
    [msg] = await _messages(listener)
    assert msg["candle"]["time"] == int(NOW.timestamp()) and msg["candle"]["close"] == 10.7


async def test_ingest_succeeds_when_publish_fails(
    client: AsyncClient, admin_headers, instrument, session: AsyncSession, monkeypatch, caplog
) -> None:
    async def broken_publish(*args, **kwargs):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(publisher, "publish", broken_publish)
    body = {"candles": [candle_json(NOW)]}
    with caplog.at_level(logging.ERROR, logger="app.services.market_events"):
        res = await client.post(_ingest(instrument.id), json=body, headers=admin_headers)
    assert res.status_code == 200 and res.json() == {"written": 1}
    assert "Publishing live candle updates" in caplog.text
    rows = await market_service.get_candles(session, instrument.id, Timeframe.m1)
    assert len(rows) == 1  # the write itself was committed


# --- simulate-live ---------------------------------------------------------------------------


async def test_simulate_live_writes_and_publishes(
    session_factory, session: AsyncSession, instrument, listener: PubSub, capsys
) -> None:
    await _listen(listener, instrument.id, Timeframe.m1)
    code = await simulate_live(
        "BTC/USDT", "binance", 0.01, max_ticks=3, seed=3, session_factory=session_factory
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "DEMO LIVE SIMULATION" in out and out.count("[DEMO]") == 3
    assert "Stopped after 3 ticks" in out
    messages = await _messages(listener)
    assert len(messages) == 3
    latest = await market_service.get_latest_candle(session, instrument.id, Timeframe.m1)
    assert messages[-1]["candle"] == CandleOut.from_candle(latest).model_dump(exclude_none=True)
    for m in messages:
        c = m["candle"]
        assert c["high"] >= max(c["open"], c["close"]) >= min(c["open"], c["close"]) >= c["low"]


async def test_simulate_live_unknown_instrument(session_factory, capsys) -> None:
    assert await simulate_live("NOPE/X", "binance", 1, session_factory=session_factory) == 1
    assert "not found" in capsys.readouterr().err
