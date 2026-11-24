"""Migration 0023 on a database with existing data: upgrade -> downgrade -> upgrade. It only
adds ``chart_analyses`` (and its two indexes): existing users and other tables are untouched, no
row is written, the checks hold, a user's deletion cascades, downgrade drops the table.

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
    database=f"{make_url(TEST_DATABASE_URL).database}_m0023"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0023_chart_analyses.py"


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


ROW = (
    "INSERT INTO chart_analyses (user_id, image_sha256, image_bytes, width, height, mime, "
    "language, model, prompt_version, status) VALUES ($1, $2, 1000, 800, 500, 'image/png', "
    "$3, 'gemini-3.6-flash', 'chart_v1', $4)"
)
USER = (
    "INSERT INTO users (id, email, hashed_password, role, is_active) "
    "VALUES ($1, $2, 'x', 'trader', true)"
)


def _tables() -> set[str]:
    rows = _run(
        "fetch", "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    return {r["table_name"] for r in rows}


def test_upgrade_downgrade_upgrade(scratch) -> None:
    _alembic("0022")
    alice, bob = uuid.uuid4(), uuid.uuid4()
    _run("execute", USER, alice, "alice@example.com")
    _run("execute", USER, bob, "bob@example.com")
    before = _tables()

    _alembic("0023")
    assert _tables() == before | {"chart_analyses"}
    assert _run("fetchval", "SELECT count(*) FROM chart_analyses") == 0
    assert _run("fetchval", "SELECT count(*) FROM users") == 2
    indexes = {
        r["indexname"]
        for r in _run(
            "fetch", "SELECT indexname FROM pg_indexes WHERE tablename = 'chart_analyses'"
        )
    }
    assert {"ix_chart_analyses_user_created", "ix_chart_analyses_user_sha"} <= indexes
    _run("execute", ROW, alice, "a" * 64, "ar", "ok")
    _run("execute", ROW, bob, "b" * 64, "en", "not_chart")
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", ROW, alice, "c" * 64, "fr", "ok")
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", ROW, alice, "c" * 64, "ar", "pending")
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        _run("execute", ROW, uuid.uuid4(), "c" * 64, "ar", "ok")
    _run("execute", "DELETE FROM users WHERE id = $1", bob)
    assert _run("fetchval", "SELECT count(*) FROM chart_analyses") == 1  # cascaded

    _alembic("0022", down=True)
    assert _tables() == before
    assert _run("fetchval", "SELECT count(*) FROM users") == 1  # untouched
    _alembic("0023")
    assert "chart_analyses" in _tables()
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0023"


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
