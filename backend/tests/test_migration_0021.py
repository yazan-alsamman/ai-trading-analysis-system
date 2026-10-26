"""Migration 0021 on a database with existing data: upgrade -> downgrade -> upgrade. A nullable
``instruments.cost_per_unit``; the fxpro XAU/USD gets 0.25 only while it is null (a manual value
is kept), every other instrument stays null; downgrade drops the column.

Runs on its own scratch database, created and dropped here."""

import asyncio
import importlib.util
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL

SCRATCH_URL = make_url(TEST_DATABASE_URL).set(
    database=f"{make_url(TEST_DATABASE_URL).database}_m0021"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0021_instrument_cost_per_unit.py"


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


def _cost(source: str, symbol: str):
    return _run(
        "fetchval",
        "SELECT cost_per_unit FROM instruments WHERE source = $1 AND symbol = $2",
        source,
        symbol,
    )


def test_upgrade_downgrade_upgrade(scratch) -> None:
    _alembic("0020")
    # 0013 created the fxpro XAU/USD; another instrument with data of its own
    _run(
        "execute",
        "INSERT INTO instruments (symbol, source, market, base_asset, quote_asset) "
        "VALUES ('BTC/USDT', 'binance', 'crypto', 'BTC', 'USDT')",
    )
    count = _run("fetchval", "SELECT count(*) FROM instruments")
    _alembic("0021")
    assert _cost("fxpro", "XAU/USD") == 0.25
    assert _cost("binance", "BTC/USDT") is None
    assert _run("fetchval", "SELECT count(*) FROM instruments WHERE cost_per_unit IS NOT NULL") == 1
    assert _run("fetchval", "SELECT count(*) FROM instruments") == count
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE instruments SET cost_per_unit = -0.1 WHERE symbol = 'BTC/USDT'")

    # a manual value is kept: the data step only fills a null
    _run("execute", "UPDATE instruments SET cost_per_unit = 0.3 WHERE source = 'fxpro'")
    _run("execute", _migration().SET_XAU_COST)
    assert _cost("fxpro", "XAU/USD") == 0.3

    _alembic("0020", down=True)
    columns = _run(
        "fetchval",
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'instruments' AND column_name = 'cost_per_unit'",
    )
    assert columns == 0 and _run("fetchval", "SELECT count(*) FROM instruments") == count
    _alembic("0021")
    assert _cost("fxpro", "XAU/USD") == 0.25  # null again after the downgrade: filled
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0021"


def _migration():
    spec = importlib.util.spec_from_file_location("m0021", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
