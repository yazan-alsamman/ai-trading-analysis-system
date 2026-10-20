"""Live signal engine.

Every minute (Celery beat, ~10 s after the boundary) the engine finds the timeframes that just
closed a bar and evaluates, once per (instrument, timeframe), every *distinct* active strategy
setup on the **last closed bar only**. New signals are stored idempotently and published to
``signals:{instrument_id}`` and to the ``user:{id}`` topic of each user whose active setup
produced them with ``notify = true``. A signal of a **private** custom strategy is never
broadcast: it goes to its owner's and the admins' ``private_signals_topic`` instead.

Global and custom strategies (``custom:<uuid>``, resolved by ``strategy_resolver``) run in the
same evaluation, on candles loaded once. A custom setup always runs its current definition and
is tagged with its current hash, so an edit becomes a new setup from the next bar on.

All functions take their session factory / Redis client as arguments, so the Celery tasks, the
tests and the CLI can drive them with their own connections.
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.notification import NotificationType
from app.models.risk import SignalPlan
from app.models.strategy import Signal, SignalSide, UserStrategy
from app.notifications import service as notifications
from app.realtime import publisher
from app.realtime.topics import private_signals_topic, signals_topic, user_topic
from app.services import indicator_service, market_service, risk_service, strategy_resolver
from app.services.market_service import floor_to_bucket
from app.services.strategy_resolver import Resolved

logger = logging.getLogger(__name__)

MAX_HISTORY = indicator_service.MAX_HISTORY
LOCK_TTL = timedelta(seconds=120)  # while an evaluation runs (a crashed worker frees it)
DONE_TTL = timedelta(hours=6)  # marker that the evaluation completed
MINUTE = timedelta(minutes=1)


# --- scheduling ------------------------------------------------------------------------------


def closed_bars(now: datetime) -> list[tuple[Timeframe, datetime]]:
    """Timeframes whose bar closed at the minute boundary at or before ``now``, with the start
    of that closed bar. ``12:00:10`` -> 1m (11:59), 5m (11:55), 15m (11:45), 1h (11:00)."""
    boundary = floor_to_bucket(now.astimezone(UTC), MINUTE)
    return [
        (tf, boundary - tf.interval)
        for tf in Timeframe
        if floor_to_bucket(boundary, tf.interval) == boundary
    ]


@dataclass(frozen=True)
class Job:
    instrument_id: uuid.UUID
    timeframe: Timeframe
    bar_time: datetime  # start of the closed bar to evaluate

    @property
    def lock_key(self) -> str:
        return (
            f"lock:signals:{self.instrument_id}:{self.timeframe.value}:{self.bar_time.isoformat()}"
        )


async def due_jobs(session: AsyncSession, now: datetime) -> list[Job]:
    """One job per (instrument, timeframe) that has an active setup and a bar that just
    closed, however many users run strategies on it."""
    bars = dict(closed_bars(now))
    rows = await session.execute(
        select(UserStrategy.instrument_id, UserStrategy.timeframe)
        .join(Instrument, Instrument.id == UserStrategy.instrument_id)
        .where(
            UserStrategy.is_active.is_(True),
            Instrument.is_active.is_(True),
            UserStrategy.timeframe.in_(list(bars)),
        )
        .distinct()
    )
    jobs = [Job(iid, tf, bars[tf]) for iid, tf in rows.all()]
    return sorted(jobs, key=lambda j: (j.timeframe.interval, str(j.instrument_id)))


async def custom_snapshots(
    session: AsyncSession, jobs: list[Job]
) -> dict[tuple[uuid.UUID, Timeframe], dict[str, dict[str, Any]]]:
    """For the beat tick: the custom setups of all due jobs resolved in one batch (one query for
    the active custom keys, then :func:`strategy_resolver.engine_snapshots`), per job."""
    if not jobs:
        return {}
    pairs = {(j.instrument_id, j.timeframe) for j in jobs}
    rows = await session.execute(
        select(UserStrategy.instrument_id, UserStrategy.timeframe, UserStrategy.strategy_key)
        .where(
            UserStrategy.is_active.is_(True),
            UserStrategy.strategy_key.startswith(strategy_resolver.KEY_PREFIX),
            UserStrategy.instrument_id.in_({p[0] for p in pairs}),
        )
        .distinct()
    )
    wanted = [(iid, tf, key) for iid, tf, key in rows.all() if (iid, tf) in pairs]
    if not wanted:
        return {}
    resolved = await strategy_resolver.engine_snapshots(session, {k for _, _, k in wanted})
    out: dict[tuple[uuid.UUID, Timeframe], dict[str, dict[str, Any]]] = defaultdict(dict)
    for iid, tf, key in wanted:
        out[(iid, tf)][key] = resolved[key]
    return dict(out)


@dataclass(frozen=True)
class Setup:
    strategy_key: str
    params_hash: str
    params: dict[str, Any]


async def active_setups(
    session: AsyncSession, instrument_id: uuid.UUID, timeframe: Timeframe
) -> list[Setup]:
    """Distinct (strategy, params) setups active on a market, across all users."""
    rows = await session.execute(
        select(UserStrategy.strategy_key, UserStrategy.params_hash, UserStrategy.params)
        .where(
            UserStrategy.instrument_id == instrument_id,
            UserStrategy.timeframe == timeframe,
            UserStrategy.is_active.is_(True),
        )
        .ext(distinct_on(UserStrategy.strategy_key, UserStrategy.params_hash))
        .order_by(UserStrategy.strategy_key, UserStrategy.params_hash)
    )
    return [Setup(k, h, p) for k, h, p in rows.all()]


# --- evaluation ------------------------------------------------------------------------------


@dataclass
class EvaluationResult:
    job: Job
    status: str = "done"  # done | locked | already_done | no_data | no_setups
    setups: int = 0
    signals: int = 0
    inserted: int = 0
    published: int = 0
    user_messages: int = 0
    plans: int = 0
    notifications: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


def signal_payload(row: dict[str, Any]) -> dict[str, Any]:
    bar_time: datetime = row["bar_time"]
    return {
        "id": str(row["id"]),
        "instrument_id": str(row["instrument_id"]),
        "timeframe": Timeframe(row["timeframe"]).value,
        "strategy_key": row["strategy_key"],
        "params": row["params"],
        "params_hash": row["params_hash"],
        "time": int(bar_time.timestamp()),
        "bar_time": bar_time.astimezone(UTC).isoformat(),
        "side": SignalSide(row["side"]).value,
        "strength": row["strength"],
        "price": row["price"],
        "reason": row["reason"],
        "details": row["details"],
    }


async def _acquire(redis: Redis, key: str, token: str) -> str | None:
    """None if acquired, else "already_done" or "locked"."""
    if await redis.set(key, token, nx=True, px=int(LOCK_TTL.total_seconds() * 1000)):
        return None
    return "already_done" if await redis.get(key) == "done" else "locked"


async def _release(redis: Redis, key: str, token: str) -> None:
    if await redis.get(key) == token:  # only our own lock
        await redis.delete(key)


def _evaluate_setups(
    df, candles: list[market_service.CandleRow], setups: list[Resolved], result: EvaluationResult
) -> list[dict[str, Any]]:
    """Run every setup on the candles; signals of the last (closed) bar only."""
    last = candles[-1]
    rows = []
    for setup in setups:
        try:
            out = setup.strategy.generate(df, setup.params)
            sig = int(out["signal"].iloc[-1])
        except Exception as exc:  # noqa: BLE001 - one bad setup must not stop the others
            logger.exception("Strategy %s failed on %s", setup.key, result.job)
            result.errors.append(f"{setup.key}: {type(exc).__name__}: {exc}")
            continue
        if sig == 0:
            continue
        rows.append(
            {
                "instrument_id": result.job.instrument_id,
                "timeframe": result.job.timeframe,
                "strategy_key": setup.key,
                "params": setup.params,
                "params_hash": setup.params_hash,
                "bar_time": last.ts,
                "side": SignalSide.buy if sig == 1 else SignalSide.sell,
                "strength": float(out["strength"].iloc[-1]),
                "price": float(last.close),
                "reason": out["reason"].iloc[-1],
                "details": out["details"].iloc[-1],
            }
        )
    return rows


@dataclass(frozen=True)
class Activation:
    id: uuid.UUID
    user_id: uuid.UUID
    strategy_key: str
    params_hash: str
    notify: bool
    risk_override: dict[str, Any] | None


async def active_activations(session: AsyncSession, job: Job) -> list[Activation]:
    rows = await session.execute(
        select(
            UserStrategy.id,
            UserStrategy.user_id,
            UserStrategy.strategy_key,
            UserStrategy.params_hash,
            UserStrategy.notify,
            UserStrategy.risk_override,
        ).where(
            UserStrategy.instrument_id == job.instrument_id,
            UserStrategy.timeframe == job.timeframe,
            UserStrategy.is_active.is_(True),
        )
    )
    return [Activation(*r) for r in rows.all()]


def _risk_history(activations, profiles, result: EvaluationResult) -> int:
    needed, seen = 1, set()
    for a in activations:
        config = risk_service.effective(a.risk_override, profiles.get(a.user_id))[0]
        key = risk_service.config_key(config)
        if key in seen:
            continue
        seen.add(key)
        try:
            needed = max(needed, risk_service.history_for(config))
        except ValueError as exc:  # a stored config the library no longer accepts
            result.errors.append(f"risk config of user {a.user_id}: {exc}")
    return needed


async def _lot_sizing(
    session: AsyncSession,
    job: Job,
    df,
    activations: list[Activation],
    profiles: dict,
    result: EvaluationResult,
) -> dict[str, risk_service.LotSizing]:
    """Account currency -> lot sizing on this instrument (empty without contract specs)."""
    try:
        instrument = await session.get(Instrument, job.instrument_id)
        if instrument is None or not instrument.has_specs:
            return {}
        entry = float(df["close"].iloc[-1])
        currencies = {
            risk_service.effective(a.risk_override, profiles.get(a.user_id))[2] for a in activations
        }
        return {
            c: await risk_service.lot_sizing(session, instrument, c, entry)
            for c in sorted(currencies)
        }
    except Exception as exc:  # noqa: BLE001 - plans fall back to the quantity only
        logger.exception("Lot sizing for %s failed", job)
        result.errors.append(f"lot sizing: {type(exc).__name__}: {exc}")
        return {}


def _plans(
    df,
    inserted: list[dict[str, Any]],
    activations: list[Activation],
    profiles: dict,
    result: EvaluationResult,
    sizing: dict[str, risk_service.LotSizing] | None = None,
) -> tuple[list[dict[str, Any]], dict[tuple[uuid.UUID, uuid.UUID], list[tuple[Activation, Any]]]]:
    """(signal_plans rows, (signal id, user id) -> [(activation, plan or None)])."""
    sizing = sizing or {}
    rows: list[dict[str, Any]] = []
    by_user: dict[tuple[uuid.UUID, uuid.UUID], list[tuple[Activation, Any]]] = defaultdict(list)
    cache: dict[tuple[str, float, int, str], dict[str, Any]] = {}
    for signal in inserted:
        side = 1 if SignalSide(signal["side"]) == SignalSide.buy else -1
        for a in activations:
            if (a.strategy_key, a.params_hash) != (signal["strategy_key"], signal["params_hash"]):
                continue
            plan = None
            try:
                config, size, currency, source = risk_service.effective(
                    a.risk_override, profiles.get(a.user_id)
                )
                key = (risk_service.config_key(config), size, side, currency)
                if key not in cache:
                    cache[key] = risk_service.plan_dict(
                        df, side, config, size, sizing.get(currency)
                    )
                plan = {
                    **cache[key],
                    "account_size": size,
                    "quote_currency": currency,
                    "risk_source": source,
                    "risk_config": config,
                }
                rows.append(
                    {
                        "signal_id": signal["id"],
                        "user_id": a.user_id,
                        "user_strategy_id": a.id,
                        "plan": plan,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - never block the signal or other users
                logger.exception("Trade plan failed for user %s on %s", a.user_id, result.job)
                result.errors.append(f"plan for user {a.user_id}: {type(exc).__name__}: {exc}")
            by_user[(signal["id"], a.user_id)].append((a, plan))
    return rows, by_user


async def evaluate(
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    job: Job,
    custom: dict[str, dict[str, Any]] | None = None,
) -> EvaluationResult:
    """Evaluate one (instrument, timeframe) on its last closed bar. Safe to call twice: a Redis
    lock stops concurrent runs and the unique constraints make the inserts idempotent.
    ``custom``: custom setups already resolved by the beat tick (key -> snapshot)."""
    started = time.perf_counter()
    result = EvaluationResult(job)
    token = uuid.uuid4().hex
    busy = await _acquire(redis, job.lock_key, token)
    if busy:
        result.status = busy
        _log(result, started)
        return result
    try:
        async with session_factory() as session:
            active = await active_setups(session, job.instrument_id, job.timeframe)
            setups, errors = await strategy_resolver.for_engine(
                session, ((s.strategy_key, s.params_hash, s.params) for s in active), custom
            )
            result.errors.extend(errors)
            result.setups = len(setups)
            activations = await active_activations(session, job)
            profiles = await risk_service.profiles_for(
                session, sorted({a.user_id for a in activations})
            )
            needed = _risk_history(activations, profiles, result)
            for s in setups:
                needed = max(needed, s.strategy.history(s.params) + 1)
            # end = bar_time: the forming bucket (and anything newer) is never loaded
            candles = await market_service.get_candles(
                session,
                job.instrument_id,
                job.timeframe,
                end=job.bar_time,
                limit=min(needed, MAX_HISTORY),
            )
            if not setups or not candles or candles[-1].ts != job.bar_time:
                # nothing to run, or the closed bar has no candle (yet): release instead of
                # marking it done, so a later run can still evaluate it
                result.status = "no_data" if setups else "no_setups"
                await _release(redis, job.lock_key, token)
                _log(result, started)
                return result
            df = indicator_service.frame(candles)
            rows = _evaluate_setups(df, candles, setups, result)
            result.signals = len(rows)
            inserted: list[dict[str, Any]] = []
            if rows:
                stmt = (
                    insert(Signal)
                    .values(rows)
                    .on_conflict_do_nothing(constraint="uq_signals_bar")
                    .returning(*Signal.__table__.columns)
                )
                inserted = [dict(r._mapping) for r in (await session.execute(stmt)).all()]
            sizing = (
                await _lot_sizing(session, job, df, activations, profiles, result)
                if inserted
                else {}
            )
            plan_rows, by_user = _plans(df, inserted, activations, profiles, result, sizing)
            if plan_rows:
                stmt = (
                    insert(SignalPlan)
                    .values(plan_rows)
                    .on_conflict_do_nothing(constraint="uq_signal_plans_signal_user_setup")
                    .returning(SignalPlan.id)
                )
                result.plans = len((await session.execute(stmt)).all())
            prepared = await _notifications(session, redis, job, inserted, by_user, setups, result)
            keys = {r["strategy_key"] for r in inserted}
            owners = await strategy_resolver.signal_owners(session, keys) if keys else {}
            await session.commit()
        result.inserted = len(inserted)
        await _publish(redis, inserted, by_user, result, owners)
        await notifications.after_commit(redis, prepared)
        await redis.set(job.lock_key, "done", px=int(DONE_TTL.total_seconds() * 1000))
    except BaseException:
        await _release(redis, job.lock_key, token)
        raise
    _log(result, started)
    return result


async def _notifications(
    session: AsyncSession,
    redis: Redis,
    job: Job,
    inserted: list[dict[str, Any]],
    by_user: dict[tuple[uuid.UUID, uuid.UUID], list[tuple[Activation, Any]]],
    setups: list[Resolved],
    result: EvaluationResult,
) -> notifications.Prepared:
    """One ``signal`` notification per (signal, user with notify = true), with the user's plans;
    stored in a savepoint so a failure never loses the signal (Y15)."""
    if not inserted:
        return notifications.Prepared()
    instrument = await session.get(Instrument, job.instrument_id)
    names = {s.key: s.name for s in setups}
    items = []
    for row in inserted:
        payload = signal_payload(row)
        for (signal_id, user_id), entries in by_user.items():
            notified = [(a, plan) for a, plan in entries if a.notify]
            if signal_id != row["id"] or not notified:
                continue
            items.append(
                notifications.NotifyItem(
                    user_id=user_id,
                    type=NotificationType.signal,
                    data={
                        "signal": payload,
                        "strategy_name": names.get(row["strategy_key"], row["strategy_key"]),
                        "instrument": {
                            "id": str(job.instrument_id),
                            "symbol": instrument.symbol if instrument else "?",
                            "price_precision": instrument.price_precision if instrument else None,
                            "quantity_precision": (
                                instrument.quantity_precision if instrument else None
                            ),
                        },
                        "user_strategy_ids": [str(a.id) for a, _ in notified],
                        "plan": notified[0][1],
                        "plans": [
                            {"user_strategy_id": str(a.id), "plan": plan} for a, plan in notified
                        ],
                    },
                    dedup_key=f"signal:{row['id']}",
                )
            )
    if not items:
        return notifications.Prepared()
    try:
        async with session.begin_nested():
            prepared = await notifications.prepare(session, redis, items)
    except Exception as exc:  # noqa: BLE001 - never block the signal
        logger.exception("Notifications for %s failed", job)
        result.errors.append(f"notifications: {type(exc).__name__}: {exc}")
        return notifications.Prepared()
    result.notifications = len(prepared.notifications)
    return prepared


async def _publish(
    redis: Redis,
    inserted: list[dict[str, Any]],
    by_user: dict[tuple[uuid.UUID, uuid.UUID], list[tuple[Activation, Any]]],
    result: EvaluationResult,
    owners: dict[str, uuid.UUID | None],
) -> None:
    """Publishing failures are logged: the signals and plans are stored and listed by the API.
    Users get one message per signal with the plans of their activations (``notify`` only).

    ``owners`` (``strategy_resolver.signal_owners``): a global or public strategy's signal is
    broadcast once on ``signals:{instrument_id}``; a private one only to its owner's and the
    admins' private topics (same frame); a deleted strategy's to no one."""
    for row in inserted:
        payload = signal_payload(row)
        key, topic = row["strategy_key"], signals_topic(row["instrument_id"])
        message = {"type": "signal", "signal": payload}
        try:
            if key not in owners:
                continue
            owner = owners[key]
            if owner is None:
                await publisher.publish(topic, message, redis)
            else:
                for audience in (owner, None):
                    via = private_signals_topic(row["instrument_id"], audience)
                    await publisher.publish(topic, message, redis, via=via)
            result.published += 1
            for (signal_id, user_id), items in by_user.items():
                if signal_id != row["id"] or owner not in (None, user_id):
                    continue
                notified = [(a, plan) for a, plan in items if a.notify]
                if not notified:
                    continue
                plans = [{"user_strategy_id": str(a.id), "plan": plan} for a, plan in notified]
                await publisher.publish(
                    user_topic(user_id),
                    {
                        "type": "signal",
                        "user_strategy_ids": [str(a.id) for a, _ in notified],
                        "signal": payload,
                        "plan": plans[0]["plan"],
                        "plans": plans,
                    },
                    redis,
                )
                result.user_messages += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Publishing signal %s failed", row["id"])
            result.errors.append(f"publish: {type(exc).__name__}: {exc}")


def _log(result: EvaluationResult, started: float) -> None:
    result.duration_ms = round((time.perf_counter() - started) * 1000, 1)
    job = result.job
    logger.info(
        "signals.evaluate instrument=%s timeframe=%s bar=%s status=%s setups=%d signals=%d "
        "inserted=%d plans=%d notifications=%d published=%d user_messages=%d errors=%d "
        "duration_ms=%.1f",
        job.instrument_id,
        job.timeframe.value,
        job.bar_time.isoformat(),
        result.status,
        result.setups,
        result.signals,
        result.inserted,
        result.plans,
        result.notifications,
        result.published,
        result.user_messages,
        len(result.errors),
        result.duration_ms,
    )
