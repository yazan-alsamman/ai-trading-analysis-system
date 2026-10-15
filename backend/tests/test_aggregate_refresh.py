"""Explicit continuous-aggregate refresh (used after backfills).

refresh_continuous_aggregate cannot run inside a transaction and only sees committed rows, so
this test commits its own data in a dedicated instrument and removes it afterwards. The data
lives in January 2001, far from every other test's timestamps (2021+), so the watermark moves
it leaves behind cannot hide rows that other tests insert and read back via real-time
aggregation.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.candle import Timeframe
from app.models.instrument import Instrument, MarketType
from app.services import market_service
from tests.market_utils import known_candles

T0 = datetime(2001, 1, 2, 10, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 15, 12, 34, 56, tzinfo=UTC)


def test_refresh_windows_cover_whole_days_and_skip_forming_buckets() -> None:
    windows = market_service.refresh_windows(
        NOW - timedelta(days=2, hours=3), NOW - timedelta(minutes=1), now=NOW
    )
    day0 = datetime(2026, 10, 13, tzinfo=UTC)
    assert [(tf.value, start, end) for tf, start, end in windows] == [
        ("5m", day0, datetime(2026, 10, 15, 12, 25, tzinfo=UTC)),
        ("15m", day0, datetime(2026, 10, 15, 12, 15, tzinfo=UTC)),
        ("1h", day0, datetime(2026, 10, 15, 11, tzinfo=UTC)),
        ("4h", day0, datetime(2026, 10, 15, 8, tzinfo=UTC)),
        ("1d", day0, datetime(2026, 10, 14, tzinfo=UTC)),
    ]


def test_refresh_windows_for_old_data_are_not_clamped() -> None:
    windows = market_service.refresh_windows(T0, T0 + timedelta(hours=2), now=NOW)
    assert {(start, end) for _, start, end in windows} == {
        (datetime(2001, 1, 2, tzinfo=UTC), datetime(2001, 1, 3, tzinfo=UTC))
    }
    assert len(windows) == 5


def test_refresh_windows_skip_aggregates_with_only_forming_buckets() -> None:
    windows = market_service.refresh_windows(NOW - timedelta(minutes=90), NOW, now=NOW)
    assert [tf for tf, *_ in windows] == [Timeframe.m5, Timeframe.m15, Timeframe.h1, Timeframe.h4]


def test_needs_aggregate_refresh() -> None:
    recent = known_candles(NOW.replace(second=0) - timedelta(minutes=30), 3)
    old = known_candles(NOW.replace(second=0) - timedelta(hours=3), 3)
    assert market_service.needs_aggregate_refresh(recent, now=NOW) is False
    assert market_service.needs_aggregate_refresh(old + recent, now=NOW) is True
    assert market_service.needs_aggregate_refresh([], now=NOW) is False


@pytest.fixture
async def committed_engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    yield engine
    await engine.dispose()


async def _materialized(engine: AsyncEngine, view: str, instrument_id) -> list[tuple]:
    async with engine.connect() as conn:
        schema, table = (
            await conn.execute(
                text(
                    "SELECT materialization_hypertable_schema, materialization_hypertable_name "
                    "FROM timescaledb_information.continuous_aggregates WHERE view_name = :v"
                ),
                {"v": view},
            )
        ).one()
        rows = await conn.execute(
            text(
                f'SELECT ts, open, close, volume FROM "{schema}"."{table}" '
                "WHERE instrument_id = :i ORDER BY ts"
            ),
            {"i": instrument_id},
        )
        return list(rows.all())


async def test_refresh_aggregates_materializes_backfill(committed_engine: AsyncEngine) -> None:
    sessions = async_sessionmaker(committed_engine, expire_on_commit=False)
    async with sessions() as session:
        instrument = Instrument(
            symbol="REFRESH/TEST",
            source="pytest",
            market=MarketType.crypto,
            base_asset="REFRESH",
            quote_asset="TEST",
        )
        session.add(instrument)
        await session.commit()
    try:
        async with sessions() as session:
            await market_service.upsert_candles(session, instrument.id, known_candles(T0, 120))
            await session.commit()
        assert await _materialized(committed_engine, "candles_1h", instrument.id) == []

        await market_service.refresh_aggregates(
            T0, T0 + timedelta(minutes=119), engine=committed_engine
        )

        assert await _materialized(committed_engine, "candles_1h", instrument.id) == [
            (T0, 100.0, 159.5, 1830.0),
            (T0 + timedelta(hours=1), 160.0, 219.5, 5430.0),
        ]
        assert len(await _materialized(committed_engine, "candles_5m", instrument.id)) == 24
        assert await _materialized(committed_engine, "candles_1d", instrument.id) == [
            (T0.replace(hour=0), 100.0, 219.5, 7260.0)
        ]
        # and the API-facing read returns the same through the view
        async with sessions() as session:
            bars = await market_service.get_candles(
                session, instrument.id, Timeframe.h4, start=T0.replace(hour=0)
            )
        assert [(b.ts, b.open, b.close) for b in bars] == [(T0.replace(hour=8), 100.0, 219.5)]
    finally:
        async with sessions() as session:
            await session.execute(
                text("DELETE FROM instruments WHERE id = :i"), {"i": instrument.id}
            )
            await session.commit()
        # re-materialize the now empty window so no rows of this test stay behind
        await market_service.refresh_aggregates(
            T0, T0 + timedelta(minutes=119), engine=committed_engine
        )
    assert await _materialized(committed_engine, "candles_1h", instrument.id) == []
