"""Migration 0016 on a database with existing data: upgrade -> downgrade -> upgrade. Existing
risk profiles keep their values and get leverage 100; ai_setup_sizes gains source and
computed_at; ai_setup_takes is new. Nothing else changes.

Runs on its own scratch database (``<test db>_m0016``), created and dropped here, because the
shared test database is already at head.
"""

import asyncio
import json
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL

SCRATCH_URL = make_url(TEST_DATABASE_URL).set(
    database=f"{make_url(TEST_DATABASE_URL).database}_m0016"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0016_ai_risk_takes.py"


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


def _columns(table: str) -> set[str]:
    rows = _run(
        "fetch", "SELECT column_name FROM information_schema.columns WHERE table_name = $1", table
    )
    return {r["column_name"] for r in rows}


def _profiles() -> list[tuple]:
    rows = _run(
        "fetch",
        "SELECT user_id::text, account_size, quote_currency, config::text, template "
        "FROM risk_profiles ORDER BY account_size",
    )
    return [tuple(r) for r in rows]


def test_upgrade_downgrade_upgrade_with_existing_profiles(scratch) -> None:
    _alembic("0015")
    users = [
        _run(
            "fetchval",
            "INSERT INTO users (email, hashed_password, role) VALUES ($1, 'x', 'trader') "
            "RETURNING id",
            f"m16-{i}@example.com",
        )
        for i in range(3)
    ]
    config = json.dumps({"sizing": {"mode": "risk", "risk_pct": 1.0}})
    for i, user in enumerate(users):
        _run(
            "execute",
            "INSERT INTO risk_profiles (user_id, account_size, quote_currency, config, template) "
            "VALUES ($1, $2, $3, $4::jsonb, 'balanced')",
            user,
            1000.0 * (i + 1),
            ["USD", "USDT", "EUR"][i],
            config,
        )
    gold = _run("fetchval", "SELECT id FROM instruments WHERE source = 'fxpro'")
    _run(
        "execute",
        "INSERT INTO ai_setups (setup_id, instrument_id, profile, direction, state, "
        "last_payload, first_request_id, last_request_id) "
        "VALUES ('s1', $1, 'intraday', 'buy', 'ARMED', '{}', 'r', 'r')",
        gold,
    )
    before = _profiles()

    # --- upgrade ---------------------------------------------------------------------------
    _alembic("0016")
    assert _profiles() == before  # kept as they were
    leverage = _run("fetch", "SELECT leverage, balance_set_at FROM risk_profiles")
    assert [tuple(r) for r in leverage] == [(100.0, None)] * 3
    assert {"source", "computed_at"} <= _columns("ai_setup_sizes")
    assert _columns("ai_setup_takes") >= {
        "setup_id", "user_id", "taken_at", "lots", "risk_amount", "entry_price", "closed_at",
        "realized_r", "pnl", "close_reason",
    }  # fmt: skip
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE risk_profiles SET leverage = 0")
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE risk_profiles SET leverage = 20000")
    _run(
        "execute",
        "INSERT INTO ai_setup_sizes (setup_id, user_id, lots, risk_usd, feasible, inputs) "
        "VALUES ('s1', $1, 0.04, 20, true, '{}')",
        users[0],
    )
    assert _run("fetchval", "SELECT source FROM ai_setup_sizes") == "local"  # the default
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE ai_setup_sizes SET source = 'magic'")
    _run(
        "execute",
        "INSERT INTO ai_setup_takes (setup_id, user_id, lots, risk_amount) "
        "VALUES ('s1', $1, 0.04, 20)",
        users[0],
    )
    with pytest.raises(asyncpg.UniqueViolationError):  # one take per user and setup
        _run(
            "execute", "INSERT INTO ai_setup_takes (setup_id, user_id) VALUES ('s1', $1)", users[0]
        )
    index = _run(
        "fetchval", "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_ai_setup_takes_user'"
    )
    assert "(user_id, taken_at DESC)" in index
    _run("execute", "DELETE FROM users WHERE id = $1", users[0])  # takes and sizes cascade
    assert _run("fetchval", "SELECT count(*) FROM ai_setup_takes") == 0
    assert _run("fetchval", "SELECT count(*) FROM ai_setup_sizes") == 0
    before = _profiles()

    # --- downgrade ---------------------------------------------------------------------------
    _alembic("0015", down=True)
    assert "leverage" not in _columns("risk_profiles")
    assert "source" not in _columns("ai_setup_sizes")
    assert _run("fetchval", "SELECT to_regclass('ai_setup_takes')") is None
    assert _profiles() == before

    # --- upgrade again -----------------------------------------------------------------------
    _alembic("0016")
    assert _profiles() == before
    assert _run("fetchval", "SELECT min(leverage) FROM risk_profiles") == 100.0
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0016"


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
