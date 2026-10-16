"""GET /indicators and POST /market/instruments/{id}/indicators."""

import random
import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
import trading_indicators as ti
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Timeframe
from app.schemas.indicators import IndicatorsResponse
from app.services import market_service
from app.services.seed_service import generate_demo_candles
from tests.market_utils import make_instrument

END = datetime(2026, 1, 6, 2, 59, tzinfo=UTC)  # 600 minutes from 17:00 the day before
N = 600


def url(instrument_id) -> str:
    return f"/api/v1/market/instruments/{instrument_id}/indicators"


@pytest.fixture
async def instrument(session: AsyncSession):
    instrument = await make_instrument(session, price_precision=2, quantity_precision=4)
    candles = generate_demo_candles(instrument, minutes=N, end=END, rng=random.Random(5))
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    return instrument


async def frame(session: AsyncSession, instrument_id, timeframe=Timeframe.m1) -> pd.DataFrame:
    rows = await market_service.get_candles(session, instrument_id, timeframe, limit=5000)
    return pd.DataFrame(
        {
            "open": [r.open for r in rows],
            "high": [r.high for r in rows],
            "low": [r.low for r in rows],
            "close": [r.close for r in rows],
            "volume": [r.volume for r in rows],
        },
        index=pd.DatetimeIndex([r.ts for r in rows]),
    )


def values(result: dict, output: str) -> np.ndarray:
    return np.array(
        [np.nan if p["value"] is None else p["value"] for p in result["outputs"][output]]
    )


def times(result: dict, output: str) -> list[int]:
    return [p["time"] for p in result["outputs"][output]]


# --- catalog ---------------------------------------------------------------------------------


async def test_catalog(client: AsyncClient, trader_headers) -> None:
    res = await client.get("/api/v1/indicators", headers=trader_headers)
    assert res.status_code == 200
    catalog = res.json()
    assert len(catalog) == 21
    rsi = next(i for i in catalog if i["name"] == "rsi")
    assert rsi["placement"] == "pane" and rsi["levels"] == [30, 70]
    assert rsi["params"][0] == {
        "name": "length",
        "type": "int",
        "default": 14,
        "min": 1,
        "max": 1000,
        "title": "Length",
    }
    assert (await client.get("/api/v1/indicators")).status_code == 401


# --- computing -------------------------------------------------------------------------------


async def test_single_indicator_matches_full_history(
    client: AsyncClient, session: AsyncSession, trader_headers, instrument
) -> None:
    body = {"timeframe": "1m", "limit": 100, "indicators": [{"name": "rsi"}]}
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    IndicatorsResponse.model_validate(data)  # serialized directly, but still the documented shape
    assert data["instrument_id"] == str(instrument.id) and data["timeframe"] == "1m"
    [result] = data["results"]
    assert result["name"] == "rsi" and result["params"] == {"length": 14}
    assert result["placement"] == "pane" and list(result["outputs"]) == ["rsi"]

    # the same window the candles endpoint returns
    candles = await client.get(
        f"/api/v1/market/instruments/{instrument.id}/candles",
        params={"timeframe": "1m", "limit": 100},
        headers=trader_headers,
    )
    assert times(result, "rsi") == [c["time"] for c in candles.json()["candles"]]

    # warm-up was loaded: no nulls, and equal to RSI computed on the whole history
    got = values(result, "rsi")
    assert not np.isnan(got).any()
    expected = ti.rsi((await frame(session, instrument.id))["close"]).to_numpy()[-100:]
    np.testing.assert_allclose(got, expected, rtol=1e-6)


async def test_multiple_indicators_with_defaults(
    client: AsyncClient, session: AsyncSession, trader_headers, instrument
) -> None:
    body = {
        "timeframe": "1m",
        "limit": 50,
        "indicators": [
            {"name": "macd"},
            {"name": "bollinger", "params": {"length": 20, "std": 2}},
            {"name": "ema", "params": {"length": 50}},
            {"name": "atr", "params": {"length": 14.0}},
            {"name": "ema", "params": {"length": 9}},
        ],
    }
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    assert res.status_code == 200, res.text
    results = res.json()["results"]
    assert [(r["name"], r["params"]) for r in results] == [
        ("macd", {"fast": 12, "slow": 26, "signal": 9}),
        ("bollinger", {"length": 20, "std": 2.0}),
        ("ema", {"length": 50}),
        ("atr", {"length": 14}),
        ("ema", {"length": 9}),
    ]
    assert list(results[0]["outputs"]) == ["macd", "signal", "histogram"]
    assert list(results[1]["outputs"]) == ["upper", "middle", "lower"]
    assert results[1]["placement"] == "overlay"
    df = await frame(session, instrument.id)
    for result, name, output in (
        (results[0], "macd", "signal"),
        (results[1], "bollinger", "upper"),
        (results[2], "ema", "ema"),
        (results[3], "atr", "atr"),
    ):
        got = values(result, output)
        assert len(got) == 50 and not np.isnan(got).any()
        expected = ti.compute(name, df, **result["params"])[output].to_numpy()[-50:]
        np.testing.assert_allclose(got, expected, rtol=1e-5)


async def test_nulls_when_history_is_too_short(
    client: AsyncClient, trader_headers, instrument
) -> None:
    first = END - timedelta(minutes=N - 1)
    body = {
        "timeframe": "1m",
        "start": first.isoformat(),
        "limit": 30,
        "indicators": [{"name": "rsi"}, {"name": "sma", "params": {"length": 5}}],
    }
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    rsi, sma = res.json()["results"]
    assert times(rsi, "rsi")[0] == int(first.timestamp())
    got = values(rsi, "rsi")
    assert np.isnan(got[:14]).all() and not np.isnan(got[14:]).any()
    got = values(sma, "sma")
    assert np.isnan(got[:4]).all() and not np.isnan(got[4:]).any()


async def test_start_end_window(client: AsyncClient, trader_headers, instrument) -> None:
    start, end = END - timedelta(minutes=100), END - timedelta(minutes=91)
    body = {
        "timeframe": "1m",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "indicators": [{"name": "wma", "params": {"length": 10}}],
    }
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    [wma] = res.json()["results"]
    assert times(wma, "wma") == [int((start + timedelta(minutes=m)).timestamp()) for m in range(10)]
    assert not np.isnan(values(wma, "wma")).any()


async def test_higher_timeframe(
    client: AsyncClient, session: AsyncSession, trader_headers, instrument
) -> None:
    body = {"timeframe": "1h", "limit": 4, "indicators": [{"name": "sma", "params": {"length": 3}}]}
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    [sma] = res.json()["results"]
    hourly = await frame(session, instrument.id, Timeframe.h1)
    assert len(hourly) == 10  # 17:00 .. 02:00
    np.testing.assert_allclose(values(sma, "sma"), ti.sma(hourly["close"], 3).to_numpy()[-4:])


async def test_vwap_window_starting_mid_day(
    client: AsyncClient, session: AsyncSession, trader_headers, instrument
) -> None:
    # the window starts at 01:00 UTC; VWAP still accumulates from 00:00 UTC
    start = datetime(2026, 1, 6, 1, 0, tzinfo=UTC)
    body = {"timeframe": "1m", "start": start.isoformat(), "indicators": [{"name": "vwap"}]}
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    [vwap] = res.json()["results"]
    full = ti.vwap(await frame(session, instrument.id)).loc[start:].to_numpy()
    np.testing.assert_allclose(values(vwap, "vwap"), full)


async def test_empty_instrument(client: AsyncClient, session: AsyncSession, trader_headers) -> None:
    empty = await make_instrument(session, "SOL/USDT")
    body = {"timeframe": "1m", "indicators": [{"name": "macd"}]}
    res = await client.post(url(empty.id), json=body, headers=trader_headers)
    assert res.status_code == 200
    assert res.json()["results"][0]["outputs"] == {"macd": [], "signal": [], "histogram": []}


# --- errors ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("indicators", "message"),
    [
        ([{"name": "nope"}], "indicators[0]: unknown indicator 'nope'"),
        ([{"name": "rsi"}, {"name": "rsi", "params": {"length": 0}}], "indicators[1]: rsi: length"),
        ([{"name": "rsi", "params": {"window": 3}}], "unknown parameter(s) window"),
        ([{"name": "macd", "params": {"fast": 30}}], "must be smaller than slow"),
        ([{"name": "ema", "params": {"length": "14"}}], "length must be a number"),
        ([{"name": "ema", "params": {"length": 2.5}}], "length must be an integer"),
    ],
)
async def test_invalid_indicators_422(
    client: AsyncClient, trader_headers, instrument, indicators, message: str
) -> None:
    body = {"timeframe": "1m", "indicators": indicators}
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    assert res.status_code == 422
    assert message in res.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {"timeframe": "1m", "indicators": []},
        {"timeframe": "1m", "indicators": [{"name": "sma"}] * 11},
        {"timeframe": "2h", "indicators": [{"name": "sma"}]},
        {"timeframe": "1m", "limit": 5001, "indicators": [{"name": "sma"}]},
        {
            "timeframe": "1m",
            "start": "2026-01-06T00:00:00Z",
            "end": "2026-01-05T00:00:00Z",
            "indicators": [{"name": "sma"}],
        },
        {"indicators": [{"name": "sma"}]},
    ],
)
async def test_bad_request_body_422(
    client: AsyncClient, trader_headers, instrument, body: dict
) -> None:
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    assert res.status_code == 422


async def test_ten_indicators_allowed(client: AsyncClient, trader_headers, instrument) -> None:
    body = {"timeframe": "1m", "limit": 10, "indicators": [{"name": "sma"}] * 10}
    res = await client.post(url(instrument.id), json=body, headers=trader_headers)
    assert res.status_code == 200 and len(res.json()["results"]) == 10


async def test_unknown_instrument_and_auth(client: AsyncClient, trader_headers) -> None:
    body = {"timeframe": "1m", "indicators": [{"name": "sma"}]}
    res = await client.post(url(uuid.uuid4()), json=body, headers=trader_headers)
    assert res.status_code == 404
    assert (await client.post(url(uuid.uuid4()), json=body)).status_code == 401
