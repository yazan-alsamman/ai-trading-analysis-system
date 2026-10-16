"""/ws/market with API keys (?api_key=) and the WebSocket connection limits (close 4429)."""

import json
from contextlib import AsyncExitStack

import pytest
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.realtime.hub import WebSocketHub
from app.realtime.topics import user_topic
from tests.api_key_utils import create_key
from tests.utils import bearer
from tests.ws_utils import recv_until, wait_for, ws_connect


async def assert_closed(ws, code: int) -> str:
    with pytest.raises(WebSocketDisconnect) as exc:
        while True:
            await ws.receive_text(timeout=3)
    assert exc.value.code == code
    return exc.value.reason


async def assert_open(ws) -> None:
    await ws.send_text(json.dumps({"op": "ping"}))
    await recv_until(ws, lambda m: m["type"] == "pong")


@pytest.fixture
async def user(make_user):
    return await make_user("trader@example.com")


@pytest.fixture
def headers(user) -> dict[str, str]:
    return bearer(create_access_token(user))


async def test_api_key_with_stream_connects_and_gets_its_owners_topic(
    client: AsyncClient, hub: WebSocketHub, user, headers
) -> None:
    created = await create_key(client, headers, ["stream"])
    async with ws_connect(None, query=f"?api_key={created['key']}") as ws:
        await assert_open(ws)
        assert hub.stats()["clients"] == 1
        assert user_topic(user.id) in hub.stats()["busiest_topics"]
        await ws.send_text(
            json.dumps({"op": "subscribe", "topic": "user", "user_id": str(user.id)})
        )
        msg = await recv_until(ws, lambda m: m["type"] in ("subscribed", "error"))
        assert msg == {"type": "subscribed", "topic": user_topic(user.id)}


@pytest.mark.parametrize("kind", ["no_stream", "garbage", "revoked", "inactive_owner"])
async def test_api_key_refused_with_4401(
    client: AsyncClient, hub: WebSocketHub, session: AsyncSession, user, headers, kind: str
) -> None:
    created = await create_key(
        client, headers, ["market:read"] if kind == "no_stream" else ["stream"]
    )
    key = created["key"]
    if kind == "garbage":
        key = "tk_nothere_secret"
    elif kind == "revoked":
        await client.delete(f"/api/v1/me/api-keys/{created['id']}", headers=headers)
    elif kind == "inactive_owner":
        user.is_active = False
        await session.commit()
    async with ws_connect(None, query=f"?api_key={key}") as ws:
        reason = await assert_closed(ws, 4401)
    if kind == "no_stream":
        assert reason == "API key lacks the 'stream' scope"
    assert hub.stats()["connections_total"] == 0


async def test_too_many_concurrent_connections_4429(
    client: AsyncClient, hub: WebSocketHub, rate_limits, headers
) -> None:
    created = await create_key(client, headers, ["stream"])
    token = headers["Authorization"].removeprefix("Bearer ")
    async with AsyncExitStack() as stack:  # contexts must close in reverse order (anyio)
        sockets = [await stack.enter_async_context(ws_connect(token)) for _ in range(4)]
        for ws in sockets:
            await assert_open(ws)
        async with ws_connect(token) as fifth:
            await assert_open(fifth)
            async with ws_connect(token) as sixth:
                assert await assert_closed(sixth, 4429) == "too many connections"
            # the API key is its own identity with its own 5 connections
            async with ws_connect(None, query=f"?api_key={created['key']}") as by_key:
                await assert_open(by_key)
            await wait_for(lambda: hub.stats()["clients"] == 5)
        # the fifth connection ended: its slot is free again
        async with ws_connect(token) as again:
            await assert_open(again)
            async with ws_connect(token) as over:
                await assert_closed(over, 4429)


async def test_too_many_new_connections_per_ip_4429(
    client: AsyncClient, hub: WebSocketHub, rate_limits, headers
) -> None:
    token = headers["Authorization"].removeprefix("Bearer ")
    assert rate_limits.ws_new_connections_ip_per_minute == 20
    for _ in range(20):
        async with ws_connect(token) as ws:
            await assert_open(ws)
    async with ws_connect(token) as ws:
        assert await assert_closed(ws, 4429) == "too many new connections"
    async with ws_connect("not-even-a-token") as ws:  # checked before authentication
        await assert_closed(ws, 4429)
