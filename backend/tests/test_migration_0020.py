"""Migration 0020 on a database with existing data: upgrade -> downgrade -> upgrade. A new,
empty feed_credentials table (the encrypted cTrader tokens); nothing else changes.

Runs on its own scratch database, created and dropped here."""

import asyncio
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL

SCRATCH_URL = make_url(TEST_DATABASE_URL).set(
    database=f"{make_url(TEST_DATABASE_URL).database}_m0020"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0020_feed_credentials.py"


def _run(method: str, query: str, *args, database: str | None = None):
    async def go():
        conn = await asyncpg.connect(
            user=SCRATCH_URL.username,
            password=SCRATCH_URL.password,
            host=SCRATCH_URL.host,
            port=SCRATCH_URL.port,
            database=database or SCRATCH_URL.database,
        )
        try:
            return await getattr(conn, method)(query, *args)
        finally:
            await conn.close()

    return asyncio.run(go())


def _alembic(target: str, *, down: bool = False) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["keep_logging"] = True
    cfg.attributes["database_url"] = SCRATCH_URL.render_as_string(hide_password=False)
    (command.downgrade if down else command.upgrade)(cfg, target)


@pytest.fixture
def scratch():
    drop = f'DROP DATABASE IF EXISTS "{SCRATCH_URL.database}" WITH (FORCE)'
    _run("execute", drop, database="postgres")
    _run("execute", f'CREATE DATABASE "{SCRATCH_URL.database}"', database="postgres")
    try:
        yield
    finally:
        _run("execute", drop, database="postgres")


def test_upgrade_downgrade_upgrade(scratch) -> None:
    _alembic("0019")
    users = _run("fetchval", "SELECT count(*) FROM users")
    _alembic("0020")
    assert _run("fetchval", "SELECT count(*) FROM feed_credentials") == 0
    _run(
        "execute",
        "INSERT INTO feed_credentials (provider, env, access_token_enc, refresh_token_enc, "
        "expires_at, scope) VALUES ('ctrader', 'demo', 'v1:a', 'v1:r', now(), 'accounts')",
    )
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE feed_credentials SET env = 'paper'")
    assert _run("fetchval", "SELECT accounts::text FROM feed_credentials") == "[]"
    _alembic("0019", down=True)
    assert _run("fetchval", "SELECT to_regclass('feed_credentials')") is None
    assert _run("fetchval", "SELECT count(*) FROM users") == users
    _alembic("0020")
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0020"


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
