import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import MarketType
from tests.market_utils import make_instrument

ADMIN = "/api/v1/admin/instruments"
PUBLIC = "/api/v1/market/instruments"


async def test_create_instrument(client: AsyncClient, admin_headers) -> None:
    res = await client.post(
        ADMIN,
        json={
            "symbol": " btc/usdt ",
            "source": "Binance",
            "market": "crypto",
            "price_precision": 2,
        },
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["symbol"] == "BTC/USDT" and body["source"] == "binance"
    assert body["base_asset"] == "BTC" and body["quote_asset"] == "USDT"
    assert body["price_precision"] == 2 and body["quantity_precision"] is None
    assert body["is_active"] is True


async def test_create_instrument_explicit_assets(client: AsyncClient, admin_headers) -> None:
    res = await client.post(
        ADMIN,
        json={
            "symbol": "AAPL",
            "source": "twelvedata",
            "market": "stock",
            "base_asset": "aapl",
            "quote_asset": "usd",
        },
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    assert (res.json()["base_asset"], res.json()["quote_asset"]) == ("AAPL", "USD")


async def test_create_duplicate_409(client: AsyncClient, admin_headers) -> None:
    payload = {"symbol": "ETH/USDT", "source": "binance", "market": "crypto"}
    assert (await client.post(ADMIN, json=payload, headers=admin_headers)).status_code == 201
    payload |= {"symbol": "eth/usdt", "source": "BINANCE"}
    assert (await client.post(ADMIN, json=payload, headers=admin_headers)).status_code == 409
    # same symbol from another source is a different instrument
    payload["source"] = "kraken"
    assert (await client.post(ADMIN, json=payload, headers=admin_headers)).status_code == 201


@pytest.mark.parametrize(
    "payload",
    [
        {"symbol": "AAPL", "source": "twelvedata", "market": "stock"},  # no assets, no slash
        {"symbol": "BTC/USDT", "source": "binance", "market": "futures"},
        {"symbol": "", "source": "binance", "market": "crypto"},
        {"symbol": "BTC/USDT", "source": "binance", "market": "crypto", "price_precision": -1},
    ],
)
async def test_create_invalid_422(client: AsyncClient, admin_headers, payload: dict) -> None:
    assert (await client.post(ADMIN, json=payload, headers=admin_headers)).status_code == 422


async def test_update_instrument(client: AsyncClient, session: AsyncSession, admin_headers) -> None:
    instrument = await make_instrument(session)
    res = await client.patch(
        f"{ADMIN}/{instrument.id}",
        json={"is_active": False, "quantity_precision": 5},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False and res.json()["quantity_precision"] == 5
    assert res.json()["symbol"] == "BTC/USDT"

    res = await client.patch(
        f"{ADMIN}/{instrument.id}", json={"is_active": None}, headers=admin_headers
    )
    assert res.status_code == 422
    res = await client.patch(f"{ADMIN}/{uuid.uuid4()}", json={}, headers=admin_headers)
    assert res.status_code == 404


async def test_admin_instrument_endpoints_access(
    client: AsyncClient, session: AsyncSession, trader_headers
) -> None:
    instrument = await make_instrument(session)
    payload = {"symbol": "SOL/USDT", "source": "binance", "market": "crypto"}
    assert (await client.post(ADMIN, json=payload)).status_code == 401
    assert (await client.post(ADMIN, json=payload, headers=trader_headers)).status_code == 403
    res = await client.patch(
        f"{ADMIN}/{instrument.id}", json={"is_active": False}, headers=trader_headers
    )
    assert res.status_code == 403


@pytest.fixture
async def catalog(session: AsyncSession) -> None:
    await make_instrument(session, "BTC/USDT", "binance")
    await make_instrument(session, "ETH/USDT", "binance")
    await make_instrument(session, "ETH/BTC", "binance", is_active=False)
    await make_instrument(session, "EUR/USD", "twelvedata", MarketType.forex)
    await make_instrument(session, "XAU/USD", "twelvedata", MarketType.commodity)


def _symbols(res) -> list[str]:
    return [f"{i['source']}:{i['symbol']}" for i in res.json()["items"]]


async def test_list_instruments_filters(client: AsyncClient, trader_headers, catalog) -> None:
    res = await client.get(PUBLIC, headers=trader_headers)
    assert res.status_code == 200
    assert res.json()["total"] == 5
    assert _symbols(res) == [
        "binance:BTC/USDT",
        "binance:ETH/BTC",
        "binance:ETH/USDT",
        "twelvedata:EUR/USD",
        "twelvedata:XAU/USD",
    ]
    res = await client.get(PUBLIC, params={"market": "forex"}, headers=trader_headers)
    assert _symbols(res) == ["twelvedata:EUR/USD"]
    res = await client.get(PUBLIC, params={"source": "TwelveData"}, headers=trader_headers)
    assert res.json()["total"] == 2
    res = await client.get(PUBLIC, params={"q": "eth"}, headers=trader_headers)
    assert _symbols(res) == ["binance:ETH/BTC", "binance:ETH/USDT"]
    res = await client.get(PUBLIC, params={"q": "/usd"}, headers=trader_headers)
    assert _symbols(res) == [
        "binance:BTC/USDT",
        "binance:ETH/USDT",
        "twelvedata:EUR/USD",
        "twelvedata:XAU/USD",
    ]
    res = await client.get(PUBLIC, params={"is_active": "false"}, headers=trader_headers)
    assert _symbols(res) == ["binance:ETH/BTC"]
    res = await client.get(PUBLIC, params={"q": "%"}, headers=trader_headers)
    assert res.json()["total"] == 0


async def test_list_instruments_pagination(client: AsyncClient, trader_headers, catalog) -> None:
    res = await client.get(PUBLIC, params={"limit": 2, "offset": 3}, headers=trader_headers)
    body = res.json()
    assert (body["total"], body["limit"], body["offset"]) == (5, 2, 3)
    assert _symbols(res) == ["twelvedata:EUR/USD", "twelvedata:XAU/USD"]
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"market": "x"}):
        assert (await client.get(PUBLIC, params=params, headers=trader_headers)).status_code == 422


async def test_get_instrument(client: AsyncClient, session: AsyncSession, trader_headers) -> None:
    instrument = await make_instrument(session)
    res = await client.get(f"{PUBLIC}/{instrument.id}", headers=trader_headers)
    assert res.status_code == 200 and res.json()["id"] == str(instrument.id)
    assert (await client.get(f"{PUBLIC}/{uuid.uuid4()}", headers=trader_headers)).status_code == 404
    assert (await client.get(f"{PUBLIC}/not-a-uuid", headers=trader_headers)).status_code == 422


async def test_public_market_endpoints_require_auth(client: AsyncClient) -> None:
    assert (await client.get(PUBLIC)).status_code == 401
    assert (await client.get(f"{PUBLIC}/{uuid.uuid4()}")).status_code == 401
