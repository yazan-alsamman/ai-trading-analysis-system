"""Migration 0015 on a database with existing data: upgrade -> downgrade -> upgrade. It only
creates the five AI tables (with their keys, constraints and indexes); nothing else changes.

Runs on its own scratch database (``<test db>_m0015``), created and dropped here, because the
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
    database=f"{make_url(TEST_DATABASE_URL).database}_m0015"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0015_ai_setups.py"
NEW_TABLES = {
    "ai_setups",
    "ai_setup_events",
    "ai_model_versions",
    "ai_setup_sizes",
    "ai_setup_explanations",
}
INDEXES = {
    "ai_setups_pkey",
    "ix_ai_setups_open",
    "ix_ai_setups_created",
    "ai_setup_events_pkey",
    "uq_ai_setup_events_setup_state_at",
    "ai_model_versions_pkey",
    "uq_ai_model_versions_one_active",
    "ai_setup_sizes_pkey",
    "ai_setup_explanations_pkey",
}
SETUP = (
    "INSERT INTO ai_setups (setup_id, instrument_id, profile, direction, state, last_payload, "
    "first_request_id, last_request_id) VALUES ($1, $2, 'intraday', $3, $4, '{}', 'r', 'r')"
)


def _args(database: str | None = None) -> dict:
    return {
        "user": SCRATCH_URL.username,
        "password": SCRATCH_URL.password,
        "host": SCRATCH_URL.host,
        "port": SCRATCH_URL.port,
        "database": database or SCRATCH_URL.database,
    }


def _run(method: str, query: str, *args, database: str | None = None):
    async def go():
        conn = await asyncpg.connect(**_args(database))
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


def _snapshot() -> dict:
    """Row counts of the existing tables and the schema of everything but the new tables."""
    tables = [
        r["tablename"]
        for r in _run("fetch", "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        if r["tablename"] not in NEW_TABLES | {"alembic_version"}
    ]
    columns = _run(
        "fetch",
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND NOT (table_name = ANY($1)) ORDER BY 1, 2",
        list(NEW_TABLES),
    )
    return {
        "counts": {t: _run("fetchval", f'SELECT count(*) FROM "{t}"') for t in sorted(tables)},
        "columns": [tuple(r) for r in columns],
    }


def test_upgrade_downgrade_upgrade_with_existing_data(scratch) -> None:
    _alembic("0014")
    user = _run(
        "fetchval",
        "INSERT INTO users (email, hashed_password, role) VALUES ('m15@example.com', 'x', "
        "'trader') RETURNING id",
    )
    gold = _run("fetchval", "SELECT id FROM instruments WHERE source = 'fxpro'")
    _run(
        "execute",
        "INSERT INTO candles_1m (instrument_id, ts, open, high, low, close, volume) "
        "SELECT $1, ts, 2000, 2001, 1999, 2000, 1 FROM generate_series("
        "date_trunc('minute', now()) - interval '1 hour', date_trunc('minute', now()), "
        "interval '1 minute') ts",
        gold,
    )
    _run(
        "execute",
        "INSERT INTO economic_events (event_key, source, currency, title, impact, "
        "scheduled_date, fetched_at, content_hash) VALUES ('k', 'manual', 'USD', 'CPI', "
        "'high', '2026-01-13', now(), 'h')",
    )
    before = _snapshot()
    assert before["counts"]["candles_1m"] == 61 and before["counts"]["economic_events"] == 1

    # --- upgrade ---------------------------------------------------------------------------
    _alembic("0015")
    assert _snapshot() == before  # nothing else changed
    indexes = {
        r["indexname"]
        for r in _run(
            "fetch", "SELECT indexname FROM pg_indexes WHERE tablename = ANY($1)", list(NEW_TABLES)
        )
    }
    assert indexes == INDEXES
    one_active = _run(
        "fetchval",
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_ai_model_versions_one_active'",
    )
    assert "UNIQUE" in one_active and "WHERE is_active" in one_active
    _run("execute", SETUP, "s1", gold, "buy", "ARMED")
    for direction, state in (("long", "ARMED"), ("buy", "PENDING")):
        with pytest.raises(asyncpg.CheckViolationError):
            _run("execute", SETUP, "s2", gold, direction, state)
    event = (
        "INSERT INTO ai_setup_events (setup_id, from_state, to_state, at, request_id) "
        "VALUES ('s1', NULL, 'ARMED', '2026-10-19 14:15+00', 'r')"
    )
    _run("execute", event)
    with pytest.raises(asyncpg.UniqueViolationError):  # the same event again
        _run("execute", event)
    _run("execute", "INSERT INTO ai_model_versions (model_id, is_active) VALUES ('m1', true)")
    _run("execute", "INSERT INTO ai_model_versions (model_id) VALUES ('m2')")
    with pytest.raises(asyncpg.UniqueViolationError):  # one active model at most
        _run("execute", "UPDATE ai_model_versions SET is_active = true WHERE model_id = 'm2'")
    _run(
        "execute",
        "INSERT INTO ai_setup_sizes (setup_id, user_id, lots, risk_usd, feasible, inputs) "
        "VALUES ('s1', $1, 0.04, 20, true, '{}')",
        user,
    )
    _run(
        "execute",
        "INSERT INTO ai_setup_explanations (setup_id, lang, text, verified, template_used) "
        "VALUES ('s1', 'ar', 'نص', true, false)",
    )
    with pytest.raises(asyncpg.CheckViolationError):
        _run(
            "execute",
            "INSERT INTO ai_setup_explanations (setup_id, lang, text, verified, template_used) "
            "VALUES ('s1', 'fr', 'x', true, false)",
        )

    # --- downgrade ---------------------------------------------------------------------------
    _alembic("0014", down=True)
    for table in NEW_TABLES:
        assert _run("fetchval", "SELECT to_regclass($1)", table) is None
    assert _snapshot() == before

    # --- upgrade again -----------------------------------------------------------------------
    _alembic("0015")
    assert _run("fetchval", "SELECT count(*) FROM ai_setups") == 0
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0015"
    assert _snapshot() == before


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
