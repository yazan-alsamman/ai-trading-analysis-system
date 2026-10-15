"""WebSocket test helpers (httpx-ws over ASGI, in the test's own event loop).

ASGIWebSocketTransport runs the app inside an anyio task group, which must be entered and exited
by the same task, so it is opened inside each test (``async with ws_connect(...)``) rather than
in a fixture. The ``client`` fixture must be active: it installs the DB overrides.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from httpx import AsyncClient
from httpx_ws import AsyncWebSocketSession, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from app.main import app


@asynccontextmanager
async def ws_connect(token: str | None, *, query: str = "") -> AsyncIterator[AsyncWebSocketSession]:
    url = "/ws/market" + (f"?token={token}" if token is not None else "") + query
    async with (
        AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test") as http,
        aconnect_ws(url, http) as ws,
    ):
        yield ws


async def recv(ws: AsyncWebSocketSession, timeout: float = 3.0) -> dict:
    return json.loads(await ws.receive_text(timeout=timeout))


async def recv_until(
    ws: AsyncWebSocketSession, predicate: Callable[[dict], bool], timeout: float = 3.0
) -> dict:
    """Next message matching ``predicate`` (heartbeats and others are skipped)."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        msg = await recv(ws, timeout=max(0.05, deadline - loop.time()))
        if predicate(msg):
            return msg


async def wait_for(condition: Callable[[], object], timeout: float = 3.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        result = condition()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        if loop.time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.02)
