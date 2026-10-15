"""WebSocketHub without the endpoint: fan-out, Redis subscription lifecycle, back-pressure."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis

from app.realtime import publisher
from app.realtime.hub import CLOSE_TRY_AGAIN_LATER, Client, HubConfig, WebSocketHub
from app.realtime.topics import channel_for
from tests.conftest import TEST_REDIS_URL
from tests.ws_utils import wait_for


class FakeWebSocket:
    def __init__(self, *, stalled: bool = False) -> None:
        self.sent: list[dict] = []
        self._gate = asyncio.Event()
        if not stalled:
            self._gate.set()

    async def send_text(self, text: str) -> None:
        await self._gate.wait()
        self.sent.append(json.loads(text))


async def _client(hub: WebSocketHub, topic: str, *, stalled: bool = False) -> Client:
    client = hub.new_client(FakeWebSocket(stalled=stalled), uuid.uuid4())
    await hub.register(client)
    await hub.subscribe(client, topic)
    return client


async def _numsub(redis: Redis, topic: str) -> int:
    return dict(await redis.pubsub_numsub(channel_for(topic)))[channel_for(topic)]


@pytest.fixture
def topic() -> str:
    return f"candles:{uuid.uuid4()}:1m"


@pytest.fixture
async def second_hub() -> AsyncIterator[WebSocketHub]:
    """Another hub with its own Redis connection, as in a second worker process."""
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    hub = WebSocketHub(redis, HubConfig())
    await hub.start()
    yield hub
    await hub.stop()
    await redis.aclose()


async def test_fan_out_and_subscription_lifecycle(
    hub: WebSocketHub, redis_client: Redis, topic: str
) -> None:
    a, b = await _client(hub, topic), await _client(hub, topic)
    other = await _client(hub, f"candles:{uuid.uuid4()}:1m")
    await wait_for(lambda: _numsub_is(redis_client, topic, 1))

    assert await publisher.publish(topic, {"type": "candle", "n": 1}) == 1  # one hub, one sub
    await wait_for(lambda: len(a.websocket.sent) == 1 and len(b.websocket.sent) == 1)
    assert a.websocket.sent[0]["n"] == 1 and a.websocket.sent[0]["topic"] == topic
    assert other.websocket.sent == []

    await hub.unregister(a)
    assert hub.subscriber_count(topic) == 1
    await wait_for(lambda: _numsub_is(redis_client, topic, 1))
    await hub.unregister(b)
    assert hub.subscriber_count(topic) == 0
    await wait_for(lambda: _numsub_is(redis_client, topic, 0))
    stats = hub.stats()
    assert stats["clients"] == 1 and stats["messages_received"] == 1
    assert stats["messages_delivered"] == 2


async def _numsub_is(redis: Redis, topic: str, expected: int) -> bool:
    return await _numsub(redis, topic) == expected


async def test_two_hubs_each_deliver_once(
    hub: WebSocketHub, second_hub: WebSocketHub, redis_client: Redis, topic: str
) -> None:
    a = await _client(hub, topic)
    b = await _client(second_hub, topic)
    await wait_for(lambda: _numsub_is(redis_client, topic, 2))

    assert await publisher.publish(topic, {"type": "candle", "n": 7}) == 2
    await wait_for(lambda: a.websocket.sent and b.websocket.sent)
    await asyncio.sleep(0.2)  # no duplicates arrive later
    assert [m["n"] for m in a.websocket.sent] == [7]
    assert [m["n"] for m in b.websocket.sent] == [7]


async def test_slow_client_is_dropped_others_unaffected(redis_client: Redis, topic: str) -> None:
    hub = WebSocketHub(redis_client, HubConfig(queue_size=4))
    await hub.start()
    try:
        slow = await _client(hub, topic, stalled=True)
        fast = await _client(hub, topic)
        for n in range(10):
            hub.deliver(topic, json.dumps({"n": n}))
            await asyncio.sleep(0)  # let senders run between messages
        await wait_for(lambda: len(fast.websocket.sent) == 10)
        assert [m["n"] for m in fast.websocket.sent] == list(range(10))
        assert slow.close_code == CLOSE_TRY_AGAIN_LATER
        assert slow.stopped.is_set()
        assert slow.websocket.sent == []
        assert hub.stats()["clients_dropped"] == 1  # counted once, even if it overflows again
    finally:
        await hub.stop()


async def test_close_with_flush_sends_queued_frames_first(hub: WebSocketHub, topic: str) -> None:
    client = await _client(hub, topic)
    client.send(json.dumps({"n": 1}))
    client.close(4401, "token expired", flush=True)
    await wait_for(lambda: client.stopped.is_set())
    assert client.websocket.sent == [{"n": 1}]
    assert client.close_code == 4401


async def test_stop_closes_clients(redis_client: Redis, topic: str) -> None:
    hub = WebSocketHub(redis_client, HubConfig())
    await hub.start()
    client = await _client(hub, topic)
    await hub.stop()
    assert client.close_code == 1001 and client.stopped.is_set()
