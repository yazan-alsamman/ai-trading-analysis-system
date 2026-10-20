"""B6 live calendar: the ForexFactory fetch (mocked transport, never the network), the refresh
schedule, the Redis lock, the back-off after 429/403, the state in Redis, the admin refresh."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calendar import forexfactory, service
from app.core.config import get_settings
from app.models.economic_event import EconomicEvent
from app.tasks import calendar as calendar_task
from app.tasks import celery_app

WINTER = (Path(__file__).parent / "fixtures" / "ff_calendar_week_winter.json").read_bytes()
NOW = datetime(2026, 1, 6, 12, tzinfo=UTC)
LOGGER = "app.calendar.service"


class FakeFF:
    def __init__(self) -> None:
        self.body = WINTER
        self.status = 200
        self.etag = 'W/"week-1"'
        self.delay = 0.0
        self.stream_bytes: int | None = None
        self.requests: list[httpx.Request] = []

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.status != 200:
            return httpx.Response(self.status, headers={"Retry-After": "3600"}, text="slow down")
        if request.headers.get("if-none-match") == self.etag:
            return httpx.Response(304)
        if self.stream_bytes is not None:

            async def chunks():
                for _ in range(self.stream_bytes // 1024 + 1):
                    yield b" " * 1024

            return httpx.Response(200, content=chunks())  # no Content-Length
        return httpx.Response(200, content=self.body, headers={"ETag": self.etag})


@pytest.fixture(autouse=True)
async def _clean_keys(redis_client: Redis):
    async def clean() -> None:
        keys = [k async for k in redis_client.scan_iter(match="cal:*")]
        if keys:
            await redis_client.delete(*keys)

    await clean()
    yield
    await clean()


@pytest.fixture
def ff(monkeypatch: pytest.MonkeyPatch) -> FakeFF:
    fake = FakeFF()
    monkeypatch.setattr(forexfactory, "transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(get_settings(), "calendar_enabled", True)
    return fake


async def _rows(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(EconomicEvent))


async def test_refresh_once_per_interval(
    ff: FakeFF, session: AsyncSession, session_factory, redis_client: Redis, caplog
) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    result = await service.refresh(session_factory, redis_client, now=NOW)
    assert result == {"status": "ok", "items": 17, "skipped": 1, "inserted": 16, "unchanged": 0}
    [request] = ff.requests
    assert request.url == get_settings().calendar_ff_url
    assert request.headers["user-agent"].startswith("AI-Trading-Platform-Calendar/1.0")
    assert request.headers["accept"] == "application/json"
    assert await _rows(session) == 16
    assert "calendar.refresh ok inserted=16 unchanged=0 skipped=1" in caplog.text

    # the beat checks every 15 minutes: not due before the interval (240 min), no request
    again = await service.refresh(session_factory, redis_client, now=NOW + timedelta(minutes=15))
    assert again["status"] == "not_due" and 14000 < again["next_in_seconds"] <= 14400
    assert len(ff.requests) == 1

    # due again (the key expired): a conditional GET, 304, nothing stored
    await redis_client.delete(service.DUE_KEY)
    later = await service.refresh(session_factory, redis_client, now=NOW + timedelta(hours=4))
    assert later["status"] == "not_modified"
    assert ff.requests[1].headers["if-none-match"] == ff.etag

    state = await service.state(redis_client)
    assert state["last_success"]["status"] == "not_modified" and state["last_error"] is None
    assert state["backoff_until"] is None and state["interval_minutes"] == 240


@pytest.mark.parametrize("code", [429, 403])
async def test_blocked_backs_off(
    ff: FakeFF, session: AsyncSession, session_factory, redis_client: Redis, caplog, code: int
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    ff.status = code
    result = await service.refresh(session_factory, redis_client, now=NOW)
    assert result["status"] == "blocked" and result["http_status"] == code
    assert result["until"] == (NOW + timedelta(hours=6)).isoformat()
    assert 6 * 3600 - 5 < await redis_client.ttl(service.BACKOFF_KEY) <= 6 * 3600

    # the next runs (even forced) send nothing and log nothing new
    for minutes in (15, 30, 300):
        skipped = await service.refresh(
            session_factory, redis_client, now=NOW + timedelta(minutes=minutes), force=True
        )
        assert skipped == {"status": "backoff", "until": result["until"]}
    assert len(ff.requests) == 1
    warnings = [r for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]
    assert len(warnings) == 1 and f"answered {code}" in warnings[0].getMessage()
    state = await service.state(redis_client)
    assert state["backoff_until"] == result["until"]
    assert state["last_error"]["error"].startswith(f"HTTP {code} (backing off until")

    # after the back-off: one request again
    ff.status = 200
    await redis_client.delete(service.DUE_KEY)
    done = await service.refresh(session_factory, redis_client, now=NOW + timedelta(hours=7))
    assert done["status"] == "ok" and len(ff.requests) == 2
    assert await _rows(session) == 16


async def test_malformed_items_are_skipped(
    ff: FakeFF, session: AsyncSession, session_factory, redis_client: Redis, caplog
) -> None:
    ff.body = (
        b'[{"title": "Good", "country": "USD", "date": "2026-01-06T10:00:00-05:00",'
        b' "impact": "High", "forecast": "1%", "previous": "2%"},'
        b' {"title": "No country", "date": "2026-01-06T10:00:00-05:00", "impact": "High"},'
        b' {"title": "Bad date", "country": "USD", "date": "next tuesday", "impact": "Low"}]'
    )
    result = await service.refresh(session_factory, redis_client, now=NOW)
    assert (result["inserted"], result["skipped"]) == (1, 2)
    assert "2 of 3 items skipped (first: item 1: country: Field required)" in caplog.text


async def test_unexpected_shape_fails_soft(
    ff: FakeFF, session: AsyncSession, session_factory, redis_client: Redis
) -> None:
    ff.body = b'{"error": "maintenance"}'
    result = await service.refresh(session_factory, redis_client, now=NOW)
    assert result == {"status": "error", "error": "unexpected shape: a dict, not a list"}
    assert (await service.state(redis_client))["last_error"]["error"].startswith("unexpected")
    assert await _rows(session) == 0


async def test_too_many_bytes_aborts(
    ff: FakeFF, session: AsyncSession, session_factory, redis_client: Redis, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "calendar_fetch_max_bytes", 1000)
    result = await service.refresh(session_factory, redis_client, now=NOW)  # Content-Length
    assert result == {"status": "error", "error": "body larger than 1000 bytes"}
    ff.stream_bytes = 50_000  # streamed without a length: stopped while reading
    result = await service.refresh(session_factory, redis_client, now=NOW, force=True)
    assert result == {"status": "error", "error": "body larger than 1000 bytes"}
    assert await _rows(session) == 0


async def test_timeout(
    ff: FakeFF, session_factory, redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "calendar_fetch_timeout_seconds", 0.05)
    ff.delay = 1
    result = await service.refresh(session_factory, redis_client, now=NOW)
    assert result == {"status": "error", "error": "timeout after 0.05s"}


async def test_lock_blocks_a_second_run(
    ff: FakeFF, session: AsyncSession, session_factory, redis_client: Redis
) -> None:
    ff.delay = 0.2
    first, second = await asyncio.gather(
        service.refresh(session_factory, redis_client, now=NOW, force=True),
        service.refresh(session_factory, redis_client, now=NOW, force=True),
    )
    assert sorted([first["status"], second["status"]]) == ["locked", "ok"]
    assert len(ff.requests) == 1
    assert not await redis_client.exists(service.LOCK_KEY)  # released

    await redis_client.set(service.LOCK_KEY, "another-worker", ex=60)
    assert await service.refresh(session_factory, redis_client, now=NOW, force=True) == {
        "status": "locked"
    }
    assert await redis_client.get(service.LOCK_KEY) == "another-worker"  # not ours to release


async def test_disabled_is_a_no_op(
    ff: FakeFF, session_factory, redis_client: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "calendar_enabled", False)
    assert await service.refresh(session_factory, redis_client, force=True) == {
        "status": "disabled"
    }
    assert calendar_task.refresh() == {"status": "disabled"}  # no database, no Redis
    assert ff.requests == []


def test_beat_schedule() -> None:
    entry = celery_app.conf.beat_schedule["calendar-refresh"]
    assert entry["task"] == "calendar.refresh"
    assert entry["schedule"].minute == {7, 22, 37, 52}
    # no route: the default queue (the "worker" service)
    assert not any(fnmatch("calendar.refresh", p) for p in celery_app.conf.task_routes)


async def test_admin_refresh_and_status(
    ff: FakeFF, client: AsyncClient, session: AsyncSession, admin_headers, trader_headers
) -> None:
    res = await client.post("/api/v1/admin/calendar/refresh", headers=trader_headers)
    assert res.status_code == 403
    res = await client.post("/api/v1/admin/calendar/refresh", headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "status": "ok", "items": 17, "skipped": 1, "inserted": 16, "unchanged": 0
    }  # fmt: skip
    # In tests every session shares one connection: the refresh's own session is a savepoint
    # inside the request's, which is rolled back when the request ends. Store the week here.
    await service.upsert_versions(session, forexfactory.parse(WINTER).events)
    status = (await client.get("/api/v1/admin/system/status", headers=admin_headers)).json()
    calendar = status["calendar"]
    assert calendar["enabled"] is True and calendar["rows"] == 16
    assert calendar["last_success"]["inserted"] == 16 and calendar["next_due_in_seconds"] > 0
    assert "calendar.refresh" in status["celery"]["tasks"]
