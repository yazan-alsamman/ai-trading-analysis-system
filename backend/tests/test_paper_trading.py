"""Paper trading (docs/paper-trading.md): the account (portfolio) on first use, market orders
at the latest 1m close, P/L, margin and free margin, manual close, SL/TP edits, validation
(lots, levels, trigger side, stale prices, margin), pending orders and the engine (fills,
gaps, SL/TP, the stop winning a tie, rejections, notifications), cancel and reset."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.instrument import MarketType
from app.models.notification import Notification, NotificationType
from app.models.paper import PaperAccount, PaperOrder, PaperPosition
from app.paper import engine
from app.schemas.market import CandleIn
from app.services import market_service
from tests.market_utils import make_instrument
from tests.utils import bearer

BASE = "/api/v1/me/paper"
T0 = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)  # a Monday, in the past


@pytest.fixture(autouse=True)
async def _clean_lock(redis_client: Redis):
    await redis_client.delete(engine.LOCK_KEY)
    yield
    await redis_client.delete(engine.LOCK_KEY)


@pytest.fixture
async def alice(make_user):
    user = await make_user("alice@example.com")
    return user, bearer(create_access_token(user))


async def _gold(session: AsyncSession, **over):
    return await make_instrument(
        session,
        "XAU/USD",
        source="fxpro",
        market=MarketType.commodity,
        price_precision=2,
        contract_size=100,
        min_lot=0.01,
        lot_step=0.01,
        max_lot=50,
        quote_currency="USD",
        **over,
    )


async def _bars(session, instrument, bars, start):
    candles = [
        CandleIn(ts=start + timedelta(minutes=i), open=o, high=h, low=lo, close=c, volume=1)
        for i, (o, h, lo, c) in enumerate(bars)
    ]
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()


def _now_minute() -> datetime:
    return datetime.now(UTC).replace(second=0, microsecond=0)


@pytest.fixture
async def gold(session: AsyncSession):
    instrument = await _gold(session)
    # fresh prices: the last close is 2404.50, two minutes ago
    start = _now_minute() - timedelta(minutes=6)
    await _bars(
        session, instrument, [(2400 + i, 2401 + i, 2399 + i, 2400.5 + i) for i in range(5)], start
    )
    return instrument


async def test_account_market_order_and_close(
    client: AsyncClient, session: AsyncSession, alice, gold
) -> None:
    _, headers = alice
    account = (await client.get(f"{BASE}/account", headers=headers)).json()
    assert account["balance"] == 10_000 and account["equity"] == 10_000
    assert account["leverage"] == 100 and account["open_positions"] == 0
    assert account["currency"] == "USD" and account["margin_level_pct"] is None

    res = await client.post(
        f"{BASE}/orders",
        json={
            "instrument_id": str(gold.id),
            "side": "buy",
            "lots": 0.1,
            "stop_loss": 2390,
            "take_profit": 2450,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    order = res.json()
    assert order["status"] == "filled" and order["type"] == "market"
    assert order["fill_price"] == 2404.5 and order["position_id"]
    assert order["instrument"]["symbol"] == "XAU/USD"

    account = (await client.get(f"{BASE}/account", headers=headers)).json()
    assert account["margin_used"] == pytest.approx(240.45)  # 2404.5 x 0.1 x 100 / 100
    assert account["free_margin"] == pytest.approx(10_000 - 240.45)
    assert account["open_positions"] == 1

    # the price moves up 10 dollars: +100 USD open P/L on 10 oz
    await _bars(session, gold, [(2405, 2415, 2404, 2414.5)], _now_minute() - timedelta(minutes=1))
    positions = (await client.get(f"{BASE}/positions", headers=headers)).json()
    assert positions["total"] == 1
    pos = positions["items"][0]
    assert pos["current_price"] == 2414.5 and pos["unrealized_pnl"] == pytest.approx(100)
    account = (await client.get(f"{BASE}/account", headers=headers)).json()
    assert account["equity"] == pytest.approx(10_100) and account["today_pnl"] == pytest.approx(100)

    # move the stop loss, then a wrong one
    res = await client.patch(
        f"{BASE}/positions/{pos['id']}", json={"stop_loss": 2405}, headers=headers
    )
    assert res.status_code == 200 and res.json()["stop_loss"] == 2405
    assert res.json()["take_profit"] == 2450  # unchanged
    res = await client.patch(
        f"{BASE}/positions/{pos['id']}", json={"stop_loss": 2420}, headers=headers
    )
    assert res.status_code == 422 and res.json()["detail"]["code"] == "invalid_stop_loss"

    res = await client.post(f"{BASE}/positions/{pos['id']}/close", headers=headers)
    assert res.status_code == 200, res.text
    closed = res.json()
    assert closed["status"] == "closed" and closed["close_reason"] == "manual"
    assert closed["close_price"] == 2414.5 and closed["pnl"] == pytest.approx(100)
    res = await client.post(f"{BASE}/positions/{pos['id']}/close", headers=headers)
    assert res.status_code == 409

    account = (await client.get(f"{BASE}/account", headers=headers)).json()
    assert account["balance"] == pytest.approx(10_100) and account["realized_pnl"] == pytest.approx(
        100
    )
    assert account["return_pct"] == pytest.approx(1.0) and account["margin_used"] == 0
    history = (
        await client.get(f"{BASE}/positions", params={"status": "closed"}, headers=headers)
    ).json()
    assert history["total"] == 1


async def test_cost_is_taken_at_close(client: AsyncClient, session: AsyncSession, alice) -> None:
    _, headers = alice
    gold = await _gold(session, cost_per_unit=0.25)
    await _bars(session, gold, [(2400, 2401, 2399, 2400)], _now_minute() - timedelta(minutes=1))
    res = await client.post(
        f"{BASE}/orders",
        json={"instrument_id": str(gold.id), "side": "sell", "lots": 0.5},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    pid = res.json()["position_id"]
    closed = (await client.post(f"{BASE}/positions/{pid}/close", headers=headers)).json()
    assert closed["cost"] == pytest.approx(12.5)  # 0.25 x 50 oz
    assert closed["pnl"] == pytest.approx(-12.5)  # flat price: only the cost


async def test_validation(client: AsyncClient, session: AsyncSession, alice, gold) -> None:
    _, headers = alice
    url = f"{BASE}/orders"

    async def code(body, status=422):
        res = await client.post(url, json={"instrument_id": str(gold.id), **body}, headers=headers)
        assert res.status_code == status, res.text
        detail = res.json()["detail"]
        return detail["code"] if isinstance(detail, dict) else "validation"

    assert await code({"side": "buy", "lots": 0.005}) == "invalid_lots"
    assert await code({"side": "buy", "lots": 0.015}) == "invalid_lots"
    assert await code({"side": "buy", "lots": 60}) == "invalid_lots"
    assert await code({"side": "buy", "lots": 0.1, "stop_loss": 2410}) == "invalid_stop_loss"
    assert await code({"side": "sell", "lots": 0.1, "take_profit": 2410}) == "invalid_take_profit"
    assert await code({"side": "buy", "lots": 0.1, "price": 2400}) == "validation"
    assert await code({"side": "buy", "type": "limit", "lots": 0.1}) == "validation"
    assert (
        await code({"side": "buy", "type": "limit", "lots": 0.1, "price": 2410}) == "invalid_price"
    )
    assert (
        await code({"side": "buy", "type": "stop", "lots": 0.1, "price": 2390}) == "invalid_price"
    )
    assert (
        await code({"side": "sell", "type": "limit", "lots": 0.1, "price": 2390}) == "invalid_price"
    )
    # 50 lots of gold at 1:1 needs 12 million: more than the account
    res = await client.patch(f"{BASE}/account", json={"leverage": 1}, headers=headers)
    assert res.status_code == 200 and res.json()["leverage"] == 1
    assert await code({"side": "buy", "lots": 50}) == "insufficient_margin"
    assert (await client.get(f"{BASE}/positions", headers=headers)).json()["total"] == 0

    stale = await make_instrument(
        session, "EUR/USD", source="twelvedata", market=MarketType.forex, contract_size=100_000
    )
    await _bars(session, stale, [(1.08, 1.09, 1.07, 1.085)], _now_minute() - timedelta(days=2))
    res = await client.post(
        url, json={"instrument_id": str(stale.id), "side": "buy", "lots": 0.01}, headers=headers
    )
    assert res.status_code == 409 and res.json()["detail"]["code"] == "market_closed"
    jpy = await make_instrument(
        session, "USD/JPY", source="twelvedata", market=MarketType.forex, contract_size=100_000
    )
    res = await client.post(
        url, json={"instrument_id": str(jpy.id), "side": "buy", "lots": 0.01}, headers=headers
    )
    assert res.status_code == 422 and res.json()["detail"]["code"] == "unsupported_currency"
    assert (await client.get(f"{BASE}/account")).status_code == 401


async def test_pending_order_cancel_and_reset(
    client: AsyncClient, session: AsyncSession, alice, gold
) -> None:
    _, headers = alice
    res = await client.post(
        f"{BASE}/orders",
        json={"instrument_id": str(gold.id), "side": "buy", "type": "limit", "lots": 0.2,
              "price": 2390, "stop_loss": 2380, "take_profit": 2420},
        headers=headers,
    )  # fmt: skip
    assert res.status_code == 201, res.text
    order = res.json()
    assert order["status"] == "pending" and order["fill_price"] is None
    pending = (
        await client.get(f"{BASE}/orders", params={"status": "pending"}, headers=headers)
    ).json()
    assert pending["total"] == 1
    assert (await client.get(f"{BASE}/account", headers=headers)).json()["pending_orders"] == 1
    res = await client.delete(f"{BASE}/orders/{order['id']}", headers=headers)
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    assert (await client.delete(f"{BASE}/orders/{order['id']}", headers=headers)).status_code == 409

    await client.post(
        f"{BASE}/orders",
        json={"instrument_id": str(gold.id), "side": "buy", "lots": 0.1},
        headers=headers,
    )
    res = await client.post(
        f"{BASE}/account/reset", json={"initial_balance": 5000}, headers=headers
    )
    assert res.status_code == 200, res.text
    account = res.json()
    assert account["balance"] == 5000 and account["initial_balance"] == 5000
    assert account["open_positions"] == 0 and account["reset_at"] is not None
    assert (await client.get(f"{BASE}/orders", headers=headers)).json()["total"] == 0


async def test_orders_of_others_are_not_found(client: AsyncClient, make_user, alice, gold) -> None:
    _, headers = alice
    bob = await make_user("bob@example.com")
    bob_h = bearer(create_access_token(bob))
    res = await client.post(
        f"{BASE}/orders",
        json={"instrument_id": str(gold.id), "side": "buy", "lots": 0.1},
        headers=headers,
    )
    pid = res.json()["position_id"]
    assert (await client.post(f"{BASE}/positions/{pid}/close", headers=bob_h)).status_code == 404
    assert (await client.get(f"{BASE}/positions", headers=bob_h)).json()["total"] == 0


# --- the engine ----------------------------------------------------------------------------------


async def _order(session, user, instrument, **fields) -> PaperOrder:
    row = PaperOrder(
        user_id=user.id,
        instrument_id=instrument.id,
        status="pending",
        created_at=T0 - timedelta(seconds=30),
        checked_until=T0,
        **fields,
    )
    session.add(row)
    await session.commit()
    return row


async def _notes(session) -> list[dict]:
    rows = await session.scalars(
        select(Notification)
        .where(Notification.type == NotificationType.paper_trade)
        .order_by(Notification.created_at)
    )
    return [n.data for n in rows]


async def test_engine_fills_then_takes_profit(
    session: AsyncSession, session_factory, redis_client, alice
) -> None:
    user, _ = alice
    gold = await _gold(session)
    order = await _order(
        session, user, gold, side="buy", type="limit", lots=0.1, price=2395,
        stop_loss=2385, take_profit=2420,
    )  # fmt: skip
    await _bars(
        session,
        gold,
        [
            (2400, 2401, 2398, 2399),  # not reached
            (2399, 2400, 2394, 2396),  # limit 2395 reached: filled at 2395
            (2396, 2421, 2395, 2419),  # take profit 2420 reached
            (2419, 2425, 2418, 2424),
        ],
        T0,
    )
    run = await engine.evaluate(session_factory, redis_client, now=T0 + timedelta(minutes=10))
    assert (run.filled, run.closed, run.rejected) == (1, 1, 0), run
    await session.refresh(order)
    assert order.status == "filled" and order.fill_price == 2395
    assert order.filled_at == T0 + timedelta(minutes=2)
    position = await session.get(PaperPosition, order.position_id)
    await session.refresh(position)
    assert position.status == "closed" and position.close_reason == "take_profit"
    assert position.close_price == 2420 and position.pnl == pytest.approx(250)
    account = await session.get(PaperAccount, user.id)
    await session.refresh(account)
    assert account.balance == pytest.approx(10_250)
    notes = await _notes(session)
    assert [n["event"] for n in notes] == ["order_filled", "take_profit"]
    assert notes[1]["pnl"] == 250 and notes[1]["instrument"]["symbol"] == "XAU/USD"

    # a second run finds nothing new and never notifies twice
    run = await engine.evaluate(session_factory, redis_client, now=T0 + timedelta(minutes=11))
    assert (run.filled, run.closed) == (0, 0)
    assert len(await _notes(session)) == 2


async def test_engine_gap_tie_and_rejection(
    session: AsyncSession, session_factory, redis_client, alice
) -> None:
    user, _ = alice
    gold = await _gold(session)
    # a sell stop below the price; the bar opens below it (gap): filled at the open
    stop = await _order(session, user, gold, side="sell", type="stop", lots=0.1, price=2398)
    # an open buy whose stop and target are both inside one bar: the stop wins
    tie = PaperPosition(
        user_id=user.id, instrument_id=gold.id, side="buy", lots=0.1, contract_size=100,
        entry_price=2400, stop_loss=2396, take_profit=2404, margin=240, opened_at=T0,
        checked_until=T0,
    )  # fmt: skip
    session.add(tie)
    # far too big for the account at the fill: rejected
    big = await _order(session, user, gold, side="buy", type="limit", lots=50, price=2396)
    await session.commit()
    await _bars(session, gold, [(2395, 2405, 2390, 2400)], T0)
    run = await engine.evaluate(session_factory, redis_client, now=T0 + timedelta(minutes=2))
    assert (run.filled, run.rejected, run.closed) == (1, 1, 1), run
    await session.refresh(stop)
    await session.refresh(big)
    await session.refresh(tie)
    assert stop.status == "filled" and stop.fill_price == 2395  # the open, beyond 2398
    assert big.status == "rejected" and big.reject_reason == "insufficient_margin"
    assert tie.close_reason == "stop_loss" and tie.close_price == 2396
    assert tie.pnl == pytest.approx(-40)
    events = sorted(n["event"] for n in await _notes(session))
    assert events == ["order_filled", "order_rejected", "stop_loss"]


async def test_engine_waits_for_closed_bars_and_lock(
    session: AsyncSession, session_factory, redis_client, alice
) -> None:
    user, _ = alice
    gold = await _gold(session)
    order = await _order(session, user, gold, side="buy", type="limit", lots=0.1, price=2390)
    await _bars(session, gold, [(2395, 2396, 2389, 2391)], T0)
    # the bar of T0 is still forming at T0 + 30 s: not used
    run = await engine.evaluate(session_factory, redis_client, now=T0 + timedelta(seconds=30))
    assert run.filled == 0
    await redis_client.set(engine.LOCK_KEY, "other")
    run = await engine.evaluate(session_factory, redis_client, now=T0 + timedelta(minutes=2))
    assert run.status == "locked"
    await redis_client.delete(engine.LOCK_KEY)
    run = await engine.evaluate(session_factory, redis_client, now=T0 + timedelta(minutes=2))
    assert run.filled == 1
    await session.refresh(order)
    assert order.fill_price == 2390
