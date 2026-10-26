"""Migration 0013 on a database with existing data: instruments from before 0013 and 1m candles
older than 30 days in *compressed* chunks. Upgrade -> data step re-run -> downgrade -> upgrade.

Runs on its own scratch database (``<test db>_m0013``), created and dropped here, because the
shared test database is already at head.
"""

import asyncio
import importlib.util
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL

SCRATCH_URL = make_url(TEST_DATABASE_URL).set(
    database=f"{make_url(TEST_DATABASE_URL).database}_m0013"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0013_instrument_specs_candle_fields.py"
NEW_INSTRUMENT_COLUMNS = {
    "contract_size",
    "tick_size",
    "lot_step",
    "min_lot",
    "max_lot",
    "quote_currency",
    "margin_rate",
    "price_basis",
    "session_calendar",
    "spec_source",
    "spec_updated_at",
}
NEW_CANDLE_COLUMNS = {"spread", "source", "received_at"}


def _connect_args(url) -> dict:
    return {
        "user": url.username,
        "password": url.password,
        "host": url.host,
        "port": url.port,
        "database": url.database,
    }


async def _admin(statement: str) -> None:
    conn = await asyncpg.connect(**{**_connect_args(SCRATCH_URL), "database": "postgres"})
    try:
        await conn.execute(statement)
    finally:
        await conn.close()


class Db:
    """Small synchronous helpers over asyncpg (alembic's env.py runs its own event loop, so
    this test is synchronous)."""

    def __init__(self) -> None:
        self.args = _connect_args(SCRATCH_URL)

    def _run(self, method: str, query: str, *args):
        async def go():
            conn = await asyncpg.connect(**self.args)
            try:
                return await getattr(conn, method)(query, *args)
            finally:
                await conn.close()

        return asyncio.run(go())

    def execute(self, query: str, *args) -> str:
        return self._run("execute", query, *args)

    def fetch(self, query: str, *args) -> list:
        return self._run("fetch", query, *args)

    def value(self, query: str, *args):
        return self._run("fetchval", query, *args)

    def columns(self, table: str) -> set[str]:
        rows = self.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1", table
        )
        return {r["column_name"] for r in rows}

    def instrument(self, source: str, symbol: str):
        rows = self.fetch(
            "SELECT * FROM instruments WHERE source = $1 AND symbol = $2", source, symbol
        )
        return rows[0] if rows else None

    def compressed_chunks(self) -> int:
        return self.value(
            "SELECT count(*) FROM timescaledb_information.chunks "
            "WHERE hypertable_name = 'candles_1m' AND is_compressed"
        )

    def cagg_definitions(self) -> dict[str, str]:
        rows = self.fetch(
            "SELECT view_name, view_definition FROM timescaledb_information.continuous_aggregates"
        )
        return {r["view_name"]: r["view_definition"] for r in rows}


def _alembic(target: str, *, down: bool = False) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["keep_logging"] = True
    cfg.attributes["database_url"] = SCRATCH_URL.render_as_string(hide_password=False)
    (command.downgrade if down else command.upgrade)(cfg, target)


def _rerun_data_step() -> None:
    spec = importlib.util.spec_from_file_location("migration_0013", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async def go():
        engine = create_async_engine(
            SCRATCH_URL.render_as_string(hide_password=False), poolclass=NullPool
        )
        async with engine.begin() as conn:
            await conn.run_sync(module.seed)
        await engine.dispose()

    asyncio.run(go())


@pytest.fixture
def scratch() -> Db:
    drop = f'DROP DATABASE IF EXISTS "{SCRATCH_URL.database}" WITH (FORCE)'
    asyncio.run(_admin(drop))
    asyncio.run(_admin(f'CREATE DATABASE "{SCRATCH_URL.database}"'))
    try:
        yield Db()
    finally:
        asyncio.run(_admin(drop))


def _seed_before_0013(db: Db) -> str:
    """Instruments and 3 weeks of 1m candles, 60-40 days old (compressed), plus a recent hour."""
    eurusd = db.value(
        "INSERT INTO instruments (symbol, source, market, base_asset, quote_asset, "
        "price_precision) VALUES ('EUR/USD', 'twelvedata', 'forex', 'EUR', 'USD', 5) "
        "RETURNING id::text"
    )
    db.execute(
        "INSERT INTO instruments (symbol, source, market, base_asset, quote_asset, "
        "price_precision) VALUES ('XAU/USD', 'twelvedata', 'commodity', 'XAU', 'USD', 2), "
        "('XAU/USD', 'fxpro', 'commodity', 'XAU', 'USD', 3)"  # already there: not overwritten
    )
    for start, end in (("60 days", "40 days"), ("1 hour", "1 minute")):
        db.execute(
            "INSERT INTO candles_1m (instrument_id, ts, open, high, low, close, volume) "
            "SELECT $1::uuid, ts, 1.08, 1.09, 1.07, 1.08, 1 FROM generate_series("
            f"date_trunc('minute', now()) - interval '{start}', "
            f"date_trunc('minute', now()) - interval '{end}', interval '1 minute') ts",
            eurusd,
        )
    db.value(
        "SELECT count(compress_chunk(c)) FROM show_chunks('candles_1m', older_than => "
        "interval '30 days') c"
    )
    return eurusd


def test_upgrade_downgrade_upgrade_with_compressed_chunks(scratch: Db) -> None:
    db = scratch
    _alembic("0012")
    eurusd = _seed_before_0013(db)
    candles = db.value("SELECT count(*) FROM candles_1m")
    compressed = db.compressed_chunks()
    caggs = db.cagg_definitions()
    assert candles == 28801 + 60 and compressed >= 3 and len(caggs) == 5

    # --- upgrade ---------------------------------------------------------------------------
    _alembic("0013")
    assert NEW_INSTRUMENT_COLUMNS <= db.columns("instruments")
    assert NEW_CANDLE_COLUMNS <= db.columns("candles_1m")
    # nothing rewritten or decompressed, aggregates unchanged
    assert db.value("SELECT count(*) FROM candles_1m") == candles
    assert db.compressed_chunks() == compressed
    assert db.cagg_definitions() == caggs
    old = db.fetch(
        "SELECT spread, source, received_at FROM candles_1m "
        "WHERE ts < now() - interval '45 days' LIMIT 1"
    )
    assert tuple(old[0]) == (None, None, None)

    gold = db.instrument("fxpro", "XAU/USD")
    assert gold["price_precision"] == 3  # the existing row was kept
    assert (gold["contract_size"], gold["tick_size"], gold["lot_step"]) == (100, 0.01, 0.01)
    assert (gold["min_lot"], gold["max_lot"], gold["quote_currency"]) == (0.01, 100, "USD")
    assert (gold["price_basis"], gold["spec_source"]) == ("bid", "typical")
    assert '"America/New_York"' in gold["session_calendar"]
    eur = db.instrument("twelvedata", "EUR/USD")
    assert (eur["contract_size"], eur["tick_size"], eur["spec_source"]) == (
        100_000,
        0.00001,
        "typical",
    )
    untouched = db.instrument("twelvedata", "XAU/USD")
    assert untouched["contract_size"] is None and untouched["spec_source"] is None

    # constraints hold
    for bad in ("min_lot = 200", "tick_size = 0", "price_basis = 'ask'", "margin_rate = 2"):
        with pytest.raises(asyncpg.CheckViolationError):
            db.execute(f"UPDATE instruments SET {bad} WHERE source = 'fxpro'")

    # a bar can be written into a compressed chunk with the new columns
    db.execute(
        "INSERT INTO candles_1m AS c (instrument_id, ts, open, high, low, close, volume, "
        "spread, source, received_at) VALUES ($1::uuid, date_trunc('minute', now()) - "
        "interval '50 days', 1.08, 1.09, 1.07, 1.08, 2, 0.0001, 'test', now()) "
        "ON CONFLICT (instrument_id, ts) DO UPDATE SET spread = excluded.spread, "
        "source = excluded.source, received_at = excluded.received_at",
        eurusd,
    )
    assert db.value("SELECT count(*) FROM candles_1m WHERE spread IS NOT NULL") == 1

    # --- the data step again: fills only nulls -----------------------------------------------
    db.execute(
        "UPDATE instruments SET lot_step = 0.1, spec_source = 'manual' "
        "WHERE source = 'twelvedata' AND symbol = 'EUR/USD'"
    )
    db.execute("UPDATE instruments SET session_calendar = NULL WHERE source = 'fxpro'")
    _rerun_data_step()
    eur = db.instrument("twelvedata", "EUR/USD")
    assert (eur["lot_step"], eur["spec_source"]) == (0.1, "manual")
    assert db.instrument("fxpro", "XAU/USD")["session_calendar"] is not None
    assert db.value("SELECT count(*) FROM instruments WHERE source = 'fxpro'") == 1

    # --- downgrade ---------------------------------------------------------------------------
    _alembic("0012", down=True)
    assert not NEW_INSTRUMENT_COLUMNS & db.columns("instruments")
    assert not NEW_CANDLE_COLUMNS & db.columns("candles_1m")
    assert db.value("SELECT count(*) FROM candles_1m") == candles
    assert db.cagg_definitions() == caggs
    assert db.instrument("fxpro", "XAU/USD") is not None  # kept (its candles would cascade)

    # --- upgrade again -----------------------------------------------------------------------
    _alembic("0013")
    assert NEW_CANDLE_COLUMNS <= db.columns("candles_1m")
    assert db.instrument("fxpro", "XAU/USD")["spec_source"] == "typical"
    assert db.value("SELECT count(*) FROM candles_1m") == candles
    assert db.value("SELECT version_num FROM alembic_version") == "0013"
    # the aggregates still read the hypertable
    assert db.value("SELECT count(*) FROM candles_5m") > 0


def test_migration_module_is_literal() -> None:
    """The migration does not import application code (it must keep working as the app moves)."""
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
