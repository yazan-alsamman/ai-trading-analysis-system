"""One JSON-over-WebSocket connection to the cTrader Open API (protocol.py has the sources).

- ``request`` sends a message with a fresh ``clientMsgId`` and waits for the answer carrying
  the same id ("Request message id, assigned by the client that will be returned in the
  response", ProtoMessage in OpenApiCommonMessages.proto). An error answer (``ERROR_RES`` 50 or
  ``PROTO_OA_ERROR_RES`` 2142) raises ``CTraderError``; ``TokenError`` when its code means the
  access token is no good.
- Messages without a pending request (spot events, token-invalidated and disconnect events,
  errors not tied to a request) go to ``on_event``; heartbeats only refresh ``last_received``.
- When the socket closes, every pending request fails with ``Disconnected`` and ``closed`` is
  set. Payloads are never logged (they carry tokens).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

import websockets

from app.feeds.ctrader import protocol as p

logger = logging.getLogger(__name__)
# the websockets library logs every frame at DEBUG, and the frames carry the client secret and
# the access token: its logger for this connection never goes below WARNING
_wire = logging.getLogger("app.feeds.ctrader.wire")
_wire.setLevel(logging.WARNING)

MAX_MESSAGE_BYTES = 16 * 1024 * 1024  # a symbols list is the largest answer


class CTraderError(Exception):
    def __init__(self, code: str, description: str = "") -> None:
        super().__init__(f"{code}: {description}" if description else code)
        self.code = code
        self.description = description


class TokenError(CTraderError):
    """The access token is expired or invalid: refresh it and authorise again."""


class Disconnected(Exception):
    """The connection closed (or went silent) before an answer came."""


def error_from(payload: dict[str, Any]) -> CTraderError:
    code = str(payload.get("errorCode") or "UNKNOWN_ERROR")
    description = str(payload.get("description") or "")
    return (TokenError if code in p.TOKEN_ERRORS else CTraderError)(code, description)


class Connection:
    def __init__(
        self, url: str, on_event: Callable[[int, dict[str, Any]], None] | None = None
    ) -> None:
        self.url = url
        self.on_event = on_event or (lambda _type, _payload: None)
        self.closed = asyncio.Event()
        self.last_received = time.monotonic()
        self._ws: Any = None
        self._pending: dict[str, asyncio.Future] = {}
        self._reader: asyncio.Task | None = None

    async def __aenter__(self) -> Connection:
        await self.open()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def open(self, timeout: float = 15.0) -> None:
        self._ws = await websockets.connect(
            self.url,
            open_timeout=timeout,
            max_size=MAX_MESSAGE_BYTES,
            ping_interval=None,  # the protocol's own heartbeats (51) keep it alive
            close_timeout=5,
            logger=_wire,
        )
        self.last_received = time.monotonic()
        self._reader = asyncio.create_task(self._read(), name="ctrader-reader")

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001 - already gone
                pass
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)
        self._fail_pending(Disconnected("connection closed"))
        self.closed.set()

    async def send(self, payload_type: int, payload: dict[str, Any]) -> None:
        if self.closed.is_set() or self._ws is None:
            raise Disconnected("connection closed")
        await self._ws.send(json.dumps(p.envelope(payload_type, payload, uuid.uuid4().hex)))

    async def request(
        self, message: tuple[int, dict[str, Any]], timeout: float = 20.0
    ) -> tuple[int, dict[str, Any]]:
        """Send and wait for the answer: (payload type, payload)."""
        if self.closed.is_set() or self._ws is None:
            raise Disconnected("connection closed")
        payload_type, payload = message
        msg_id = uuid.uuid4().hex
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        try:
            await self._ws.send(json.dumps(p.envelope(payload_type, payload, msg_id)))
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            raise Disconnected(
                f"no answer to payload type {payload_type} in {timeout:g}s"
            ) from None
        finally:
            self._pending.pop(msg_id, None)

    async def _read(self) -> None:
        try:
            async for raw in self._ws:
                self.last_received = time.monotonic()
                try:
                    message = json.loads(raw)
                    payload_type = int(message["payloadType"])
                except (ValueError, KeyError, TypeError):
                    logger.warning("cTrader: ignoring a malformed message")
                    continue
                payload = message.get("payload") or {}
                future = self._pending.get(message.get("clientMsgId") or "")
                if future is not None and not future.done():
                    if payload_type in (p.ERROR_RES, p.OA_ERROR_RES):
                        future.set_exception(error_from(payload))
                    else:
                        future.set_result((payload_type, payload))
                elif payload_type != p.HEARTBEAT_EVENT:
                    try:
                        self.on_event(payload_type, payload)
                    except Exception:  # noqa: BLE001 - one bad event must not stop the reader
                        logger.exception("cTrader: handling event %s failed", payload_type)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the socket closed
            logger.info("cTrader connection ended: %s", type(exc).__name__)
        finally:
            self._fail_pending(Disconnected("connection closed"))
            self.closed.set()

    def _fail_pending(self, exc: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()
