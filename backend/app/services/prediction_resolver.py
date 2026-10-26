"""Resolve strategy signals into ``signal_outcomes`` (Y16, docs/predictions.md#resolution).

A buy/sell signal is resolved on the ``H = PREDICTION_HORIZON_BARS`` bars of its timeframe that
follow its bar. They are the bars the market should have (``sessions.expected_bar_starts``: a
weekend or a daily break is not a gap). Without a session calendar the instrument trades 24/7,
and the H-th bar starts at ``bar_time + H x timeframe``. A signal is due once that bar is closed
(B5 watermark). Before that it stays open.

- The entry is the signal's price. The exit is the close of the H-th bar, MFE and MAE come
  from the highs and lows of the H bars, all signed in the signal's direction, in %.
- ``correct``: ``side x (exit - entry) > cost``, where cost is the instrument's
  ``cost_per_unit`` (XAU/USD 0.25, Fadi's fixed cost) or 0.
- A missing bar in the horizon: ``correct`` null, no prices, the reason in ``note``. The
  stats leave such rows out.

Light on memory: one run handles at most ``PREDICTION_RESOLVE_BATCH`` signals, oldest first,
reading only the H bars of each from the candle views (no history, no pandas). Rows are
inserted with ON CONFLICT DO NOTHING, so a re-run or two overlapping runs write nothing twice.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import islice
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.prediction import SignalOutcome
from app.models.strategy import Signal, SignalSide
from app.services import market_service, sessions

logger = logging.getLogger(__name__)

STATUS_KEY = "predictions:resolver"  # JSON: the last run (GET /admin/predictions/resolver)
STATUS_TTL = 30 * 86400


@dataclass
class RunResult:
    resolved: int = 0
    gaps: int = 0
    waiting: int = 0  # due by the clock but not by the session calendar yet
    by_timeframe: dict[str, int] = field(default_factory=dict)


def horizon_starts(
    calendar: dict[str, Any] | None,
    bar_time: datetime,
    timeframe: Timeframe,
    horizon: int,
    watermark: datetime,
) -> list[datetime] | None:
    """Starts of the ``horizon`` bars after ``bar_time`` that should exist, or None while the
    last of them is not closed by ``watermark``."""
    interval = timeframe.interval
    if calendar is None:
        starts = [bar_time + interval * k for k in range(1, horizon + 1)]
    else:
        expected = sessions.expected_bar_starts(calendar, bar_time + interval, watermark, timeframe)
        starts = list(islice(expected, horizon))
        if len(starts) < horizon:
            return None
    return starts if starts[-1] + interval <= watermark else None


def outcome_values(
    side: SignalSide | str,
    entry: float,
    starts: list[datetime],
    bars: list[tuple],
    cost: float,
) -> dict[str, Any]:
    """The outcome of one signal from its horizon bars ``(ts, open, high, low, close, ...)``
    (pure). Missing expected bars: ``correct`` null and the reason in ``note``."""
    sign = 1.0 if SignalSide(side) == SignalSide.buy else -1.0
    found = {row[0] for row in bars}
    missing = [ts for ts in starts if ts not in found]
    if missing:
        first = missing[0].astimezone(UTC).isoformat().replace("+00:00", "Z")
        return {
            "correct": None,
            "note": f"gap: {len(missing)} of {len(starts)} bars missing (first {first})"[:200],
        }
    rows = [row for row in bars if starts[0] <= row[0] <= starts[-1]]
    exit_price = float(next(row[4] for row in rows if row[0] == starts[-1]))
    high = max(float(row[2]) for row in rows)
    low = min(float(row[3]) for row in rows)
    best, worst = (high, low) if sign > 0 else (low, high)
    move = sign * (exit_price - entry)
    return {
        "exit_ts": starts[-1],
        "exit_price": exit_price,
        "return_pct": move / entry * 100,
        "mfe_pct": sign * (best - entry) / entry * 100,
        "mae_pct": sign * (worst - entry) / entry * 100,
        "correct": move > cost,
        "note": None,
    }


def _no_outcome():
    return ~exists().where(SignalOutcome.signal_id == Signal.id)


async def resolve_signals(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    horizon: int | None = None,
    batch: int | None = None,
) -> RunResult:
    """One run: at most ``batch`` due signals, oldest first per instrument and timeframe."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    horizon = max(1, horizon or settings.prediction_horizon_bars)
    left = max(1, batch or settings.prediction_resolve_batch)
    result = RunResult()
    instruments = await session.scalars(
        select(Instrument)
        .where(exists().where(Signal.instrument_id == Instrument.id))
        .order_by(Instrument.id)
    )
    for instrument in list(instruments):
        if left <= 0:
            break
        watermark = await market_service.closed_watermark(session, instrument, now)
        if watermark is None:
            continue
        calendar = instrument.session_calendar or None
        cost = float(instrument.cost_per_unit or 0.0)
        for timeframe in Timeframe:
            if left <= 0:
                break
            # necessary for any calendar: the H-th bar after it is closed on a 24/7 clock
            cutoff = watermark - timeframe.interval * (horizon + 1)
            due = await session.execute(
                select(Signal.id, Signal.bar_time, Signal.side, Signal.price)
                .where(
                    Signal.instrument_id == instrument.id,
                    Signal.timeframe == timeframe,
                    Signal.bar_time <= cutoff,
                    _no_outcome(),
                )
                .order_by(Signal.bar_time, Signal.id)
                .limit(left)
            )
            values = []
            for signal_id, bar_time, side, price in due.all():
                left -= 1
                starts = horizon_starts(calendar, bar_time, timeframe, horizon, watermark)
                if starts is None:
                    result.waiting += 1
                    continue
                bars = await market_service.candle_range(
                    session, instrument.id, timeframe, starts[0], starts[-1]
                )
                row = outcome_values(side, float(price), starts, bars, cost)
                values.append(
                    {"signal_id": signal_id, "horizon_bars": horizon, "cost_per_unit": cost, **row}
                )
                result.gaps += row["correct"] is None
            if values:
                written = await session.execute(
                    insert(SignalOutcome)
                    .values(values)
                    .on_conflict_do_nothing(index_elements=["signal_id"])
                    .returning(SignalOutcome.signal_id)
                )
                count = len(written.all())
                await session.commit()
                result.resolved += count
                result.by_timeframe[timeframe.value] = count
    return result


async def backlog(session: AsyncSession) -> int:
    """Signals without an outcome yet (due or not)."""
    return await session.scalar(select(func.count()).select_from(Signal).where(_no_outcome()))


async def run(
    factory: async_sessionmaker[AsyncSession], redis: Redis, *, now: datetime | None = None
) -> RunResult:
    """The beat task: one run, its result (or error) stored in Redis for the admin view."""
    settings = get_settings()
    started = time.monotonic()
    status = await read_status(redis)
    status.update(
        last_run_at=(now or datetime.now(UTC)).isoformat(),
        horizon_bars=settings.prediction_horizon_bars,
        batch=settings.prediction_resolve_batch,
    )
    try:
        async with factory() as session:
            result = await resolve_signals(session, now=now)
    except Exception as exc:
        status.update(
            last_status="error",
            last_error=f"{type(exc).__name__}: {exc}"[:500],
            last_error_at=status["last_run_at"],
            last_duration_ms=round((time.monotonic() - started) * 1000),
        )
        await _write_status(redis, status)
        raise
    status.update(
        last_status="ok",
        last_resolved=result.resolved,
        last_gaps=result.gaps,
        last_waiting=result.waiting,
        last_duration_ms=round((time.monotonic() - started) * 1000),
    )
    await _write_status(redis, status)
    if result.resolved or result.waiting:
        logger.info(
            "predictions.resolve_signals resolved=%d gaps=%d waiting=%d by_timeframe=%s",
            result.resolved,
            result.gaps,
            result.waiting,
            result.by_timeframe,
        )
    return result


async def read_status(redis: Redis) -> dict[str, Any]:
    try:
        raw = await redis.get(STATUS_KEY)
        return json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001 - the status is informative only
        logger.warning("predictions: could not read the resolver status", exc_info=True)
        return {}


async def _write_status(redis: Redis, status: dict[str, Any]) -> None:
    try:
        await redis.set(STATUS_KEY, json.dumps(status), ex=STATUS_TTL)
    except Exception:  # noqa: BLE001
        logger.warning("predictions: could not store the resolver status", exc_info=True)
