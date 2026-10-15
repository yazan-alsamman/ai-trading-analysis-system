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
# Must be set before anything imports app.* (settings and the engine are created at import time).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-secret-that-is-at-least-32-characters-long"
os.environ["FIRST_ADMIN_EMAIL"] = ""
os.environ["FIRST_ADMIN_PASSWORD"] = ""

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from alembic import command  # noqa: E402
from app.api.deps import get_aggregate_refresher  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
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
