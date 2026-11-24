"""Publish real-time events. Usable from anywhere (API, Celery, CLI, collectors): it only needs
Redis, not the WebSocket hub. Every API process's hub relays the message to its own clients."""

import json
import time
from typing import Any

from redis.asyncio import Redis

from app.core.redis import get_redis
from app.realtime.topics import channel_for


def encode(topic: str, payload: dict[str, Any]) -> str:
    """The exact text frame clients receive. ``sent_at`` is the publish time in unix ms."""
    return json.dumps(
        {**payload, "topic": topic, "sent_at": int(time.time() * 1000)}, separators=(",", ":")
    )


async def publish(
    topic: str, payload: dict[str, Any], redis: Redis | None = None, *, via: str | None = None
) -> int:
    """Publish ``payload`` to ``topic``. Returns the number of API processes that received it.
    ``via``: deliver through that topic's channel instead (the frame still says ``topic``),
    e.g. a private signal through ``private_signals_topic``."""
    redis = redis or get_redis()
    return await redis.publish(channel_for(via or topic), encode(topic, payload))
