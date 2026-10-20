"""/ws/market: live market data over WebSocket (protocol: docs/websocket.md).

Mounted at the app root (not /api/v1) because Nginx proxies /ws/ with the Upgrade headers.
"""

import asyncio
import logging
import math
import time
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_session_factory
from app.api.limits import WsConnectionSlot, client_ip, ws_ip_allowed
from app.chat import presence
from app.core.redis import get_redis
from app.core.security import decode_token
from app.models.api_key import ApiKey, Scope
from app.models.chat import Conversation
from app.models.instrument import Instrument
from app.models.user import User, UserRole
from app.realtime import protocol, publisher
from app.realtime.hub import (
    CLOSE_GOING_AWAY,
    CLOSE_RATE_LIMITED,
    CLOSE_UNAUTHORIZED,
    Client,
    WebSocketHub,
)
from app.realtime.protocol import SubscribeMessage, TypingMessage, UnsubscribeMessage
from app.realtime.topics import (
    candles_topic,
    chat_topic,
    is_private_signals,
    news_topic,
    private_signals_topic,
    signals_topic,
    user_topic,
)
from app.schemas.market import CandleOut
from app.services import api_key_service, market_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])

SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]


@dataclass
class _Auth:
    user: User
    expires_at: float  # unix seconds of the token's / key's expiry (inf: never)
    identity: str  # rate-limit identity: user:<id> (JWT) or key:<id> (API key)
    credential: str  # "access token" / "API key", for the expiry message
    scopes: frozenset[str] | None = None  # an API key's scopes (None: a login, every scope)
    key_id: uuid.UUID | None = None  # the API key (None: a login)


async def _authenticate(
    token: str | None, api_key: str | None, session_factory: async_sessionmaker[AsyncSession]
) -> _Auth | str:
    """The connection's identity, or why it is refused (closed with 4401). A token wins over
    an API key; a key needs the ``stream`` scope."""
    if token:
        try:
            payload = decode_token(token, "access")
        except HTTPException:
            return "invalid or expired token"
        async with session_factory() as session:
            user = await session.get(User, payload["sub"])
        if user is None or not user.is_active:
            return "invalid or expired token"
        return _Auth(user, float(payload["exp"]), f"user:{user.id}", "access token")
    if api_key:
        async with session_factory() as session:
            try:
                user, row = await api_key_service.authenticate(session, get_redis(), api_key)
            except HTTPException:
                return "invalid API key"
        if Scope.stream.value not in row.scopes:
            return "API key lacks the 'stream' scope"
        expires_at = row.expires_at.timestamp() if row.expires_at is not None else math.inf
        return _Auth(user, expires_at, f"key:{row.id}", "API key", frozenset(row.scopes), row.id)
    return "invalid or expired token"


async def _refuse(websocket: WebSocket, code: int, reason: str) -> None:
    # A close sent before accept() becomes an HTTP 403 and browsers only see code 1006,
    # so accept and close with the application code.
    await websocket.accept()
    await websocket.close(code=code, reason=reason)


@router.websocket("/ws/market")
async def market_ws(
    websocket: WebSocket,
    session_factory: SessionFactory,
    token: str | None = None,
    api_key: str | None = None,
) -> None:
    # Limit and authenticate before doing any work for the connection.
    if not await ws_ip_allowed(client_ip(websocket)):
        await _refuse(websocket, CLOSE_RATE_LIMITED, "too many new connections")
        return
    auth = await _authenticate(token, api_key, session_factory)
    if isinstance(auth, str):
        await _refuse(websocket, CLOSE_UNAUTHORIZED, auth)
        return
    hub: WebSocketHub = websocket.app.state.hub
    slot = WsConnectionSlot(
        auth.identity, uuid.uuid4().hex, stale_seconds=3 * hub.config.heartbeat_seconds
    )
    if not await slot.acquire():
        await _refuse(websocket, CLOSE_RATE_LIMITED, "too many connections")
        return
    try:
        await _serve(websocket, hub, session_factory, auth, slot)
    finally:
        await slot.release()


async def _serve(
    websocket: WebSocket,
    hub: WebSocketHub,
    session_factory: async_sessionmaker[AsyncSession],
    auth: _Auth,
    slot: WsConnectionSlot,
) -> None:
    user = auth.user
    await websocket.accept()
    client = hub.new_client(websocket, user.id, auth.key_id)
    client.is_admin = user.role == UserRole.admin
    await hub.register(client)
    receiver = watchdog = stop_wait = None
    try:
        await hub.subscribe(client, user_topic(user.id))
        receiver = asyncio.create_task(_receive_loop(client, hub, session_factory, auth))
        watchdog = asyncio.create_task(_watchdog(client, hub, auth, slot, session_factory))
        stop_wait = asyncio.create_task(client.stopped.wait())
        await asyncio.wait({receiver, watchdog, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
        if watchdog.done() and not watchdog.cancelled() and watchdog.exception() is not None:
            # without its watchdog a connection would never be re-checked, expire or time out
            logger.error(
                "WebSocket %s watchdog failed; closing",
                client.id,
                exc_info=watchdog.exception(),
            )
            client.close(1011, "internal error")
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
        for conversation_id in list(client.presence):
            await presence.clear(get_redis(), conversation_id, client.user_id)
        await hub.unregister(client)
        if not client.peer_closed:
            try:
                await websocket.close(code=client.close_code or 1000, reason=client.close_reason)
            except Exception:  # noqa: BLE001 - already closed
                pass


async def _watchdog(
    client: Client,
    hub: WebSocketHub,
    auth: _Auth,
    slot: WsConnectionSlot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Heartbeats (which also refresh the connection slot), idle timeout, expiry of the access
    token or API key, and re-authorisation: on every heartbeat, and right away when an auth
    event wakes it (``client.recheck``), the user and key are read again (``_recheck``)."""
    loop = asyncio.get_running_loop()
    heartbeat, idle = hub.config.heartbeat_seconds, hub.config.idle_timeout_seconds
    next_heartbeat = loop.time() + heartbeat
    while True:
        now = loop.time()
        seconds_to_exp = auth.expires_at - time.time()
        if seconds_to_exp <= 0:
            client.send(protocol.error(protocol.TOKEN_EXPIRED, f"{auth.credential} expired"))
            client.close(CLOSE_UNAUTHORIZED, "token expired", flush=True)
            return
        if now - client.last_seen >= idle:
            client.close(CLOSE_GOING_AWAY, "idle timeout")
            return
        due = now >= next_heartbeat
        if due or client.recheck.is_set():
            client.recheck.clear()
            if not await _recheck(client, hub, session_factory, auth):
                return
        if due:
            if not client.send(protocol.heartbeat()):
                hub.drop(client)
                return
            next_heartbeat = now + heartbeat
            await slot.touch()
            for conversation_id in list(client.presence):
                await presence.mark(get_redis(), conversation_id, client.user_id)
        wait = min(next_heartbeat - now, client.last_seen + idle - now, seconds_to_exp)
        try:
            await asyncio.wait_for(
                client.recheck.wait(), max(wait, 0.01) if math.isfinite(wait) else heartbeat
            )
        except TimeoutError:
            pass


def _revoked(found, auth: _Auth) -> str | None:
    """Why the connection may no longer stay open (None: it may)."""
    if found is None:
        return "API key revoked" if auth.key_id is not None else "user deactivated"
    if not found.is_active:
        return "user deactivated"
    if auth.key_id is None:
        return None
    if found.revoked_at is not None:
        return "API key revoked"
    if found.expires_at is not None and found.expires_at.timestamp() <= time.time():
        return "API key expired"
    if Scope.stream.value not in found.scopes:
        return "API key lacks the 'stream' scope"
    return None


async def _recheck(
    client: Client,
    hub: WebSocketHub,
    session_factory: async_sessionmaker[AsyncSession],
    auth: _Auth,
) -> bool:
    """Read the user (and API key) again: one primary-key query. Closes the connection with
    ``auth_revoked`` / 4401 if the user is gone or inactive, or the key is revoked, expired or
    without ``stream``; otherwise drops the topics the role or scopes no longer allow. False
    if it closed. A database error keeps the connection (checked again next heartbeat)."""
    if auth.key_id is None:
        query = select(User.is_active, User.role).where(User.id == client.user_id)
    else:
        query = (
            select(User.is_active, User.role, ApiKey.revoked_at, ApiKey.expires_at, ApiKey.scopes)
            .join(User, User.id == ApiKey.user_id)
            .where(ApiKey.id == auth.key_id)
        )
    try:
        async with hub.auth_lock, session_factory() as session:
            found = (await session.execute(query)).first()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Re-checking WebSocket %s failed (%s); next try at the heartbeat",
            client.id,
            type(exc).__name__,
        )
        return True
    reason = _revoked(found, auth)
    if reason is not None:
        logger.info("Closing WebSocket %s (user %s): %s", client.id, client.user_id, reason)
        client.send(protocol.error(protocol.AUTH_REVOKED, reason))
        client.close(CLOSE_UNAUTHORIZED, reason, flush=True)
        return False
    if auth.key_id is not None:
        auth.scopes = frozenset(found.scopes)
    await _trim(client, hub, session_factory, auth, found.role == UserRole.admin)
    return True


async def _trim(
    client: Client,
    hub: WebSocketHub,
    session_factory: async_sessionmaker[AsyncSession],
    auth: _Auth,
    is_admin: bool,
) -> None:
    """Apply a role or scope change to the topics: news without ``news:read``, chats a demoted
    admin does not take part in, and the private-signal topic that matches the role."""
    dropped = []
    if auth.scopes is not None and Scope.news_read.value not in auth.scopes:
        dropped += [t for t in client.topics if t == "news" or t.startswith("news:")]
    if is_admin != client.is_admin:
        chats = [t for t in client.topics if t.startswith("chat:")]
        kept = await _own_chats(client, session_factory, chats) if chats and not is_admin else chats
        if kept is not None:
            dropped += [t for t in chats if t not in kept]
            client.is_admin = is_admin
            for topic in [t for t in client.topics if _is_signals(t)]:
                await _sync_private_signals(client, hub, topic)
        # kept is None: the database failed; is_admin stays as it was, so the next check (the
        # heartbeat) applies the role change again
    for topic in dropped:
        await hub.unsubscribe(client, topic)
        client.send(protocol.unsubscribed(topic, reason="forbidden"))


async def _own_chats(
    client: Client, session_factory: async_sessionmaker[AsyncSession], chats: list[str]
) -> list[str] | None:
    """The chat topics of conversations the user takes part in; None on a database error
    (logged, like a failed re-check: the connection stays and the next check retries)."""
    try:
        async with session_factory() as session:
            mine = set(
                await session.scalars(
                    select(Conversation.id).where(
                        or_(
                            Conversation.user_id == client.user_id,
                            Conversation.expert_id == client.user_id,
                        )
                    )
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Re-checking the chats of WebSocket %s failed (%s); next try at the heartbeat",
            client.id,
            type(exc).__name__,
        )
        return None
    return [t for t in chats if uuid.UUID(t.split(":", 1)[1]) in mine]


def _is_signals(topic: str) -> bool:
    return topic.startswith("signals:") and not is_private_signals(topic)


def _private_topics(client: Client, topic: str) -> tuple[str, str]:
    """(the private-signal topic this connection should hold for the public signals ``topic``:
    its own, or the admins' one for an admin; the other one)."""
    instrument_id = topic.split(":", 1)[1]
    own = private_signals_topic(instrument_id, client.user_id)
    admins = private_signals_topic(instrument_id, None)
    return (admins, own) if client.is_admin else (own, admins)


async def _sync_private_signals(client: Client, hub: WebSocketHub, topic: str) -> None:
    wanted, other = _private_topics(client, topic)
    await hub.unsubscribe(client, other)
    await hub.subscribe(client, wanted)


async def _receive_loop(
    client: Client,
    hub: WebSocketHub,
    session_factory: async_sessionmaker[AsyncSession],
    auth: _Auth | None = None,
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
            await _subscribe(client, hub, session_factory, msg, auth)
        elif isinstance(msg, UnsubscribeMessage):
            await _unsubscribe(client, hub, msg)
        elif isinstance(msg, TypingMessage):
            await _typing(client, msg)
        else:
            client.send(protocol.pong())


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err.get("loc", ()))
    return f"{where}: {err['msg']}" if where else err["msg"]


def _counted_subscriptions(client: Client) -> int:
    own = user_topic(client.user_id)
    return sum(1 for t in client.topics if t != own and not is_private_signals(t))


async def _subscribe(
    client: Client,
    hub: WebSocketHub,
    session_factory: async_sessionmaker[AsyncSession],
    msg: SubscribeMessage,
    auth: _Auth | None = None,
) -> None:
    if msg.topic == "user":
        if msg.user_id != client.user_id:
            client.send(protocol.error(protocol.FORBIDDEN, "you can only subscribe to yourself"))
            return
        topic = user_topic(client.user_id)
        await hub.subscribe(client, topic)
        client.send(protocol.subscribed(topic))
        return

    if (
        msg.topic == "news"
        and auth is not None
        and auth.scopes is not None
        and Scope.news_read.value not in auth.scopes
    ):
        client.send(protocol.error(protocol.FORBIDDEN, "API key lacks the 'news:read' scope"))
        return
    if msg.topic == "chat":
        await _subscribe_chat(client, hub, session_factory, msg)
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
    if msg.topic == "news" and msg.instrument_id is None:
        await _subscribe_plain(client, hub, topic)
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
            if msg.topic == "signals":
                # private custom-strategy signals arrive on the connection's own private topic
                await _sync_private_signals(client, hub, topic)
        except Exception:  # noqa: BLE001
            logger.exception("Subscribing %s to %s failed", client.id, topic)
            client.send(protocol.error(protocol.UNAVAILABLE, "live updates are unavailable"))
            return
        client.send(protocol.subscribed(topic))
        if msg.topic in ("signals", "news"):
            return  # no snapshot: GET /api/v1/signals and /news list the past ones
        latest = await market_service.get_latest_candle(session, msg.instrument_id, msg.timeframe)
    candle = (
        CandleOut.from_candle(latest).model_dump(exclude_none=True) if latest is not None else None
    )
    client.send(protocol.snapshot(topic, candle))


async def _subscribe_plain(client: Client, hub: WebSocketHub, topic: str) -> None:
    try:
        await hub.subscribe(client, topic)
    except Exception:  # noqa: BLE001
        logger.exception("Subscribing %s to %s failed", client.id, topic)
        client.send(protocol.error(protocol.UNAVAILABLE, "live updates are unavailable"))
        return
    client.send(protocol.subscribed(topic))


TYPING_INTERVAL_MS = 3000


async def _subscribe_chat(
    client: Client,
    hub: WebSocketHub,
    session_factory: async_sessionmaker[AsyncSession],
    msg: SubscribeMessage,
) -> None:
    """Only the two participants (and admins) may subscribe. A participant's subscription
    counts as presence: no chat notifications while it lasts."""
    topic = chat_topic(msg.conversation_id)
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
        conv = await session.get(Conversation, msg.conversation_id)
        user = await session.get(User, client.user_id)
    participant = conv is not None and client.user_id in (conv.expert_id, conv.user_id)
    if not participant and not (conv is not None and user.role == UserRole.admin):
        client.send(protocol.error(protocol.FORBIDDEN, "not a participant of this conversation"))
        return
    try:
        await hub.subscribe(client, topic)
    except Exception:  # noqa: BLE001
        logger.exception("Subscribing %s to %s failed", client.id, topic)
        client.send(protocol.error(protocol.UNAVAILABLE, "live updates are unavailable"))
        return
    if participant:
        client.presence.add(conv.id)
        await presence.mark(get_redis(), conv.id, client.user_id)
    client.send(protocol.subscribed(topic))


async def _typing(client: Client, msg: TypingMessage) -> None:
    """``chat_typing`` to the conversation, at most once per 3 s per user (others dropped)."""
    if msg.conversation_id not in client.presence:
        client.send(protocol.error(protocol.FORBIDDEN, "subscribe to the chat topic first"))
        return
    redis = get_redis()
    try:
        key = f"chat:typing:{msg.conversation_id}:{client.user_id}"
        if not await redis.set(key, "1", nx=True, px=TYPING_INTERVAL_MS):
            return
        await publisher.publish(
            chat_topic(msg.conversation_id),
            {
                "type": "chat_typing",
                "conversation_id": str(msg.conversation_id),
                "user_id": str(client.user_id),
            },
            redis,
        )
    except Exception:  # noqa: BLE001 - typing is best effort
        logger.warning("typing event for %s failed", msg.conversation_id)


def _market_topic(msg: SubscribeMessage | UnsubscribeMessage) -> str:
    if msg.topic == "chat":
        return chat_topic(msg.conversation_id)
    if msg.topic == "news":
        return news_topic(msg.instrument_id)
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
    if msg.topic == "chat" and msg.conversation_id in client.presence:
        client.presence.discard(msg.conversation_id)
        await presence.clear(get_redis(), msg.conversation_id, client.user_id)
    await hub.unsubscribe(client, topic)
    if msg.topic == "signals":
        for private in _private_topics(client, topic):
            await hub.unsubscribe(client, private)
    client.send(protocol.unsubscribed(topic))
