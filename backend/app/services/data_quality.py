"""Data-quality gate (B5): may the AI engine be called on the last closed bar of an instrument?

:func:`assess` is pure (no database): it gets the 1m candles of the lookback window, the session
calendar and ``now``, and returns a :class:`QualityReport`. :func:`load_and_assess` reads those
inputs with two small queries. docs/data-quality.md explains every check and what the caller
does with each status (evaluate only on ``ok``).

The bar to evaluate is the last **closed** ``timeframe`` bucket: it ends at or before the
watermark (``market_service.watermark_from``), so a still-forming bar is never sent.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.candle import Candle, Timeframe
from app.models.instrument import Instrument
from app.schemas.sessions import SessionCalendar
from app.services import sessions
from app.services.market_service import MINUTE, CandleRow, floor_to_bucket, watermark_from

DEFAULT_TIMEFRAME = Timeframe.m15
DEFAULT_LOOKBACK = 200  # bars of the timeframe
ALWAYS_OPEN = SessionCalendar(tz="UTC")  # instruments without a calendar trade 24/7 (crypto)


class QualityStatus(StrEnum):
    ok = "ok"  # evaluate
    degraded = "degraded"  # a check failed: skip and log
    closed = "closed"  # the market is closed now: skip
    no_data = "no_data"  # no 1m candles in the window: skip and log


BAD_STATUSES = frozenset({QualityStatus.degraded, QualityStatus.no_data})


class Thresholds(BaseModel):
    max_lag_seconds: float = Field(default=120, gt=0)
    max_missing_pct: float = Field(default=1.0, ge=0)
    spike_pct: float = Field(default=2.0, gt=0)  # |close / previous close - 1| on 1m, in %
    max_spread: float | None = Field(default=None, ge=0)  # price units; None: not checked

    @classmethod
    def from_settings(cls) -> Thresholds:
        settings = get_settings()
        return cls(
            max_lag_seconds=settings.data_quality_max_lag_seconds,
            max_missing_pct=settings.data_quality_max_missing_pct,
            spike_pct=settings.data_quality_spike_pct,
        )


class QualityCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class QualityReport(BaseModel):
    instrument: str | None = Field(default=None, examples=["fxpro:XAU/USD"])
    timeframe: Timeframe
    status: QualityStatus
    checks: list[QualityCheck]
    last_closed_bar: datetime | None = Field(
        default=None, description="start of the bar to evaluate (the last closed one)"
    )
    watermark: datetime | None = Field(default=None, description="end of the last closed 1m bar")
    evaluated_at: datetime
    lag_seconds: float | None = None
    next_open: datetime | None = Field(default=None, description="only when status is closed")

    @property
    def failed(self) -> list[QualityCheck]:
        return [c for c in self.checks if not c.ok]


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")


def evaluation_window(
    watermark: datetime | None,
    now: datetime,
    calendar: SessionCalendar,
    timeframe: Timeframe,
    lookback: int = DEFAULT_LOOKBACK,
    bar: datetime | None = None,
) -> tuple[datetime | None, datetime, datetime]:
    """``(bar_start, window_start, window_end)``: the bar to evaluate (the given ``bar``, or the
    last bucket that has ended by the watermark and in which the market traded) and the
    ``lookback`` buckets of wall-clock time that end with it."""
    interval = timeframe.interval
    if bar is not None:
        bar_start = floor_to_bucket(bar.astimezone(UTC), interval)
        end = bar_start + interval
        return bar_start, end - lookback * interval, end
    closed_end = floor_to_bucket(
        watermark if watermark is not None else floor_to_bucket(now, MINUTE), interval
    )
    bar_start = None
    if watermark is not None:
        starts = list(
            sessions.expected_bar_starts(
                calendar, closed_end - lookback * interval, closed_end, timeframe
            )
        )
        bar_start = starts[-1] if starts else None
    end = bar_start + interval if bar_start is not None else closed_end
    return bar_start, end - lookback * interval, end


def _runs(missing: Sequence[datetime]) -> tuple[int, datetime | None]:
    """Longest run of consecutive missing minutes: (length, start)."""
    best, best_start, length, start = 0, None, 0, None
    previous = None
    for ts in missing:
        if previous is not None and ts - previous == MINUTE:
            length += 1
        else:
            length, start = 1, ts
        if length > best:
            best, best_start = length, start
        previous = ts
    return best, best_start


def _bad_prices(row: Any) -> str | None:
    if min(row.open, row.high, row.low, row.close) <= 0:
        return "price <= 0"
    if (
        row.high < row.low
        or row.high < max(row.open, row.close)
        or row.low > min(row.open, row.close)
    ):
        return "inconsistent OHLC"
    spread = getattr(row, "spread", None)
    if spread is not None and spread < 0:
        return "negative spread"
    return None


def _closure_between(calendar: SessionCalendar, previous: datetime, current: datetime) -> bool:
    """Whether the market closed at some minute between two bars (a weekend or a break), so the
    move between them is a session gap, not a spike."""
    minutes = int((current - previous) / MINUTE) - 1
    if minutes <= 0:
        return False
    expected = sum(1 for _ in sessions.expected_bar_starts(calendar, previous + MINUTE, current))
    return expected < minutes


def _no_data(
    *,
    instrument: str | None,
    timeframe: Timeframe,
    now: datetime,
    detail: str,
    status: QualityStatus = QualityStatus.no_data,
    watermark: datetime | None = None,
    next_open: datetime | None = None,
) -> QualityReport:
    return QualityReport(
        instrument=instrument,
        timeframe=timeframe,
        status=status,
        checks=[QualityCheck(name="no_data", ok=False, detail=detail)],
        watermark=watermark,
        evaluated_at=now,
        lag_seconds=round((now - watermark).total_seconds(), 1) if watermark else None,
        next_open=next_open,
    )


def missing_instrument(
    name: str, now: datetime | None = None, timeframe: Timeframe | str = DEFAULT_TIMEFRAME
) -> QualityReport:
    """The report of a monitored instrument that does not exist (yet)."""
    return _no_data(
        instrument=name,
        timeframe=Timeframe(timeframe),
        now=(now or datetime.now(UTC)).astimezone(UTC),
        detail="instrument not found",
    )


def assess(
    candles_1m: Iterable[Any],
    *,
    calendar: SessionCalendar | Mapping[str, Any] | None,
    now: datetime,
    timeframe: Timeframe | str = DEFAULT_TIMEFRAME,
    lookback: int = DEFAULT_LOOKBACK,
    thresholds: Thresholds | None = None,
    bar: datetime | None = None,
    last_bar_ts: datetime | None = None,
    instrument: str | None = None,
) -> QualityReport:
    """Assess the last closed ``timeframe`` bar (or ``bar``) and its lookback window.

    ``candles_1m``: objects with ``ts``, ``open``, ``high``, ``low``, ``close`` and optionally
    ``spread`` (``CandleRow``), covering at least the window. ``last_bar_ts``: the newest 1m
    candle at or before ``now`` if it is not among them. ``calendar`` None: open 24/7.
    """
    cal = sessions.calendar_of(calendar) if calendar is not None else ALWAYS_OPEN
    tf = Timeframe(timeframe)
    limits = thresholds or Thresholds()
    now = now.astimezone(UTC)
    cutoff = floor_to_bucket(now, MINUTE)
    rows = sorted((c for c in candles_1m if c.ts <= cutoff), key=lambda c: c.ts)
    if rows and (last_bar_ts is None or rows[-1].ts > last_bar_ts):
        last_bar_ts = rows[-1].ts
    watermark = watermark_from(last_bar_ts, now, cal)
    market_open = sessions.is_open(cal, now)
    next_open = None if market_open else sessions.next_open(cal, now)
    lag = round((now - watermark).total_seconds(), 1) if watermark is not None else None

    bar_start, start, end = evaluation_window(watermark, now, cal, tf, lookback, bar)
    window = [r for r in rows if start <= r.ts < end]
    if not window:
        expected_any = next(sessions.expected_bar_starts(cal, start, end), None) is not None
        return _no_data(
            instrument=instrument,
            timeframe=tf,
            now=now,
            detail=f"no 1m candles between {_iso(start)} and {_iso(end)}",
            status=QualityStatus.no_data if expected_any or market_open else QualityStatus.closed,
            watermark=watermark,
            next_open=next_open,
        )

    have = {r.ts for r in window}
    checks = [
        QualityCheck(name="no_data", ok=True, detail=f"{len(window)} 1m candles in the window")
    ]

    # closed_bar: the bar has ended and holds every 1m bar the calendar expects
    missing_in_bar: list[datetime] = []
    if bar_start is None:
        checks.append(
            QualityCheck(name="closed_bar", ok=False, detail="no closed bar in the window")
        )
    else:
        bar_end = bar_start + tf.interval
        expected_bar = list(sessions.expected_bar_starts(cal, bar_start, bar_end))
        missing_in_bar = [t for t in expected_bar if t not in have]
        if watermark is None or bar_end > watermark:
            ok, detail = False, f"bar {_iso(bar_start)} has not closed yet"
        elif missing_in_bar:
            ok, detail = (
                False,
                (
                    f"bar {_iso(bar_start)} is missing {len(missing_in_bar)} of "
                    f"{len(expected_bar)} 1m bars, first {_iso(missing_in_bar[0])}"
                ),
            )
        else:
            ok, detail = True, f"bar {_iso(bar_start)} complete ({len(expected_bar)} 1m bars)"
        checks.append(QualityCheck(name="closed_bar", ok=ok, detail=detail))

    # gaps: expected 1m bars missing over the window (closures are never gaps)
    expected = list(sessions.expected_bar_starts(cal, start, end))
    missing = [t for t in expected if t not in have]
    pct = 100 * len(missing) / len(expected) if expected else 0.0
    longest, longest_start = _runs(missing)
    detail = (
        f"{len(missing)} of {len(expected)} expected 1m bars missing ({pct:.2f} %, "
        f"max {limits.max_missing_pct:g} %)"
    )
    if longest_start is not None:
        detail += f"; longest gap {longest} min from {_iso(longest_start)}"
    if missing_in_bar:
        detail += f"; {len(missing_in_bar)} inside the evaluated bar"
    checks.append(
        QualityCheck(
            name="gaps",
            ok=not missing_in_bar and pct <= limits.max_missing_pct,
            detail=detail,
        )
    )

    # ohlc: valid prices over the window; spikes and spread on the evaluated bar
    problems = [f"{_iso(r.ts)} {reason}" for r in window if (reason := _bad_prices(r)) is not None]
    if bar_start is not None:
        bar_end = bar_start + tf.interval
        position = {r.ts: i for i, r in enumerate(window)}
        for r in window:
            if not bar_start <= r.ts < bar_end:
                continue
            i = position[r.ts]
            spread = getattr(r, "spread", None)
            if limits.max_spread is not None and spread is not None and spread > limits.max_spread:
                problems.append(f"{_iso(r.ts)} spread {spread:g} > {limits.max_spread:g}")
            if i == 0:
                continue
            prev = window[i - 1]
            if prev.close <= 0 or r.close <= 0 or _closure_between(cal, prev.ts, r.ts):
                continue
            move = abs(r.close / prev.close - 1) * 100
            if move > limits.spike_pct:
                problems.append(f"{_iso(r.ts)} spike {move:.2f} % (max {limits.spike_pct:g} %)")
    detail = "; ".join(problems[:5]) if problems else "prices valid, no spike"
    if len(problems) > 5:
        detail += f" (+{len(problems) - 5} more)"
    checks.append(QualityCheck(name="ohlc", ok=not problems, detail=detail))

    # freshness: the feed keeps up while the market is open
    if not market_open:
        checks.append(
            QualityCheck(
                name="freshness", ok=True, detail=f"market closed; next open {_iso(next_open)}"
            )
        )
    else:
        just_opened = not sessions.is_open(cal, now - timedelta(seconds=limits.max_lag_seconds))
        within = lag is not None and lag <= limits.max_lag_seconds
        detail = f"lag {lag:.0f} s (max {limits.max_lag_seconds:g} s)"
        if just_opened and not within:
            detail += ", grace after the open"
        checks.append(QualityCheck(name="freshness", ok=within or just_opened, detail=detail))

    if not market_open:
        status = QualityStatus.closed
    elif all(c.ok for c in checks):
        status = QualityStatus.ok
    else:
        status = QualityStatus.degraded
    return QualityReport(
        instrument=instrument,
        timeframe=tf,
        status=status,
        checks=checks,
        last_closed_bar=bar_start,
        watermark=watermark,
        evaluated_at=now,
        lag_seconds=lag,
        next_open=next_open,
    )


async def load_and_assess(
    session: AsyncSession,
    instrument: Instrument,
    timeframe: Timeframe | str = DEFAULT_TIMEFRAME,
    now: datetime | None = None,
    *,
    lookback: int = DEFAULT_LOOKBACK,
    thresholds: Thresholds | None = None,
    bar: datetime | None = None,
) -> QualityReport:
    """Read the inputs of :func:`assess` and run it. Two queries: the newest 1m candle (an index
    lookup), then the 1m candles of the window (3,000 rows for 200 bars of 15m)."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    tf = Timeframe(timeframe)
    calendar = (
        sessions.calendar_of(instrument.session_calendar)
        if instrument.session_calendar
        else ALWAYS_OPEN
    )
    cutoff = floor_to_bucket(now, MINUTE)
    last = await session.scalar(
        select(func.max(Candle.ts)).where(
            Candle.instrument_id == instrument.id, Candle.ts <= cutoff
        )
    )
    watermark = watermark_from(last, now, calendar)
    _, start, end = evaluation_window(watermark, now, calendar, tf, lookback, bar)
    rows = (
        await session.execute(
            select(Candle.ts, Candle.open, Candle.high, Candle.low, Candle.close, Candle.spread)
            .where(Candle.instrument_id == instrument.id, Candle.ts >= start, Candle.ts < end)
            .order_by(Candle.ts)
        )
    ).all()
    candles = [CandleRow(ts, o, h, lo, c, 0.0, None, spread) for ts, o, h, lo, c, spread in rows]
    return assess(
        candles,
        calendar=calendar,
        now=now,
        timeframe=tf,
        lookback=lookback,
        thresholds=thresholds,
        bar=bar,
        last_bar_ts=last,
        instrument=f"{instrument.source}:{instrument.symbol}",
    )
