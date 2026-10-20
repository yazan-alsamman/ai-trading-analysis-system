"""B5 data-quality state: the beat task's reports in Redis, one log line and one admin
notification per transition, ``/health/data`` (503 when bad) and ``/health/ready`` (unchanged)."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.notification import Notification, NotificationType
from app.models.user import UserRole
from app.schemas.market import CandleIn
from app.services import data_health, market_service
from app.services.data_quality import QualityStatus
from app.tasks import celery_app
from app.tasks import data_quality as data_quality_task
from tests.market_utils import make_instrument

MIN = timedelta(minutes=1)
LOGGER = "app.services.data_health"


@pytest.fixture(autouse=True)
async def _clean_keys(redis_client: Redis):
    async def clean() -> None:
        keys = [k async for k in redis_client.scan_iter(match="dq:*")]
        if keys:
            await redis_client.delete(*keys)

    await clean()
    yield
    await clean()


@pytest.fixture
async def ready_engine():
    """/health/ready uses the app's own engine: drop its connections before this test's event
    loop closes."""
    yield
    from app.db.session import engine

    await engine.dispose()


@pytest.fixture
def monitor(monkeypatch: pytest.MonkeyPatch):
    def _monitor(value: str, enabled: bool = True) -> None:
        settings = get_settings()
        monkeypatch.setattr(settings, "data_quality_instruments", value)
        monkeypatch.setattr(settings, "data_quality_enabled", enabled)

    return _monitor


async def _write(session: AsyncSession, instrument_id, start: datetime, end: datetime) -> None:
    count = int((end - start) / MIN)
    await market_service.upsert_candles(
        session,
        instrument_id,
        [
            CandleIn(ts=start + i * MIN, open=10, high=11, low=9, close=10.5, volume=1)
            for i in range(count)
        ],
    )
    await session.commit()


async def test_missing_instrument_is_no_data(
    client: AsyncClient, session_factory, redis_client: Redis, monitor, caplog, ready_engine
) -> None:
    """Production today: fxpro:XAU/USD has no candles (here: no row at all)."""
    monitor("fxpro:XAU/USD")
    caplog.set_level(logging.INFO, logger=LOGGER)
    for _ in range(3):  # the beat task, three minutes in a row
        [report] = await data_health.run(session_factory, redis_client)
        assert report.status == QualityStatus.no_data
    assert report.failed[0].detail == "instrument not found"
    # the first check is logged once, then nothing (no spam every minute)
    lines = [r for r in caplog.records if r.name == LOGGER]
    assert len(lines) == 1 and "unknown -> no_data" in lines[0].getMessage()
    assert await redis_client.ttl("dq:report:fxpro:XAU/USD") > 200

    res = await client.get("/api/v1/health/data")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "no_data"
    [item] = body["instruments"]
    assert item["instrument"] == "fxpro:XAU/USD" and item["status"] == "no_data"
    assert item["last_closed_bar"] is None and item["lag_seconds"] is None
    assert [c["name"] for c in item["failed_checks"]] == ["no_data"]

    ready = await client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ok" and ready.json()["data"] == "no_data"
    assert '"status":"ok"' in ready.text  # what infra/deploy/remote-deploy.sh greps


async def test_instrument_without_candles(
    client: AsyncClient, session: AsyncSession, monitor
) -> None:
    """No report stored yet: /health/data computes it on the spot."""
    await make_instrument(session, symbol="XAU/USD", source="fxpro")
    monitor("fxpro:XAU/USD")
    res = await client.get("/api/v1/health/data")
    assert res.status_code == 503
    [item] = res.json()["instruments"]
    assert item["status"] == "no_data"
    assert item["failed_checks"][0]["detail"].startswith("no 1m candles between")


async def test_health_data_ok_and_disabled(
    client: AsyncClient, session: AsyncSession, monitor, ready_engine
) -> None:
    instrument = await make_instrument(session)  # binance:BTC/USDT, no calendar: 24/7
    now = market_service.floor_to_bucket(datetime.now(UTC), MIN)
    await _write(session, instrument.id, now - timedelta(hours=52), now)
    monitor("binance:BTC/USDT, binance:btc/usdt,bad-entry")
    res = await client.get("/api/v1/health/data")
    assert res.status_code == 200, res.text
    [item] = res.json()["instruments"]
    assert res.json()["status"] == "ok" and item["status"] == "ok"
    assert item["failed_checks"] == [] and item["lag_seconds"] < 120

    monitor("binance:BTC/USDT", enabled=False)
    res = await client.get("/api/v1/health/data")
    assert res.status_code == 200
    assert res.json() == {"status": "disabled", "instruments": []}
    assert (await client.get("/api/v1/health/ready")).json()["data"] == "disabled"


async def test_transitions_log_and_notify_once(
    session: AsyncSession, session_factory, redis_client: Redis, make_user, monitor, caplog
) -> None:
    admin = await make_user("dq-admin@example.com", role=UserRole.admin)
    await make_user("dq-trader@example.com")
    instrument = await make_instrument(session)
    monitor("binance:BTC/USDT")
    caplog.set_level(logging.INFO, logger=LOGGER)
    base = datetime(2026, 7, 15, 10, tzinfo=UTC)
    t0 = base + timedelta(seconds=15)  # the task runs 15 s after the boundary
    await _write(session, instrument.id, base - timedelta(hours=52), base)

    async def run(now: datetime) -> QualityStatus:
        [report] = await data_health.run(session_factory, redis_client, now)
        return report.status

    async def notifications() -> list[Notification]:
        return list(
            await session.scalars(
                select(Notification)
                .where(Notification.type == NotificationType.system)
                .order_by(Notification.created_at)
            )
        )

    def lines() -> list[str]:
        return [r.getMessage() for r in caplog.records if r.name == LOGGER]

    assert await run(t0) == QualityStatus.ok  # first check: logged, nobody notified
    assert await run(t0 + timedelta(seconds=30)) == QualityStatus.ok
    assert len(lines()) == 1 and await notifications() == []

    # the feed stops: degraded at 10:03, still degraded at 10:04 and 10:05
    for minute in (3, 4, 5):
        assert await run(t0 + timedelta(minutes=minute)) == QualityStatus.degraded
    assert len(lines()) == 2 and "ok -> degraded" in lines()[1]
    assert [r for r in caplog.records if r.name == LOGGER][-1].levelno == logging.WARNING
    [alert] = await notifications()
    assert alert.user_id == admin.id  # admins only
    assert alert.data["title"] == "Data quality: binance:BTC/USDT is degraded"
    assert "freshness" in alert.data["body"]

    # it comes back: one line, one recovery notification
    await _write(session, instrument.id, base, base + timedelta(minutes=7))
    for minute in (6, 7):
        assert await run(t0 + timedelta(minutes=minute)) == QualityStatus.ok
    assert len(lines()) == 3 and "degraded -> ok" in lines()[2]
    assert len(await notifications()) == 2
    assert (await notifications())[1].data["title"] == "Data quality: binance:BTC/USDT is ok"
    assert (
        await session.scalar(select(func.count()).select_from(Notification))
    ) == 2  # the trader got nothing


async def test_closed_market_is_not_alerted(
    session: AsyncSession, session_factory, redis_client: Redis, make_user, monitor
) -> None:
    """ok -> closed -> ok (the daily break) is logged, never sent to admins."""
    from app.services.seed_service import FXPRO_SESSION_CALENDAR

    await make_user("dq-admin2@example.com", role=UserRole.admin)
    instrument = await make_instrument(
        session, symbol="XAU/USD", source="fxpro", session_calendar=FXPRO_SESSION_CALENDAR
    )
    monitor("fxpro:XAU/USD")
    base = datetime(2026, 7, 15, 20, 50, tzinfo=UTC)  # break 20:55-22:00 UTC
    t0 = base + timedelta(seconds=15)
    await _write(session, instrument.id, base - timedelta(hours=52), base)
    statuses = []
    for now in (t0, t0 + timedelta(minutes=30)):
        [report] = await data_health.run(session_factory, redis_client, now)
        statuses.append(report.status)
    assert statuses == [QualityStatus.ok, QualityStatus.closed]
    assert (await session.scalar(select(func.count()).select_from(Notification))) == 0


async def test_system_status_includes_reports(client: AsyncClient, admin_headers, monitor) -> None:
    monitor("fxpro:XAU/USD")
    res = await client.get("/api/v1/admin/system/status", headers=admin_headers)
    assert res.status_code == 200
    [report] = res.json()["data_quality"]
    assert report["instrument"] == "fxpro:XAU/USD" and report["status"] == "no_data"
    assert "data_quality.check" in res.json()["celery"]["tasks"]


def test_beat_schedule(monitor) -> None:
    entry = celery_app.conf.beat_schedule["data-quality-check"]
    assert entry["task"] == "data_quality.check"
    assert entry["options"]["countdown"] == 15
    monitor("", enabled=True)
    assert data_quality_task.check() == {}  # nothing monitored: no database touched
