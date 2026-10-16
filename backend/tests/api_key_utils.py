from httpx import AsyncClient
from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

KEYS = "/api/v1/me/api-keys"


async def create_key(
    client: AsyncClient, headers: dict[str, str], scopes=("market:read",), **extra
) -> dict:
    """Create an API key through the API; the response includes the full ``key``."""
    body = {"name": extra.pop("name", "bot"), "scopes": list(scopes), **extra}
    res = await client.post(KEYS, json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def xkey(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


def unreachable_redis() -> Redis:
    """A client for a port nobody listens on, failing fast (no retries)."""
    return Redis.from_url(
        "redis://127.0.0.1:1/0",
        decode_responses=True,
        socket_connect_timeout=0.2,
        retry=Retry(NoBackoff(), 0),
    )
