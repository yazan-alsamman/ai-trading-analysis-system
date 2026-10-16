"""Per-channel circuit breaker in Redis, shared by all worker processes.

After ``notification_breaker_failures`` consecutive transient failures of a channel (timeouts,
5xx, SMTP down), the channel is *open* for ``notification_breaker_seconds``: deliveries are held
(``hold = circuit_open``) instead of being retried one by one, and the opening is logged once.
When the period ends the next delivery tries again (half-open): a success closes the circuit, a
failure opens it again.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _keys(channel: str) -> tuple[str, str]:
    return f"notif:breaker:{channel}:failures", f"notif:breaker:{channel}:open"


async def open_for(redis: Redis, channel: str) -> int:
    """Seconds the circuit stays open (0 = closed)."""
    ttl = await redis.ttl(_keys(channel)[1])
    return max(0, int(ttl or 0))


async def failure(redis: Redis, channel: str) -> bool:
    """Record a transient failure; True if this one opened the circuit."""
    settings = get_settings()
    failures_key, open_key = _keys(channel)
    count = await redis.incr(failures_key)
    await redis.expire(failures_key, settings.notification_breaker_seconds * 2)
    if count >= settings.notification_breaker_failures:
        opened = await redis.set(open_key, "1", nx=True, ex=settings.notification_breaker_seconds)
        await redis.delete(failures_key)
        if opened:
            logger.warning(
                "notifications: %s circuit opened after %d consecutive failures, paused %ds",
                channel,
                count,
                settings.notification_breaker_seconds,
            )
            return True
    return False


async def success(redis: Redis, channel: str) -> None:
    await redis.delete(_keys(channel)[0])


async def state(redis: Redis, channel: str) -> dict[str, int | bool]:
    failures_key, _ = _keys(channel)
    seconds = await open_for(redis, channel)
    return {
        "open": seconds > 0,
        "open_seconds_left": seconds,
        "consecutive_failures": int(await redis.get(failures_key) or 0),
    }
