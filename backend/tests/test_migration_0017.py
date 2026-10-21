"""Migration 0017 on a database with existing data: upgrade -> downgrade -> upgrade. Existing
notifications and deliveries are kept (next_attempt_at null); the notification type ai_setup,
ai_setup_outbox and ai_alert_follows are new.

Runs on its own scratch database (``<test db>_m0017``), created and dropped here, because the
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
    database=f"{make_url(TEST_DATABASE_URL).database}_m0017"
)
MIGRATION = BACKEND_DIR / "alembic" / "versions" / "0017_ai_alerts_outbox.py"


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


def _notifications() -> list[tuple]:
    rows = _run(
        "fetch",
        "SELECT n.dedup_key, n.type::text, d.channel::text, d.status::text FROM notifications n "
        "LEFT JOIN notification_deliveries d ON d.notification_id = n.id ORDER BY 1, 3",
    )
    return [tuple(r) for r in rows]


def test_upgrade_downgrade_upgrade_with_existing_notifications(scratch) -> None:
    _alembic("0016")
    user = _run(
        "fetchval",
        "INSERT INTO users (email, hashed_password, role) VALUES ('m17@example.com', 'x', "
        "'trader') RETURNING id",
    )
    for i in range(3):
        note = _run(
            "fetchval",
            "INSERT INTO notifications (user_id, type, title, body, data, severity, dedup_key) "
            "VALUES ($1, 'system', 't', 'b', '{}', 'info', $2) RETURNING id",
            user,
            f"k{i}",
        )
        _run(
            "execute",
            "INSERT INTO notification_deliveries (notification_id, channel, target, status) "
            "VALUES ($1, 'telegram', '42', $2)",
            note,
            "pending" if i else "sent",
        )
    gold = _run("fetchval", "SELECT id FROM instruments WHERE source = 'fxpro'")
    _run(
        "execute",
        "INSERT INTO ai_setups (setup_id, instrument_id, profile, direction, state, "
        "last_payload, first_request_id, last_request_id) "
        "VALUES ('s1', $1, 'intraday', 'buy', 'ARMED', '{}', 'r', 'r')",
        gold,
    )
    before = _notifications()

    # --- upgrade ---------------------------------------------------------------------------
    _alembic("0017")
    assert _notifications() == before
    assert "ai_setup" in [
        r["v"]
        for r in _run("fetch", "SELECT unnest(enum_range(NULL::notification_type))::text AS v")
    ]
    assert _run("fetchval", "SELECT count(*) FROM notification_deliveries "
                "WHERE next_attempt_at IS NOT NULL") == 0  # fmt: skip
    indexes = {
        r["indexname"]: r["indexdef"]
        for r in _run(
            "fetch",
            "SELECT indexname, indexdef FROM pg_indexes WHERE indexname IN "
            "('ix_ai_setup_outbox_due', 'ix_notification_deliveries_unsent', "
            "'uq_ai_setup_outbox_setup_state', 'ix_ai_alert_follows_market')",
        )
    }
    assert len(indexes) == 4
    assert "WHERE ((status)::text = 'pending'::text)" in indexes["ix_ai_setup_outbox_due"]
    assert "COALESCE(next_attempt_at, created_at)" in indexes["ix_notification_deliveries_unsent"]
    outbox = (
        "INSERT INTO ai_setup_outbox (setup_id, from_state, to_state, at) "
        "VALUES ('s1', NULL, $1, now())"
    )
    _run("execute", outbox, "ARMED")
    assert _run("fetchval", "SELECT status FROM ai_setup_outbox") == "pending"
    with pytest.raises(asyncpg.UniqueViolationError):  # one row per (setup, state)
        _run("execute", outbox, "ARMED")
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", outbox, "PENDING")
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE ai_setup_outbox SET status = 'lost'")
    _run(
        "execute",
        "INSERT INTO ai_alert_follows (user_id, instrument_id, profile, min_grade) "
        "VALUES ($1, $2, 'intraday', 'B')",
        user,
        gold,
    )
    with pytest.raises(asyncpg.CheckViolationError):
        _run("execute", "UPDATE ai_alert_follows SET min_grade = 'E'")
    _run(
        "execute",
        "INSERT INTO notifications (user_id, type, title, body, data, severity, dedup_key) "
        "VALUES ($1, 'ai_setup', 't', 'b', '{}', 'warning', 'ai:s1:ARMED')",
        user,
    )

    # --- downgrade ---------------------------------------------------------------------------
    _alembic("0016", down=True)
    for table in ("ai_setup_outbox", "ai_alert_follows"):
        assert _run("fetchval", "SELECT to_regclass($1)", table) is None
    assert "next_attempt_at" not in _columns("notification_deliveries")
    assert _notifications() == before  # the ai_setup notification is gone, the others kept

    # --- upgrade again -----------------------------------------------------------------------
    _alembic("0017")
    assert _notifications() == before
    assert _run("fetchval", "SELECT count(*) FROM ai_setup_outbox") == 0
    assert _run("fetchval", "SELECT version_num FROM alembic_version") == "0017"


def test_migration_module_is_literal() -> None:
    source = Path(MIGRATION).read_text(encoding="utf-8")
    assert "from app" not in source and "import app" not in source
