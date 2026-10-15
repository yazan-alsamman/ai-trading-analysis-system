"""In-process WebSocket hub backed by Redis Pub/Sub.

One hub per API process. It keeps ``topic -> local clients`` and holds a single Redis Pub/Sub
connection: a Redis channel is subscribed when the first local client subscribes to its topic
and unsubscribed when the last one leaves. One reader task receives Redis messages and fans
them out to local clients, so several workers/containers each relay every published message to
their own sockets.

Back-pressure: every client has a bounded outgoing queue drained by its own sender task. The
fan-out only does ``put_nowait``; a client whose queue is full is dropped (close 1013) instead
of slowing everyone else down.
"""

import asyncio
import logging
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from starlette.websockets import WebSocket

from app.core.config import Settings
from app.realtime.topics import channel_for, topic_for

logger = logging.getLogger(__name__)

CLOSE_NORMAL = 1000
CLOSE_GOING_AWAY = 1001  # idle timeout / server shutdown
CLOSE_TRY_AGAIN_LATER = 1013  # client too slow (queue full)
CLOSE_UNAUTHORIZED = 4401  # invalid or expired access token

SUBSCRIBE_CONFIRM_TIMEOUT = 1.0  # seconds to wait for Redis to confirm a SUBSCRIBE


@dataclass(frozen=True)
class HubConfig:
    queue_size: int = 256
    heartbeat_seconds: float = 25
    idle_timeout_seconds: float = 75
    max_subscriptions: int = 50
    max_message_bytes: int = 4096

    @classmethod
    def from_settings(cls, settings: Settings) -> "HubConfig":
        return cls(
            queue_size=settings.ws_queue_size,
            heartbeat_seconds=settings.ws_heartbeat_seconds,
            idle_timeout_seconds=settings.ws_idle_timeout_seconds,
            max_subscriptions=settings.ws_max_subscriptions,
            max_message_bytes=settings.ws_max_message_bytes,
        )


class Client:
    """One accepted WebSocket connection."""

    def __init__(self, websocket: WebSocket, user_id: uuid.UUID, queue_size: int) -> None:
        self.id = uuid.uuid4()
        self.websocket = websocket
        self.user_id = user_id
        self.queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=queue_size)
        self.topics: set[str] = set()
        self.stopped = asyncio.Event()
        self.close_code: int | None = None
        self.close_reason = ""
        self.peer_closed = False
        self.last_seen = asyncio.get_running_loop().time()
        self.sender: asyncio.Task | None = None

    def send(self, text: str) -> bool:
        """Queue a frame without waiting. False if the queue is full."""
        try:
            self.queue.put_nowait(text)
        except asyncio.QueueFull:
            return False
        return True

    def close(self, code: int, reason: str = "", *, flush: bool = False) -> None:
        """Ask the connection to close. With ``flush``, frames already queued are sent first."""
        if self.close_code is None:
            self.close_code, self.close_reason = code, reason
        if flush:
            try:
                self.queue.put_nowait(None)  # sender stops after draining the queue
                return
            except asyncio.QueueFull:
                pass
        self.stopped.set()


class WebSocketHub:
    def __init__(self, redis: Redis, config: HubConfig | None = None) -> None:
        self.config = config or HubConfig()
        self._redis = redis
        self._pubsub = redis.pubsub()  # subscribe confirmations are used, see subscribe()
        self._confirmations: dict[str, asyncio.Event] = {}
        self._topics: dict[str, set[Client]] = {}
        self._clients: set[Client] = set()
        self._lock = asyncio.Lock()
        self._pubsub_ready = asyncio.Event()  # redis-py needs a subscribe() before reading
        self._reader: asyncio.Task | None = None
        self.started_at = time.time()
        self.connections_total = 0
        self.messages_received = 0  # from Redis
        self.messages_delivered = 0  # frames written to sockets
        self.clients_dropped = 0

    # --- lifecycle -------------------------------------------------------------------------

    async def start(self) -> None:
        if self._reader is None:
            self._reader = asyncio.create_task(self._read_loop(), name="ws-hub-reader")

    async def stop(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)
            self._reader = None
        for client in list(self._clients):
            client.close(CLOSE_GOING_AWAY, "server shutdown")
        try:
            await self._pubsub.aclose()
        except Exception:  # noqa: BLE001
            logger.exception("Closing the hub's Redis Pub/Sub connection failed")

    async def _read_loop(self) -> None:
        while True:
            try:
                await self._pubsub_ready.wait()
                message = await self._pubsub.get_message(timeout=1.0)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - keep the reader alive; redis-py reconnects
                logger.exception("Redis Pub/Sub read failed; retrying in 1s")
                await asyncio.sleep(1)
                continue
            if message is None:
                continue
            if message.get("type") == "subscribe":
                confirmed = self._confirmations.pop(message["channel"], None)
                if confirmed is not None:
                    confirmed.set()
                continue
            if message.get("type") != "message":
                continue
            topic = topic_for(message["channel"])
            if topic is not None:
                self.messages_received += 1
                self.deliver(topic, message["data"])

    # --- clients ---------------------------------------------------------------------------

    def new_client(self, websocket: WebSocket, user_id: uuid.UUID) -> Client:
        return Client(websocket, user_id, self.config.queue_size)

    async def register(self, client: Client) -> None:
        self._clients.add(client)
        self.connections_total += 1
        client.sender = asyncio.create_task(self._send_loop(client), name=f"ws-send-{client.id}")

    async def unregister(self, client: Client) -> None:
        if client.sender is not None and not client.sender.done():
            client.sender.cancel()
            await asyncio.gather(client.sender, return_exceptions=True)
        for topic in list(client.topics):
            await self.unsubscribe(client, topic)
        self._clients.discard(client)

    async def _send_loop(self, client: Client) -> None:
        try:
            while True:
                text = await client.queue.get()
                if text is None:
                    break
                await client.websocket.send_text(text)
                self.messages_delivered += 1
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the socket is gone
            client.peer_closed = True
        finally:
            client.stopped.set()

    def drop(self, client: Client) -> None:
        if client.close_code is None:
            self.clients_dropped += 1
            logger.warning(
                "Dropping slow WebSocket client %s (user %s): outgoing queue full",
                client.id,
                client.user_id,
            )
        client.close(CLOSE_TRY_AGAIN_LATER, "client too slow")

    # --- topics ----------------------------------------------------------------------------

    async def subscribe(self, client: Client, topic: str) -> bool:
        """Subscribe a client; returns False if it already was."""
        if topic in client.topics:
            return False
        async with self._lock:
            clients = self._topics.get(topic)
            if clients is None:
                # register locally first so a message arriving right after SUBSCRIBE is kept
                self._topics[topic] = {client}
                channel = channel_for(topic)
                confirmed = self._confirmations[channel] = asyncio.Event()
                try:
                    await self._pubsub.subscribe(channel)
                except Exception:
                    del self._topics[topic]
                    self._confirmations.pop(channel, None)
                    raise
                self._pubsub_ready.set()
                # redis-py's subscribe() only sends the command; wait for Redis' confirmation
                # (read by the reader task) so a message published right after the client's
                # "subscribed" ack cannot miss this process.
                try:
                    await asyncio.wait_for(confirmed.wait(), SUBSCRIBE_CONFIRM_TIMEOUT)
                except TimeoutError:
                    self._confirmations.pop(channel, None)
                    logger.warning("Redis did not confirm SUBSCRIBE %s in time", channel)
            else:
                clients.add(client)
        client.topics.add(topic)
        return True

    async def unsubscribe(self, client: Client, topic: str) -> bool:
        """Unsubscribe a client; returns False if it was not subscribed."""
        if topic not in client.topics:
            return False
        client.topics.discard(topic)
        async with self._lock:
            clients = self._topics.get(topic)
            if clients is None:
                return True
            clients.discard(client)
            if not clients:
                del self._topics[topic]
                try:
                    await self._pubsub.unsubscribe(channel_for(topic))
                except Exception:  # noqa: BLE001
                    logger.exception("Redis UNSUBSCRIBE %s failed", topic)
        return True

    def deliver(self, topic: str, text: str) -> int:
        """Queue ``text`` for every local subscriber of ``topic``; never awaits a socket."""
        queued = 0
        for client in list(self._topics.get(topic, ())):
            if client.send(text):
                queued += 1
            else:
                self.drop(client)
        return queued

    # --- introspection ---------------------------------------------------------------------

    def subscriber_count(self, topic: str) -> int:
        return len(self._topics.get(topic, ()))

    def stats(self) -> dict[str, Any]:
        per_kind = Counter(topic.split(":", 1)[0] for topic in self._topics)
        busiest = sorted(self._topics.items(), key=lambda kv: len(kv[1]), reverse=True)[:20]
        return {
            "clients": len(self._clients),
            "topics": len(self._topics),
            "topics_by_kind": dict(per_kind),
            "subscriptions": sum(len(c) for c in self._topics.values()),
            "connections_total": self.connections_total,
            "messages_received": self.messages_received,
            "messages_delivered": self.messages_delivered,
            "clients_dropped": self.clients_dropped,
            "queued_messages": sum(c.queue.qsize() for c in self._clients),
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "busiest_topics": {topic: len(clients) for topic, clients in busiest},
        }
