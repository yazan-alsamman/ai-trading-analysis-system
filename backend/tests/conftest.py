"""Test fixtures. Tests run against a real PostgreSQL/TimescaleDB (``TEST_DATABASE_URL``).

The database is created if missing and migrated once per session; every test runs inside an
outer transaction that is rolled back afterwards, so ``session.commit()`` in app code only
releases a savepoint.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://trading:trading@localhost:5432/trading_test"
)
TEST_REDIS_URL = os.environ.get(
    "TEST_REDIS_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)
# Must be set before anything imports app.* (settings and the engine are created at import time).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = TEST_REDIS_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-secret-that-is-at-least-32-characters-long"
os.environ["FIRST_ADMIN_EMAIL"] = ""
os.environ["FIRST_ADMIN_PASSWORD"] = ""
# Rate limiting is off in tests unless a test uses the ``rate_limits`` fixture; its Redis keys
# get their own prefix so tests never touch a running stack's buckets.
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["RATE_LIMIT_KEY_PREFIX"] = "test-rl"

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from redis.asyncio import Redis  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from alembic import command  # noqa: E402
from app.api.deps import get_aggregate_refresher, get_session_factory  # noqa: E402
from app.core import rate_limit  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.redis import set_redis  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.realtime.hub import HubConfig, WebSocketHub  # noqa: E402
from tests.utils import DEFAULT_PASSWORD, bearer  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


async def _create_database_if_missing(url: str) -> None:
    u = make_url(url)
    conn = await asyncpg.connect(
        user=u.username, password=u.password, host=u.host, port=u.port, database="postgres"
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", u.database)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{u.database}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def migrated_db() -> str:
    asyncio.run(_create_database_if_missing(TEST_DATABASE_URL))
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def db_connection(migrated_db: str) -> AsyncIterator[AsyncConnection]:
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            await trans.rollback()
    await engine.dispose()


@pytest.fixture
def session_factory(db_connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest.fixture
async def session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s


@pytest.fixture(autouse=True)
async def redis_client() -> AsyncIterator[Redis]:
    """A Redis client per test (async clients are bound to the event loop that uses them),
    installed as the app's shared client. Connections are only opened when used."""
    client = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    set_redis(client)
    yield client
    set_redis(None)
    await client.aclose()


class FrozenClock:
    """The rate limiter's clock in tests (ms since the epoch); ``advance`` moves it."""

    def __init__(self) -> None:
        self.now_ms = 1_800_000_000_000.0

    def __call__(self) -> float:
        return self.now_ms

    def advance(self, seconds: float) -> None:
        self.now_ms += seconds * 1000


async def _delete_keys(redis: Redis, pattern: str) -> None:
    keys = [k async for k in redis.scan_iter(match=pattern, count=1000)]
    if keys:
        await redis.delete(*keys)


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> FrozenClock:
    clock = FrozenClock()
    monkeypatch.setattr(rate_limit, "clock_ms", clock)
    return clock


@pytest.fixture
async def rate_limits(
    redis_client: Redis, monkeypatch: pytest.MonkeyPatch, frozen_clock: FrozenClock
) -> AsyncIterator[Settings]:
    """Rate limiting on, with a frozen clock and no leftover buckets."""
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    pattern = f"{settings.rate_limit_key_prefix}:*"
    await _delete_keys(redis_client, pattern)
    yield settings
    await _delete_keys(redis_client, pattern)


@pytest.fixture
def hub_config() -> HubConfig:
    return HubConfig()


@pytest.fixture
async def hub(redis_client: Redis, hub_config: HubConfig) -> AsyncIterator[WebSocketHub]:
    """The app's WebSocket hub (normally started by the lifespan, which tests do not run)."""
    hub = WebSocketHub(redis_client, hub_config)
    await hub.start()
    app.state.hub = hub
    yield hub
    await hub.stop()
    del app.state.hub


@pytest.fixture
def refresh_calls() -> list[tuple[datetime, datetime]]:
    """Calls the API made to refresh the continuous aggregates (recorded, not executed).

    A real refresh runs on its own connection, so it cannot see the uncommitted test data and
    would only move the aggregates' watermarks; see tests/test_aggregate_refresh.py instead.
    """
    return []


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    refresh_calls: list[tuple[datetime, datetime]],
) -> AsyncIterator[AsyncClient]:
    async def _get_test_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    async def _record_refresh(start: datetime, end: datetime) -> None:
        refresh_calls.append((start, end))

    app.dependency_overrides[get_session] = _get_test_session
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_aggregate_refresher] = lambda: _record_refresh
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(session: AsyncSession):
    async def _make_user(
        email: str,
        role: UserRole = UserRole.trader,
        password: str = DEFAULT_PASSWORD,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        return user

    return _make_user


@pytest.fixture
def login(client: AsyncClient):
    async def _login(email: str, password: str = DEFAULT_PASSWORD) -> dict:
        res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        return res.json()

    return _login


@pytest.fixture
async def admin_headers(make_user, login) -> dict[str, str]:
    await make_user("admin@example.com", role=UserRole.admin)
    return bearer((await login("admin@example.com"))["access_token"])


@pytest.fixture
async def trader_headers(make_user, login) -> dict[str, str]:
    await make_user("trader@example.com", role=UserRole.trader)
    return bearer((await login("trader@example.com"))["access_token"])


@pytest.fixture(autouse=True)
def notification_queue(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list, float | None]]:
    """Notification sends handed to Celery are recorded instead (``(ids, countdown)``)."""
    from app.notifications import service as notification_service

    sent: list[tuple[list, float | None]] = []
    monkeypatch.setattr(
        notification_service, "enqueue", lambda ids, countdown=None: sent.append((ids, countdown))
    )
    monkeypatch.setattr(notification_service, "enqueue_broadcast", lambda *a: None)
    # every test session shares one connection (savepoints): send one delivery at a time
    monkeypatch.setattr(notification_service, "SEND_CONCURRENCY", 1)
    return sent


@pytest.fixture(autouse=True)
async def _clean_notification_keys(redis_client: Redis) -> AsyncIterator[None]:
    """Hourly caps, circuit breakers, cached FCM token and link codes start empty."""
    await _delete_keys(redis_client, "notif:*")
    yield
    await _delete_keys(redis_client, "notif:*")
