"""Migration 0018 on a database with existing data: upgrade -> downgrade -> upgrade. Stored
sizes keep their rows and get the new source name ('ai-service' -> 'remote', 'local' stays);
ai_evaluation_runs is new.

Runs on its own scratch database (``<test db>_m0018``), created and dropped here, because the
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
    database=f"{make_url(TEST_DATABASE_URL).database}_m0018"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0018_ai_evaluation_runs.py"


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


def _sources() -> list[tuple]:
    rows = _run("fetch", "SELECT user_id::text, source FROM ai_setup_sizes ORDER BY lots")
    return [tuple(r) for r in rows]


def test_upgrade_downgrade_upgrade_with_existing_sizes(scratch) -> None:
    _alembic("0017")
    gold = _run("fetchval", "SELECT id FROM instruments WHERE source = 'fxpro'")
    _run(
        "execute",
        "INSERT INTO ai_setups (setup_id, instrument_id, profile, direction, state, "
        "last_payload, first_request_id, last_request_id) "
        "VALUES ('s1', $1, 'intraday', 'buy', 'ARMED', '{}', 'r', 'r')",
        gold,
    )
    users = []
    for i, source in enumerate(("ai-service", "local")):
        user = _run(
            "fetchval",
            "INSERT INTO users (email, hashed_password, role) VALUES ($1, 'x', 'trader') "
            "RETURNING id::text",
            f"m18-{i}@example.com",
        )
        users.append(user)
        _run(
            "execute",
            "INSERT INTO ai_setup_sizes (setup_id, user_id, lots, risk_usd, feasible, inputs, "
            "source) VALUES ('s1', $1::uuid, $2, 20, true, '{}', $3)",
            user,
            0.01 * (i + 1),
            source,
        )

    # --- upgrade ---------------------------------------------------------------------------
    _alembic("0018")
    assert _sources() == [(users[0], "remote"), (users[1], "local")]
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE ai_setup_sizes SET source = 'ai-service'")
    run = (
        "INSERT INTO ai_evaluation_runs (instrument_id, profile, bar_close_ts, request_id, "
        "status, reason) VALUES ($1, 'intraday', '2026-10-19T14:15:00Z', 'r', $2, 'x')"
    )
    _run("execute", run, gold, "skipped")
    assert _run("fetchval", "SELECT coverage::text FROM ai_evaluation_runs") == "{}"
    with pytest.raises(asyncpg.UniqueViolationError):  # one run per instrument, profile, bar
        _run("execute", run, gold, "ok")
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE ai_evaluation_runs SET status = 'maybe'")

    # --- downgrade ---------------------------------------------------------------------------
    _alembic("0017", down=True)
    assert _run("fetchval", "SELECT to_regclass('ai_evaluation_runs')") is None
    assert _sources() == [(users[0], "ai-service"), (users[1], "local")]

    # --- upgrade again -----------------------------------------------------------------------
    _alembic("0018")
    assert _sources() == [(users[0], "remote"), (users[1], "local")]
    assert _run("fetchval", "SELECT count(*) FROM ai_evaluation_runs") == 0
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0018"


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
