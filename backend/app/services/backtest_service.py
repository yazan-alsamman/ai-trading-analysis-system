"""Backtests: validation and quotas at creation, the run itself (Celery task on the
``backtests`` queue, app/tasks/backtests.py), reads, chart markers, CSV export and comparison.

Status transitions are atomic ``UPDATE ... WHERE status = ...`` statements, so a cancel
(``DELETE``) racing with the worker always wins cleanly: the worker checks at each checkpoint
(after loading, after computing, when saving) and stops without storing anything.
"""

import asyncio
import csv
import io
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import trading_backtest as tb
import trading_strategies as ts
from celery.exceptions import SoftTimeLimitExceeded
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from trading_backtest.metrics import unix_seconds

from app.core.config import get_settings
from app.models.backtest import ACTIVE_STATUSES, Backtest, BacktestStatus, BacktestTrade
from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.user import User
from app.realtime import publisher
from app.realtime.topics import user_topic
from app.schemas.backtests import HEADLINE_METRICS, BacktestCreate
from app.services import market_service, risk_service, strategy_resolver

logger = logging.getLogger(__name__)

MAX_CURVE_POINTS = 2000
PROGRESS_RUNNING, PROGRESS_LOADED, PROGRESS_COMPUTED = 5, 30, 80
QUEUED_TOO_LONG = timedelta(hours=6)
SNAPSHOT_KEY = "strategy"  # config.strategy: the custom strategy's snapshot
COST_KEY = "cost_per_unit"  # config.cost_per_unit: the instrument's fixed cost, set by the server
PROFILE_KEY = "risk_profile"  # config.risk_profile: true in a request, the profile's snapshot after
RISK_KEYS = ("stop", "trailing", "take_profit", "sizing", "guards")
SECONDS_PER_YEAR = 365 * 24 * 3600

ENTRY_COLOR, EXIT_WIN_COLOR, EXIT_LOSS_COLOR = "#2196F3", "#26a69a", "#ef5350"
EXIT_LABELS = {
    "opposite_signal": "Exit",
    "stop_loss": "SL",
    "trailing_stop": "Trail",
    "breakeven_stop": "BE",
    "take_profit": "TP",
    "partial_tp": "Partial TP",
    "max_bars": "Time",
    "end_of_data": "End",
}
CSV_COLUMNS = (
    "number",
    "side",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "quantity",
    "gross_pnl",
    "fees",
    "net_pnl",
    "return_pct",
    "bars_held",
    "entry_reason",
    "exit_reason",
    "initial_stop",
    "risk_amount",
    "r_multiple",
)


class BacktestError(Exception):
    """A failure with a message meant for the user."""


def time_limit_message(seconds: int) -> str:
    return (
        f"Time limit exceeded: the backtest ran longer than {seconds} s "
        "(shorten the range or use a higher timeframe)"
    )


def bars_per_year(timeframe: Timeframe) -> float:
    return SECONDS_PER_YEAR / timeframe.interval.total_seconds()


async def _publish(redis: Redis | None, user_id: uuid.UUID, payload: dict[str, Any]) -> None:
    try:
        await publisher.publish(user_topic(user_id), payload, redis)
    except Exception:  # noqa: BLE001 - progress messages must never fail a backtest
        logger.exception("Publishing %s for user %s failed", payload.get("type"), user_id)


async def publish_progress(
    redis: Redis | None, user_id: uuid.UUID, backtest_id: uuid.UUID, state: str, progress: int
) -> None:
    await _publish(
        redis,
        user_id,
        {
            "type": "backtest_progress",
            "backtest_id": str(backtest_id),
            "status": state,
            "progress": progress,
        },
    )


# --- creation ----------------------------------------------------------------------------------


async def _lock_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Serialize quota checks of one user (two POSTs at once cannot both slip through)."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"backtests:{user_id}"},
    )


async def check_quota(session: AsyncSession, user: User) -> None:
    concurrent, daily = get_settings().backtest_quota(user.role.value)
    active = await session.scalar(
        select(func.count())
        .select_from(Backtest)
        .where(Backtest.user_id == user.id, Backtest.status.in_(ACTIVE_STATUSES))
    )
    if active >= concurrent:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You already have {active} backtest(s) queued or running (at most {concurrent} "
            "for your role); wait for one to finish or cancel it",
        )
    if daily:
        day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today = await session.scalar(
            select(func.count())
            .select_from(Backtest)
            .where(Backtest.user_id == user.id, Backtest.created_at >= day_start)
        )
        if today >= daily:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Daily backtest limit reached ({daily} per UTC day for your role); "
                "try again after 00:00 UTC",
            )


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def strategy_snapshot(resolved: strategy_resolver.Resolved) -> dict[str, Any]:
    """What a custom strategy was when the backtest was created (stored in ``config.strategy``),
    so results stay reproducible after the strategy is edited or deleted."""
    assert resolved.custom is not None and resolved.snapshot is not None
    return {
        "key": resolved.key,
        "name": resolved.custom.name,
        "version": resolved.custom.version,
        "definition_hash": resolved.params_hash,
        **resolved.snapshot,
    }


def strategy_of(row: Backtest) -> tuple[ts.Strategy, tb.BacktestConfig]:
    """The strategy a backtest runs (custom ones from their snapshot) and its engine config."""
    config = dict(row.config)
    snapshot = config.pop(SNAPSHOT_KEY, None)
    config.pop(PROFILE_KEY, None)
    if snapshot is not None:
        strategy = ts.from_snapshot(snapshot, key=row.strategy_key, title=snapshot.get("name"))
    else:
        strategy = ts.get_strategy(row.strategy_key)
    return strategy, tb.BacktestConfig.from_dict(config)


async def capital_conversion(
    session: AsyncSession, instrument: Instrument, account_currency: str
) -> dict[str, Any] | None:
    """How the engine converts a capital in ``account_currency`` (the profile's) into the
    instrument's quote currency (``tb.Conversion``): None when they are the same currency (USD,
    USDT and USDC count as one), ``inverse_price`` when the account currency is the base
    (USD/JPY for a USD account: 1 JPY = 1 / price USD at every fill), otherwise the latest
    rate of a matching market, fixed for the run. 422 when there is none (never assumed 1)."""
    quote, base = instrument.pnl_currency, instrument.base_asset
    usd = risk_service._usd  # noqa: SLF001 - the same alias rule as live sizing
    if usd(quote) == usd(account_currency):
        return None
    if usd(base) == usd(account_currency):
        return {"type": "inverse_price"}
    rate, _ = await risk_service.conversion_rate(session, instrument, account_currency, 1.0)
    if rate is None:
        raise _unprocessable(
            f"No conversion rate from {quote} to {account_currency} (the risk profile's "
            f"currency): set config.initial_capital, in {quote}"
        )
    return {"type": "fixed", "rate": rate}


async def _with_profile(
    session: AsyncSession, user: User, requested: dict[str, Any], instrument: Instrument
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The caller's risk profile under the request: its rules, fee and account size, unless the
    request sets them (a Y11 ``exits.stop_loss_pct`` / ``take_profit_pct`` replaces the
    profile's stop / take profit). Returns the config and the profile's snapshot.

    The profile's account size is in the profile's currency: when that is not the instrument's
    quote currency, the config gets the engine's ``conversion`` (``capital_conversion``)."""
    profile = await risk_service.get_or_create(session, user)
    rules = {k: v for k, v in profile.config.items() if k in RISK_KEYS}
    exits = requested.get("exits") or {}
    if isinstance(exits, dict):
        if exits.get("stop_loss_pct") is not None:
            rules.pop("stop", None)
        if exits.get("take_profit_pct") is not None:
            rules.pop("take_profit", None)
    merged = {
        **rules,
        "fee_bps": profile.config.get("fee_bps", 10.0),
        "initial_capital": profile.account_size,
        **requested,
    }
    meta = {
        "template": profile.template,
        "account_size": profile.account_size,
        "quote_currency": profile.quote_currency,
        "config": profile.config,
        "updated_at": profile.updated_at.isoformat(),
    }
    if "initial_capital" not in requested and "conversion" not in requested:
        conversion = await capital_conversion(session, instrument, profile.quote_currency)
        if conversion is not None:
            merged["conversion"] = conversion
            meta["conversion"] = {
                "account_currency": profile.quote_currency,
                "quote_currency": instrument.pnl_currency,
                **conversion,
            }
    return merged, meta


async def create(session: AsyncSession, user: User, data: BacktestCreate) -> Backtest:
    """Validate everything that can be checked now and store the backtest as ``queued``."""
    resolved = await strategy_resolver.get(session, data.strategy_key, user, data.params)
    requested = dict(data.config or {})
    if SNAPSHOT_KEY in requested:
        raise _unprocessable(f"config: {SNAPSHOT_KEY} is set by the server")
    use_profile = requested.pop(PROFILE_KEY, False)
    if not isinstance(use_profile, bool):
        raise _unprocessable(f"config: {PROFILE_KEY} must be true or false")
    if COST_KEY in requested:
        raise _unprocessable(f"config: {COST_KEY} is set by the server (from the instrument)")
    profile_meta = None
    instrument = await market_service.get_instrument_or_404(session, data.instrument_id)
    if use_profile:
        requested, profile_meta = await _with_profile(session, user, requested, instrument)
    if instrument.cost_per_unit is not None:
        # the instrument's fixed cost (XAU/USD 0.25 per oz, Fadi) replaces fee_bps and
        # slippage_bps for this run: the engine ignores them (docs/risk-management.md)
        requested[COST_KEY] = instrument.cost_per_unit
    try:
        config = tb.BacktestConfig.from_dict(requested)
    except tb.ConfigError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            risk_service.config_errors(exc, ("body", "config")),
        ) from None
    if data.end > datetime.now(UTC):
        raise _unprocessable("end must not be in the future")

    await _lock_user(session, user.id)
    await check_quota(session, user)
    bars = await market_service.count_candles(
        session, data.instrument_id, data.timeframe, data.start, data.end
    )
    maximum = get_settings().backtest_max_bars
    if bars == 0:
        raise _unprocessable("No candles in [start, end] for this instrument and timeframe")
    if bars > maximum:
        raise _unprocessable(
            f"The range has {bars} {data.timeframe.value} bars; at most {maximum} per backtest "
            "(shorten the range or use a higher timeframe)"
        )
    stored = config.to_dict()
    if profile_meta is not None:
        stored[PROFILE_KEY] = profile_meta
    if resolved.custom is not None:
        stored[SNAPSHOT_KEY] = strategy_snapshot(resolved)
    row = Backtest(
        user_id=user.id,
        instrument_id=data.instrument_id,
        timeframe=data.timeframe,
        strategy_key=resolved.key,
        params=resolved.params,
        params_hash=resolved.params_hash,
        config=stored,
        range_start=data.start,
        range_end=data.end,
        status=BacktestStatus.queued,
    )
    session.add(row)
    await session.commit()
    return row


def _enqueue_celery(backtest_id: uuid.UUID) -> None:
    from app.tasks.backtests import run  # the API process only needs Celery to send

    run.apply_async((str(backtest_id),), queue="backtests")


# Replaced in tests (they run backtests inline).
enqueue: Callable[[uuid.UUID], None] = _enqueue_celery


async def submit(session: AsyncSession, row: Backtest) -> None:
    """Queue the run; if the broker is unreachable the backtest is failed and 503 raised."""
    try:
        await asyncio.to_thread(enqueue, row.id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not queue backtest %s", row.id)
        await session.execute(
            update(Backtest)
            .where(Backtest.id == row.id)
            .values(
                status=BacktestStatus.failed,
                error="Could not queue the backtest (task queue unavailable)",
                finished_at=func.now(),
            )
        )
        await session.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Backtests are temporarily unavailable"
        ) from exc


# --- execution ---------------------------------------------------------------------------------


async def _set_progress(
    factory: async_sessionmaker[AsyncSession], backtest_id: uuid.UUID, progress: int
) -> bool:
    """Record progress; False if the backtest is no longer running (cancelled)."""
    async with factory() as session:
        found = await session.scalar(
            update(Backtest)
            .where(Backtest.id == backtest_id, Backtest.status == BacktestStatus.running)
            .values(progress=progress)
            .returning(Backtest.id)
        )
        await session.commit()
    return found is not None


async def fail(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis | None,
    backtest_id: uuid.UUID,
    message: str,
) -> bool:
    """Mark a queued/running backtest failed (finished ones are left alone)."""
    async with factory() as session:
        row = (
            await session.execute(
                update(Backtest)
                .where(Backtest.id == backtest_id, Backtest.status.in_(ACTIVE_STATUSES))
                .values(
                    status=BacktestStatus.failed,
                    error=message[:1000],
                    finished_at=func.now(),
                    duration_ms=func.round(
                        func.extract("epoch", func.now() - Backtest.started_at) * 1000
                    ),
                )
                .returning(Backtest)
            )
        ).scalar_one_or_none()
        await session.commit()
    if row is None:
        return False
    await _publish(
        redis,
        row.user_id,
        {
            "type": "backtest_failed",
            "backtest_id": str(backtest_id),
            "status": "failed",
            "error": message[:1000],
        },
    )
    await _notify(factory, redis, row, "backtest_failed", error=message[:300])
    return True


async def _notify(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis | None,
    row: Backtest,
    kind: str,
    **data: Any,
) -> None:
    """A ``backtest_completed`` / ``backtest_failed`` notification (Y15); never raises."""
    from app.models.notification import NotificationType, Severity  # noqa: PLC0415
    from app.notifications import service as notifications  # noqa: PLC0415

    try:
        async with factory() as session:
            instrument = await session.get(Instrument, row.instrument_id)
        snapshot = (row.config or {}).get(SNAPSHOT_KEY) or {}
        strategy = snapshot.get("name")
        if strategy is None:
            try:
                strategy = ts.get_strategy(row.strategy_key).title
            except ValueError:
                strategy = row.strategy_key
        item = notifications.NotifyItem(
            user_id=row.user_id,
            type=NotificationType(kind),
            data={
                "backtest_id": str(row.id),
                "strategy_key": row.strategy_key,
                "strategy_name": strategy,
                "symbol": instrument.symbol if instrument else "?",
                "timeframe": Timeframe(row.timeframe).value,
                **data,
            },
            dedup_key=f"backtest:{row.id}:{kind}",
            severity=Severity.success if kind == "backtest_completed" else Severity.warning,
        )
        await notifications.notify_with(factory, item, redis)
    except Exception:  # noqa: BLE001
        logger.exception("notifying %s of backtest %s failed", kind, row.id)


def _frame(history: Sequence[market_service.CandleRow], rows: Sequence[tuple]) -> pd.DataFrame:
    records = [(r.ts, r.open, r.high, r.low, r.close, r.volume) for r in history] + list(rows)
    df = pd.DataFrame.from_records(
        records, columns=["ts", "open", "high", "low", "close", "volume"]
    )
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("ts"), utc=True))
    return df.astype("float64")


def _curve(result: tb.BacktestResult) -> dict[str, list]:
    equity = result.equity.to_numpy()
    dd = result.drawdown.to_numpy()
    keep = tb.downsample_indices(equity, dd / 100, MAX_CURVE_POINTS)
    times = unix_seconds(result.equity.index)[keep]
    return {
        "time": times.tolist(),
        "equity": [round(float(v), 4) for v in equity[keep]],
        "drawdown": [round(float(v), 4) for v in dd[keep]],
    }


def _trade_rows(backtest_id: uuid.UUID, trades: Sequence[tb.Trade]) -> list[dict[str, Any]]:
    return [
        {
            "backtest_id": backtest_id,
            "number": t.number,
            "side": t.side,
            "entry_time": t.entry_time.to_pydatetime(),
            "entry_price": t.entry_price,
            "exit_time": t.exit_time.to_pydatetime(),
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "gross_pnl": t.gross_pnl,
            "fees": t.fees,
            "net_pnl": t.net_pnl,
            "return_pct": t.return_pct,
            "bars_held": t.bars_held,
            "entry_reason": t.entry_reason,
            "exit_reason": t.exit_reason,
            "initial_stop": t.initial_stop,
            "risk_amount": t.risk_amount,
            "r_multiple": t.r_multiple,
            "fills": [dict(f) for f in t.fills] or None,
        }
        for t in trades
    ]


async def execute(
    factory: async_sessionmaker[AsyncSession], redis: Redis | None, backtest_id: uuid.UUID
) -> BacktestStatus | None:
    """Run one backtest (the Celery task's body). Returns the final status, or None if it was
    not queued any more (cancelled before it started, or already handled)."""
    started = time.perf_counter()
    async with factory() as session:
        row = await session.scalar(
            update(Backtest)
            .where(Backtest.id == backtest_id, Backtest.status == BacktestStatus.queued)
            .values(status=BacktestStatus.running, started_at=func.now(), progress=PROGRESS_RUNNING)
            .returning(Backtest)
        )
        await session.commit()
    if row is None:
        return None
    user_id = row.user_id
    await publish_progress(redis, user_id, backtest_id, "running", PROGRESS_RUNNING)

    def cancelled() -> BacktestStatus:
        logger.info("backtest %s cancelled", backtest_id)
        return BacktestStatus.cancelled

    try:
        strategy, config = strategy_of(row)
        async with factory() as session:
            history = await market_service.get_candles(
                session,
                row.instrument_id,
                row.timeframe,
                end=row.range_start - timedelta(microseconds=1),
                limit=strategy.history(row.params),
            )
            rows = await market_service.candle_range(
                session, row.instrument_id, row.timeframe, row.range_start, row.range_end
            )
        if not rows:
            raise BacktestError("No candles in [start, end] for this instrument and timeframe")
        if len(rows) > get_settings().backtest_max_bars:
            raise BacktestError(
                f"The range now has {len(rows)} bars; at most "
                f"{get_settings().backtest_max_bars} per backtest"
            )
        if not await _set_progress(factory, backtest_id, PROGRESS_LOADED):
            return cancelled()
        await publish_progress(redis, user_id, backtest_id, "running", PROGRESS_LOADED)

        engine_started = time.perf_counter()
        result = tb.backtest(
            _frame(history, rows),
            strategy,
            row.params,
            config,
            start=rows[0][0],
            bars_per_year=bars_per_year(row.timeframe),
        )
        engine_ms = round((time.perf_counter() - engine_started) * 1000)
        curve = _curve(result)
        if not await _set_progress(factory, backtest_id, PROGRESS_COMPUTED):
            return cancelled()
        await publish_progress(redis, user_id, backtest_id, "running", PROGRESS_COMPUTED)

        async with factory() as session:
            if result.trades:
                await session.execute(
                    insert(BacktestTrade), _trade_rows(backtest_id, result.trades)
                )
            done = await session.scalar(
                update(Backtest)
                .where(Backtest.id == backtest_id, Backtest.status == BacktestStatus.running)
                .values(
                    status=BacktestStatus.completed,
                    progress=100,
                    metrics=result.metrics,
                    equity_curve=curve,
                    bars=result.bars,
                    first_bar_at=rows[0][0],
                    last_bar_at=rows[-1][0],
                    finished_at=func.now(),
                    duration_ms=round((time.perf_counter() - started) * 1000),
                    engine_ms=engine_ms,
                )
                .returning(Backtest.id)
            )
            if done is None:  # cancelled while computing: keep nothing
                await session.rollback()
                return cancelled()
            await session.commit()
    except BacktestError as exc:
        await fail(factory, redis, backtest_id, str(exc))
        return BacktestStatus.failed
    except SoftTimeLimitExceeded:
        limit = get_settings().backtest_time_limit_seconds
        await fail(factory, redis, backtest_id, time_limit_message(limit))
        return BacktestStatus.failed
    except Exception as exc:  # noqa: BLE001 - recorded on the backtest, never lost
        logger.exception("backtest %s failed", backtest_id)
        await fail(factory, redis, backtest_id, f"Internal error: {type(exc).__name__}: {exc}")
        return BacktestStatus.failed

    headline = {k: result.metrics.get(k) for k in HEADLINE_METRICS}
    await _publish(
        redis,
        user_id,
        {
            "type": "backtest_completed",
            "backtest_id": str(backtest_id),
            "status": "completed",
            "progress": 100,
            "metrics": headline,
        },
    )
    await _notify(factory, redis, row, "backtest_completed", metrics=headline)
    logger.info(
        "backtest %s completed bars=%d trades=%d engine_ms=%d total_ms=%d",
        backtest_id,
        result.bars,
        len(result.trades),
        engine_ms,
        round((time.perf_counter() - started) * 1000),
    )
    return BacktestStatus.completed


async def recover_stuck(
    factory: async_sessionmaker[AsyncSession], redis: Redis | None, now: datetime | None = None
) -> int:
    """Fail backtests a dead worker left behind: ``running`` longer than the time limit (plus a
    minute), or ``queued`` for more than 6 hours (the queued task was lost)."""
    now = now or datetime.now(UTC)
    limit = timedelta(seconds=get_settings().backtest_time_limit_seconds + 60)
    async with factory() as session:
        stuck = await session.scalars(
            select(Backtest.id).where(
                ((Backtest.status == BacktestStatus.running) & (Backtest.started_at < now - limit))
                | (
                    (Backtest.status == BacktestStatus.queued)
                    & (Backtest.created_at < now - QUEUED_TOO_LONG)
                )
            )
        )
        ids = list(stuck)
    recovered = 0
    for backtest_id in ids:
        message = "The backtest worker stopped before this backtest finished; please run it again"
        recovered += await fail(factory, redis, backtest_id, message)
    if recovered:
        logger.warning("Marked %d stuck backtest(s) as failed", recovered)
    return recovered


# --- reads -----------------------------------------------------------------------------------


async def get_own_or_404(session: AsyncSession, user: User, backtest_id: uuid.UUID) -> Backtest:
    row = await session.get(Backtest, backtest_id, populate_existing=True)
    if row is None or row.user_id != user.id:  # never 403: do not reveal it exists
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Backtest not found")
    return row


def _instrument(instrument: Instrument) -> dict[str, Any]:
    return {"id": instrument.id, "symbol": instrument.symbol, "source": instrument.source}


def summary(row: Backtest, instrument: Instrument) -> dict[str, Any]:
    headline = None
    if row.metrics is not None:
        headline = {k: row.metrics.get(k) for k in HEADLINE_METRICS}
    return {
        "id": row.id,
        "status": row.status,
        "progress": row.progress,
        "instrument": _instrument(instrument),
        "timeframe": row.timeframe,
        "strategy_key": row.strategy_key,
        "params": row.params,
        "start": row.range_start,
        "end": row.range_end,
        "bars": row.bars,
        "error": row.error,
        "headline": headline,
        "created_at": row.created_at,
        "finished_at": row.finished_at,
    }


async def list_backtests(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
    offset: int,
    status_: BacktestStatus | None = None,
    strategy_key: str | None = None,
    instrument_id: uuid.UUID | None = None,
) -> tuple[list[dict[str, Any]], int]:
    conditions = [Backtest.user_id == user.id]
    if status_ is not None:
        conditions.append(Backtest.status == status_)
    if strategy_key is not None:
        conditions.append(Backtest.strategy_key == strategy_key)
    if instrument_id is not None:
        conditions.append(Backtest.instrument_id == instrument_id)
    total = await session.scalar(select(func.count()).select_from(Backtest).where(*conditions))
    rows = await session.execute(
        select(Backtest, Instrument)
        .join(Instrument, Instrument.id == Backtest.instrument_id)
        .where(*conditions)
        .order_by(Backtest.created_at.desc(), Backtest.id)
        .limit(limit)
        .offset(offset)
    )
    return [summary(b, i) for b, i in rows.all()], total


def _points(curve: dict[str, list] | None, key: str) -> list[dict[str, Any]]:
    if not curve:
        return []
    return [{"time": t, "value": v} for t, v in zip(curve["time"], curve[key], strict=True)]


def markers(trades: Sequence[BacktestTrade]) -> list[dict[str, Any]]:
    """Lightweight Charts markers: an arrow per entry and per exit (with reason and P&L %),
    sorted by time as the library requires."""
    out = []
    for t in trades:
        long = t.side == "long"
        out.append(
            {
                "time": int(t.entry_time.timestamp()),
                "position": "belowBar" if long else "aboveBar",
                "shape": "arrowUp" if long else "arrowDown",
                "color": ENTRY_COLOR,
                "text": f"#{t.number} {'Long' if long else 'Short'}",
            }
        )
        # partial exits (targets that closed part of the position) get their own marker
        for fill in (t.fills or [])[:-1]:
            move = (fill["price"] / t.entry_price - 1) * 100 * (1 if long else -1)
            out.append(
                {
                    "time": int(datetime.fromisoformat(fill["time"]).timestamp()),
                    "position": "aboveBar" if long else "belowBar",
                    "shape": "arrowDown" if long else "arrowUp",
                    "color": EXIT_WIN_COLOR if move > 0 else EXIT_LOSS_COLOR,
                    "text": f"#{t.number} {EXIT_LABELS.get(fill['reason'], fill['reason'])} "
                    f"{move:+.2f}%",
                }
            )
        out.append(
            {
                "time": int(t.exit_time.timestamp()),
                "position": "aboveBar" if long else "belowBar",
                "shape": "arrowDown" if long else "arrowUp",
                "color": EXIT_WIN_COLOR if t.net_pnl > 0 else EXIT_LOSS_COLOR,
                "text": f"#{t.number} {EXIT_LABELS.get(t.exit_reason, t.exit_reason)} "
                f"{t.return_pct:+.2f}%",
            }
        )
    out.sort(key=lambda m: m["time"])  # stable: an exit and a new entry on one bar keep order
    return out


async def all_trades(session: AsyncSession, backtest_id: uuid.UUID) -> list[BacktestTrade]:
    rows = await session.scalars(
        select(BacktestTrade)
        .where(BacktestTrade.backtest_id == backtest_id)
        .order_by(BacktestTrade.number)
    )
    return list(rows.all())


async def read(session: AsyncSession, row: Backtest) -> dict[str, Any]:
    instrument = await session.get(Instrument, row.instrument_id)
    trades = await all_trades(session, row.id) if row.status == BacktestStatus.completed else []
    cost = row.config.get(COST_KEY)
    return {
        **summary(row, instrument),
        "params_hash": row.params_hash,
        "config": row.config,
        "cost_model": "bps" if cost is None else "fixed_per_unit",
        "cost_per_unit": cost,
        "first_bar": row.first_bar_at,
        "last_bar": row.last_bar_at,
        "metrics": row.metrics,
        "equity": _points(row.equity_curve, "equity"),
        "drawdown": _points(row.equity_curve, "drawdown"),
        "markers": markers(trades),
        "started_at": row.started_at,
        "duration_ms": row.duration_ms,
        "engine_ms": row.engine_ms,
    }


async def trades_page(
    session: AsyncSession, row: Backtest, limit: int, offset: int
) -> tuple[list[BacktestTrade], int]:
    total = await session.scalar(
        select(func.count()).select_from(BacktestTrade).where(BacktestTrade.backtest_id == row.id)
    )
    rows = await session.scalars(
        select(BacktestTrade)
        .where(BacktestTrade.backtest_id == row.id)
        .order_by(BacktestTrade.number)
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all()), total


def trades_csv(trades: Sequence[BacktestTrade]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for t in trades:
        values = []
        for column in CSV_COLUMNS:
            value = getattr(t, column)
            values.append(value.isoformat() if isinstance(value, datetime) else value)
        writer.writerow(values)
    return buffer.getvalue()


# --- cancel / delete / compare -------------------------------------------------------------------


async def cancel_or_delete(
    session: AsyncSession, redis: Redis | None, user: User, backtest_id: uuid.UUID
) -> str:
    """Cancel a queued/running backtest (the task stops at its next checkpoint); delete a
    finished one with its trades. Returns ``"cancelled"`` or ``"deleted"``."""
    row = await get_own_or_404(session, user, backtest_id)
    if row.status in ACTIVE_STATUSES:
        cancelled = await session.scalar(
            update(Backtest)
            .where(Backtest.id == backtest_id, Backtest.status.in_(ACTIVE_STATUSES))
            .values(status=BacktestStatus.cancelled, finished_at=func.now())
            .returning(Backtest.id)
        )
        await session.commit()
        if cancelled is not None:
            await publish_progress(redis, user.id, backtest_id, "cancelled", row.progress)
            return "cancelled"
    await session.execute(delete(Backtest).where(Backtest.id == backtest_id))
    await session.commit()
    return "deleted"


async def compare(session: AsyncSession, user: User, ids: list[uuid.UUID]) -> dict[str, Any]:
    """Metrics side by side and equity curves normalised to 100 at the start."""
    rows = await session.execute(
        select(Backtest, Instrument)
        .join(Instrument, Instrument.id == Backtest.instrument_id)
        .where(Backtest.id.in_(ids), Backtest.user_id == user.id)
    )
    found = {b.id: (b, i) for b, i in rows.all()}
    missing = [str(i) for i in ids if i not in found]
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Backtest(s) not found: {', '.join(missing)}"
        )
    items = []
    for backtest_id in ids:
        row, instrument = found[backtest_id]
        if row.status != BacktestStatus.completed:
            raise _unprocessable(f"Backtest {backtest_id} is {row.status.value}, not completed")
        initial = row.config["initial_capital"]
        curve = row.equity_curve
        items.append(
            {
                "id": row.id,
                "instrument": _instrument(instrument),
                "timeframe": row.timeframe,
                "strategy_key": row.strategy_key,
                "params": row.params,
                "config": row.config,
                "start": row.range_start,
                "end": row.range_end,
                "metrics": row.metrics,
                "equity": [
                    {"time": t, "value": round(v / initial * 100, 4)}
                    for t, v in zip(curve["time"], curve["equity"], strict=True)
                ],
            }
        )
    return {"items": items}
