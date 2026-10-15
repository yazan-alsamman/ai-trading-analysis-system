"""/strategies, /me/strategies, /signals and the signals WebSocket topic."""

import random
import uuid
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
import trading_strategies as ts
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.candle import Timeframe
from app.models.strategy import Signal, SignalSide
from app.realtime import publisher
from app.realtime.topics import signals_topic
from app.services import market_service
from app.services.seed_service import generate_demo_candles
from tests.market_utils import make_instrument
from tests.strategy_utils import activate
from tests.utils import bearer
from tests.ws_utils import recv, ws_connect

END = datetime(2026, 1, 6, 2, 59, tzinfo=UTC)
ME = "/api/v1/me/strategies"


@pytest.fixture
async def instrument(session: AsyncSession):
    instrument = await make_instrument(session, price_precision=2, quantity_precision=4)
    candles = generate_demo_candles(instrument, minutes=900, end=END, rng=random.Random(9))
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    return instrument


@pytest.fixture
async def other_headers(make_user, login) -> dict[str, str]:
    await make_user("other@example.com")
    return bearer((await login("other@example.com"))["access_token"])


def create_body(instrument, **overrides) -> dict:
    body = {
        "strategy_key": "rsi_reversal",
        "instrument_id": str(instrument.id),
        "timeframe": "1h",
        "params": {"length": 14},
    }
    return body | overrides


# --- catalog / preview -----------------------------------------------------------------------


async def test_catalog(client: AsyncClient, trader_headers) -> None:
    res = await client.get("/api/v1/strategies", headers=trader_headers)
    assert res.status_code == 200
    keys = [s["key"] for s in res.json()]
    assert keys == list(ts.STRATEGIES)
    assert (await client.get("/api/v1/strategies")).status_code == 401


async def test_preview(client: AsyncClient, trader_headers, instrument) -> None:
    body = {
        "instrument_id": str(instrument.id),
        "timeframe": "1m",
        "params": {"oversold": 45, "overbought": 55},
        "limit": 300,
    }
    res = await client.post(
        "/api/v1/strategies/rsi_reversal/preview", json=body, headers=trader_headers
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["strategy_key"] == "rsi_reversal" and data["bars"] == 300
    assert data["params"] == {"length": 14, "oversold": 45.0, "overbought": 55.0}
    signals, markers = data["signals"], data["markers"]
    assert len(signals) == len(markers) > 0
    candles = await client.get(
        f"/api/v1/market/instruments/{instrument.id}/candles",
        params={"timeframe": "1m", "limit": 300},
        headers=trader_headers,
    )
    times = [c["time"] for c in candles.json()["candles"]]
    for sig, marker in zip(signals, markers, strict=True):
        assert sig["time"] in times and marker["time"] == sig["time"]
        if sig["side"] == "buy":
            assert (marker["position"], marker["shape"]) == ("belowBar", "arrowUp")
            assert sig["reason"] == "rsi_cross_up_oversold"
        else:
            assert (marker["position"], marker["shape"]) == ("aboveBar", "arrowDown")
        assert 0 <= sig["strength"] <= 1 and set(sig["details"]) >= {"rsi_prev", "rsi", "level"}
    [rsi] = data["indicators"]
    assert rsi["name"] == "rsi" and len(rsi["outputs"]["rsi"]) == 300
    assert rsi["outputs"]["rsi"][0]["value"] is not None  # warm-up history was loaded


async def test_preview_matches_library_on_full_history(
    client: AsyncClient, session: AsyncSession, trader_headers, instrument
) -> None:
    rows = await market_service.get_candles(session, instrument.id, Timeframe.m1, limit=5000)
    df = pd.DataFrame(
        {k: [getattr(r, k) for r in rows] for k in ("open", "high", "low", "close", "volume")},
        index=pd.DatetimeIndex([r.ts for r in rows]),
    )
    params = {"fast": 3, "slow": 8}
    full = ts.run("ma_crossover", df, **params).iloc[-200:]
    expected = [int(t.timestamp()) for t, s in full["signal"].items() if s != 0]
    body = {"instrument_id": str(instrument.id), "timeframe": "1m", "params": params, "limit": 200}
    res = await client.post(
        "/api/v1/strategies/ma_crossover/preview", json=body, headers=trader_headers
    )
    assert [s["time"] for s in res.json()["signals"]] == expected and expected


@pytest.mark.parametrize(
    ("key", "body_update", "status"),
    [
        ("nope", {}, 422),
        ("rsi_reversal", {"params": {"oversold": 80}}, 422),
        ("rsi_reversal", {"timeframe": "2h"}, 422),
        ("rsi_reversal", {"start": "2026-01-02T00:00:00Z", "end": "2026-01-01T00:00:00Z"}, 422),
        ("rsi_reversal", {"instrument_id": str(uuid.uuid4())}, 404),
    ],
)
async def test_preview_errors(
    client: AsyncClient, trader_headers, instrument, key, body_update, status
) -> None:
    body = {"instrument_id": str(instrument.id), "timeframe": "1m"} | body_update
    res = await client.post(f"/api/v1/strategies/{key}/preview", json=body, headers=trader_headers)
    assert res.status_code == status, res.text


# --- /me/strategies --------------------------------------------------------------------------


async def test_activate_list_update_delete(client: AsyncClient, trader_headers, instrument) -> None:
    res = await client.post(ME, json=create_body(instrument, name="My RSI"), headers=trader_headers)
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["params"] == {"length": 14, "oversold": 30.0, "overbought": 70.0}
    assert created["params_hash"] == ts.params_hash("rsi_reversal", {})
    assert created["is_active"] is True and created["notify"] is True

    listed = (await client.get(ME, headers=trader_headers)).json()
    assert [r["id"] for r in listed] == [created["id"]]

    res = await client.patch(
        f"{ME}/{created['id']}",
        json={"params": {"oversold": 25}, "notify": False, "name": "Deep RSI"},
        headers=trader_headers,
    )
    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["params"]["oversold"] == 25.0 and updated["notify"] is False
    assert updated["params_hash"] == ts.params_hash("rsi_reversal", {"oversold": 25})
    assert updated["name"] == "Deep RSI"

    res = await client.patch(
        f"{ME}/{created['id']}", json={"params": {"oversold": 90}}, headers=trader_headers
    )
    assert res.status_code == 422
    res = await client.patch(
        f"{ME}/{created['id']}", json={"is_active": None}, headers=trader_headers
    )
    assert res.status_code == 422

    assert (await client.delete(f"{ME}/{created['id']}", headers=trader_headers)).status_code == 204
    assert (await client.get(ME, headers=trader_headers)).json() == []
    res = await client.delete(f"{ME}/{created['id']}", headers=trader_headers)
    assert res.status_code == 404


async def test_activate_duplicate_409(client: AsyncClient, trader_headers, instrument) -> None:
    assert (
        await client.post(ME, json=create_body(instrument), headers=trader_headers)
    ).status_code == 201
    # the same resolved params written differently are the same setup
    same = create_body(instrument, params={"overbought": 70, "length": 14.0})
    assert (await client.post(ME, json=same, headers=trader_headers)).status_code == 409
    # other timeframe or params: fine
    res = await client.post(
        ME, json=create_body(instrument, timeframe="4h"), headers=trader_headers
    )
    assert res.status_code == 201
    res = await client.post(
        ME, json=create_body(instrument, params={"length": 15}), headers=trader_headers
    )
    assert res.status_code == 201
    # changing params into an existing setup is a conflict too
    res = await client.patch(
        f"{ME}/{res.json()['id']}", json={"params": {"length": 14}}, headers=trader_headers
    )
    assert res.status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"strategy_key": "nope"},
        {"params": {"oversold": 80}},
        {"params": {"length": "14"}},
        {"params": {"window": 3}},
        {"timeframe": "2h"},
        {"instrument_id": str(uuid.uuid4())},
    ],
)
async def test_activate_422(client: AsyncClient, trader_headers, instrument, overrides) -> None:
    res = await client.post(ME, json=create_body(instrument, **overrides), headers=trader_headers)
    assert res.status_code == 422, res.text


async def test_activate_inactive_instrument_422(
    client: AsyncClient, session: AsyncSession, trader_headers
) -> None:
    dead = await make_instrument(session, "XRP/USDT", is_active=False)
    res = await client.post(ME, json=create_body(dead), headers=trader_headers)
    assert res.status_code == 422 and "inactive" in res.json()["detail"]


async def test_limit_of_20(client: AsyncClient, trader_headers, instrument) -> None:
    for length in range(2, 22):
        body = create_body(instrument, params={"length": length})
        assert (await client.post(ME, json=body, headers=trader_headers)).status_code == 201
    res = await client.post(
        ME, json=create_body(instrument, params={"length": 30}), headers=trader_headers
    )
    assert res.status_code == 400 and "20" in res.json()["detail"]


async def test_ownership(client: AsyncClient, trader_headers, other_headers, instrument) -> None:
    created = (await client.post(ME, json=create_body(instrument), headers=trader_headers)).json()
    url = f"{ME}/{created['id']}"
    assert (await client.get(ME, headers=other_headers)).json() == []
    assert (
        await client.patch(url, json={"notify": False}, headers=other_headers)
    ).status_code == 404
    assert (await client.delete(url, headers=other_headers)).status_code == 404
    # the other user may run the very same setup
    assert (
        await client.post(ME, json=create_body(instrument), headers=other_headers)
    ).status_code == 201
    assert (await client.get(ME, headers=trader_headers)).json()[0]["notify"] is True


async def test_me_strategies_require_auth(client: AsyncClient) -> None:
    assert (await client.get(ME)).status_code == 401
    assert (await client.post(ME, json={})).status_code == 401
    assert (await client.delete(f"{ME}/{uuid.uuid4()}")).status_code == 401


# --- /signals --------------------------------------------------------------------------------


async def _signal(session: AsyncSession, instrument, minutes: int, **kw) -> Signal:
    key = kw.pop("strategy_key", "rsi_reversal")
    params = ts.get_strategy(key).resolve(kw.pop("params", {}))
    row = Signal(
        instrument_id=instrument.id,
        timeframe=kw.pop("timeframe", Timeframe.h1),
        strategy_key=key,
        params=params,
        params_hash=ts.params_hash(key, params),
        bar_time=END - timedelta(minutes=minutes),
        side=kw.pop("side", SignalSide.buy),
        strength=0.5,
        price=100.0,
        reason="rsi_cross_up_oversold",
        details={"rsi": 31.0},
    )
    session.add(row)
    await session.commit()
    return row


async def test_list_signals(
    client: AsyncClient, session: AsyncSession, make_user, login, instrument
) -> None:
    user = await make_user("signals@example.com")
    headers = bearer((await login("signals@example.com"))["access_token"])
    eth = await make_instrument(session, "ETH/USDT")
    await activate(session, user, instrument, timeframe=Timeframe.h1)  # default rsi_reversal
    a = await _signal(session, instrument, 120)
    b = await _signal(session, instrument, 60, side=SignalSide.sell)
    c = await _signal(session, instrument, 30, params={"length": 7})  # not my params
    d = await _signal(session, eth, 10, strategy_key="ma_crossover")

    res = await client.get("/api/v1/signals", headers=headers)
    body = res.json()
    assert res.status_code == 200 and body["total"] == 4
    assert [s["id"] for s in body["items"]] == [str(x.id) for x in (d, c, b, a)]  # newest first
    first = body["items"][0]
    assert first["time"] == int(d.bar_time.timestamp()) and first["side"] == "buy"

    async def ids(**params) -> list[str]:
        res = await client.get("/api/v1/signals", params=params, headers=headers)
        assert res.status_code == 200, res.text
        return [s["id"] for s in res.json()["items"]]

    assert await ids(instrument_id=str(eth.id)) == [str(d.id)]
    assert await ids(strategy_key="rsi_reversal", limit=2) == [str(c.id), str(b.id)]
    assert await ids(strategy_key="rsi_reversal", limit=2, offset=2) == [str(a.id)]
    assert await ids(timeframe="1m") == []
    assert await ids(since=(END - timedelta(minutes=45)).isoformat()) == [str(d.id), str(c.id)]
    assert await ids(mine="true") == [str(b.id), str(a.id)]
    res = await client.get("/api/v1/signals", params={"limit": 101}, headers=headers)
    assert res.status_code == 422
    assert (await client.get("/api/v1/signals")).status_code == 401


# --- WebSocket topic -------------------------------------------------------------------------


async def test_ws_signals_topic(client: AsyncClient, hub, make_user, instrument) -> None:
    token = create_access_token(await make_user("ws-signals@example.com"))
    topic = signals_topic(instrument.id)
    async with ws_connect(token) as ws:
        await ws.send_json(
            {"op": "subscribe", "topic": "signals", "instrument_id": str(uuid.uuid4())}
        )
        assert (await recv(ws))["code"] == "unknown_instrument"
        await ws.send_json(
            {
                "op": "subscribe",
                "topic": "signals",
                "instrument_id": str(instrument.id),
                "timeframe": "1m",
            }
        )
        assert (await recv(ws))["code"] == "bad_request"  # signals topics have no timeframe
        await ws.send_json(
            {"op": "subscribe", "topic": "signals", "instrument_id": str(instrument.id)}
        )
        assert await recv(ws) == {"type": "subscribed", "topic": topic}
        await publisher.publish(topic, {"type": "signal", "signal": {"side": "buy"}})
        msg = await recv(ws)
        assert msg["type"] == "signal" and msg["topic"] == topic and msg["signal"]["side"] == "buy"
        await ws.send_json(
            {"op": "unsubscribe", "topic": "signals", "instrument_id": str(instrument.id)}
        )
        assert await recv(ws) == {"type": "unsubscribed", "topic": topic}
        assert hub.subscriber_count(topic) == 0
