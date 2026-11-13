"""Migration 0024 (B13) on a database with existing AI data: upgrade -> downgrade -> upgrade.

Additive: existing setups, events and alerts are kept as they are (``exit_type``,
``exit_reason`` and ``sl`` null: a setup with a target); the outbox stays unique per (setup,
state) for state changes while stop moves (``sl`` set) are unique per (setup, at), so several
moves of one setup are kept; ``ai_volatility_daily`` is new, keyed by (instrument, day), and
cascades with its instrument. Downgrade removes the stop-move alerts, restores the old
constraint and drops what 0024 added.

Runs on its own scratch database, created and dropped here."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL

SCRATCH_URL = make_url(TEST_DATABASE_URL).set(
    database=f"{make_url(TEST_DATABASE_URL).database}_m0024"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0024_gold_levels_volatility.py"


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


SETUP = (
    "INSERT INTO ai_setups (setup_id, instrument_id, profile, direction, state, entry, sl, tp, "
    "last_payload, first_request_id, last_request_id) "
    "VALUES ($1, $2, 'intraday', 'buy', 'ACTIVE', 2400, 2395, 2410, '{}', 'r', 'r')"
)
EVENT = (
    "INSERT INTO ai_setup_events (setup_id, from_state, to_state, at, request_id) "
    "VALUES ($1, $2, $3, $4, 'r')"
)
OUTBOX = "INSERT INTO ai_setup_outbox (setup_id, from_state, to_state, at) VALUES ($1, $2, $3, $4)"
MOVE = (
    "INSERT INTO ai_setup_outbox (setup_id, from_state, to_state, at, reason, sl) "
    "VALUES ($1, 'ACTIVE', 'ACTIVE', $2, 'sl_moved', $3)"
)
VOL = (
    "INSERT INTO ai_volatility_daily (instrument_id, day, status, level, range_pct, request_id) "
    "VALUES ($1, $2, 'ok', 'normal', '{\"p50\": 0.9}', 'r')"
)
T0 = datetime(2026, 11, 13, 14, 15, tzinfo=UTC)


def _rows(table: str, order: str) -> list[tuple]:
    return [tuple(r) for r in _run("fetch", f"SELECT * FROM {table} ORDER BY {order}")]


def _columns(table: str) -> set[str]:
    rows = _run(
        "fetch", "SELECT column_name FROM information_schema.columns WHERE table_name = $1", table
    )
    return {r["column_name"] for r in rows}


def test_upgrade_downgrade_upgrade(scratch) -> None:
    _alembic("0023")
    gold = _run("fetchval", "SELECT id FROM instruments WHERE source = 'fxpro'")
    _run("execute", SETUP, "s1", gold)
    _run("execute", EVENT, "s1", None, "ARMED", T0)
    _run("execute", EVENT, "s1", "ARMED", "ACTIVE", T0 + timedelta(minutes=5))
    _run("execute", OUTBOX, "s1", None, "ARMED", T0)
    _run("execute", OUTBOX, "s1", "ARMED", "ACTIVE", T0 + timedelta(minutes=5))
    setups = _rows("ai_setups", "setup_id")
    events = _rows("ai_setup_events", "id")
    outbox = _rows("ai_setup_outbox", "id")

    _alembic("0024")
    assert {"exit_type", "exit_reason"} <= _columns("ai_setups")
    assert "sl" in _columns("ai_setup_events") and "sl" in _columns("ai_setup_outbox")
    # the existing rows are as they were, with the new columns null
    assert _rows("ai_setups", "setup_id") == [(*r, None, None) for r in setups]
    assert _run("fetchval", "SELECT count(*) FROM ai_setup_events WHERE sl IS NULL") == len(events)
    assert _run("fetchval", "SELECT count(*) FROM ai_setup_outbox WHERE sl IS NULL") == len(outbox)
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE ai_setups SET exit_type = 'breakeven'")
    _run("execute", "UPDATE ai_setups SET exit_type = 'trailing', tp = NULL")
    # state changes: still one alert per (setup, state)
    with pytest.raises(asyncpg.UniqueViolationError):
        _run("execute", OUTBOX, "s1", "ARMED", "ACTIVE", T0 + timedelta(minutes=9))
    # stop moves: one per (setup, at), several per setup
    _run("execute", MOVE, "s1", T0 + timedelta(minutes=10), 2396.0)
    _run("execute", MOVE, "s1", T0 + timedelta(minutes=15), 2398.0)
    with pytest.raises(asyncpg.UniqueViolationError):
        _run("execute", MOVE, "s1", T0 + timedelta(minutes=15), 2399.0)
    _run("execute", EVENT, "s1", "ACTIVE", "ACTIVE", T0 + timedelta(minutes=10))
    # the daily volatility: one row per (instrument, day), cascading with the instrument
    _run("execute", VOL, gold, date(2026, 11, 13))
    with pytest.raises(asyncpg.UniqueViolationError):
        _run("execute", VOL, gold, date(2026, 11, 13))
    other = _run(
        "fetchval",
        "INSERT INTO instruments (symbol, source, market, base_asset, quote_asset) "
        "VALUES ('XAG/USD', 'fxpro', 'commodity', 'XAG', 'USD') RETURNING id",
    )
    _run("execute", VOL, other, date(2026, 11, 13))
    _run("execute", "DELETE FROM instruments WHERE id = $1", other)
    assert _run("fetchval", "SELECT count(*) FROM ai_volatility_daily") == 1

    _alembic("0023", down=True)
    assert _run("fetchval", "SELECT to_regclass('ai_volatility_daily')") is None
    assert "exit_type" not in _columns("ai_setups") and "sl" not in _columns("ai_setup_outbox")
    assert _rows("ai_setup_outbox", "id") == outbox  # the stop moves are gone, the rest kept
    assert len(_rows("ai_setup_events", "id")) == len(events) + 1
    with pytest.raises(asyncpg.UniqueViolationError):  # the old constraint is back
        _run("execute", OUTBOX, "s1", "ARMED", "ACTIVE", T0 + timedelta(minutes=9))

    _alembic("0024")
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0024"
    assert _rows("ai_setup_outbox", "id") == [(*r, None) for r in outbox]
    indexes = {
        r["indexname"]
        for r in _run(
            "fetch", "SELECT indexname FROM pg_indexes WHERE tablename = 'ai_setup_outbox'"
        )
    }
    assert {"uq_ai_setup_outbox_setup_state", "uq_ai_setup_outbox_sl_moved"} <= indexes


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
