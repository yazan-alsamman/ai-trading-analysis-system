"""Heartbeat and idle timeout, with intervals shrunk so the tests run fast."""

import asyncio

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.realtime.hub import HubConfig, WebSocketHub
from tests.ws_utils import recv, ws_connect

HEARTBEAT = 0.2
IDLE = 0.7


@pytest.fixture
def hub_config() -> HubConfig:
    return HubConfig(heartbeat_seconds=HEARTBEAT, idle_timeout_seconds=IDLE)


@pytest.fixture
async def token(make_user) -> str:
    return create_access_token(await make_user("ws-timeouts@example.com"))


async def test_heartbeats_then_idle_close(client: AsyncClient, hub: WebSocketHub, token) -> None:
    from httpx_ws import WebSocketDisconnect

    loop = asyncio.get_running_loop()
    started = loop.time()  # before the handshake: the server's idle clock starts during it
    async with ws_connect(token) as ws:
        assert await recv(ws, timeout=1) == {"type": "heartbeat"}
        heartbeats = 1
        with pytest.raises(WebSocketDisconnect) as exc:
            while True:
                assert await recv(ws, timeout=2) == {"type": "heartbeat"}
                heartbeats += 1
        elapsed = loop.time() - started
    assert exc.value.code == 1001
    assert IDLE <= elapsed < IDLE + 1.0
    assert heartbeats >= 2


async def test_client_activity_prevents_idle_close(
    client: AsyncClient, hub: WebSocketHub, token
) -> None:
    loop = asyncio.get_running_loop()
    async with ws_connect(token) as ws:
        deadline = loop.time() + IDLE * 3
        while loop.time() < deadline:
            await ws.send_json({"op": "ping"})
            msg = await recv(ws, timeout=1)
            while msg["type"] == "heartbeat":
                msg = await recv(ws, timeout=1)
            assert msg == {"type": "pong"}
            await asyncio.sleep(IDLE / 3)
        assert hub.stats()["clients"] == 1  # still connected after 3x the idle timeout
