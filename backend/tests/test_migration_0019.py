"""Migration 0019 on a database with existing refresh tokens: upgrade -> downgrade -> upgrade.
Every existing row is backfilled with family_id = id (an old rotation chain counts as separate
sessions), the index exists, users get a null sessions_revoked_at; downgrade drops them.

Runs on its own scratch database (``<test db>_m0019``), created and dropped here, because the
shared test database is already at head.
"""

import asyncio
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL

SCRATCH_URL = make_url(TEST_DATABASE_URL).set(
    database=f"{make_url(TEST_DATABASE_URL).database}_m0019"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0019_refresh_token_family.py"


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


def _families() -> list[tuple]:
    rows = _run("fetch", "SELECT id, family_id FROM refresh_tokens ORDER BY created_at, id")
    return [tuple(r) for r in rows]


def test_upgrade_backfills_existing_refresh_tokens(scratch) -> None:
    _alembic("0018")
    user = _run(
        "fetchval",
        "INSERT INTO users (email, hashed_password, role) VALUES ('m19@example.com', 'x', "
        "'trader') RETURNING id",
    )
    # a rotation chain (first revoked, replaced by second) and a separate login
    first, second, other = (_run("fetchval", "SELECT gen_random_uuid()") for _ in range(3))
    for row_id, revoked, replaced in ((first, True, second), (second, False, None),
                                      (other, False, None)):  # fmt: skip
        _run(
            "execute",
            "INSERT INTO refresh_tokens (id, user_id, expires_at, revoked_at, replaced_by) "
            "VALUES ($1, $2, now() + interval '1 day', "
            "CASE WHEN $3 THEN now() END, $4)",
            row_id,
            user,
            revoked,
            replaced,
        )

    # --- upgrade ---------------------------------------------------------------------------
    _alembic("0019")
    assert all(row_id == family for row_id, family in _families())
    assert len(_families()) == 3
    assert _run(
        "fetchval",
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_refresh_tokens_family_id'",
    )
    assert _run("fetchval", "SELECT sessions_revoked_at FROM users WHERE id = $1", user) is None
    _run("execute", "UPDATE users SET sessions_revoked_at = now() WHERE id = $1", user)

    # --- downgrade ---------------------------------------------------------------------------
    _alembic("0018", down=True)
    columns = {
        r["column_name"]
        for r in _run(
            "fetch",
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name IN ('refresh_tokens', 'users')",
        )
    }
    assert "family_id" not in columns and "sessions_revoked_at" not in columns
    assert _run("fetchval", "SELECT count(*) FROM refresh_tokens") == 3  # rows kept

    # --- upgrade again -----------------------------------------------------------------------
    _alembic("0019")
    assert all(row_id == family for row_id, family in _families())
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0019"


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
