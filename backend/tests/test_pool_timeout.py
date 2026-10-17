"""Database pool exhausted under overload: 503 with Retry-After, not an unhandled 500 (C2)."""

import json

from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.core.config import get_settings
from app.db.session import engine
from app.main import POOL_RETRY_AFTER, pool_timeout_handler


async def test_pool_timeout_is_503_with_retry_after():
    res = await pool_timeout_handler(None, PoolTimeout("QueuePool limit reached"))
    assert res.status_code == 503
    assert res.headers["Retry-After"] == str(POOL_RETRY_AFTER)
    assert json.loads(res.body) == {
        "detail": "Server busy, try again shortly",
        "retry_after": POOL_RETRY_AFTER,
    }


def test_engine_uses_pool_settings():
    settings = get_settings()
    assert engine.pool.size() == settings.db_pool_size
    assert engine.pool._max_overflow == settings.db_max_overflow
    assert engine.pool._timeout == settings.db_pool_timeout
