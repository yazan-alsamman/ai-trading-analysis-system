"""Migration 0003: hypertable, compression, continuous aggregates and their policies."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import AGGREGATE_TIMEFRAMES, Timeframe
from tests.market_utils import make_instrument

AGGREGATE_SOURCES = {
    "candles_5m": "candles_1m",
    "candles_15m": "candles_5m",
    "candles_1h": "candles_15m",
    "candles_4h": "candles_1h",
    "candles_1d": "candles_1h",
}


async def _scalar_rows(session: AsyncSession, sql: str, **params) -> list:
    return list((await session.execute(text(sql), params)).all())


async def test_candles_1m_is_a_hypertable(session: AsyncSession) -> None:
    rows = await _scalar_rows(
        session,
        "SELECT compression_enabled FROM timescaledb_information.hypertables "
        "WHERE hypertable_name = 'candles_1m'",
    )
    assert rows == [(True,)]
    rows = await _scalar_rows(
        session,
        "SELECT column_name, time_interval FROM timescaledb_information.dimensions "
        "WHERE hypertable_name = 'candles_1m'",
    )
    assert rows == [("ts", timedelta(days=7))]


async def test_compression_settings_and_policy(session: AsyncSession) -> None:
    rows = await _scalar_rows(
        session,
        "SELECT attname, segmentby_column_index, orderby_column_index, orderby_asc "
        "FROM timescaledb_information.compression_settings "
        "WHERE hypertable_name = 'candles_1m' ORDER BY attname",
    )
    assert rows == [("instrument_id", 1, None, None), ("ts", None, 1, False)]
    rows = await _scalar_rows(
        session,
        "SELECT config->>'compress_after' FROM timescaledb_information.jobs "
        "WHERE proc_name = 'policy_compression' AND hypertable_name = 'candles_1m'",
    )
    assert rows == [("30 days",)]


async def test_continuous_aggregates_are_hierarchical_and_real_time(
    session: AsyncSession,
) -> None:
    rows = await _scalar_rows(
        session,
        "SELECT view_name, materialized_only, view_definition "
        "FROM timescaledb_information.continuous_aggregates",
    )
    views = {name: (materialized_only, definition) for name, materialized_only, definition in rows}
    assert set(views) == set(AGGREGATE_SOURCES)
    for view, source in AGGREGATE_SOURCES.items():
        materialized_only, definition = views[view]
        assert materialized_only is False, view
        assert f"FROM {source}" in definition, view


async def test_refresh_policies_match_the_timeframe_mapping(session: AsyncSession) -> None:
    rows = await _scalar_rows(
        session,
        "SELECT ca.view_name, j.schedule_interval, j.config->>'start_offset', "
        "       j.config->>'end_offset' "
        "FROM timescaledb_information.jobs j "
        "JOIN timescaledb_information.continuous_aggregates ca "
        "  ON ca.materialization_hypertable_name = j.hypertable_name "
        "WHERE j.proc_name = 'policy_refresh_continuous_aggregate'",
    )
    policies = {view: (schedule, start, end) for view, schedule, start, end in rows}
    assert set(policies) == {tf.relation for tf in AGGREGATE_TIMEFRAMES}
    expected = {
        "candles_5m": (timedelta(minutes=1), "02:00:00", "00:05:00"),
        "candles_15m": (timedelta(minutes=5), "06:00:00", "00:15:00"),
        "candles_1h": (timedelta(minutes=15), "1 day", "01:00:00"),
        "candles_4h": (timedelta(hours=1), "3 days", "04:00:00"),
        "candles_1d": (timedelta(hours=1), "7 days", "1 day"),
    }
    assert policies == expected
    # the app's manual refresh relies on these end offsets (see market_service.refresh_windows)
    end_offsets = {
        Timeframe.m5: timedelta(minutes=5),
        Timeframe.m15: timedelta(minutes=15),
        Timeframe.h1: timedelta(hours=1),
        Timeframe.h4: timedelta(hours=4),
        Timeframe.d1: timedelta(days=1),
    }
    assert {tf: tf.policy_end_offset for tf in AGGREGATE_TIMEFRAMES} == end_offsets


async def test_aggregates_have_instrument_ts_index(session: AsyncSession) -> None:
    rows = await _scalar_rows(
        session,
        "SELECT ca.view_name, pg_get_indexdef(i.indexrelid) "
        "FROM timescaledb_information.continuous_aggregates ca "
        "JOIN pg_class c ON c.relname = ca.materialization_hypertable_name "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "  AND n.nspname = ca.materialization_hypertable_schema "
        "JOIN pg_index i ON i.indrelid = c.oid",
    )
    indexed = {view for view, definition in rows if "(instrument_id, ts DESC)" in definition}
    assert indexed == set(AGGREGATE_SOURCES)


async def test_candles_1m_check_constraints_exist(session: AsyncSession) -> None:
    rows = await _scalar_rows(
        session,
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'candles_1m'::regclass AND contype = 'c' ORDER BY conname",
    )
    assert [r[0] for r in rows] == [
        "ck_candles_1m_high",
        "ck_candles_1m_high_low",
        "ck_candles_1m_low",
        "ck_candles_1m_ts_minute",
        "ck_candles_1m_volume",
    ]


@pytest.mark.parametrize(
    ("column_sql", "constraint"),
    [
        ("'2026-01-05 10:00:30+00', 10, 11, 9, 10, 1", "ck_candles_1m_ts_minute"),
        # high < low always breaks high/low vs open/close too; any of them may fire first
        ("'2026-01-05 10:00+00', 10, 8, 9, 10, 1", "ck_candles_1m_"),
        ("'2026-01-05 10:00+00', 10, 10.5, 9, 11, 1", "ck_candles_1m_high"),
        ("'2026-01-05 10:00+00', 10, 11, 9.5, 9, 1", "ck_candles_1m_low"),
        ("'2026-01-05 10:00+00', 10, 11, 9, 10, -1", "ck_candles_1m_volume"),
    ],
)
async def test_check_constraints(session: AsyncSession, column_sql: str, constraint: str) -> None:
    instrument = await make_instrument(session)
    with pytest.raises(IntegrityError, match=constraint):
        async with session.begin_nested():
            await session.execute(
                text(
                    "INSERT INTO candles_1m (instrument_id, ts, open, high, low, close, volume) "
                    f"VALUES (:iid, {column_sql})"
                ),
                {"iid": instrument.id},
            )


async def test_upsert_into_compressed_chunk(session: AsyncSession) -> None:
    from app.services import market_service
    from tests.market_utils import known_candles

    instrument = await make_instrument(session)
    old = datetime(2021, 3, 1, 10, 0, tzinfo=UTC)
    await market_service.upsert_candles(session, instrument.id, known_candles(old, 2))
    chunks = await _scalar_rows(
        session,
        "SELECT compress_chunk(c) FROM show_chunks('candles_1m', "
        "newer_than => CAST(:lo AS timestamptz), older_than => CAST(:hi AS timestamptz)) c",
        lo=old - timedelta(days=8),
        hi=old + timedelta(days=8),
    )
    assert len(chunks) == 1
    compressed = await _scalar_rows(
        session,
        "SELECT is_compressed FROM timescaledb_information.chunks "
        "WHERE hypertable_name = 'candles_1m' AND range_start <= :ts AND range_end > :ts",
        ts=old,
    )
    assert compressed == [(True,)]

    updated = known_candles(old, 3)  # same 2 minutes with new values + one new minute
    for c in updated:
        c.close = c.open + 0.25
        c.volume = 42
    assert await market_service.upsert_candles(session, instrument.id, updated) == 3
    rows = await market_service.get_candles(
        session, instrument.id, Timeframe.m1, start=old, limit=10
    )
    assert [(r.close, r.volume) for r in rows] == [(100.25, 42), (101.25, 42), (102.25, 42)]
