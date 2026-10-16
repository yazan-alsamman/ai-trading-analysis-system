"""Live signal engine: closed bars, distinct setups, idempotency, locking, publishing."""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import trading_strategies as ts
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.tasks.signals as signal_tasks
from app.models.candle import Timeframe
from app.models.strategy import Signal, SignalSide
from app.realtime.topics import channel_for, signals_topic, user_topic
from app.services import signal_engine
from app.services.signal_engine import Job
from tests.market_utils import make_instrument
from tests.strategy_utils import RSI1, activate, add_closes

T0 = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
# RSI(1) on these closes: nan 0 0 100 -> crosses 30 upward on the 4th bar (T0 + 3 min)
DIP = [10.0, 9.0, 8.0, 9.0]
BAR = T0 + timedelta(minutes=3)


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


# --- closed bars -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # 4h buckets are aligned to 00:00 UTC, so 12:00 also closes the 08:00 4h bar
        ("2026-03-02 12:00:10", {"1m": "11:59", "5m": "11:55", "15m": "11:45", "1h": "11:00",
                                 "4h": "08:00"}),
        ("2026-03-02 13:00:10", {"1m": "12:59", "5m": "12:55", "15m": "12:45", "1h": "12:00"}),
        ("2026-03-02 12:07:10", {"1m": "12:06"}),
        ("2026-03-02 12:15:00", {"1m": "12:14", "5m": "12:10", "15m": "12:00"}),
        ("2026-03-02 04:00:59", {"1m": "03:59", "5m": "03:55", "15m": "03:45", "1h": "03:00",
                                 "4h": "00:00"}),
    ],
)  # fmt: skip
def test_closed_bars(now: str, expected: dict[str, str]) -> None:
    bars = signal_engine.closed_bars(utc(now))
    assert {tf.value: t.strftime("%H:%M") for tf, t in bars} == expected
    for tf, bar_time in bars:  # the evaluated bar is fully in the past: never the forming one
        assert bar_time + tf.interval <= utc(now)


def test_closed_bars_at_midnight_include_4h_and_1d() -> None:
    bars = dict(signal_engine.closed_bars(utc("2026-03-02 00:00:10")))
    assert set(bars) == set(Timeframe)
    assert bars[Timeframe.d1] == utc("2026-03-01 00:00")
    assert bars[Timeframe.h4] == utc("2026-03-01 20:00")


# --- due jobs / distinct setups --------------------------------------------------------------


async def test_due_jobs_and_distinct_setups(session: AsyncSession, make_user) -> None:
    users = [await make_user(f"u{i}@example.com") for i in range(3)]
    btc = await make_instrument(session, "BTC/USDT")
    eth = await make_instrument(session, "ETH/USDT")
    dead = await make_instrument(session, "XRP/USDT", is_active=False)
    for user in users:  # 3 users, identical setup
        await activate(session, user, btc, params=RSI1)
    await activate(session, users[0], btc, params={"length": 14})  # a second setup
    await activate(session, users[1], btc, key="ma_crossover", timeframe=Timeframe.h1)
    await activate(session, users[2], eth, is_active=False)
    await activate(session, users[0], dead)

    jobs = await signal_engine.due_jobs(session, utc("2026-03-02 12:00:10"))
    assert jobs == [
        Job(btc.id, Timeframe.m1, utc("2026-03-02 11:59")),
        Job(btc.id, Timeframe.h1, utc("2026-03-02 11:00")),
    ]
    assert await signal_engine.due_jobs(session, utc("2026-03-02 12:07:10")) == [
        Job(btc.id, Timeframe.m1, utc("2026-03-02 12:06"))
    ]
    setups = await signal_engine.active_setups(session, btc.id, Timeframe.m1)
    assert sorted(s.params["length"] for s in setups) == [1, 14]  # 3 users -> computed once


# --- evaluation ------------------------------------------------------------------------------


class Listener:
    def __init__(self, redis: Redis) -> None:
        self.pubsub = redis.pubsub(ignore_subscribe_messages=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.pubsub.aclose()

    async def listen(self, *topics: str) -> None:
        await self.pubsub.subscribe(*(channel_for(t) for t in topics))

    async def messages(self, wait: float = 0.3) -> list[tuple[str, dict]]:
        out, loop = [], asyncio.get_running_loop()
        deadline = loop.time() + wait
        while loop.time() < deadline:
            msg = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=0.05)
            if msg:
                out.append((msg["channel"].removeprefix("ws:"), json.loads(msg["data"])))
        return out


async def _signals(session: AsyncSession, instrument_id) -> list[Signal]:
    rows = await session.scalars(
        select(Signal)
        .where(Signal.instrument_id == instrument_id)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


async def test_three_users_one_computation_one_row(
    session: AsyncSession, session_factory, redis_client: Redis, make_user
) -> None:
    alice, bob, carol = [await make_user(f"{n}@example.com") for n in ("alice", "bob", "carol")]
    btc = await make_instrument(session, "BTC/USDT")
    a = await activate(session, alice, btc, params=RSI1)
    b = await activate(session, bob, btc, params={"oversold": 30, "length": 1})  # same setup
    await activate(session, carol, btc, params=RSI1, notify=False)
    await add_closes(session, btc.id, T0, DIP)

    async with Listener(redis_client) as listener:
        await listener.listen(
            signals_topic(btc.id), *(user_topic(u.id) for u in (alice, bob, carol))
        )
        result = await signal_engine.evaluate(
            session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR)
        )
        messages = await listener.messages()

    assert (result.status, result.setups, result.signals, result.inserted) == ("done", 1, 1, 1)
    [row] = await _signals(session, btc.id)
    assert (row.side, row.bar_time, row.price, row.reason) == (
        SignalSide.buy,
        BAR,
        9.0,
        "rsi_cross_up_oversold",
    )
    assert row.details == {"rsi_prev": 0.0, "rsi": 100.0, "level": 30.0, "extreme": 0.0}
    assert row.params_hash == ts.params_hash("rsi_reversal", RSI1)

    by_topic = {topic: msg for topic, msg in messages}
    assert set(by_topic) == {signals_topic(btc.id), user_topic(alice.id), user_topic(bob.id)}
    signal = by_topic[signals_topic(btc.id)]["signal"]
    assert signal["id"] == str(row.id) and signal["side"] == "buy"
    assert signal["time"] == int(BAR.timestamp()) and signal["timeframe"] == "1m"
    assert by_topic[user_topic(alice.id)]["user_strategy_ids"] == [str(a.id)]
    assert by_topic[user_topic(bob.id)]["user_strategy_ids"] == [str(b.id)]
    assert (result.published, result.user_messages) == (1, 2)  # carol has notify = false


async def test_rerun_inserts_nothing(
    session: AsyncSession, session_factory, redis_client: Redis, make_user
) -> None:
    user = await make_user("rerun@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    await activate(session, user, btc, params=RSI1)
    await add_closes(session, btc.id, T0, DIP)
    job = Job(btc.id, Timeframe.m1, BAR)

    first = await signal_engine.evaluate(session_factory, redis_client, job)
    second = await signal_engine.evaluate(session_factory, redis_client, job)
    assert (first.inserted, second.status) == (1, "already_done")  # done marker in Redis
    await redis_client.delete(job.lock_key)  # even without the marker: unique key
    third = await signal_engine.evaluate(session_factory, redis_client, job)
    assert (third.status, third.signals, third.inserted, third.published) == ("done", 1, 0, 0)
    assert len(await _signals(session, btc.id)) == 1


async def test_lock_prevents_double_processing(
    session: AsyncSession, session_factory, redis_client: Redis, make_user
) -> None:
    user = await make_user("lock@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    await activate(session, user, btc, params=RSI1)
    await add_closes(session, btc.id, T0, DIP)
    job = Job(btc.id, Timeframe.m1, BAR)

    await redis_client.set(job.lock_key, "another-worker", ex=60)
    busy = await signal_engine.evaluate(session_factory, redis_client, job)
    assert busy.status == "locked" and await _signals(session, btc.id) == []
    assert await redis_client.get(job.lock_key) == "another-worker"  # not stolen

    # two concurrent runs: exactly one does the work
    await redis_client.delete(job.lock_key)
    results = []
    for _ in range(2):  # sequential awaits share the test DB connection; the lock decides
        results.append(await signal_engine.evaluate(session_factory, redis_client, job))
    assert sorted(r.status for r in results) == ["already_done", "done"]
    assert len(await _signals(session, btc.id)) == 1


async def test_lock_released_when_evaluation_fails(
    session: AsyncSession, session_factory, redis_client: Redis, make_user, monkeypatch
) -> None:
    user = await make_user("crash@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    await activate(session, user, btc, params=RSI1)
    await add_closes(session, btc.id, T0, DIP)
    job = Job(btc.id, Timeframe.m1, BAR)

    async def broken(*args, **kwargs):
        raise ConnectionError("db went away")

    monkeypatch.setattr(signal_engine.market_service, "get_candles", broken)
    with pytest.raises(ConnectionError):
        await signal_engine.evaluate(session_factory, redis_client, job)
    assert await redis_client.get(job.lock_key) is None  # a retry can run


async def test_error_in_one_strategy_does_not_block_others(
    session: AsyncSession, session_factory, redis_client: Redis, make_user, monkeypatch
) -> None:
    user = await make_user("errors@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    await activate(session, user, btc, params=RSI1)
    await activate(session, user, btc, key="ma_crossover", params={"fast": 2, "slow": 3})
    await add_closes(session, btc.id, T0, DIP)

    def boom(self, df, params=None):
        raise RuntimeError("strategy bug")

    monkeypatch.setattr(type(ts.get_strategy("ma_crossover")), "generate", boom)
    result = await signal_engine.evaluate(
        session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR)
    )
    assert result.setups == 2 and result.inserted == 1
    assert result.errors == ["ma_crossover: RuntimeError: strategy bug"]
    [row] = await _signals(session, btc.id)
    assert row.strategy_key == "rsi_reversal"


async def test_never_evaluates_the_forming_bar(
    session: AsyncSession, session_factory, redis_client: Redis, make_user
) -> None:
    user = await make_user("forming@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    await activate(session, user, btc, params=RSI1)
    # the bar after BAR is still forming and would be a sell (RSI 100 -> 0 crosses 70 down)
    await add_closes(session, btc.id, T0, [*DIP, 7.0])
    now = BAR + timedelta(minutes=1, seconds=10)  # 12:04:10: 12:03 closed, 12:04 forming
    [job] = [j for j in await signal_engine.due_jobs(session, now) if j.instrument_id == btc.id]
    assert job.bar_time == BAR
    await signal_engine.evaluate(session_factory, redis_client, job)
    assert [(s.bar_time, s.side) for s in await _signals(session, btc.id)] == [
        (BAR, SignalSide.buy)
    ]


async def test_missing_candle_for_the_closed_bar(
    session: AsyncSession, session_factory, redis_client: Redis, make_user
) -> None:
    user = await make_user("gap@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    await activate(session, user, btc, params=RSI1)
    await add_closes(session, btc.id, T0, DIP[:3])  # no candle at BAR yet
    job = Job(btc.id, Timeframe.m1, BAR)
    result = await signal_engine.evaluate(session_factory, redis_client, job)
    assert result.status == "no_data" and await redis_client.get(job.lock_key) is None
    await add_closes(session, btc.id, T0, DIP)  # it arrives late: a re-run picks it up
    assert (await signal_engine.evaluate(session_factory, redis_client, job)).inserted == 1


async def test_higher_timeframe_uses_aggregated_closed_bar(
    session: AsyncSession, session_factory, redis_client: Redis, make_user
) -> None:
    user = await make_user("5m@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    await activate(session, user, btc, params=RSI1, timeframe=Timeframe.m5)
    # 5m closes: 10, 9, 8, 9 (each bucket flat inside) -> buy on the 4th 5m bar
    closes = [c for c in DIP for _ in range(5)]
    await add_closes(session, btc.id, T0, closes)
    [job] = await signal_engine.due_jobs(session, T0 + timedelta(minutes=20, seconds=10))
    assert (job.timeframe, job.bar_time) == (Timeframe.m5, T0 + timedelta(minutes=15))
    assert (await signal_engine.evaluate(session_factory, redis_client, job)).inserted == 1


# --- schema ----------------------------------------------------------------------------------


async def test_schema_objects(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            "SELECT conname FROM pg_constraint WHERE conrelid IN "
            "('signals'::regclass, 'user_strategies'::regclass) AND contype = 'u' ORDER BY 1"
        )
    )
    assert [r[0] for r in rows] == ["uq_signals_bar", "uq_user_strategies_setup"]
    rows = await session.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_signals_market_time'")
    )
    assert "(instrument_id, timeframe, bar_time DESC)" in rows.scalar_one()
    rows = await session.execute(text("SELECT enum_range(NULL::signal_side)::text"))
    assert rows.scalar_one() == "{buy,sell}"


async def test_user_strategy_unique_setup(session: AsyncSession, make_user) -> None:
    user = await make_user("uniq@example.com")
    btc = await make_instrument(session)
    first = await activate(session, user, btc, params=RSI1)
    same = dict(reversed(list(RSI1.items())))  # other key order -> same params_hash
    with pytest.raises(IntegrityError, match="uq_user_strategies_setup"):
        async with session.begin_nested():
            session.add(
                signal_engine.UserStrategy(
                    user_id=user.id,
                    strategy_key="rsi_reversal",
                    params=same,
                    params_hash=ts.params_hash("rsi_reversal", same),
                    instrument_id=btc.id,
                    timeframe=Timeframe.m1,
                )
            )
            await session.flush()
    assert first.params_hash == ts.params_hash("rsi_reversal", same)
    total = await session.scalar(select(func.count()).select_from(signal_engine.UserStrategy))
    assert total == 1


# --- Celery wrappers -------------------------------------------------------------------------


def test_tick_schedules_evaluations_after_the_boundary(monkeypatch) -> None:
    job = Job(uuid.uuid4(), Timeframe.m1, utc("2026-03-02 11:59"))
    snapshots = {"custom:x": {"error": "test"}}
    monkeypatch.setattr(
        signal_tasks,
        "run_async",
        lambda fn: ([job], {(job.instrument_id, job.timeframe): snapshots}),
    )
    calls = []
    monkeypatch.setattr(
        signal_tasks.evaluate,
        "apply_async",
        lambda args, kwargs, eta: calls.append((args, kwargs, eta)),
    )
    assert signal_tasks.tick.run() == 1
    [(args, kwargs, eta)] = calls
    assert args == (str(job.instrument_id), "1m", "2026-03-02T11:59:00+00:00")
    assert kwargs == {"custom": snapshots}  # custom setups resolved once per beat run
    assert eta.second == 10 and eta.microsecond == 0


def test_evaluate_task_retries_when_locked(monkeypatch) -> None:
    from celery.exceptions import Retry

    job_args = (str(uuid.uuid4()), "1m", "2026-03-02T11:59:00+00:00")
    locked = signal_engine.EvaluationResult(Job(uuid.UUID(job_args[0]), Timeframe.m1, BAR))
    locked.status = "locked"
    monkeypatch.setattr(signal_tasks, "run_async", lambda fn: locked)
    with pytest.raises(Retry):
        signal_tasks.evaluate.apply(args=job_args, throw=True)
