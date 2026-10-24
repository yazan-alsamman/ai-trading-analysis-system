"""Ops visibility: /health/live, X-Request-ID, the request log line with user id, the error
counter, the admin system status, the daily summary, the Celery hooks."""

import json
import logging
import os

from httpx import AsyncClient

from app.core import ops
from app.core.logging import JsonFormatter, user_id_var
from app.tasks import ops as ops_tasks


async def test_live_and_request_id(client: AsyncClient) -> None:
    res = await client.get("/api/v1/health/live")
    assert res.json() == {"status": "ok"} and len(res.headers["X-Request-ID"]) == 32
    res = await client.get("/api/v1/health/live", headers={"X-Request-ID": "abc-123"})
    assert res.headers["X-Request-ID"] == "abc-123"
    res = await client.get("/api/v1/health/live", headers={"X-Request-ID": "bad id <script>"})
    assert res.headers["X-Request-ID"] != "bad id <script>"


async def test_request_log_line(client: AsyncClient, trader_headers, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.request")
    await client.get("/api/v1/users/me", headers={**trader_headers, "X-Request-ID": "req-1"})
    [record] = [r for r in caplog.records if r.name == "app.request"]
    assert (record.method, record.route, record.status) == ("GET", "/api/v1/users/me", 200)
    assert record.duration_ms >= 0 and record.user_id
    line = json.loads(JsonFormatter().format(record))
    assert line["request_id"] == "req-1" and line["route"] == "/api/v1/users/me"
    assert line["user_id"] == record.user_id and "Authorization" not in json.dumps(line)
    assert user_id_var.get() is None  # reset after the request


def test_json_formatter_redacts() -> None:
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "GET /ws/market?token=%s", ("abc",), None
    )
    assert "abc" not in JsonFormatter().format(record)


async def test_system_status(
    client: AsyncClient, admin_headers, trader_headers, redis_client
) -> None:
    await ops.count_error(redis_client)
    ops.task_finished("signals.tick", True)
    res = await client.get("/api/v1/admin/system/status", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["database"]["migration"] == "0019" and body["database"]["size_mb"] > 0
    assert set(body["celery"]["queues"]) == {"celery", "notifications", "backtests", "maintenance"}
    assert body["celery"]["tasks"]["signals.tick"]["seconds_ago"] is not None
    assert body["errors_last_hour"] >= 1
    assert set(body["notifications"]) == {"telegram", "email", "push"}
    assert "keys" in body["redis"] and isinstance(body["market_data"], list)
    assert (
        await client.get("/api/v1/admin/system/status", headers=trader_headers)
    ).status_code == 403


async def test_status_adds_up_api_processes(
    client: AsyncClient, admin_headers, redis_client
) -> None:
    """With several uvicorn workers each process reports its WebSocket numbers to Redis."""
    stale = [k async for k in redis_client.scan_iter(match=f"{ops.API_PREFIX}*")]
    if stale:
        await redis_client.delete(*stale)
    await ops.publish_api_process(
        redis_client, {"clients": 3, "subscriptions": 5, "topics_by_kind": {"candles": 2}}
    )
    other = {
        "host": "other",
        "pid": 7,
        "clients": 4,
        "subscriptions": 6,
        "topics_by_kind": {"candles": 1, "user": 1},
    }
    await redis_client.set(f"{ops.API_PREFIX}other:7", json.dumps(other), ex=60)
    try:
        res = await client.get("/api/v1/admin/system/status", headers=admin_headers)
        ws = res.json()["websocket"]
        assert ws["api_processes"] == 2
        assert (ws["clients"], ws["subscriptions"]) == (7, 11)
        assert ws["topics_by_kind"] == {"candles": 3, "user": 1}
        assert {p["pid"] for p in ws["processes"]} == {7, os.getpid()}
        await ops.forget_api_process(redis_client)
        assert len(await ops.api_processes(redis_client)) == 1
    finally:
        await redis_client.delete(ops.api_process_key(), f"{ops.API_PREFIX}other:7")


async def test_daily_summary(session_factory, make_user) -> None:
    await make_user("new@example.com")
    result = await ops_tasks.summary(session_factory)
    assert result["new_users"] == 1 and result["signals"] == 0
    assert set(result) >= {"deliveries_sent", "deliveries_failed", "active_subscriptions"}


def test_cors_wildcard_is_refused() -> None:
    import pytest

    from app.core.config import Settings

    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings(cors_origins="http://localhost:5173,*")


async def test_demo_page_headers(client, make_user, session) -> None:
    from tests.expert_utils import make_expert, make_person, make_plan, start_checkout

    _, eh = await make_expert(client, make_user, session)
    _, th = await make_person(make_user, session, "payer")
    plan = await make_plan(client, eh)
    checkout = await start_checkout(client, th, plan["id"])
    res = await client.get(checkout["checkout_path"])
    csp = res.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp and "form-action 'self'" in csp
    assert "script-src" not in csp and res.headers["Cache-Control"] == "no-store"


def test_docs_are_off_in_production() -> None:
    import subprocess
    import sys

    code = (
        "import os; os.environ.update(ENVIRONMENT='production', JWT_SECRET='x'*40); "
        "from app.main import app; print(app.docs_url, app.openapi_url)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.split() == ["None", "None"]


def test_uvicorn_access_log_is_off():
    """One log line per request (the middleware's), not a second one from uvicorn: the access
    logger neither propagates to the root handler nor has one of its own (pytest adds its
    capture handlers to it during tests, so those are ignored)."""
    import app.main  # noqa: F401  (configures logging on import)

    access = logging.getLogger("uvicorn.access")
    assert access.propagate is False
    assert [h for h in access.handlers if not type(h).__module__.startswith("_pytest")] == []
