"""B5 data-quality gate: the last-closed-bar cut and every check of ``data_quality.assess``,
on synthetic candles and the FxPro calendar (docs/instruments.md), with fixed UTC times."""

import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Timeframe
from app.models.instrument import MarketType
from app.schemas.market import CandleIn
from app.services import data_quality, market_service, sessions
from app.services.data_quality import QualityStatus, Thresholds
from app.services.market_service import CandleRow
from app.services.seed_service import FXPRO_SESSION_CALENDAR as FXPRO
from tests.market_utils import make_instrument

MIN = timedelta(minutes=1)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def bars(
    start: datetime,
    end: datetime,
    calendar=FXPRO,
    skip=(),
    price: float = 2000.0,
) -> list[CandleRow]:
    """A consistent 1m candle for every minute the calendar expects in [start, end), except
    ``skip``; closes move by at most 0.05 % from one minute to the next."""
    out = []
    for i, ts in enumerate(sessions.expected_bar_starts(calendar, start, end)):
        if ts in skip:
            continue
        p = price + (i % 10) * 0.1
        out.append(CandleRow(ts, p, p + 0.5, p - 0.5, p + 0.1, 1.0, None, 0.2))
    return out


def with_close(rows: list[CandleRow], ts: datetime, close: float) -> list[CandleRow]:
    out = []
    for r in rows:
        if r.ts == ts:
            r = CandleRow(
                r.ts, r.open, max(r.high, close), min(r.low, close), close, 1.0, None, 0.2
            )
        out.append(r)
    return out


def check(report, name: str):
    return next(c for c in report.checks if c.name == name)


# --- the last closed bar --------------------------------------------------------------------


def test_watermark_rule() -> None:
    # data up to the 10:06 bar, 20 s into 10:07: the 10:06 bar has ended
    assert market_service.watermark_from(utc(2026, 7, 15, 10, 6), utc(2026, 7, 15, 10, 7, 20)) == (
        utc(2026, 7, 15, 10, 7)
    )
    # the running minute is never closed, even when a source already wrote it
    assert market_service.watermark_from(utc(2026, 7, 15, 10, 7), utc(2026, 7, 15, 10, 7, 20)) == (
        utc(2026, 7, 15, 10, 7)
    )
    # a closure right after the last bar: the watermark follows the clock
    assert market_service.watermark_from(
        utc(2026, 7, 15, 20, 54), utc(2026, 7, 15, 21, 30, 5), FXPRO
    ) == utc(2026, 7, 15, 21, 30)
    assert market_service.watermark_from(None, utc(2026, 7, 15, 10, 7)) is None


# (last 1m bar, now, timeframe, last closed bar)
CUTS = [
    (utc(2026, 7, 15, 10, 6), utc(2026, 7, 15, 10, 7, 20), "15m", utc(2026, 7, 15, 9, 45)),
    (utc(2026, 7, 15, 10, 14), utc(2026, 7, 15, 10, 15, 5), "15m", utc(2026, 7, 15, 10, 0)),
    (utc(2026, 7, 15, 10, 6), utc(2026, 7, 15, 10, 7, 20), "1h", utc(2026, 7, 15, 9, 0)),
    (utc(2026, 7, 15, 10, 59), utc(2026, 7, 15, 11, 0, 5), "1h", utc(2026, 7, 15, 10, 0)),
]


@pytest.mark.parametrize(("last_bar", "now", "timeframe", "closed"), CUTS)
def test_last_closed_bar(last_bar, now, timeframe, closed) -> None:
    rows = bars(now - timedelta(days=10), last_bar + MIN)  # 200 x 1h is 8.3 days
    report = data_quality.assess(rows, calendar=FXPRO, now=now, timeframe=timeframe)
    assert report.last_closed_bar == closed
    assert report.status == QualityStatus.ok, report.checks


@pytest.mark.parametrize(("last_bar", "now", "timeframe", "closed"), CUTS)
async def test_closed_candles_cut(session: AsyncSession, last_bar, now, timeframe, closed) -> None:
    timeframe = Timeframe(timeframe)
    instrument = await make_instrument(session)
    start = utc(2026, 7, 15, 7)
    minutes = int((last_bar - start) / MIN) + 1
    candles = [
        CandleIn(ts=start + i * MIN, open=10, high=11, low=9, close=10.5, volume=1)
        for i in range(minutes)
    ]
    # the running minute is already written too (simulate-live does that)
    candles.append(CandleIn(ts=last_bar + MIN, open=10, high=11, low=9, close=10.5, volume=1))
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()

    result = await market_service.get_closed_candles(
        session, instrument.id, timeframe, now=now, limit=50
    )
    assert result.watermark == last_bar + MIN
    assert result.candles[-1].ts == closed
    assert result.last_closed_bar_ts == closed
    assert all(c.ts + timeframe.interval <= result.watermark for c in result.candles)
    # the plain read still has the forming bucket
    plain = await market_service.get_candles(session, instrument.id, timeframe, limit=50)
    assert plain[-1].ts == closed + timeframe.interval
    # paging back: last_closed_bar_ts is still the newest closed bar
    older = await market_service.get_closed_candles(
        session, instrument.id, timeframe, end=start + timeframe.interval, now=now
    )
    assert older.candles[-1].ts == start + timeframe.interval
    assert older.last_closed_bar_ts == closed


async def test_closed_only_query_parameter(client, session: AsyncSession, admin_headers) -> None:
    instrument = await make_instrument(session)
    # data ending in the middle of a 15m bucket, an hour ago
    end = market_service.floor_to_bucket(datetime.now(UTC), timedelta(minutes=15)) - timedelta(
        hours=1, minutes=8
    )
    start = end - timedelta(hours=2)
    candles = [
        CandleIn(ts=start + i * MIN, open=10, high=11, low=9, close=10.5, volume=1)
        for i in range(int((end - start) / MIN) + 1)
    ]
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    url = f"/api/v1/market/instruments/{instrument.id}/candles?timeframe=15m"

    default = (await client.get(url, headers=admin_headers)).json()
    closed = (await client.get(url + "&closed_only=true", headers=admin_headers)).json()
    forming = int(market_service.floor_to_bucket(end, timedelta(minutes=15)).timestamp())
    assert default["candles"][-1]["time"] == forming
    assert "last_closed_bar" not in default
    assert closed["candles"][-1]["time"] == forming - 900
    assert closed["last_closed_bar"] == forming - 900
    assert len(closed["candles"]) == len(default["candles"]) - 1

    other = await make_instrument(session, symbol="ETH/USDT")
    empty = await client.get(
        f"/api/v1/market/instruments/{other.id}/candles?timeframe=15m&closed_only=true",
        headers=admin_headers,
    )
    assert empty.status_code == 200
    assert empty.json()["candles"] == [] and "last_closed_bar" not in empty.json()


# --- gaps -----------------------------------------------------------------------------------


def test_winter_weekend_is_not_a_gap() -> None:
    # Friday 9 Jan 2026 closes 21:55 UTC, Sunday 11 Jan opens 23:00 UTC (EST)
    now = utc(2026, 1, 11, 23, 31, 10)
    rows = bars(utc(2026, 1, 8), utc(2026, 1, 11, 23, 31))
    assert rows[-1].ts == utc(2026, 1, 11, 23, 30)
    assert not any(utc(2026, 1, 9, 21, 55) <= r.ts < utc(2026, 1, 11, 23) for r in rows)
    report = data_quality.assess(rows, calendar=FXPRO, now=now)
    assert report.status == QualityStatus.ok, report.checks
    assert report.last_closed_bar == utc(2026, 1, 11, 23, 15)
    assert check(report, "gaps").detail.startswith("0 of ")
    # the same weekend assessed on Saturday: closed, the gate does not run
    saturday = data_quality.assess(
        bars(utc(2026, 1, 6), utc(2026, 1, 10, 12)), calendar=FXPRO, now=utc(2026, 1, 10, 12)
    )
    assert saturday.status == QualityStatus.closed
    assert check(saturday, "gaps").ok


def test_summer_daily_break_is_not_a_gap() -> None:
    # Wednesday 15 July 2026: break 20:55-22:00 UTC (EDT)
    now = utc(2026, 7, 15, 22, 21, 15)
    rows = bars(utc(2026, 7, 12, 22), utc(2026, 7, 15, 22, 21))
    assert not any(utc(2026, 7, 15, 20, 55) <= r.ts < utc(2026, 7, 15, 22) for r in rows)
    report = data_quality.assess(rows, calendar=FXPRO, now=now)
    assert report.status == QualityStatus.ok, report.checks
    assert report.last_closed_bar == utc(2026, 7, 15, 22)
    # during the break the last bar before it is the last closed one
    during = data_quality.assess(
        [r for r in rows if r.ts < utc(2026, 7, 15, 21)],
        calendar=FXPRO,
        now=utc(2026, 7, 15, 21, 30),
    )
    assert during.status == QualityStatus.closed
    assert during.last_closed_bar == utc(2026, 7, 15, 20, 45)
    assert check(during, "closed_bar").ok and check(during, "gaps").ok


def test_missing_minute_inside_the_evaluated_bar() -> None:
    now = utc(2026, 7, 15, 10, 15, 20)
    rows = bars(utc(2026, 7, 13), utc(2026, 7, 15, 10, 15), skip={utc(2026, 7, 15, 10, 7)})
    report = data_quality.assess(rows, calendar=FXPRO, now=now)
    assert report.status == QualityStatus.degraded
    assert report.last_closed_bar == utc(2026, 7, 15, 10)
    assert not check(report, "closed_bar").ok
    assert "10:07" in check(report, "closed_bar").detail
    assert not check(report, "gaps").ok
    assert "1 inside the evaluated bar" in check(report, "gaps").detail


def _spread_missing(share: float) -> tuple[list[CandleRow], datetime]:
    now = utc(2026, 7, 15, 10, 15, 20)
    start, end = utc(2026, 7, 13, 8, 15), utc(2026, 7, 15, 10, 15)  # 200 x 15m
    expected = list(sessions.expected_bar_starts(FXPRO, start, end))
    outside = [t for t in expected if t < utc(2026, 7, 15, 10)]
    count = round(share * len(expected))
    step = len(outside) // count
    skip = set(outside[::step][:count])
    return bars(start - timedelta(hours=1), end, skip=skip), now


def test_missing_share_over_the_limit() -> None:
    rows, now = _spread_missing(0.015)
    report = data_quality.assess(rows, calendar=FXPRO, now=now)
    assert report.status == QualityStatus.degraded
    gaps = check(report, "gaps")
    assert not gaps.ok and "(1.50 %" in gaps.detail and "longest gap 1 min" in gaps.detail
    assert check(report, "closed_bar").ok


def test_missing_share_under_the_limit() -> None:
    rows, now = _spread_missing(0.005)
    report = data_quality.assess(rows, calendar=FXPRO, now=now)
    assert report.status == QualityStatus.ok, report.checks
    assert "14 of 2870 expected 1m bars missing (0.49 %" in check(report, "gaps").detail


def test_holiday_is_not_a_gap() -> None:
    holiday = {**FXPRO, "holidays": [{"name": "test holiday", "date": "2026-07-14"}]}
    now = utc(2026, 7, 15, 22, 21, 15)
    rows = bars(utc(2026, 7, 12, 22), utc(2026, 7, 15, 22, 21), calendar=holiday)
    report = data_quality.assess(rows, calendar=holiday, now=now)
    assert report.status == QualityStatus.ok, report.checks
    # without the holiday entry, the same data misses a whole day
    plain = data_quality.assess(rows, calendar=FXPRO, now=now)
    assert plain.status == QualityStatus.degraded and not check(plain, "gaps").ok
    assert "longest gap" in check(plain, "gaps").detail


# --- freshness ------------------------------------------------------------------------------


def test_fresh_feed() -> None:
    rows = bars(utc(2026, 7, 13), utc(2026, 7, 15, 10))  # last bar 09:59, watermark 10:00
    report = data_quality.assess(rows, calendar=FXPRO, now=utc(2026, 7, 15, 10, 1, 30))
    assert report.lag_seconds == 90
    assert report.status == QualityStatus.ok, report.checks


def test_stale_feed_during_the_session() -> None:
    rows = bars(utc(2026, 7, 13), utc(2026, 7, 15, 10))
    report = data_quality.assess(rows, calendar=FXPRO, now=utc(2026, 7, 15, 10, 5))
    assert report.lag_seconds == 300
    assert report.status == QualityStatus.degraded
    assert [c.name for c in report.failed] == ["freshness"]
    assert "lag 300 s (max 120 s)" in report.failed[0].detail


@pytest.mark.parametrize(
    ("saturday", "opens"),
    [
        (utc(2026, 1, 10, 12), utc(2026, 1, 11, 23)),  # EST: Sunday 23:00 UTC
        (utc(2026, 7, 18, 12), utc(2026, 7, 19, 22)),  # EDT: Sunday 22:00 UTC
    ],
)
def test_saturday_is_closed(saturday, opens) -> None:
    rows = bars(saturday - timedelta(days=3), saturday)
    report = data_quality.assess(rows, calendar=FXPRO, now=saturday)
    assert report.status == QualityStatus.closed
    assert report.next_open == opens
    freshness = check(report, "freshness")
    assert freshness.ok and f"next open {opens:%Y-%m-%dT%H:%M}Z" in freshness.detail


def test_grace_after_the_sunday_open() -> None:
    # the feed stopped two hours before Friday's close and nothing came since
    rows = bars(utc(2026, 1, 7), utc(2026, 1, 9, 20))
    opened = utc(2026, 1, 11, 23)
    early = data_quality.assess(rows, calendar=FXPRO, now=opened + timedelta(seconds=90))
    assert early.status == QualityStatus.ok, early.checks
    assert "grace after the open" in check(early, "freshness").detail
    late = data_quality.assess(rows, calendar=FXPRO, now=opened + timedelta(minutes=3))
    assert late.status == QualityStatus.degraded
    assert not check(late, "freshness").ok

    # a feed that was fine on Friday: right after the open the lag counts from the open
    rows = bars(utc(2026, 1, 7), utc(2026, 1, 9, 22))
    report = data_quality.assess(rows, calendar=FXPRO, now=opened + timedelta(seconds=50))
    assert report.status == QualityStatus.ok and report.lag_seconds == 50
    report = data_quality.assess(rows, calendar=FXPRO, now=opened + timedelta(minutes=4))
    assert report.status == QualityStatus.degraded and report.lag_seconds == 240


# --- prices ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("move", "status"), [(0.03, QualityStatus.degraded), (0.01, QualityStatus.ok)]
)
def test_spike_on_the_evaluated_bar(move: float, status: QualityStatus) -> None:
    now = utc(2026, 7, 15, 10, 15, 20)
    rows = bars(utc(2026, 7, 13), utc(2026, 7, 15, 10, 15))
    previous = next(r for r in rows if r.ts == utc(2026, 7, 15, 10, 9))
    rows = with_close(rows, utc(2026, 7, 15, 10, 10), round(previous.close * (1 + move), 2))
    report = data_quality.assess(rows, calendar=FXPRO, now=now)
    assert report.status == status, report.checks
    if status == QualityStatus.degraded:
        assert [c.name for c in report.failed] == ["ohlc"]
        assert "spike 3.00 %" in report.failed[0].detail


def test_weekend_gap_is_not_a_spike() -> None:
    friday = bars(utc(2026, 1, 8), utc(2026, 1, 9, 22))
    sunday = bars(utc(2026, 1, 11, 23), utc(2026, 1, 11, 23, 31), price=2060.0)  # +3 %
    report = data_quality.assess(friday + sunday, calendar=FXPRO, now=utc(2026, 1, 11, 23, 31))
    assert report.last_closed_bar == utc(2026, 1, 11, 23, 15)
    assert report.status == QualityStatus.ok, report.checks


def test_zero_price_is_rejected() -> None:
    now = utc(2026, 7, 15, 10, 15, 20)
    rows = bars(utc(2026, 7, 13), utc(2026, 7, 15, 10, 15))
    rows = [
        CandleRow(r.ts, 0.0, r.high, 0.0, r.close, 1.0, None, None)
        if r.ts == utc(2026, 7, 14, 12)
        else r
        for r in rows
    ]
    report = data_quality.assess(rows, calendar=FXPRO, now=now)
    assert report.status == QualityStatus.degraded
    assert "2026-07-14T12:00Z price <= 0" in check(report, "ohlc").detail


def test_spread_limit_is_optional() -> None:
    now = utc(2026, 7, 15, 10, 15, 20)
    rows = bars(utc(2026, 7, 13), utc(2026, 7, 15, 10, 15))  # spread 0.2
    assert data_quality.assess(rows, calendar=FXPRO, now=now).status == QualityStatus.ok
    strict = data_quality.assess(
        rows, calendar=FXPRO, now=now, thresholds=Thresholds(max_spread=0.1)
    )
    assert (
        strict.status == QualityStatus.degraded
        and "spread 0.2 > 0.1" in check(strict, "ohlc").detail
    )


# --- no data --------------------------------------------------------------------------------


def test_no_data() -> None:
    report = data_quality.assess([], calendar=FXPRO, now=utc(2026, 7, 15, 10))
    assert report.status == QualityStatus.no_data
    assert report.last_closed_bar is None and report.lag_seconds is None
    assert [c.name for c in report.failed] == ["no_data"]
    # stale data outside the window: still no_data, with the lag of the last bar
    report = data_quality.assess(
        [], calendar=None, now=utc(2026, 7, 15, 10), last_bar_ts=utc(2026, 7, 1)
    )
    assert report.status == QualityStatus.no_data and report.lag_seconds == 14 * 86400 + 36000 - 60


def test_crypto_without_calendar_trades_all_week() -> None:
    now = utc(2026, 1, 10, 12, 0, 20)  # a Saturday
    rows = bars(utc(2026, 1, 8), utc(2026, 1, 10, 12), calendar=data_quality.ALWAYS_OPEN)
    report = data_quality.assess(rows, calendar=None, now=now)
    assert report.status == QualityStatus.ok, report.checks
    assert report.last_closed_bar == utc(2026, 1, 10, 11, 45)


# --- loader ---------------------------------------------------------------------------------


async def test_load_and_assess(session: AsyncSession, db_connection) -> None:
    instrument = await make_instrument(
        session,
        symbol="XAU/USD",
        source="fxpro",
        market=MarketType.commodity,
        session_calendar=FXPRO,
    )
    now = utc(2026, 7, 15, 10, 15, 20)
    rows = bars(utc(2026, 7, 12, 22), utc(2026, 7, 15, 10, 16))  # incl. the running minute
    await market_service.upsert_candles(
        session,
        instrument.id,
        [
            CandleIn(ts=r.ts, open=r.open, high=r.high, low=r.low, close=r.close, volume=1)
            for r in rows
        ],
    )
    await session.commit()

    statements: list[str] = []
    sync = db_connection.sync_connection

    def count(*_args) -> None:
        statements.append(_args[2])

    event.listen(sync, "before_cursor_execute", count)
    try:
        started = time.perf_counter()
        report = await data_quality.load_and_assess(session, instrument, "15m", now)
        elapsed = time.perf_counter() - started
    finally:
        event.remove(sync, "before_cursor_execute", count)

    assert len([s for s in statements if s.startswith("SELECT")]) == 2  # not the savepoint
    assert report.instrument == "fxpro:XAU/USD"
    assert report.status == QualityStatus.ok, report.checks
    assert report.last_closed_bar == utc(2026, 7, 15, 10)
    assert report.watermark == utc(2026, 7, 15, 10, 15)
    assert int(check(report, "no_data").detail.split()[0]) > 2500  # 200 x 15m, breaks excluded
    print(f"load_and_assess: 2 queries, {elapsed * 1000:.1f} ms")
    assert elapsed < 2
