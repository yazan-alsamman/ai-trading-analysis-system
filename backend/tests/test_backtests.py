"""/backtests: creation checks and quotas, the run (status, progress messages, stored results),
cancellation, failures, stuck-job recovery, reads, CSV, compare and access rules."""

import asyncio
import csv
import io
import json
import random
import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
import trading_backtest as tb
from celery.exceptions import SoftTimeLimitExceeded
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.backtest import Backtest, BacktestStatus, BacktestTrade
from app.models.user import UserRole
from app.realtime.topics import channel_for, user_topic
from app.services import backtest_service, market_service
from app.services.seed_service import generate_demo_candles
from app.tasks import celery_app
from tests.api_key_utils import create_key, xkey
from tests.market_utils import make_instrument
from tests.utils import bearer

BT = "/api/v1/backtests"
END = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
MINUTES = 3_000


@pytest.fixture
async def instrument(session: AsyncSession):
    instrument = await make_instrument(session, price_precision=2, quantity_precision=4)
    candles = generate_demo_candles(instrument, minutes=MINUTES, end=END, rng=random.Random(5))
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    return instrument


@pytest.fixture
def queued(monkeypatch) -> list[uuid.UUID]:
    """Backtests handed to the task queue (recorded instead of sent to Celery)."""
    ids: list[uuid.UUID] = []
    monkeypatch.setattr(backtest_service, "enqueue", ids.append)
    return ids


@pytest.fixture
async def user(make_user):
    return await make_user("trader@example.com")


@pytest.fixture
def headers(user) -> dict[str, str]:
    return bearer(create_access_token(user))


def body(instrument, **over) -> dict:
    data = {
        "instrument_id": str(instrument.id),
        "timeframe": "1m",
        "strategy_key": "ma_crossover",
        "params": {"fast": 5, "slow": 20},
        "start": (END - timedelta(minutes=2_600)).isoformat(),
        "end": END.isoformat(),
    }
    data.update(over)
    return data


async def submit(client, headers, instrument, **over) -> str:
    res = await client.post(BT, json=body(instrument, **over), headers=headers)
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "queued"
    return res.json()["id"]


async def run(session_factory, redis_client, backtest_id) -> BacktestStatus | None:
    return await backtest_service.execute(session_factory, redis_client, uuid.UUID(backtest_id))


async def collect(pubsub, timeout: float = 1.0) -> list[dict]:
    out = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if msg is not None:
            out.append(json.loads(msg["data"]))
    return out


# --- the run ---------------------------------------------------------------------------------


async def test_end_to_end(
    client: AsyncClient,
    session: AsyncSession,
    session_factory,
    redis_client: Redis,
    instrument,
    queued,
    user,
    headers,
) -> None:
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_for(user_topic(user.id)))
    backtest_id = await submit(client, headers, instrument)
    assert queued == [uuid.UUID(backtest_id)]
    detail = (await client.get(f"{BT}/{backtest_id}", headers=headers)).json()
    assert (detail["status"], detail["progress"], detail["metrics"]) == ("queued", 0, None)

    assert await run(session_factory, redis_client, backtest_id) == BacktestStatus.completed
    messages = await collect(pubsub)
    await pubsub.aclose()
    progress = [(m["type"], m.get("status"), m.get("progress")) for m in messages]
    assert progress == [
        ("backtest_progress", "running", 5),
        ("backtest_progress", "running", 30),
        ("backtest_progress", "running", 80),
        ("backtest_completed", "completed", 100),
    ]
    assert messages[-1]["backtest_id"] == backtest_id
    assert set(messages[-1]["metrics"]) >= {"total_return_pct", "sharpe", "trades"}

    detail = (await client.get(f"{BT}/{backtest_id}", headers=headers)).json()
    assert (detail["status"], detail["progress"], detail["error"]) == ("completed", 100, None)
    assert detail["bars"] == 2_601  # both ends inclusive
    assert detail["params"] == {"fast": 5, "slow": 20, "adx_min": 0.0}
    assert detail["config"]["fee_bps"] == 10 and detail["config"]["sizing"]["mode"] == "fraction"
    assert detail["duration_ms"] >= detail["engine_ms"] >= 0

    # the same computation done directly with the library matches
    history = await market_service.get_candles(
        session, instrument.id, "1m", end=END - timedelta(minutes=2_600, microseconds=1), limit=420
    )
    rows = await market_service.candle_range(
        session, instrument.id, "1m", END - timedelta(minutes=2_600), END
    )
    direct = tb.backtest(
        backtest_service._frame(history, rows),
        "ma_crossover",
        {"fast": 5, "slow": 20},
        start=rows[0][0],
        bars_per_year=525_600,
    )
    assert detail["metrics"] == json.loads(json.dumps(direct.metrics))
    assert datetime.fromisoformat(detail["first_bar"]) == rows[0][0]
    assert datetime.fromisoformat(detail["last_bar"]) == rows[-1][0] == END
    stored = await session.scalar(
        select(func.count()).where(BacktestTrade.backtest_id == uuid.UUID(backtest_id))
    )
    assert stored == len(direct.trades) == detail["metrics"]["trades"] > 0

    # downsampled curves: at most 2,000 points, keeping the extremes
    equity = detail["equity"]
    assert len(equity) <= 2_000 < direct.bars
    values = [p["value"] for p in equity]
    assert min(values) == pytest.approx(direct.equity.min(), abs=1e-4)
    assert max(values) == pytest.approx(direct.equity.max(), abs=1e-4)
    assert min(p["value"] for p in detail["drawdown"]) == pytest.approx(
        direct.metrics["max_drawdown_pct"], abs=1e-4
    )
    assert [p["time"] for p in equity] == sorted(p["time"] for p in equity)

    markers = detail["markers"]
    assert len(markers) == 2 * stored
    assert [m["time"] for m in markers] == sorted(m["time"] for m in markers)
    first_exit = next(m for m in markers if "Long" not in m["text"])
    assert first_exit["shape"] == "arrowDown" and first_exit["text"].endswith("%")


async def test_cancel_while_queued(
    client: AsyncClient, session_factory, redis_client, instrument, queued, headers
) -> None:
    backtest_id = await submit(client, headers, instrument)
    assert (await client.delete(f"{BT}/{backtest_id}", headers=headers)).status_code == 204
    detail = (await client.get(f"{BT}/{backtest_id}", headers=headers)).json()
    assert detail["status"] == "cancelled"
    assert await run(session_factory, redis_client, backtest_id) is None  # never starts
    # a second DELETE removes it
    assert (await client.delete(f"{BT}/{backtest_id}", headers=headers)).status_code == 204
    assert (await client.get(f"{BT}/{backtest_id}", headers=headers)).status_code == 404


async def test_cancel_while_running_keeps_nothing(
    client: AsyncClient,
    session: AsyncSession,
    session_factory,
    redis_client,
    instrument,
    queued,
    user,
    headers,
    monkeypatch,
) -> None:
    """The user's DELETE arrives while the engine runs; the next checkpoint stops the task."""
    backtest_id = await submit(client, headers, instrument)

    async def delete_now() -> None:
        res = await client.delete(f"{BT}/{backtest_id}", headers=headers)
        assert res.status_code == 204

    original_set_progress = backtest_service._set_progress

    async def set_progress(factory, target, progress):
        if progress == backtest_service.PROGRESS_COMPUTED:
            await delete_now()
        return await original_set_progress(factory, target, progress)

    monkeypatch.setattr(backtest_service, "_set_progress", set_progress)
    assert await run(session_factory, redis_client, backtest_id) == BacktestStatus.cancelled
    detail = (await client.get(f"{BT}/{backtest_id}", headers=headers)).json()
    assert (detail["status"], detail["metrics"], detail["equity"]) == ("cancelled", None, [])
    count = select(func.count()).where(BacktestTrade.backtest_id == uuid.UUID(backtest_id))
    assert await session.scalar(count) == 0


async def test_cancel_racing_the_final_save(
    client: AsyncClient,
    session,
    session_factory,
    redis_client,
    instrument,
    queued,
    headers,
    monkeypatch,
) -> None:
    """Cancelled after the last checkpoint: the completing UPDATE finds no running row and the
    inserted trades are rolled back."""
    backtest_id = await submit(client, headers, instrument)
    original_set_progress = backtest_service._set_progress

    async def set_progress(factory, target, progress):
        ok = await original_set_progress(factory, target, progress)
        if progress == backtest_service.PROGRESS_COMPUTED:
            async with factory() as s:
                await s.execute(
                    update(Backtest)
                    .where(Backtest.id == target)
                    .values(status=BacktestStatus.cancelled)
                )
                await s.commit()
        return ok

    monkeypatch.setattr(backtest_service, "_set_progress", set_progress)
    assert await run(session_factory, redis_client, backtest_id) == BacktestStatus.cancelled
    count = select(func.count()).where(BacktestTrade.backtest_id == uuid.UUID(backtest_id))
    assert await session.scalar(count) == 0


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (RuntimeError("boom"), "Internal error: RuntimeError: boom"),
        (SoftTimeLimitExceeded(), "Time limit exceeded: the backtest ran longer than 300 s"),
    ],
)
async def test_failure_is_stored_and_published(
    client: AsyncClient,
    session_factory,
    redis_client,
    instrument,
    queued,
    user,
    headers,
    monkeypatch,
    error,
    message,
) -> None:
    backtest_id = await submit(client, headers, instrument)

    def broken(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(tb, "backtest", broken)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_for(user_topic(user.id)))
    assert await run(session_factory, redis_client, backtest_id) == BacktestStatus.failed
    messages = await collect(pubsub)
    await pubsub.aclose()
    assert messages[-1]["type"] == "backtest_failed"
    assert messages[-1]["error"].startswith(message)
    detail = (await client.get(f"{BT}/{backtest_id}", headers=headers)).json()
    assert detail["status"] == "failed" and detail["error"].startswith(message)
    assert detail["finished_at"] is not None


async def test_stuck_backtests_are_recovered(
    session: AsyncSession, session_factory, redis_client, instrument, user
) -> None:
    now = datetime.now(UTC)

    def make(state: BacktestStatus, started: timedelta | None, created: timedelta):
        return Backtest(
            user_id=user.id,
            instrument_id=instrument.id,
            timeframe="1m",
            strategy_key="ma_crossover",
            params={},
            params_hash="x",
            config={},
            range_start=END - timedelta(hours=1),
            range_end=END,
            status=state,
            started_at=now - started if started else None,
            created_at=now - created,
        )

    rows = {
        "dead": make(BacktestStatus.running, timedelta(minutes=10), timedelta(minutes=11)),
        "busy": make(BacktestStatus.running, timedelta(minutes=2), timedelta(minutes=3)),
        "lost": make(BacktestStatus.queued, None, timedelta(hours=7)),
        "waiting": make(BacktestStatus.queued, None, timedelta(minutes=30)),
    }
    session.add_all(rows.values())
    await session.commit()
    ids = {name: row.id for name, row in rows.items()}

    assert await backtest_service.recover_stuck(session_factory, redis_client, now) == 2
    session.expire_all()
    states = {
        name: (await session.get(Backtest, backtest_id)).status for name, backtest_id in ids.items()
    }
    assert states == {
        "dead": BacktestStatus.failed,
        "busy": BacktestStatus.running,
        "lost": BacktestStatus.failed,
        "waiting": BacktestStatus.queued,
    }
    dead = await session.get(Backtest, ids["dead"])
    assert "worker stopped" in dead.error


def test_task_routing_and_limits() -> None:
    from app.tasks import backtests as tasks

    assert celery_app.conf.task_routes["backtests.*"] == {"queue": "backtests"}
    assert celery_app.conf.beat_schedule["backtests-recover"]["task"] == "backtests.recover"
    assert tasks.run.soft_time_limit == 300 and tasks.run.time_limit == 330
    assert not tasks.run.acks_late


async def test_queue_unavailable_fails_with_503(
    client: AsyncClient, session: AsyncSession, instrument, headers, monkeypatch
) -> None:
    def down(_backtest_id):
        raise ConnectionError("broker down")

    monkeypatch.setattr(backtest_service, "enqueue", down)
    res = await client.post(BT, json=body(instrument), headers=headers)
    assert res.status_code == 503
    row = await session.scalar(select(Backtest).order_by(Backtest.created_at.desc()))
    await session.refresh(row)
    assert row.status == BacktestStatus.failed and "queue" in row.error


# --- creation checks ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("over", "fragment"),
    [
        ({"strategy_key": "nope"}, "unknown strategy"),
        ({"params": {"fast": 30, "slow": 10}}, "fast"),
        ({"config": {"fee_bps": -1}}, "config: fee_bps"),
        ({"config": {"exits": {"stop_loss_pct": 0}}}, "stop_loss_pct"),
        ({"config": {"leverage": 3}}, "unknown field"),
        ({"start": END.isoformat()}, "start must be before end"),
        ({"end": (datetime.now(UTC) + timedelta(days=1)).isoformat()}, "future"),
        ({"timeframe": "2h"}, "timeframe"),
        (
            {"start": "2020-01-01T00:00:00Z", "end": "2020-01-02T00:00:00Z"},
            "No candles in [start, end]",
        ),
    ],
)
async def test_creation_validation(
    client: AsyncClient, instrument, queued, headers, over, fragment
) -> None:
    res = await client.post(BT, json=body(instrument, **over), headers=headers)
    assert res.status_code == 422, res.text
    assert fragment in json.dumps(res.json())
    assert queued == []


async def test_unknown_instrument_404(client: AsyncClient, instrument, queued, headers) -> None:
    res = await client.post(
        BT, json=body(instrument, instrument_id=str(uuid.uuid4())), headers=headers
    )
    assert res.status_code == 404


async def test_too_many_bars(client: AsyncClient, instrument, queued, headers, monkeypatch):
    assert get_settings().backtest_max_bars == 200_000
    monkeypatch.setattr(get_settings(), "backtest_max_bars", 1_000)
    res = await client.post(BT, json=body(instrument), headers=headers)
    assert res.status_code == 422
    assert res.json()["detail"].startswith("The range has 2601 1m bars; at most 1000")


async def test_concurrent_quota(client: AsyncClient, instrument, queued, make_user) -> None:
    trader = bearer(create_access_token(await make_user("t2@example.com")))
    for _ in range(2):
        await submit(client, trader, instrument)
    res = await client.post(BT, json=body(instrument), headers=trader)
    assert res.status_code == 429
    assert "2 backtest(s) queued or running (at most 2" in res.json()["detail"]
    analyst = bearer(create_access_token(await make_user("a2@example.com", role=UserRole.analyst)))
    for _ in range(5):
        await submit(client, analyst, instrument)
    assert (await client.post(BT, json=body(instrument), headers=analyst)).status_code == 429


async def test_daily_quota_counts_finished_ones(
    client: AsyncClient, session: AsyncSession, instrument, queued, headers, monkeypatch
) -> None:
    assert get_settings().backtest_quota("trader") == (2, 30)
    assert get_settings().backtest_quota("admin") == (10, 0)
    monkeypatch.setattr(get_settings(), "backtest_daily_trader", 3)
    for _ in range(3):
        backtest_id = await submit(client, headers, instrument)
        await client.delete(f"{BT}/{backtest_id}", headers=headers)  # cancelled: not active
    res = await client.post(BT, json=body(instrument), headers=headers)
    assert res.status_code == 429
    assert "Daily backtest limit reached (3 per UTC day" in res.json()["detail"]


async def test_admin_has_no_daily_limit(
    client: AsyncClient, instrument, queued, make_user, monkeypatch
) -> None:
    admin = bearer(create_access_token(await make_user("ad@example.com", role=UserRole.admin)))
    monkeypatch.setattr(get_settings(), "backtest_concurrent_admin", 100)
    for _ in range(12):
        await submit(client, admin, instrument)


# --- reads -------------------------------------------------------------------------------


@pytest.fixture
async def completed(client, session_factory, redis_client, instrument, queued, headers) -> str:
    backtest_id = await submit(client, headers, instrument)
    assert await run(session_factory, redis_client, backtest_id) == BacktestStatus.completed
    return backtest_id


async def test_list_and_filters(client: AsyncClient, completed, instrument, headers) -> None:
    second = await submit(client, headers, instrument, strategy_key="rsi_reversal", params={})
    page = (await client.get(BT, headers=headers)).json()
    assert page["total"] == 2
    assert [i["id"] for i in page["items"]] == [second, completed]  # newest first
    done = page["items"][1]
    assert done["headline"]["trades"] > 0 and done["instrument"]["symbol"] == "BTC/USDT"
    assert page["items"][0]["headline"] is None
    for query, expected in (
        ("status=completed", [completed]),
        ("status=queued", [second]),
        ("strategy_key=rsi_reversal", [second]),
        (f"instrument_id={instrument.id}", [second, completed]),
        (f"instrument_id={uuid.uuid4()}", []),
    ):
        items = (await client.get(f"{BT}?{query}", headers=headers)).json()["items"]
        assert [i["id"] for i in items] == expected, query


async def test_trades_pages_and_csv(
    client: AsyncClient, session: AsyncSession, completed, headers
) -> None:
    total = await session.scalar(
        select(func.count()).where(BacktestTrade.backtest_id == uuid.UUID(completed))
    )
    page = (await client.get(f"{BT}/{completed}/trades?limit=3&offset=1", headers=headers)).json()
    assert page["total"] == total and [t["number"] for t in page["items"]] == [2, 3, 4]
    assert set(page["items"][0]) >= {"entry_time", "exit_reason", "net_pnl", "bars_held"}
    assert (
        await client.get(f"{BT}/{completed}/trades?limit=501", headers=headers)
    ).status_code == 422

    res = await client.get(f"{BT}/{completed}/trades.csv", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "text/csv; charset=utf-8"
    assert res.headers["content-disposition"] == (
        f'attachment; filename="backtest-{completed}-trades.csv"'
    )
    rows = list(csv.reader(io.StringIO(res.text)))
    assert rows[0] == list(backtest_service.CSV_COLUMNS)
    assert len(rows) == total + 1
    first = dict(zip(rows[0], rows[1], strict=True))
    assert first["number"] == "1" and first["side"] == "long"
    assert datetime.fromisoformat(first["entry_time"]).tzinfo is not None
    assert first["exit_reason"] in tb.EXIT_REASONS


async def test_delete_completed_removes_trades(
    client: AsyncClient, session: AsyncSession, completed, headers
) -> None:
    assert (await client.delete(f"{BT}/{completed}", headers=headers)).status_code == 204
    assert (await client.get(f"{BT}/{completed}", headers=headers)).status_code == 404
    count = select(func.count()).where(BacktestTrade.backtest_id == uuid.UUID(completed))
    assert await session.scalar(count) == 0


async def test_compare(
    client: AsyncClient,
    session_factory,
    redis_client,
    instrument,
    queued,
    completed,
    headers,
    make_user,
) -> None:
    other = await submit(
        client, headers, instrument, config={"direction": "long_short", "fee_bps": 0}
    )
    await run(session_factory, redis_client, other)
    res = await client.post(f"{BT}/compare", json={"ids": [completed, other]}, headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert [i["id"] for i in items] == [completed, other]
    assert items[1]["config"]["direction"] == "long_short"
    for item in items:
        detail = (await client.get(f"{BT}/{item['id']}", headers=headers)).json()
        assert item["metrics"] == detail["metrics"]
        assert len(item["equity"]) == len(detail["equity"])
        first = detail["equity"][0]["value"] / detail["config"]["initial_capital"] * 100
        assert item["equity"][0]["value"] == pytest.approx(first, abs=1e-3)
        last = 100 + item["metrics"]["total_return_pct"]
        assert item["equity"][-1]["value"] == pytest.approx(last, abs=1e-3)

    queued_id = await submit(client, headers, instrument)
    cases = [
        ({"ids": [completed]}, 422),
        ({"ids": [completed] * 2}, 422),
        ({"ids": [str(uuid.uuid4()) for _ in range(7)]}, 422),
        ({"ids": [completed, queued_id]}, 422),
        ({"ids": [completed, str(uuid.uuid4())]}, 404),
    ]
    for payload, code in cases:
        res = await client.post(f"{BT}/compare", json=payload, headers=headers)
        assert res.status_code == code, (payload, res.text)
    intruder = bearer(create_access_token(await make_user("x@example.com")))
    res = await client.post(f"{BT}/compare", json={"ids": [completed, other]}, headers=intruder)
    assert res.status_code == 404


# --- access ------------------------------------------------------------------------------


async def test_other_users_backtests_are_404(client: AsyncClient, completed, make_user) -> None:
    intruder = bearer(create_access_token(await make_user("x@example.com", role=UserRole.admin)))
    for method, path in (
        ("GET", f"{BT}/{completed}"),
        ("GET", f"{BT}/{completed}/trades"),
        ("GET", f"{BT}/{completed}/trades.csv"),
        ("DELETE", f"{BT}/{completed}"),
    ):
        res = await client.request(method, path, headers=intruder)
        assert res.status_code == 404, path
    assert (await client.get(BT, headers=intruder)).json()["total"] == 0


async def test_api_keys_read_with_the_scope_only(
    client: AsyncClient, completed, instrument, headers
) -> None:
    reader = (await create_key(client, headers, ["backtests:read"]))["key"]
    other = (await create_key(client, headers, ["market:read"], name="other"))["key"]
    for path in (
        BT,
        f"{BT}/{completed}",
        f"{BT}/{completed}/trades",
        f"{BT}/{completed}/trades.csv",
    ):
        assert (await client.get(path, headers=xkey(reader))).status_code == 200, path
        res = await client.get(path, headers=xkey(other))
        assert res.status_code == 403
        assert res.json()["detail"] == "This API key lacks the 'backtests:read' scope"
    for method, path, payload in (
        ("POST", BT, body(instrument)),
        ("DELETE", f"{BT}/{completed}", None),
        ("POST", f"{BT}/compare", {"ids": [completed, completed]}),
    ):
        res = await client.request(method, path, json=payload, headers=xkey(reader))
        assert res.status_code == 403, path
    assert (await client.get(BT)).status_code == 401


async def test_post_costs_5_rate_limit_units(
    client: AsyncClient, instrument, queued, headers, rate_limits
) -> None:
    res = await client.post(BT, json=body(instrument), headers=headers)
    assert res.status_code == 202
    assert res.headers["ratelimit-remaining"] == "55"


# --- migration -------------------------------------------------------------------------


async def test_migration_objects(session: AsyncSession) -> None:
    indexes = {
        row.indexname: row.indexdef
        for row in await session.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename LIKE 'backtest%'")
        )
    }
    assert "user_id, created_at DESC" in indexes["ix_backtests_user_created"]
    assert "UNIQUE" in indexes["uq_backtest_trades_number"]
    labels = list(
        await session.scalars(
            text(
                "SELECT enumlabel FROM pg_enum JOIN pg_type t ON t.oid = enumtypid "
                "WHERE typname = 'backtest_status' ORDER BY enumsortorder"
            )
        )
    )
    assert labels == ["queued", "running", "completed", "failed", "cancelled"]
    fks = set(
        await session.scalars(
            text(
                "SELECT confdeltype::text || ':' || conrelid::regclass::text FROM pg_constraint "
                "WHERE contype = 'f' AND conrelid::regclass::text LIKE 'backtest%'"
            )
        )
    )
    assert fks == {"c:backtests", "c:backtest_trades"}


def test_downsampling_bound_constant() -> None:
    assert backtest_service.MAX_CURVE_POINTS == 2_000
    assert np.iinfo(np.int32).max > get_settings().backtest_max_bars
