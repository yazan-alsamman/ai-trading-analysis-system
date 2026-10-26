"""Migration 0022 on a database with existing data: upgrade -> downgrade -> upgrade. It only
adds ``signal_outcomes`` (and its index): existing signals and other tables are untouched, no
row is written, a signal's deletion cascades, downgrade drops the table.

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
    database=f"{make_url(TEST_DATABASE_URL).database}_m0022"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0022_signal_outcomes.py"


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


SIGNAL = (
    "INSERT INTO signals (id, instrument_id, timeframe, strategy_key, params, params_hash, "
    "bar_time, side, strength, price, reason, details) VALUES ($1, $2, '1m', 'ma_crossover', "
    "'{}', 'h', '2026-03-02T12:00:00Z', 'buy', 0.7, 100, 'test', '{}')"
)


def _tables() -> set[str]:
    rows = _run(
        "fetch", "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    return {r["table_name"] for r in rows}


def test_upgrade_downgrade_upgrade(scratch) -> None:
    _alembic("0021")
    instrument = uuid.uuid4()
    _run(
        "execute",
        "INSERT INTO instruments (id, symbol, source, market, base_asset, quote_asset) "
        "VALUES ($1, 'BTC/USDT', 'binance', 'crypto', 'BTC', 'USDT')",
        instrument,
    )
    old, new = uuid.uuid4(), uuid.uuid4()
    _run("execute", SIGNAL, old, instrument)
    before = _tables()

    _alembic("0022")
    assert _tables() == before | {"signal_outcomes"}
    assert _run("fetchval", "SELECT count(*) FROM signal_outcomes") == 0  # filled by the task
    assert _run("fetchval", "SELECT count(*) FROM signals") == 1
    index = _run(
        "fetchval",
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_signal_outcomes_resolved_at'",
    )
    assert "(resolved_at)" in index
    _run(
        "execute",
        "INSERT INTO signal_outcomes (signal_id, horizon_bars, correct, cost_per_unit) "
        "VALUES ($1, 10, true, 0)",
        old,
    )
    with pytest.raises(asyncpg.CheckViolationError):
        _run(
            "execute",
            "INSERT INTO signal_outcomes (signal_id, horizon_bars, cost_per_unit) "
            "VALUES ($1, 0, 0)",
            old,
        )
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        _run(
            "execute",
            "INSERT INTO signal_outcomes (signal_id, horizon_bars, cost_per_unit) "
            "VALUES ($1, 10, 0)",
            new,
        )
    _run("execute", "DELETE FROM signals WHERE id = $1", old)
    assert _run("fetchval", "SELECT count(*) FROM signal_outcomes") == 0  # cascaded

    _run("execute", SIGNAL, new, instrument)
    _alembic("0021", down=True)
    assert _tables() == before
    assert _run("fetchval", "SELECT count(*) FROM signals") == 1  # untouched
    _alembic("0022")
    assert "signal_outcomes" in _tables()
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0022"


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
