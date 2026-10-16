"""Who is looking at a conversation right now: a Redis key per (conversation, user), set while
one of the user's WebSocket connections is subscribed to ``chat:{conversation_id}`` and
refreshed with every heartbeat. A crashed process leaves keys that expire after the TTL."""

import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError

TTL_SECONDS = 75  # 3 heartbeats


def key(conversation_id: uuid.UUID | str, user_id: uuid.UUID | str) -> str:
    return f"chat:presence:{conversation_id}:{user_id}"


async def mark(redis: Redis, conversation_id, user_id, ttl: int = TTL_SECONDS) -> None:
    try:
        await redis.set(key(conversation_id, user_id), "1", ex=ttl)
    except (RedisError, OSError):
        pass  # at worst the user gets a notification while looking


async def clear(redis: Redis, conversation_id, user_id) -> None:
    try:
        await redis.delete(key(conversation_id, user_id))
    except (RedisError, OSError):
        pass


async def present(redis: Redis, conversation_id, user_id) -> bool:
    try:
        return bool(await redis.exists(key(conversation_id, user_id)))
    except (RedisError, OSError):
        return False
