"""Identity changes that open WebSocket connections must react to at once: an API key revoked
or its scopes changed, a user deactivated or given another role.

The event only says *whose* connections to re-check; every API process's hub wakes the
matching connections and their watchdogs re-read the user and key from the database, which
decides (close with ``auth_revoked`` / 4401, or drop topics the role no longer allows). The
watchdog also re-checks on every heartbeat, so a lost event (Redis down) costs at most one
heartbeat interval. Publish **after** the commit, so the re-check sees the change.
"""

import json
import logging
import uuid

from redis.asyncio import Redis

from app.core.redis import get_redis
from app.realtime.hub import AUTH_CHANNEL

logger = logging.getLogger(__name__)


async def publish(
    *,
    user_id: uuid.UUID | None = None,
    key_id: uuid.UUID | None = None,
    redis: Redis | None = None,
) -> None:
    """Never raises: the heartbeat re-check is the safety net."""
    event = {"user_id": user_id and str(user_id), "key_id": key_id and str(key_id)}
    try:
        await (redis or get_redis()).publish(AUTH_CHANNEL, json.dumps(event))
    except Exception:  # noqa: BLE001
        logger.warning("Publishing the WebSocket auth event %s failed", event)
