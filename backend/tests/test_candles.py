import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Candle, Timeframe
from app.services import market_service
from tests.market_utils import candle_json, known_candles, make_instrument

# A Monday, so the 4h (08:00-12:00) and 1d buckets contain both hours of test data.
T0 = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)


def candles_url(instrument_id: uuid.UUID | str) -> str:
    return f"/api/v1/market/instruments/{instrument_id}/candles"


def ingest_url(instrument_id: uuid.UUID | str) -> str:
    return f"/api/v1/admin/instruments/{instrument_id}/candles"


async def _count(session: AsyncSession, instrument_id: uuid.UUID) -> int:
    return await session.scalar(
        select(func.count()).select_from(Candle).where(Candle.instrument_id == instrument_id)
    )


# --- upsert (service) -----------------------------------------------------------------------


async def test_upsert_insert_reinsert_and_update(session: AsyncSession) -> None:
    instrument = await make_instrument(session)
    candles = known_candles(T0, 3)
    assert await market_service.upsert_candles(session, instrument.id, candles) == 3
    assert await market_service.upsert_candles(session, instrument.id, candles) == 3
    assert await _count(session, instrument.id) == 3

    # a live stream keeps rewriting the newest candle
    last = candles[-1].model_copy(update={"high": 200.0, "close": 150.0, "volume": 99.0})
    assert await market_service.upsert_candles(session, instrument.id, [last]) == 1
    assert await _count(session, instrument.id) == 3
    latest = await market_service.get_latest_candle(session, instrument.id, Timeframe.m1)
    assert (latest.ts, latest.high, latest.close, latest.volume) == (last.ts, 200.0, 150.0, 99.0)


async def test_upsert_duplicates_in_one_batch_last_wins(session: AsyncSession) -> None:
    instrument = await make_instrument(session)
    first, second = known_candles(T0, 1)[0], known_candles(T0, 1)[0]
    second = second.model_copy(update={"volume": 7.0})
    assert await market_service.upsert_candles(session, instrument.id, [first, second]) == 1
    latest = await market_service.get_latest_candle(session, instrument.id, Timeframe.m1)
    assert latest.volume == 7.0


async def test_upsert_is_chunked(session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(market_service, "UPSERT_CHUNK_SIZE", 2)
    instrument = await make_instrument(session)
    assert await market_service.upsert_candles(session, instrument.id, known_candles(T0, 5)) == 5
    assert await _count(session, instrument.id) == 5


async def test_latest_candle_none_when_empty(session: AsyncSession) -> None:
    instrument = await make_instrument(session)
    for tf in Timeframe:
        assert await market_service.get_latest_candle(session, instrument.id, tf) is None


# --- aggregation (real-time continuous aggregates) ------------------------------------------


def _agg(i0: int, n: int) -> dict:
    """Expected aggregate of known_candles i0..i0+n-1."""
    last = i0 + n - 1
    return {
        "open": 100 + i0,
        "high": 101.5 + last,
        "low": 99 + i0,
        "close": 100.5 + last,
        "volume": sum(range(i0 + 1, last + 2)),
    }


def _bars(body: dict) -> list[dict]:
    return [{k: c[k] for k in ("open", "high", "low", "close", "volume")} for c in body["candles"]]


def _times(body: dict) -> list[int]:
    return [c["time"] for c in body["candles"]]


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


@pytest.fixture
async def two_hours(session: AsyncSession):
    instrument = await make_instrument(session)
    await market_service.upsert_candles(session, instrument.id, known_candles(T0, 120))
    await session.commit()
    return instrument


async def test_aggregates_1h(client: AsyncClient, trader_headers, two_hours) -> None:
    res = await client.get(
        candles_url(two_hours.id), params={"timeframe": "1h"}, headers=trader_headers
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["instrument_id"] == str(two_hours.id) and body["timeframe"] == "1h"
    assert _times(body) == [_ts(T0), _ts(T0 + timedelta(hours=1))]
    assert _bars(body) == [_agg(0, 60), _agg(60, 60)]
    assert _bars(body)[0] == {
        "open": 100,
        "high": 160.5,
        "low": 99,
        "close": 159.5,
        "volume": 1830,
    }


@pytest.mark.parametrize(
    ("timeframe", "minutes", "first_bucket"),
    [
        ("1m", 1, T0),
        ("5m", 5, T0),
        ("15m", 15, T0),
        ("4h", 120, T0.replace(hour=8)),
        ("1d", 120, T0.replace(hour=0)),
    ],
)
async def test_aggregates_other_timeframes(
    client: AsyncClient,
    trader_headers,
    two_hours,
    timeframe: str,
    minutes: int,
    first_bucket: datetime,
) -> None:
    res = await client.get(
        candles_url(two_hours.id),
        params={"timeframe": timeframe, "limit": 500},
        headers=trader_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    count = 120 // minutes
    assert len(body["candles"]) == count
    assert _bars(body) == [_agg(k * minutes, minutes) for k in range(count)]
    step = 60 * (60 if timeframe in ("4h", "1d") else minutes)
    assert _times(body)[0] == _ts(first_bucket)
    if count > 1:
        assert _times(body)[1] - _times(body)[0] == step


async def test_aggregates_service_trades_sum(session: AsyncSession, two_hours) -> None:
    rows = await market_service.get_candles(session, two_hours.id, Timeframe.h1)
    assert [r.trades for r in rows] == [600, 600]
    rows = await market_service.get_candles(session, two_hours.id, Timeframe.d1)
    assert [(r.ts, r.trades, r.volume) for r in rows] == [(T0.replace(hour=0), 1200, 7260)]


async def test_latest_candle_per_timeframe(session: AsyncSession, two_hours) -> None:
    latest = await market_service.get_latest_candle(session, two_hours.id, Timeframe.m15)
    assert latest.ts == T0 + timedelta(minutes=105)
    assert latest.close == 100.5 + 119


async def test_aggregates_do_not_mix_instruments(
    session: AsyncSession, client: AsyncClient, trader_headers, two_hours
) -> None:
    other = await make_instrument(session, "ETH/USDT")
    await market_service.upsert_candles(session, other.id, known_candles(T0, 60))
    await session.commit()
    res = await client.get(
        candles_url(two_hours.id), params={"timeframe": "1h"}, headers=trader_headers
    )
    assert _bars(res.json()) == [_agg(0, 60), _agg(60, 60)]


# --- reading: ordering, limit, ranges --------------------------------------------------------


async def test_default_is_latest_n_ascending(
    client: AsyncClient, trader_headers, two_hours
) -> None:
    res = await client.get(
        candles_url(two_hours.id),
        params={"timeframe": "1m", "limit": 3},
        headers=trader_headers,
    )
    assert _times(res.json()) == [_ts(T0 + timedelta(minutes=m)) for m in (117, 118, 119)]


async def test_start_end_filter_inclusive(client: AsyncClient, trader_headers, two_hours) -> None:
    start, end = T0 + timedelta(minutes=10), T0 + timedelta(minutes=14)
    res = await client.get(
        candles_url(two_hours.id),
        params={"timeframe": "1m", "start": start.isoformat(), "end": end.isoformat()},
        headers=trader_headers,
    )
    assert _times(res.json()) == [_ts(start + timedelta(minutes=m)) for m in range(5)]


async def test_start_with_limit_returns_first_n(
    client: AsyncClient, trader_headers, two_hours
) -> None:
    res = await client.get(
        candles_url(two_hours.id),
        params={"timeframe": "5m", "start": T0.isoformat(), "limit": 2},
        headers=trader_headers,
    )
    assert _times(res.json()) == [_ts(T0), _ts(T0 + timedelta(minutes=5))]


async def test_end_only_returns_latest_before_end(
    client: AsyncClient, trader_headers, two_hours
) -> None:
    res = await client.get(
        candles_url(two_hours.id),
        params={"timeframe": "15m", "end": "2026-01-05T10:59:00Z", "limit": 2},
        headers=trader_headers,
    )
    assert _times(res.json()) == [_ts(T0 + timedelta(minutes=m)) for m in (30, 45)]


async def test_naive_datetimes_are_utc(client: AsyncClient, trader_headers, two_hours) -> None:
    res = await client.get(
        candles_url(two_hours.id),
        params={"timeframe": "1h", "start": "2026-01-05T11:00:00"},
        headers=trader_headers,
    )
    assert _times(res.json()) == [_ts(T0 + timedelta(hours=1))]


async def test_empty_range(client: AsyncClient, trader_headers, two_hours) -> None:
    res = await client.get(
        candles_url(two_hours.id),
        params={"timeframe": "1h", "start": "2030-01-01T00:00:00Z"},
        headers=trader_headers,
    )
    assert res.status_code == 200 and res.json()["candles"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"timeframe": "1m", "start": "2026-01-05T11:00:00Z", "end": "2026-01-05T10:00:00Z"},
        {"timeframe": "2h"},
        {},
        {"timeframe": "1m", "limit": 5001},
        {"timeframe": "1m", "limit": 0},
        {"timeframe": "1m", "start": "yesterday"},
    ],
)
async def test_candles_bad_params_422(
    client: AsyncClient, trader_headers, two_hours, params: dict
) -> None:
    res = await client.get(candles_url(two_hours.id), params=params, headers=trader_headers)
    assert res.status_code == 422


async def test_candles_unknown_instrument_404(client: AsyncClient, trader_headers) -> None:
    res = await client.get(
        candles_url(uuid.uuid4()), params={"timeframe": "1m"}, headers=trader_headers
    )
    assert res.status_code == 404


async def test_candles_require_auth(client: AsyncClient, two_hours) -> None:
    res = await client.get(candles_url(two_hours.id), params={"timeframe": "1m"})
    assert res.status_code == 401


# --- ingest API ------------------------------------------------------------------------------


async def test_ingest_ok_and_idempotent(
    client: AsyncClient, session: AsyncSession, admin_headers
) -> None:
    instrument = await make_instrument(session)
    body = {"candles": [candle_json(T0), candle_json(T0 + timedelta(minutes=1))]}
    for _ in range(2):
        res = await client.post(ingest_url(instrument.id), json=body, headers=admin_headers)
        assert res.status_code == 200, res.text
        assert res.json() == {"written": 2}
    assert await _count(session, instrument.id) == 2


async def test_ingest_accepts_unix_seconds_and_offsets(
    client: AsyncClient, session: AsyncSession, admin_headers
) -> None:
    instrument = await make_instrument(session)
    unix_seconds = candle_json(_ts(T0))
    unix_seconds["ts"] = _ts(T0)
    time_alias = candle_json(T0)
    del time_alias["ts"]
    time_alias["time"] = "2026-01-05T13:01:00+03:00"  # = 10:01 UTC
    body = {"candles": [unix_seconds, time_alias]}
    res = await client.post(ingest_url(instrument.id), json=body, headers=admin_headers)
    assert res.status_code == 200, res.text
    rows = await market_service.get_candles(session, instrument.id, Timeframe.m1)
    assert [r.ts for r in rows] == [T0, T0 + timedelta(minutes=1)]


@pytest.mark.parametrize(
    "candle",
    [
        candle_json("2026-01-05T10:00:30Z"),  # not aligned to the minute
        candle_json("2026-01-05T10:00:00.5Z"),  # sub-second
        candle_json("2026-01-05T10:00:00"),  # no timezone
        candle_json(T0, high=8.0),  # high < low
        candle_json(T0, high=10.2),  # high < close
        candle_json(T0, low=10.2),  # low > open
        candle_json(T0, volume=-1),  # negative volume
        candle_json(T0, trades=-1),
        {"ts": T0.isoformat(), "open": 1, "high": 2, "low": 0.5},  # missing fields
    ],
)
async def test_ingest_validation_422(
    client: AsyncClient, session: AsyncSession, admin_headers, candle: dict
) -> None:
    instrument = await make_instrument(session)
    res = await client.post(
        ingest_url(instrument.id), json={"candles": [candle]}, headers=admin_headers
    )
    assert res.status_code == 422
    assert await _count(session, instrument.id) == 0


async def test_ingest_batch_limits(
    client: AsyncClient, session: AsyncSession, admin_headers
) -> None:
    instrument = await make_instrument(session)
    res = await client.post(ingest_url(instrument.id), json={"candles": []}, headers=admin_headers)
    assert res.status_code == 422
    too_many = [candle_json(T0 + timedelta(minutes=i)) for i in range(5001)]
    res = await client.post(
        ingest_url(instrument.id), json={"candles": too_many}, headers=admin_headers
    )
    assert res.status_code == 422
    res = await client.post(
        ingest_url(instrument.id), json={"candles": too_many[:5000]}, headers=admin_headers
    )
    assert res.status_code == 200 and res.json() == {"written": 5000}


async def test_ingest_unknown_instrument_404(client: AsyncClient, admin_headers) -> None:
    res = await client.post(
        ingest_url(uuid.uuid4()), json={"candles": [candle_json(T0)]}, headers=admin_headers
    )
    assert res.status_code == 404


async def test_ingest_access(client: AsyncClient, session: AsyncSession, trader_headers) -> None:
    instrument = await make_instrument(session)
    body = {"candles": [candle_json(T0)]}
    assert (await client.post(ingest_url(instrument.id), json=body)).status_code == 401
    res = await client.post(ingest_url(instrument.id), json=body, headers=trader_headers)
    assert res.status_code == 403


async def test_ingest_refreshes_aggregates_only_for_old_data(
    client: AsyncClient, session: AsyncSession, admin_headers, refresh_calls
) -> None:
    instrument = await make_instrument(session)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    recent = [candle_json(now - timedelta(minutes=m)) for m in range(3)]
    res = await client.post(
        ingest_url(instrument.id), json={"candles": recent}, headers=admin_headers
    )
    assert res.status_code == 200
    assert refresh_calls == []

    backfill = [candle_json(T0 + timedelta(minutes=m)) for m in range(3)]
    res = await client.post(
        ingest_url(instrument.id), json={"candles": backfill}, headers=admin_headers
    )
    assert res.status_code == 200
    assert refresh_calls == [(T0, T0 + timedelta(minutes=2))]


# --- spread, source, received_at (migration 0013) ---------------------------------------------


async def _extra(session: AsyncSession, instrument_id: uuid.UUID) -> list[tuple]:
    session.expire_all()
    rows = await session.execute(
        select(Candle.spread, Candle.source, Candle.received_at)
        .where(Candle.instrument_id == instrument_id)
        .order_by(Candle.ts)
    )
    return list(rows.all())


async def test_upsert_spread_source_received_at(session: AsyncSession) -> None:
    instrument_id = (await make_instrument(session)).id  # _extra() expires ORM objects
    first_arrival = datetime(2026, 1, 5, 10, 1, 2, tzinfo=UTC)
    [bar] = known_candles(T0, 1)
    sent = bar.model_copy(
        update={"spread": 0.25, "source": "fxpro_ctrader", "received_at": first_arrival}
    )
    await market_service.upsert_candles(session, instrument_id, [sent])
    assert await _extra(session, instrument_id) == [(0.25, "fxpro_ctrader", first_arrival)]

    # a re-send without spread/source keeps them and keeps the first arrival time
    later = first_arrival + timedelta(minutes=5)
    resent = bar.model_copy(update={"close": bar.close, "received_at": later})
    await market_service.upsert_candles(session, instrument_id, [resent])
    assert await _extra(session, instrument_id) == [(0.25, "fxpro_ctrader", first_arrival)]

    # new values overwrite spread/source; an earlier arrival time wins
    earlier = first_arrival - timedelta(seconds=30)
    update = bar.model_copy(update={"spread": 0.4, "source": "other", "received_at": earlier})
    await market_service.upsert_candles(session, instrument_id, [update])
    assert await _extra(session, instrument_id) == [(0.4, "other", earlier)]


async def test_received_at_defaults_to_now(session: AsyncSession) -> None:
    instrument_id = (await make_instrument(session)).id
    before = datetime.now(UTC) - timedelta(seconds=5)
    await market_service.upsert_candles(session, instrument_id, known_candles(T0, 2))
    rows = await _extra(session, instrument_id)
    assert [(spread, source) for spread, source, _ in rows] == [(None, None), (None, None)]
    assert all(received >= before for _, _, received in rows)


async def test_spread_on_1m_reads_only(
    client: AsyncClient, session: AsyncSession, trader_headers, admin_headers
) -> None:
    instrument_id = (await make_instrument(session)).id
    payload = [candle_json(T0 + timedelta(minutes=i)) for i in range(10)]
    payload[0] |= {"spread": 0.03, "source": " FXPRO_cTrader "}
    res = await client.post(
        ingest_url(instrument_id), json={"candles": payload}, headers=admin_headers
    )
    assert res.status_code == 200, res.text
    assert (await _extra(session, instrument_id))[0][:2] == (0.03, "fxpro_ctrader")

    res = await client.get(
        candles_url(instrument_id),
        params={"timeframe": "1m", "start": T0.isoformat()},
        headers=trader_headers,
    )
    candles = res.json()["candles"]
    assert candles[0]["spread"] == 0.03
    assert "spread" not in candles[1]  # omitted when unknown
    res = await client.get(
        candles_url(instrument_id),
        params={"timeframe": "5m", "start": T0.isoformat()},
        headers=trader_headers,
    )
    assert all("spread" not in c for c in res.json()["candles"])


@pytest.mark.parametrize(
    "extra",
    [
        {"spread": -0.01},
        {"spread": "nan"},
        {"source": ""},
        {"source": "x" * 33},
        {"source": "bad source"},
        {"received_at": "2026-01-05T10:00:00"},  # needs an offset
    ],
)
async def test_candle_fields_validation_422(
    client: AsyncClient, session: AsyncSession, admin_headers, extra: dict
) -> None:
    instrument = await make_instrument(session)
    candle = candle_json(T0, **extra)
    res = await client.post(
        ingest_url(instrument.id), json={"candles": [candle]}, headers=admin_headers
    )
    assert res.status_code == 422
