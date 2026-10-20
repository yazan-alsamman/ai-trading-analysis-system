import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import DateTime, Double, Integer, Uuid, func, select, table, text
from sqlalchemy import column as sa_column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.candle import AGGREGATE_TIMEFRAMES, Timeframe
from app.models.instrument import SPEC_FIELDS, Instrument, MarketType, SpecSource
from app.schemas.market import CandleIn, InstrumentCreate, InstrumentUpdate
from app.services import sessions

UPSERT_CHUNK_SIZE = 5000
MAX_CANDLES_LIMIT = 5000

# Refresh policies only re-materialize a recent window (the smallest is candles_5m: 2 hours).
# Writes older than this must trigger an explicit refresh, otherwise they stay invisible in the
# aggregates once the watermark has moved past them.
LATE_DATA_THRESHOLD = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class CandleRow:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int | None
    spread: float | None = None  # 1m only


# One lightweight table construct per timeframe. Relation names come only from the Timeframe
# mapping, never from request input.
_RELATIONS = {
    tf: table(
        tf.relation,
        sa_column("instrument_id", Uuid),
        sa_column("ts", DateTime(timezone=True)),
        sa_column("open", Double),
        sa_column("high", Double),
        sa_column("low", Double),
        sa_column("close", Double),
        sa_column("volume", Double),
        sa_column("trades", Integer),
        *([sa_column("spread", Double)] if tf == Timeframe.m1 else []),
    )
    for tf in Timeframe
}

# spread/source only overwrite with a value; received_at keeps the earliest arrival (least()
# ignores NULL), so a re-sent bar does not hide the feed's real lag.
_UPSERT = text(
    """
    INSERT INTO candles_1m AS c
        (instrument_id, ts, open, high, low, close, volume, trades, spread, source, received_at)
    SELECT CAST(:instrument_id AS uuid), u.ts, u.open, u.high, u.low, u.close, u.volume,
           u.trades, u.spread, u.source, coalesce(u.received_at, now())
    FROM unnest(
        CAST(:ts AS timestamptz[]),
        CAST(:open AS double precision[]),
        CAST(:high AS double precision[]),
        CAST(:low AS double precision[]),
        CAST(:close AS double precision[]),
        CAST(:volume AS double precision[]),
        CAST(:trades AS integer[]),
        CAST(:spread AS double precision[]),
        CAST(:source AS varchar[]),
        CAST(:received_at AS timestamptz[])
    ) AS u(ts, open, high, low, close, volume, trades, spread, source, received_at)
    ON CONFLICT (instrument_id, ts) DO UPDATE SET
        open = excluded.open,
        high = excluded.high,
        low = excluded.low,
        close = excluded.close,
        volume = excluded.volume,
        trades = excluded.trades,
        spread = coalesce(excluded.spread, c.spread),
        source = coalesce(excluded.source, c.source),
        received_at = least(c.received_at, excluded.received_at)
    """
)


# --- instruments ----------------------------------------------------------------------------


async def list_instruments(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    market: MarketType | None = None,
    source: str | None = None,
    is_active: bool | None = None,
    q: str | None = None,
) -> tuple[Sequence[Instrument], int]:
    filters = []
    if market is not None:
        filters.append(Instrument.market == market)
    if source:
        filters.append(Instrument.source == source.strip().lower())
    if is_active is not None:
        filters.append(Instrument.is_active == is_active)
    if q:
        escaped = q.strip().upper().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filters.append(Instrument.symbol.like(f"%{escaped}%", escape="\\"))
    total = await session.scalar(select(func.count()).select_from(Instrument).where(*filters))
    rows = await session.scalars(
        select(Instrument)
        .where(*filters)
        .order_by(Instrument.source, Instrument.symbol)
        .limit(limit)
        .offset(offset)
    )
    return rows.all(), total or 0


async def get_instrument(session: AsyncSession, instrument_id: uuid.UUID) -> Instrument | None:
    return await session.get(Instrument, instrument_id)


async def get_instrument_or_404(session: AsyncSession, instrument_id: uuid.UUID) -> Instrument:
    instrument = await get_instrument(session, instrument_id)
    if instrument is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrument not found")
    return instrument


async def get_instrument_by_symbol(
    session: AsyncSession, source: str, symbol: str
) -> Instrument | None:
    return await session.scalar(
        select(Instrument).where(
            Instrument.source == source.strip().lower(),
            Instrument.symbol == symbol.strip().upper(),
        )
    )


def _spec_values(data: InstrumentCreate | InstrumentUpdate) -> dict:
    """The fields that were set, with the session calendar as JSON (dates as strings)."""
    values = data.model_dump(exclude_unset=True, exclude={"session_calendar"})
    if "session_calendar" in data.model_fields_set:
        calendar = data.session_calendar
        values["session_calendar"] = (
            None if calendar is None else calendar.model_dump(mode="json", exclude_none=True)
        )
    return values


async def create_instrument(session: AsyncSession, data: InstrumentCreate) -> Instrument:
    if await get_instrument_by_symbol(session, data.source, data.symbol) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Instrument already exists for this source")
    values = {**data.model_dump(exclude={"session_calendar"}), **_spec_values(data)}
    values["quote_currency"] = values.get("quote_currency") or data.quote_asset
    if any(values.get(name) is not None for name in SPEC_FIELDS if name != "quote_currency"):
        values.update(spec_source=SpecSource.manual, spec_updated_at=datetime.now(UTC))
    instrument = Instrument(**values)
    session.add(instrument)
    try:
        await session.commit()
    except IntegrityError as exc:  # concurrent create of the same (source, symbol)
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Instrument already exists for this source"
        ) from exc
    await session.refresh(instrument)
    return instrument


async def update_instrument(
    session: AsyncSession, instrument: Instrument, data: InstrumentUpdate
) -> Instrument:
    """Apply the given fields. A changed spec marks the specs as ``manual``."""
    changes = _spec_values(data)
    min_lot = changes.get("min_lot", instrument.min_lot)
    max_lot = changes.get("max_lot", instrument.max_lot)
    if min_lot is not None and max_lot is not None and min_lot > max_lot:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "min_lot must be <= max_lot")
    if any(name in changes and changes[name] != getattr(instrument, name) for name in SPEC_FIELDS):
        changes.update(spec_source=SpecSource.manual, spec_updated_at=datetime.now(UTC))
    for name, value in changes.items():
        setattr(instrument, name, value)
    await session.commit()
    await session.refresh(instrument)
    return instrument


# --- candles --------------------------------------------------------------------------------


async def upsert_candles(
    session: AsyncSession, instrument_id: uuid.UUID, candles: Sequence[CandleIn]
) -> int:
    """Insert or update 1m candles. Returns the number of rows written; the caller commits.

    If the same ``ts`` appears more than once, the last occurrence wins. ``spread`` and
    ``source`` are only overwritten by a value, ``received_at`` (default: now) keeps the
    earliest arrival.
    """
    by_ts = {c.ts: c for c in candles}
    rows = [by_ts[ts] for ts in sorted(by_ts)]
    written = 0
    for i in range(0, len(rows), UPSERT_CHUNK_SIZE):
        chunk = rows[i : i + UPSERT_CHUNK_SIZE]
        result = await session.execute(
            _UPSERT,
            {
                "instrument_id": instrument_id,
                "ts": [c.ts for c in chunk],
                "open": [c.open for c in chunk],
                "high": [c.high for c in chunk],
                "low": [c.low for c in chunk],
                "close": [c.close for c in chunk],
                "volume": [c.volume for c in chunk],
                "trades": [c.trades for c in chunk],
                "spread": [c.spread for c in chunk],
                "source": [c.source for c in chunk],
                "received_at": [c.received_at for c in chunk],
            },
        )
        written += result.rowcount
    return written


async def get_candles(
    session: AsyncSession,
    instrument_id: uuid.UUID,
    timeframe: Timeframe,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> list[CandleRow]:
    """Candles in ascending ``ts`` order (both bounds inclusive).

    With ``start``: the first ``limit`` candles from ``start``. Without it: the latest ``limit``
    candles (up to ``end`` if given).
    """
    limit = max(1, min(limit, MAX_CANDLES_LIMIT))
    rel = _RELATIONS[timeframe]
    columns = [rel.c.ts, rel.c.open, rel.c.high, rel.c.low, rel.c.close, rel.c.volume]
    columns += [rel.c.trades, *([rel.c.spread] if "spread" in rel.c else [])]
    query = select(*columns).where(rel.c.instrument_id == instrument_id)
    if start is not None:
        query = query.where(rel.c.ts >= start)
    if end is not None:
        query = query.where(rel.c.ts <= end)
    if start is not None:
        result = await session.execute(query.order_by(rel.c.ts.asc()).limit(limit))
        rows = result.all()
    else:
        result = await session.execute(query.order_by(rel.c.ts.desc()).limit(limit))
        rows = result.all()[::-1]
    return [CandleRow(*row) for row in rows]


async def count_candles(
    session: AsyncSession,
    instrument_id: uuid.UUID,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> int:
    """Bars in ``[start, end]`` (both inclusive)."""
    rel = _RELATIONS[timeframe]
    return await session.scalar(
        select(func.count())
        .select_from(rel)
        .where(rel.c.instrument_id == instrument_id, rel.c.ts >= start, rel.c.ts <= end)
    )


async def candle_range(
    session: AsyncSession,
    instrument_id: uuid.UUID,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> list[tuple]:
    """Every candle in ``[start, end]`` as ``(ts, open, high, low, close, volume)`` tuples,
    ascending, without the API's row limit (for backtests; the caller bounds the range)."""
    rel = _RELATIONS[timeframe]
    result = await session.execute(
        select(rel.c.ts, rel.c.open, rel.c.high, rel.c.low, rel.c.close, rel.c.volume)
        .where(rel.c.instrument_id == instrument_id, rel.c.ts >= start, rel.c.ts <= end)
        .order_by(rel.c.ts.asc())
    )
    return [tuple(row) for row in result.all()]


async def get_latest_candle(
    session: AsyncSession, instrument_id: uuid.UUID, timeframe: Timeframe
) -> CandleRow | None:
    rows = await get_candles(session, instrument_id, timeframe, limit=1)
    return rows[0] if rows else None


# --- closed bars ----------------------------------------------------------------------------

MINUTE = timedelta(minutes=1)


def watermark_from(
    last_1m_ts: datetime | None, now: datetime, calendar: dict | None = None
) -> datetime | None:
    """End of the last closed 1m bar, from the newest 1m candle (pure; see closed_watermark).

    ``min(floor_to_minute(now), last_1m_ts + 1 minute)``: the minute that is still running is
    never closed, even when a source already wrote it (``simulate-live``, ``seed-demo-candles``
    and the admin upsert do). If the market closed right after the last bar, the watermark
    moves on to ``now`` (the bars of the closure will never come), so a bucket that ends
    during a break or a weekend counts as closed once its wall-clock end has passed.
    """
    if last_1m_ts is None:
        return None
    cutoff = floor_to_bucket(now.astimezone(UTC), MINUTE)
    following = last_1m_ts.astimezone(UTC) + MINUTE
    if calendar is not None:
        following = sessions.next_open(calendar, following)
    return min(cutoff, following)


async def closed_watermark(
    session: AsyncSession, instrument: Instrument, now: datetime | None = None
) -> datetime | None:
    """End of the last **closed** 1m bar of ``instrument`` (None without 1m data): a bar of
    any timeframe is closed when ``ts + interval <= watermark``. One index lookup."""
    now = now or datetime.now(UTC)
    cutoff = floor_to_bucket(now.astimezone(UTC), MINUTE)
    last = await session.scalar(
        select(func.max(_RELATIONS[Timeframe.m1].c.ts)).where(
            _RELATIONS[Timeframe.m1].c.instrument_id == instrument.id,
            _RELATIONS[Timeframe.m1].c.ts <= cutoff,  # rows dated in the future are ignored
        )
    )
    return watermark_from(last, now, instrument.session_calendar)


@dataclass(frozen=True, slots=True)
class ClosedCandles:
    candles: list[CandleRow]
    watermark: datetime | None
    last_closed_bar_ts: datetime | None  # start of the newest closed bar that has a candle


async def get_closed_candles(
    session: AsyncSession,
    instrument_id: uuid.UUID,
    timeframe: Timeframe,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
    now: datetime | None = None,
) -> ClosedCandles:
    """Like :func:`get_candles`, but only buckets with ``ts + interval <= watermark``: the
    still-forming bucket of every aggregate (``materialized_only = false``) is left out.

    At 10:07:20 with 1m data up to 10:06, the 15m bucket 10:00 is forming; 09:45 is the last
    closed bar."""
    instrument = await get_instrument_or_404(session, instrument_id)
    watermark = await closed_watermark(session, instrument, now)
    if watermark is None:
        return ClosedCandles([], None, None)
    limit = max(1, min(limit, MAX_CANDLES_LIMIT))
    cut = watermark - timeframe.interval  # the newest start that is closed
    bound = cut if end is None else min(end, cut)
    candles: list[CandleRow] = []
    if start is None or start <= bound:
        candles = await get_candles(session, instrument_id, timeframe, start, bound, limit)
    reaches_cut = bound == cut and (start is None or (start <= bound and len(candles) < limit))
    if reaches_cut:  # the page ends at the newest closed bar (or there is none)
        last = candles[-1].ts if candles else None
    else:
        newest = await get_candles(session, instrument_id, timeframe, end=cut, limit=1)
        last = newest[0].ts if newest else None
    return ClosedCandles(candles, watermark, last)


def needs_aggregate_refresh(candles: Sequence[CandleIn], now: datetime | None = None) -> bool:
    if not candles:
        return False
    now = now or datetime.now(UTC)
    return min(c.ts for c in candles) < now - LATE_DATA_THRESHOLD


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def floor_to_bucket(value: datetime, interval: timedelta) -> datetime:
    """Start of the time_bucket containing ``value`` (all our buckets are aligned to the epoch)."""
    return value - (value - _EPOCH) % interval


def refresh_windows(
    start: datetime, end: datetime, now: datetime | None = None
) -> list[tuple[Timeframe, datetime, datetime]]:
    """Per-aggregate refresh windows (bottom-up) covering the candles in [start, end].

    The window starts at the UTC day of ``start`` and ends after the day of ``end``, so every
    5m..1d bucket touched lies fully inside it. It is clamped to ``now - policy end_offset`` so
    a manual refresh never materializes still-forming buckets (those stay real-time); an
    aggregate whose clamped window is shorter than one bucket is skipped.
    """
    now = now or datetime.now(UTC)
    day = timedelta(days=1)
    window_start = floor_to_bucket(start.astimezone(UTC), day)
    window_end = floor_to_bucket(end.astimezone(UTC), day) + day
    windows = []
    for tf in AGGREGATE_TIMEFRAMES:
        tf_end = min(window_end, floor_to_bucket(now - tf.policy_end_offset, tf.interval))
        if tf_end - window_start >= tf.interval:
            windows.append((tf, window_start, tf_end))
    return windows


async def refresh_aggregates(
    start: datetime, end: datetime, engine: AsyncEngine | None = None
) -> None:
    """Re-materialize the continuous aggregates (bottom-up) for the candles in [start, end].

    Needed after backfilling data older than the refresh policies' windows. Runs on its own
    connection outside any transaction (refresh_continuous_aggregate cannot run inside one), so
    call it only after the written candles are committed.
    """
    if engine is None:
        from app.db.session import engine
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        for tf, window_start, window_end in refresh_windows(start, end):
            # CALL cannot be a prepared statement, so it is sent as a simple query. The relation
            # name comes from the Timeframe mapping and the bounds are formatted datetimes.
            await raw.driver_connection.execute(
                f"CALL refresh_continuous_aggregate('{tf.relation}', "
                f"'{window_start.isoformat()}'::timestamptz, "
                f"'{window_end.isoformat()}'::timestamptz)"
            )
