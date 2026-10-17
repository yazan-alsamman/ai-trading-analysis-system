"""/ws/market end to end (httpx-ws over ASGI, real Redis + TimescaleDB)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token
from app.models.candle import Timeframe
from app.realtime import publisher
from app.realtime.hub import WebSocketHub
from app.realtime.topics import candles_topic, channel_for, user_topic
from app.schemas.market import CandleOut
from app.services import market_service
from tests.market_utils import known_candles, make_instrument
from tests.ws_utils import recv, recv_until, wait_for, ws_connect

T0 = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)


def sub(instrument_id, timeframe: str = "1m", op: str = "subscribe") -> dict:
    return {
        "op": op,
        "topic": "candles",
        "instrument_id": str(instrument_id),
        "timeframe": timeframe,
    }


async def assert_closed(ws, code: int) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        while True:  # skip anything queued before the close frame
            await ws.receive_text(timeout=3)
    assert exc.value.code == code


@pytest.fixture
async def user(make_user):
    return await make_user("ws-user@example.com")


@pytest.fixture
def token(user) -> str:
    return create_access_token(user)


@pytest.fixture
async def instrument(session: AsyncSession):
    instrument = await make_instrument(session)
    await market_service.upsert_candles(session, instrument.id, known_candles(T0, 120))
    await session.commit()
    return instrument


# --- auth ------------------------------------------------------------------------------------


def _jwt(claims: dict) -> str:
    settings = get_settings()
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def test_rejects_missing_token(client: AsyncClient, hub: WebSocketHub) -> None:
    async with ws_connect(None) as ws:
        await assert_closed(ws, 4401)
    assert hub.stats()["connections_total"] == 0


@pytest.mark.parametrize("kind", ["garbage", "refresh", "expired", "unknown_user"])
async def test_rejects_bad_tokens(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, user, kind: str
) -> None:
    if kind == "garbage":
        token = "not.a.jwt"
    elif kind == "refresh":
        token, _ = await create_refresh_token(session, user)
        await session.commit()
    elif kind == "expired":
        past = datetime.now(UTC) - timedelta(minutes=1)
        token = _jwt({"sub": str(user.id), "role": "trader", "type": "access", "exp": past})
    else:
        future = datetime.now(UTC) + timedelta(minutes=5)
        token = _jwt({"sub": str(uuid.uuid4()), "role": "trader", "type": "access", "exp": future})
    async with ws_connect(token) as ws:
        await assert_closed(ws, 4401)
    assert hub.stats()["connections_total"] == 0


async def test_rejects_inactive_user(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, user, token
) -> None:
    user.is_active = False
    await session.commit()
    async with ws_connect(token) as ws:
        await assert_closed(ws, 4401)


async def test_accepts_valid_token(client: AsyncClient, hub: WebSocketHub, token) -> None:
    async with ws_connect(token) as ws:
        await ws.send_json({"op": "ping"})
        assert await recv(ws) == {"type": "pong"}
        assert hub.stats()["clients"] == 1
    await wait_for(lambda: hub.stats()["clients"] == 0)


async def test_token_expiry_closes_connection(client: AsyncClient, hub: WebSocketHub, user) -> None:
    exp = datetime.now(UTC) + timedelta(seconds=1)
    token = _jwt({"sub": str(user.id), "role": "trader", "type": "access", "exp": exp})
    async with ws_connect(token) as ws:
        msg = await recv_until(ws, lambda m: m["type"] == "error", timeout=4)
        assert msg["code"] == "token_expired"
        await assert_closed(ws, 4401)


# --- subscribe / snapshot / errors ----------------------------------------------------------


async def test_subscribe_ack_and_snapshot(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, token, instrument
) -> None:
    async with ws_connect(token) as ws:
        await ws.send_json(sub(instrument.id, "1h"))
        topic = candles_topic(instrument.id, Timeframe.h1)
        assert await recv(ws) == {"type": "subscribed", "topic": topic}
        snapshot = await recv(ws)
        latest = await market_service.get_latest_candle(session, instrument.id, Timeframe.h1)
        assert snapshot == {
            "type": "snapshot",
            "topic": topic,
            "candle": CandleOut.from_candle(latest).model_dump(),
        }
        assert snapshot["candle"]["time"] == int((T0 + timedelta(hours=1)).timestamp())

        # subscribing again is idempotent and re-sends the snapshot
        await ws.send_json(sub(instrument.id, "1h"))
        assert (await recv(ws))["type"] == "subscribed"
        assert (await recv(ws))["type"] == "snapshot"
        assert hub.subscriber_count(topic) == 1

        await ws.send_json(sub(instrument.id, "1h", op="unsubscribe"))
        assert await recv(ws) == {"type": "unsubscribed", "topic": topic}
        assert hub.subscriber_count(topic) == 0


async def test_snapshot_is_null_without_candles(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, token
) -> None:
    empty = await make_instrument(session, "SOL/USDT")
    async with ws_connect(token) as ws:
        await ws.send_json(sub(empty.id, "5m"))
        await recv(ws)
        assert (await recv(ws))["candle"] is None


async def test_unknown_and_inactive_instrument(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, token
) -> None:
    inactive = await make_instrument(session, "XRP/USDT", is_active=False)
    async with ws_connect(token) as ws:
        await ws.send_json(sub(uuid.uuid4()))
        assert (await recv(ws))["code"] == "unknown_instrument"
        await ws.send_json(sub(inactive.id))
        assert (await recv(ws))["code"] == "inactive_instrument"
        assert hub.stats()["topics_by_kind"].get("candles", 0) == 0


@pytest.mark.parametrize(
    "frame",
    [
        "not json",
        '{"op": "dance"}',
        '{"topic": "candles"}',
        '{"op": "subscribe", "topic": "candles", "instrument_id": "x", "timeframe": "1m"}',
        f'{{"op": "subscribe", "topic": "candles", "instrument_id": "{uuid.uuid4()}", '
        '"timeframe": "2h"}',
        '{"op": "subscribe", "topic": "candles", "timeframe": "1m"}',
        f'{{"op": "subscribe", "topic": "orders", "instrument_id": "{uuid.uuid4()}"}}',
        '{"op": "ping", "extra": 1}',
        f'{{"op": "ping", "pad": "{"x" * 5000}"}}',  # larger than 4 KB
    ],
)
async def test_bad_requests_keep_socket_open(
    client: AsyncClient, hub: WebSocketHub, token, frame: str
) -> None:
    async with ws_connect(token) as ws:
        await ws.send_text(frame)
        msg = await recv(ws)
        assert msg["type"] == "error" and msg["code"] == "bad_request", msg
        assert msg["message"]
        await ws.send_json({"op": "ping"})
        assert await recv(ws) == {"type": "pong"}


async def test_binary_frame_is_bad_request(client: AsyncClient, hub: WebSocketHub, token) -> None:
    async with ws_connect(token) as ws:
        await ws.send_bytes(b'{"op": "ping"}')
        assert (await recv(ws))["code"] == "bad_request"


async def test_subscription_limit(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, token
) -> None:
    instruments = [await make_instrument(session, f"C{i}/USDT") for i in range(9)]
    topics = [(i.id, tf.value) for i in instruments for tf in Timeframe][:51]
    async with ws_connect(token) as ws:
        for instrument_id, tf in topics[:50]:
            await ws.send_json(sub(instrument_id, tf))
            assert (await recv(ws))["type"] == "subscribed"
            assert (await recv(ws))["type"] == "snapshot"
        await ws.send_json(sub(*topics[50]))
        assert (await recv(ws))["code"] == "too_many_subscriptions"
        # re-subscribing to an existing topic does not count
        await ws.send_json(sub(*topics[0]))
        assert (await recv(ws))["type"] == "subscribed"
        assert hub.stats()["topics_by_kind"]["candles"] == 50


async def test_user_topic(
    client: AsyncClient, hub: WebSocketHub, redis_client: Redis, user, token
) -> None:
    own = user_topic(user.id)

    async def redis_has_subscriber() -> bool:
        return dict(await redis_client.pubsub_numsub(channel_for(own)))[channel_for(own)] == 1

    async with ws_connect(token) as ws:
        # automatic on connect (no ack to wait for): wait until Redis has applied it
        await wait_for(redis_has_subscriber)
        await publisher.publish(own, {"type": "notification", "text": "hello"})
        msg = await recv_until(ws, lambda m: m["type"] == "notification")
        assert msg["topic"] == own and msg["text"] == "hello"

        other = {"op": "subscribe", "topic": "user", "user_id": str(uuid.uuid4())}
        await ws.send_json(other)
        assert (await recv(ws))["code"] == "forbidden"
        await ws.send_json({"op": "subscribe", "topic": "user", "user_id": str(user.id)})
        assert await recv(ws) == {"type": "subscribed", "topic": own}
    await wait_for(lambda: hub.subscriber_count(own) == 0)


# --- routing through Redis ------------------------------------------------------------------


async def test_published_message_reaches_only_its_topic(
    client: AsyncClient, hub: WebSocketHub, make_user, user, token, instrument
) -> None:
    other_user = await make_user("ws-other@example.com")
    async with (
        ws_connect(token) as ws_1m,
        ws_connect(create_access_token(other_user)) as ws_5m,
    ):
        # one at a time: in tests both handlers share the transaction's single DB connection
        for ws, tf in ((ws_1m, "1m"), (ws_5m, "5m")):
            await ws.send_json(sub(instrument.id, tf))
            await recv(ws)
            await recv(ws)
        topic = candles_topic(instrument.id, Timeframe.m1)
        candle = {"time": 1, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
        await publisher.publish(topic, {"type": "candle", "candle": candle})

        msg = await recv(ws_1m)
        assert msg["type"] == "candle" and msg["topic"] == topic and msg["candle"] == candle
        assert isinstance(msg["sent_at"], int)
        await ws_5m.send_json({"op": "ping"})
        assert await recv(ws_5m) == {"type": "pong"}  # nothing else was queued before it


async def test_two_clients_one_redis_subscription(
    client: AsyncClient,
    hub: WebSocketHub,
    redis_client: Redis,
    make_user,
    token,
    instrument,
) -> None:
    channel = channel_for(candles_topic(instrument.id, Timeframe.m1))

    async def numsub_is(expected: int) -> bool:
        # SUBSCRIBE/UNSUBSCRIBE replies are read by the hub's reader task, so Redis may apply
        # them a moment after the hub's call returns: poll instead of asserting once.
        return dict(await redis_client.pubsub_numsub(channel))[channel] == expected

    other = create_access_token(await make_user("ws-second@example.com"))
    async with ws_connect(token) as ws_a:
        async with ws_connect(other) as ws_b:
            for ws in (ws_a, ws_b):
                await ws.send_json(sub(instrument.id))
                await recv(ws)
                await recv(ws)
            assert hub.subscriber_count(candles_topic(instrument.id, Timeframe.m1)) == 2
            await wait_for(lambda: numsub_is(1))
        await wait_for(lambda: hub.subscriber_count(candles_topic(instrument.id, "1m")) == 1)
        await wait_for(lambda: numsub_is(1))
    await wait_for(lambda: hub.stats()["clients"] == 0)
    await wait_for(lambda: numsub_is(0))


async def test_dropped_client_is_closed_and_others_keep_receiving(
    client: AsyncClient, hub: WebSocketHub, make_user, user, token, instrument
) -> None:
    topic = candles_topic(instrument.id, Timeframe.m1)
    other = create_access_token(await make_user("ws-fast@example.com"))
    async with ws_connect(token) as slow, ws_connect(other) as fast:
        for ws in (slow, fast):
            await ws.send_json(sub(instrument.id))
            await recv(ws)
            await recv(ws)
        # stall the first client's socket and fill its queue
        stuck = next(c for c in hub._clients if c.user_id == user.id)
        never = asyncio.Event()

        async def stalled_send(_text: str) -> None:
            await never.wait()

        stuck.websocket.send_text = stalled_send
        stuck.send("{}")
        await wait_for(lambda: stuck.queue.empty())  # the sender took it and is now stuck
        while stuck.send("{}"):
            pass
        await publisher.publish(topic, {"type": "candle", "candle": {"n": 1}})
        await assert_closed(slow, 1013)
        msg = await recv_until(fast, lambda m: m["type"] == "candle")
        assert msg["candle"] == {"n": 1}
        assert hub.stats()["clients_dropped"] == 1
    await wait_for(lambda: hub.stats()["clients"] == 0)


async def test_stats_endpoint(
    client: AsyncClient, hub: WebSocketHub, admin_headers, trader_headers
) -> None:
    res = await client.get("/api/v1/admin/realtime/stats", headers=admin_headers)
    assert res.status_code == 200
    assert {"clients", "topics", "messages_delivered", "clients_dropped"} <= res.json().keys()
    res = await client.get("/api/v1/admin/realtime/stats", headers=trader_headers)
    assert res.status_code == 403
    assert (await client.get("/api/v1/admin/realtime/stats")).status_code == 401
