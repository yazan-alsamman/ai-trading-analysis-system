"""Migration 0025 on a database with existing data: upgrade -> downgrade -> upgrade. It only
adds two nullable columns to ``users`` (existing rows keep NULL), a unique constraint and an
E.164 check on ``phone_e164``; downgrade drops them and keeps the users.

Runs on its own scratch database, created and dropped here."""

import asyncio
import uuid
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL

SCRATCH_URL = make_url(TEST_DATABASE_URL).set(
    database=f"{make_url(TEST_DATABASE_URL).database}_m0025"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0025_user_phone.py"


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


USER = (
    "INSERT INTO users (id, email, hashed_password, role, is_active) "
    "VALUES ($1, $2, 'x', 'trader', true)"
)
SET_PHONE = "UPDATE users SET phone_e164 = $2, phone_verified_at = now() WHERE id = $1"


def _columns() -> set[str]:
    rows = _run(
        "fetch", "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"
    )
    return {r["column_name"] for r in rows}


def test_upgrade_downgrade_upgrade(scratch) -> None:
    _alembic("0024")
    alice, bob = uuid.uuid4(), uuid.uuid4()
    _run("execute", USER, alice, "alice@example.com")
    _run("execute", USER, bob, "bob@example.com")
    before = _columns()

    _alembic("0025")
    assert _columns() == before | {"phone_e164", "phone_verified_at"}
    assert _run("fetchval", "SELECT count(*) FROM users WHERE phone_e164 IS NULL") == 2
    _run("execute", SET_PHONE, alice, "+963944123456")
    with pytest.raises(asyncpg.UniqueViolationError):
        _run("execute", SET_PHONE, bob, "+963944123456")
    for bad in ("0944123456", "+0944123456", "963944123456"):
        with pytest.raises(asyncpg.CheckViolationError):
            _run("execute", SET_PHONE, bob, bad)

    _alembic("0024", down=True)
    assert _columns() == before
    assert _run("fetchval", "SELECT count(*) FROM users") == 2  # untouched
    _alembic("0025")
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0025"


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
