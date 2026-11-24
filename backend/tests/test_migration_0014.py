"""Migration 0014 on a database with existing data: upgrade -> downgrade -> upgrade. It only
creates economic_events (with its indexes and constraints); nothing else changes.

Runs on its own scratch database (``<test db>_m0014``), created and dropped here, because the
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
    database=f"{make_url(TEST_DATABASE_URL).database}_m0014"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0014_economic_events.py"
INDEXES = {
    "economic_events_pkey",
    "uq_economic_events_key_hash",
    "ix_economic_events_key_fetched",
    "ix_economic_events_scheduled",
    "ix_economic_events_currency_impact",
}
INSERT = (
    "INSERT INTO economic_events (event_key, source, currency, title, impact, scheduled_at, "
    "scheduled_date, fetched_at, content_hash) VALUES ($1, $2, $3, 'CPI m/m', $4, "
    "'2026-01-13 13:30+00', '2026-01-13', now(), $5)"
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
    """Row counts of the existing tables and the schema of everything but the new table."""
    tables = [
        r["tablename"]
        for r in _run("fetch", "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        if r["tablename"] not in ("economic_events", "alembic_version")
    ]
    columns = _run(
        "fetch",
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name <> 'economic_events' ORDER BY 1, 2",
    )
    return {
        "counts": {t: _run("fetchval", f'SELECT count(*) FROM "{t}"') for t in sorted(tables)},
        "columns": [tuple(r) for r in columns],
    }


def test_upgrade_downgrade_upgrade_with_existing_data(scratch) -> None:
    _alembic("0013")
    _run(
        "execute",
        "INSERT INTO users (email, hashed_password, role) VALUES ('m14@example.com', 'x', "
        "'trader')",
    )
    gold = _run("fetchval", "SELECT id FROM instruments WHERE source = 'fxpro'")
    _run(
        "execute",
        "INSERT INTO candles_1m (instrument_id, ts, open, high, low, close, volume) "
        "SELECT $1, ts, 2000, 2001, 1999, 2000, 1 FROM generate_series("
        "date_trunc('minute', now()) - interval '2 hours', date_trunc('minute', now()), "
        "interval '1 minute') ts",
        gold,
    )
    before = _snapshot()
    assert before["counts"]["candles_1m"] == 121 and before["counts"]["users"] == 1

    # --- upgrade ---------------------------------------------------------------------------
    _alembic("0014")
    assert _snapshot() == before  # nothing else changed
    indexes = {
        r["indexname"]
        for r in _run(
            "fetch", "SELECT indexname FROM pg_indexes WHERE tablename = 'economic_events'"
        )
    }
    assert indexes == INDEXES
    definition = _run(
        "fetchval",
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_economic_events_key_fetched'",
    )
    assert "(event_key, fetched_at DESC)" in definition
    _run("execute", INSERT, "k" * 64, "forexfactory_live", "USD", "high", "h1")
    with pytest.raises(asyncpg.UniqueViolationError):  # same version again
        _run("execute", INSERT, "k" * 64, "forexfactory_live", "USD", "high", "h1")
    for source, currency, impact in (
        ("forexfactory_live", "USD", "extreme"),
        ("somewhere", "USD", "high"),
        ("manual", "usd", "high"),
    ):
        with pytest.raises(asyncpg.CheckViolationError):
            _run("execute", INSERT, "k" * 64, source, currency, impact, "h2")
    assert _run("fetchval", "SELECT count(*) FROM economic_events") == 1

    # --- downgrade ---------------------------------------------------------------------------
    _alembic("0013", down=True)
    assert _run("fetchval", "SELECT to_regclass('economic_events')") is None
    assert _snapshot() == before

    # --- upgrade again -----------------------------------------------------------------------
    _alembic("0014")
    assert _run("fetchval", "SELECT count(*) FROM economic_events") == 0
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0014"
    assert _snapshot() == before


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
