"""/ws/market: live market data over WebSocket (protocol: docs/websocket.md).

Mounted at the app root (not /api/v1) because Nginx proxies /ws/ with the Upgrade headers.
"""

import asyncio
import logging
import math
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_session_factory
from app.core.security import decode_token
from app.models.instrument import Instrument
from app.models.user import User
from app.realtime import protocol
from app.realtime.hub import (
    CLOSE_GOING_AWAY,
    CLOSE_UNAUTHORIZED,
    Client,
    WebSocketHub,
)
from app.realtime.protocol import SubscribeMessage, UnsubscribeMessage
from app.realtime.topics import candles_topic, signals_topic, user_topic
from app.schemas.market import CandleOut
from app.services import market_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])

SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]


async def _authenticate(
    token: str | None, session_factory: async_sessionmaker[AsyncSession]
) -> tuple[User, float] | None:
    """(active user, token exp as unix seconds) or None."""
    if not token:
        return None
    try:
        payload = decode_token(token, "access")
    except HTTPException:
        return None
    async with session_factory() as session:
        user = await session.get(User, payload["sub"])
    if user is None or not user.is_active:
        return None
    return user, float(payload["exp"])


@router.websocket("/ws/market")
async def market_ws(
    websocket: WebSocket, session_factory: SessionFactory, token: str | None = None
) -> None:
    # Authenticate before doing any work for the connection. A close sent before accept()
    # becomes an HTTP 403 and browsers only see code 1006, so accept and close with 4401.
    auth = await _authenticate(token, session_factory)
    if auth is None:
        await websocket.accept()
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="invalid or expired token")
        return
    user, token_exp = auth
    hub: WebSocketHub = websocket.app.state.hub

    await websocket.accept()
    client = hub.new_client(websocket, user.id)
    await hub.register(client)
    receiver = watchdog = stop_wait = None
    try:
        await hub.subscribe(client, user_topic(user.id))
        receiver = asyncio.create_task(_receive_loop(client, hub, session_factory))
        watchdog = asyncio.create_task(_watchdog(client, hub, token_exp))
        stop_wait = asyncio.create_task(client.stopped.wait())
        await asyncio.wait({receiver, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
    except Exception:  # noqa: BLE001
        logger.exception("WebSocket connection %s failed", client.id)
        client.close(1011, "internal error")
    finally:
        for task in (receiver, watchdog, stop_wait):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(t for t in (receiver, watchdog, stop_wait) if t is not None), return_exceptions=True
        )
        await hub.unregister(client)
        if not client.peer_closed:
            try:
                await websocket.close(code=client.close_code or 1000, reason=client.close_reason)
            except Exception:  # noqa: BLE001 - already closed
                pass


async def _watchdog(client: Client, hub: WebSocketHub, token_exp: float) -> None:
    """Heartbeats, idle timeout and access-token expiry."""
    loop = asyncio.get_running_loop()
    heartbeat, idle = hub.config.heartbeat_seconds, hub.config.idle_timeout_seconds
    next_heartbeat = loop.time() + heartbeat
    while True:
        now = loop.time()
        seconds_to_exp = token_exp - time.time()
        if seconds_to_exp <= 0:
            client.send(protocol.error(protocol.TOKEN_EXPIRED, "access token expired"))
            client.close(CLOSE_UNAUTHORIZED, "token expired", flush=True)
            return
        if now - client.last_seen >= idle:
            client.close(CLOSE_GOING_AWAY, "idle timeout")
            return
        if now >= next_heartbeat:
            if not client.send(protocol.heartbeat()):
                hub.drop(client)
                return
            next_heartbeat = now + heartbeat
        wait = min(next_heartbeat - now, client.last_seen + idle - now, seconds_to_exp)
        await asyncio.sleep(max(wait, 0.01) if math.isfinite(wait) else heartbeat)


async def _receive_loop(
    client: Client, hub: WebSocketHub, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    loop = asyncio.get_running_loop()
    while True:
        message = await client.websocket.receive()
        if message["type"] == "websocket.disconnect":
            client.peer_closed = True
            return
        client.last_seen = loop.time()
        text = message.get("text")
        if text is None:
            client.send(protocol.error(protocol.BAD_REQUEST, "binary frames are not supported"))
            continue
        if len(text.encode()) > hub.config.max_message_bytes:
            client.send(
                protocol.error(
                    protocol.BAD_REQUEST,
                    f"message larger than {hub.config.max_message_bytes} bytes",
                )
            )
            continue
        try:
            msg = protocol.client_message_adapter.validate_json(text)
        except ValidationError as exc:
            client.send(protocol.error(protocol.BAD_REQUEST, _first_error(exc)))
            continue
        if isinstance(msg, SubscribeMessage):
            await _subscribe(client, hub, session_factory, msg)
        elif isinstance(msg, UnsubscribeMessage):
            await _unsubscribe(client, hub, msg)
        else:
            client.send(protocol.pong())


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err.get("loc", ()))
    return f"{where}: {err['msg']}" if where else err["msg"]


def _counted_subscriptions(client: Client) -> int:
    own = user_topic(client.user_id)
    return sum(1 for topic in client.topics if topic != own)


async def _subscribe(
    client: Client,
    hub: WebSocketHub,
    session_factory: async_sessionmaker[AsyncSession],
    msg: SubscribeMessage,
) -> None:
    if msg.topic == "user":
        if msg.user_id != client.user_id:
            client.send(protocol.error(protocol.FORBIDDEN, "you can only subscribe to yourself"))
            return
        topic = user_topic(client.user_id)
        await hub.subscribe(client, topic)
        client.send(protocol.subscribed(topic))
        return

    topic = _market_topic(msg)
    if (
        topic not in client.topics
        and _counted_subscriptions(client) >= hub.config.max_subscriptions
    ):
        client.send(
            protocol.error(
                protocol.TOO_MANY_SUBSCRIPTIONS,
                f"at most {hub.config.max_subscriptions} subscriptions per connection",
            )
        )
        return
    async with session_factory() as session:
        instrument = await session.get(Instrument, msg.instrument_id)
        if instrument is None:
            client.send(protocol.error(protocol.UNKNOWN_INSTRUMENT, "instrument not found"))
            return
        if not instrument.is_active:
            client.send(protocol.error(protocol.INACTIVE_INSTRUMENT, "instrument is inactive"))
            return
        try:
            await hub.subscribe(client, topic)
        except Exception:  # noqa: BLE001
            logger.exception("Subscribing %s to %s failed", client.id, topic)
            client.send(protocol.error(protocol.UNAVAILABLE, "live updates are unavailable"))
            return
        client.send(protocol.subscribed(topic))
        if msg.topic == "signals":
            return  # no snapshot: GET /api/v1/signals lists past signals
        latest = await market_service.get_latest_candle(session, msg.instrument_id, msg.timeframe)
    candle = CandleOut.from_candle(latest).model_dump() if latest is not None else None
    client.send(protocol.snapshot(topic, candle))


def _market_topic(msg: SubscribeMessage | UnsubscribeMessage) -> str:
    if msg.topic == "signals":
        return signals_topic(msg.instrument_id)
    return candles_topic(msg.instrument_id, msg.timeframe)


async def _unsubscribe(client: Client, hub: WebSocketHub, msg: UnsubscribeMessage) -> None:
    if msg.topic == "user":
        if msg.user_id != client.user_id:
            client.send(protocol.error(protocol.FORBIDDEN, "you can only unsubscribe yourself"))
            return
        topic = user_topic(client.user_id)
    else:
        topic = _market_topic(msg)
    await hub.unsubscribe(client, topic)
    client.send(protocol.unsubscribed(topic))
