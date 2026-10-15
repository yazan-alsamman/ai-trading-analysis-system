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
from app.models.instrument import Instrument, MarketType
from app.schemas.market import CandleIn, InstrumentCreate, InstrumentUpdate

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
    )
    for tf in Timeframe
}

_UPSERT = text(
    """
    INSERT INTO candles_1m AS c (instrument_id, ts, open, high, low, close, volume, trades)
    SELECT CAST(:instrument_id AS uuid), *
    FROM unnest(
        CAST(:ts AS timestamptz[]),
        CAST(:open AS double precision[]),
        CAST(:high AS double precision[]),
        CAST(:low AS double precision[]),
        CAST(:close AS double precision[]),
        CAST(:volume AS double precision[]),
        CAST(:trades AS integer[])
    )
    ON CONFLICT (instrument_id, ts) DO UPDATE SET
        open = excluded.open,
        high = excluded.high,
        low = excluded.low,
        close = excluded.close,
        volume = excluded.volume,
        trades = excluded.trades
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


async def create_instrument(session: AsyncSession, data: InstrumentCreate) -> Instrument:
    if await get_instrument_by_symbol(session, data.source, data.symbol) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Instrument already exists for this source")
    instrument = Instrument(**data.model_dump())
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
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(instrument, name, value)
    await session.commit()
    await session.refresh(instrument)
    return instrument


# --- candles --------------------------------------------------------------------------------


async def upsert_candles(
    session: AsyncSession, instrument_id: uuid.UUID, candles: Sequence[CandleIn]
) -> int:
    """Insert or update 1m candles. Returns the number of rows written; the caller commits.

    If the same ``ts`` appears more than once, the last occurrence wins.
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
    query = select(
        rel.c.ts, rel.c.open, rel.c.high, rel.c.low, rel.c.close, rel.c.volume, rel.c.trades
    ).where(rel.c.instrument_id == instrument_id)
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


async def get_latest_candle(
    session: AsyncSession, instrument_id: uuid.UUID, timeframe: Timeframe
) -> CandleRow | None:
    rows = await get_candles(session, instrument_id, timeframe, limit=1)
    return rows[0] if rows else None


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
