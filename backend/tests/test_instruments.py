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


# --- contract specs (migration 0013) ----------------------------------------------------------

GOLD_SPECS = {
    "contract_size": 100,
    "tick_size": 0.01,
    "lot_step": 0.01,
    "min_lot": 0.01,
    "max_lot": 100,
    "price_basis": "bid",
    "margin_rate": 0.01,
    "session_calendar": {
        "tz": "America/New_York",
        "week_open": {"day": "sun", "time": "18:00"},
        "week_close": {"day": "fri", "time": "16:55"},
        "daily_breaks": [{"start": "16:55", "end": "18:00"}],
        "holidays": [{"name": "Christmas", "date": "2026-12-25"}],
    },
}


async def test_specs_are_null_by_default(client: AsyncClient, admin_headers, trader_headers):
    res = await client.post(
        ADMIN,
        json={"symbol": "ADA/USDT", "source": "binance", "market": "crypto"},
        headers=admin_headers,
    )
    body = res.json()
    assert body["quote_currency"] == "USDT"  # defaults to quote_asset
    for name in ("contract_size", "lot_step", "session_calendar", "spec_source", "price_basis"):
        assert body[name] is None
    res = await client.get(f"{PUBLIC}/{body['id']}", headers=trader_headers)
    assert res.json()["spec_updated_at"] is None


async def test_create_with_specs_and_read(client: AsyncClient, admin_headers, trader_headers):
    res = await client.post(
        ADMIN,
        json={"symbol": "XAU/USD", "source": "fxpro", "market": "commodity", **GOLD_SPECS},
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["spec_source"] == "manual" and body["spec_updated_at"]
    res = await client.get(f"{PUBLIC}/{body['id']}", headers=trader_headers)
    read = res.json()
    for name, value in GOLD_SPECS.items():
        if name != "session_calendar":
            assert read[name] == value
    assert read["session_calendar"]["holidays"] == [
        {"name": "Christmas", "date": "2026-12-25", "start": None, "end": None}
    ]
    assert read["quote_currency"] == "USD"
    listed = (await client.get(PUBLIC, params={"source": "fxpro"}, headers=trader_headers)).json()
    assert listed["items"][0]["contract_size"] == 100


async def test_admin_spec_edit_marks_manual(
    client: AsyncClient, session: AsyncSession, admin_headers
) -> None:
    instrument = await make_instrument(
        session,
        "EUR/USD",
        "twelvedata",
        MarketType.forex,
        contract_size=100_000.0,
        lot_step=0.01,
        min_lot=0.01,
        max_lot=100.0,
        spec_source="typical",
    )
    url = f"{ADMIN}/{instrument.id}"
    # a non-spec change, and a spec "change" to the same value, keep the source
    res = await client.patch(
        url, json={"is_active": False, "lot_step": 0.01}, headers=admin_headers
    )
    assert res.json()["spec_source"] == "typical" and res.json()["spec_updated_at"] is None
    res = await client.patch(url, json={"max_lot": 50}, headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["max_lot"], body["spec_source"]) == (50, "manual")
    assert body["spec_updated_at"] is not None
    # specs can be cleared
    res = await client.patch(url, json={"max_lot": None}, headers=admin_headers)
    assert res.json()["max_lot"] is None


@pytest.mark.parametrize(
    "specs",
    [
        {"contract_size": 0},
        {"tick_size": -0.01},
        {"lot_step": "inf"},
        {"min_lot": 2, "max_lot": 1},
        {"margin_rate": 0},
        {"margin_rate": 1.5},
        {"price_basis": "ask"},
        {"quote_currency": ""},
        {"session_calendar": {"tz": "Nowhere/City"}},
        {"session_calendar": {"tz": "UTC", "week_open": {"day": "sun", "time": "18:00"}}},
    ],
)
async def test_invalid_specs_422(
    client: AsyncClient, session: AsyncSession, admin_headers, specs: dict
) -> None:
    payload = {"symbol": "XAU/USD", "source": "fxpro", "market": "commodity", **specs}
    assert (await client.post(ADMIN, json=payload, headers=admin_headers)).status_code == 422
    instrument = await make_instrument(session, "XAG/USD", "fxpro", MarketType.commodity)
    res = await client.patch(f"{ADMIN}/{instrument.id}", json=specs, headers=admin_headers)
    assert res.status_code == 422


async def test_lot_range_checked_against_stored_values(
    client: AsyncClient, session: AsyncSession, admin_headers
) -> None:
    instrument = await make_instrument(session, max_lot=10.0)
    res = await client.patch(
        f"{ADMIN}/{instrument.id}", json={"min_lot": 20}, headers=admin_headers
    )
    assert res.status_code == 422
    assert "min_lot" in res.text
