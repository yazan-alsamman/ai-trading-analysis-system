"""WebSocket re-authorisation (B12, P0-05): a revoked API key, a deactivated user or a role or
scope change applies to open connections, right away through the Redis auth event (on every API
process) and, as a safety net, on the next heartbeat."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import ws as ws_api
from app.core import rate_limit
from app.core.security import create_access_token
from app.models.chat import Conversation
from app.models.user import UserRole
from app.realtime import auth_events
from app.realtime.hub import AUTH_CHANNEL, HubConfig, WebSocketHub
from app.realtime.topics import chat_topic, private_signals_topic, signals_topic
from tests.api_key_utils import KEYS, create_key
from tests.conftest import TEST_REDIS_URL
from tests.market_utils import make_instrument
from tests.test_ws_hub import FakeWebSocket
from tests.utils import bearer
from tests.ws_utils import recv_until, wait_for, ws_connect

SLOW = HubConfig(heartbeat_seconds=60, idle_timeout_seconds=120)  # only the event can be fast
FAST = HubConfig(heartbeat_seconds=0.3, idle_timeout_seconds=30)


@pytest.fixture
def session_factory(
    committed_session_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    """Real sessions on their own pool (``committed_session_factory``), for the test, its API
    requests and the server's WebSocket code alike. One auth event wakes the re-checks of
    several sockets at once, while the request that sent it still uses its session. On the
    shared savepoint-wrapped test connection those sessions overlapped and broke each other."""
    return committed_session_factory


@pytest.fixture
async def alice(make_user):
    user = await make_user("alice@example.com")
    return user, bearer(create_access_token(user))


@pytest.fixture
async def bob(make_user):
    user = await make_user("bob@example.com")
    return user, bearer(create_access_token(user))


@pytest.fixture
async def root(make_user):
    user = await make_user("root@example.com", role=UserRole.admin)
    return user, bearer(create_access_token(user))


async def revoked_message(ws, timeout: float = 3.0) -> tuple[dict, int, str]:
    """The ``auth_revoked`` error, then the close: (message, close code, close reason)."""
    loop = asyncio.get_running_loop()
    deadline, message = loop.time() + timeout, None
    with pytest.raises(WebSocketDisconnect) as closed:
        while True:
            msg = json.loads(await ws.receive_text(timeout=max(0.05, deadline - loop.time())))
            if msg["type"] == "error":
                message = msg
    return message, closed.value.code, closed.value.reason


async def assert_open(ws) -> None:
    await ws.send_text(json.dumps({"op": "ping"}))
    await recv_until(ws, lambda m: m["type"] == "pong")


def api_key_query(created: dict) -> str:
    return f"?api_key={created['key']}"


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_revoked_key_closes_at_once_through_the_event(
    client: AsyncClient, hub: WebSocketHub, redis_client: Redis, rate_limits, alice, bob
) -> None:
    (_, ah), (b, _) = alice, bob
    created = await create_key(client, ah, ["stream"])
    slot = rate_limit.key("ws", f"key:{created['id']}")
    async with (
        ws_connect(None, query=api_key_query(created)) as ws,
        ws_connect(create_access_token(b)) as other,
    ):
        await assert_open(ws)
        assert await redis_client.zcard(slot) == 1
        started = asyncio.get_running_loop().time()
        res = await client.delete(f"{KEYS}/{created['id']}", headers=ah)
        assert res.status_code == 204
        message, code, reason = await revoked_message(ws)
        elapsed = asyncio.get_running_loop().time() - started
        assert message == {"type": "error", "code": "auth_revoked", "message": "API key revoked"}
        assert (code, reason) == (4401, "API key revoked")
        assert elapsed < 2  # the heartbeat is 60 s: the event closed it
        await assert_open(other)  # another user's socket is unaffected
    await wait_for(lambda: hub.stats()["clients"] == 0)
    assert await redis_client.zcard(slot) == 0  # the connection slot is released


@pytest.mark.parametrize("hub_config", [FAST])
async def test_revoked_key_closes_on_the_heartbeat_without_the_event(
    client: AsyncClient, hub: WebSocketHub, monkeypatch, alice
) -> None:
    _, ah = alice
    created = await create_key(client, ah, ["stream"])
    published = []

    async def lost(**kw) -> None:  # Redis lost the event: only the heartbeat re-check is left
        published.append(kw)

    monkeypatch.setattr(auth_events, "publish", lost)
    async with ws_connect(None, query=api_key_query(created)) as ws:
        await assert_open(ws)
        started = asyncio.get_running_loop().time()
        assert (await client.delete(f"{KEYS}/{created['id']}", headers=ah)).status_code == 204
        message, code, _ = await revoked_message(ws)
        elapsed = asyncio.get_running_loop().time() - started
    assert published == [{"key_id": uuid.UUID(created["id"])}]
    assert (message["code"], code) == ("auth_revoked", 4401)
    assert elapsed <= FAST.heartbeat_seconds + 0.5  # within one heartbeat


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_deactivated_user_loses_every_socket(
    client: AsyncClient, hub: WebSocketHub, alice, bob, root
) -> None:
    (a, ah), (b, _), (_, rh) = alice, bob, root
    created = await create_key(client, ah, ["stream"])
    async with (
        ws_connect(create_access_token(a)) as jwt_socket,
        ws_connect(None, query=api_key_query(created)) as key_socket,
        ws_connect(create_access_token(b)) as other,
    ):
        for ws in (jwt_socket, key_socket, other):
            await assert_open(ws)
        res = await client.patch(
            f"/api/v1/admin/users/{a.id}/status", json={"is_active": False}, headers=rh
        )
        assert res.status_code == 200, res.text
        for ws in (jwt_socket, key_socket):
            message, code, reason = await revoked_message(ws)
            assert (message["code"], code, reason) == ("auth_revoked", 4401, "user deactivated")
        await assert_open(other)
        assert hub.stats()["clients"] == 1


@pytest.mark.parametrize("hub_config", [FAST])
async def test_deleted_user_closes_on_the_heartbeat(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, alice
) -> None:
    a, _ = alice
    async with ws_connect(create_access_token(a)) as ws:
        await assert_open(ws)
        await session.delete(a)  # no event at all (e.g. a purge)
        await session.commit()
        message, code, _ = await revoked_message(ws)
    assert (message["code"], code) == ("auth_revoked", 4401)


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_demoted_admin_loses_the_topics_of_the_role(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, make_user, alice, bob, root
) -> None:
    (a, _), (b, _), (_, rh) = alice, bob, root
    moderator = await make_user("mod@example.com", role=UserRole.admin)
    conv = Conversation(expert_id=a.id, user_id=b.id)  # not the moderator's conversation
    btc = await make_instrument(session, "BTC/USDT")
    session.add(conv)
    await session.commit()
    async with ws_connect(create_access_token(moderator)) as ws:
        for sub in (
            {"topic": "chat", "conversation_id": str(conv.id)},
            {"topic": "signals", "instrument_id": str(btc.id)},
        ):
            await ws.send_text(json.dumps({"op": "subscribe", **sub}))
            assert (await recv_until(ws, lambda m: m["type"] != "heartbeat"))["type"] == (
                "subscribed"
            )
        [client_] = hub._clients
        admins = private_signals_topic(btc.id, None)
        assert {chat_topic(conv.id), admins} <= client_.topics

        res = await client.patch(
            f"/api/v1/admin/users/{moderator.id}/role", json={"role": "trader"}, headers=rh
        )
        assert res.status_code == 200, res.text
        msg = await recv_until(ws, lambda m: m["type"] == "unsubscribed")
        assert msg == {"type": "unsubscribed", "topic": chat_topic(conv.id), "reason": "forbidden"}
        await assert_open(ws)  # the connection itself stays
        # private signals now come through the user's own topic, not the admins' one
        assert client_.topics == {
            f"user:{moderator.id}",
            signals_topic(btc.id),
            private_signals_topic(btc.id, moderator.id),
        }


@pytest.mark.parametrize("hub_config", [SLOW])
async def test_key_scope_change_applies_to_open_sockets(
    client: AsyncClient, hub: WebSocketHub, alice
) -> None:
    _, ah = alice
    created = await create_key(client, ah, ["stream", "news:read"])
    url = f"{KEYS}/{created['id']}"
    async with ws_connect(None, query=api_key_query(created)) as ws:
        await ws.send_text(json.dumps({"op": "subscribe", "topic": "news"}))
        await recv_until(ws, lambda m: m["type"] == "subscribed")
        assert (await client.patch(url, json={"scopes": ["stream"]}, headers=ah)).is_success
        msg = await recv_until(ws, lambda m: m["type"] == "unsubscribed")
        assert msg == {"type": "unsubscribed", "topic": "news", "reason": "forbidden"}
        await assert_open(ws)
        assert (await client.patch(url, json={"scopes": ["market:read"]}, headers=ah)).is_success
        message, code, reason = await revoked_message(ws)
    assert (message["code"], code, reason) == (
        "auth_revoked",
        4401,
        "API key lacks the 'stream' scope",
    )


# --- failures of the re-check itself ------------------------------------------------------------


class _BrokenSession:
    async def __aenter__(self):
        raise ConnectionError("database unreachable")

    async def __aexit__(self, *_exc) -> None:
        return None


@pytest.mark.parametrize("hub_config", [FAST])
async def test_a_failing_watchdog_closes_the_socket(
    client: AsyncClient, hub: WebSocketHub, alice, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without its watchdog a socket would never be re-checked, expire or time out: it is
    closed (1011) instead of staying open unchecked."""
    a, _ = alice

    async def explode(*_args) -> bool:
        raise RuntimeError("bug in a re-check")

    async with ws_connect(create_access_token(a)) as ws:
        await assert_open(ws)
        monkeypatch.setattr(ws_api, "_recheck", explode)
        with pytest.raises(WebSocketDisconnect) as closed:
            while True:
                await ws.receive_text(timeout=3)
    assert (closed.value.code, closed.value.reason) == (1011, "internal error")


async def test_a_database_error_in_the_chat_recheck_keeps_the_socket(
    hub: WebSocketHub, session_factory: async_sessionmaker[AsyncSession], alice
) -> None:
    """A demoted admin's chats are read again: if that read fails, the topics and the role stay
    as they were (the next check applies the change), and nothing is raised."""
    a, _ = alice
    client_ = hub.new_client(FakeWebSocket(), a.id)
    client_.is_admin = True
    await hub.register(client_)
    topic = chat_topic(uuid.uuid4())  # a conversation the user does not take part in
    await hub.subscribe(client_, topic)
    auth = ws_api._Auth(user=a, expires_at=float("inf"), identity=f"user:{a.id}", credential="x")

    await ws_api._trim(client_, hub, lambda: _BrokenSession(), auth, is_admin=False)
    assert topic in client_.topics and client_.is_admin  # unchanged: retried next time

    await ws_api._trim(client_, hub, session_factory, auth, is_admin=False)
    assert topic not in client_.topics and not client_.is_admin
    await wait_for(lambda: client_.websocket.sent)
    assert client_.websocket.sent[-1] == {
        "type": "unsubscribed",
        "topic": topic,
        "reason": "forbidden",
    }


# --- across API processes ----------------------------------------------------------------------


@pytest.fixture
async def worker_hubs() -> AsyncIterator[list[WebSocketHub]]:
    """Two hubs with their own Redis connections, as in the two uvicorn workers."""
    clients = [Redis.from_url(TEST_REDIS_URL, decode_responses=True) for _ in range(2)]
    hubs = [WebSocketHub(r, HubConfig()) for r in clients]
    for hub in hubs:
        await hub.start()
    yield hubs
    for hub in hubs:
        await hub.stop()
    for r in clients:
        await r.aclose()


async def test_auth_event_reaches_the_connections_of_every_worker(
    worker_hubs: list[WebSocketHub], redis_client: Redis
) -> None:
    user, key, stranger = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    first, second = worker_hubs
    on_first = first.new_client(FakeWebSocket(), user)
    on_second = second.new_client(FakeWebSocket(), user, key_id=key)
    other = second.new_client(FakeWebSocket(), stranger)
    for hub, c in ((first, on_first), (second, on_second), (second, other)):
        await hub.register(c)
    # both hubs listen on the auth channel (publish returns the number of receivers)
    await wait_for(lambda: _receivers(redis_client, 2))

    await auth_events.publish(user_id=user, redis=redis_client)
    await wait_for(lambda: on_first.recheck.is_set() and on_second.recheck.is_set())
    assert not other.recheck.is_set()

    on_second.recheck.clear()
    await auth_events.publish(key_id=key, redis=redis_client)
    await wait_for(lambda: on_second.recheck.is_set())
    assert not other.recheck.is_set()


async def _receivers(redis: Redis, expected: int) -> bool:
    return dict(await redis.pubsub_numsub(AUTH_CHANNEL))[AUTH_CHANNEL] >= expected
