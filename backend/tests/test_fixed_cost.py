"""A fixed trading cost per instrument (``instruments.cost_per_unit``, migration 0021; XAU/USD
0.25 per oz per round trip, Fadi): seeded only when null, admin-editable, used by backtests
(instead of fee_bps / slippage_bps, reported as the cost model), by trade plans and by the AI
local sizing (risk per unit = |entry - stop| + cost, in the cached size's inputs), and sent to
ai-service's /v1/size (never with /v1/evaluate: tests/test_ai_evaluate.py)."""

import json
import random
import uuid

import pandas as pd
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import seed_instruments
from app.core.security import create_access_token
from app.models.ai import AISetupSize
from app.models.backtest import BacktestStatus, BacktestTrade
from app.models.instrument import Instrument, MarketType
from app.services import market_service, risk_service
from app.services.seed_service import generate_demo_candles
from tests.market_utils import make_instrument
from tests.test_ai_sizing import (
    GOLD_SPECS,
    LOCAL,
    SETUP_ID,
    armed,
    client_for,
    profile,
    size,
)
from tests.test_backtests import BT, END, MINUTES, body, run, submit
from tests.utils import bearer

ADMIN = "/api/v1/admin/instruments"
PUBLIC = "/api/v1/market/instruments"
COST_NOTE = "risk per unit includes the fixed trading cost of 0.25 per unit (round trip)"


# --- the instrument ------------------------------------------------------------------------------


async def test_seed_sets_xau_only_when_null(session_factory, session: AsyncSession, capsys):
    assert await seed_instruments(session_factory) == 0
    rows = {(i.source, i.symbol): i for i in (await session.scalars(select(Instrument))).all()}
    assert rows[("fxpro", "XAU/USD")].cost_per_unit == 0.25
    others = [i for key, i in rows.items() if key != ("fxpro", "XAU/USD")]
    assert others and all(i.cost_per_unit is None for i in others)

    # a value an admin set is never overwritten
    await session.execute(
        update(Instrument)
        .where(Instrument.source == "fxpro", Instrument.symbol == "XAU/USD")
        .values(cost_per_unit=0.3)
    )
    await session.commit()
    assert await seed_instruments(session_factory) == 0
    session.expire_all()
    gold = await market_service.get_instrument_by_symbol(session, "fxpro", "XAU/USD")
    assert gold.cost_per_unit == 0.3


async def test_admin_edits_it_and_the_api_shows_it(
    client: AsyncClient, session: AsyncSession, admin_headers, trader_headers
) -> None:
    gold = await make_instrument(
        session, "XAU/USD", "fxpro", MarketType.commodity, **GOLD_SPECS, spec_source="typical"
    )
    assert (await client.get(f"{PUBLIC}/{gold.id}", headers=trader_headers)).json()[
        "cost_per_unit"
    ] is None
    res = await client.patch(f"{ADMIN}/{gold.id}", json={"cost_per_unit": 0.25},
                             headers=admin_headers)  # fmt: skip
    assert res.status_code == 200, res.text
    assert (res.json()["cost_per_unit"], res.json()["spec_source"]) == (0.25, "manual")
    read = (await client.get(f"{PUBLIC}/{gold.id}", headers=trader_headers)).json()
    assert read["cost_per_unit"] == 0.25
    bad = await client.patch(f"{ADMIN}/{gold.id}", json={"cost_per_unit": -0.01},
                             headers=admin_headers)  # fmt: skip
    assert bad.status_code == 422
    cleared = await client.patch(f"{ADMIN}/{gold.id}", json={"cost_per_unit": None},
                                 headers=admin_headers)  # fmt: skip
    assert cleared.json()["cost_per_unit"] is None


# --- backtests -----------------------------------------------------------------------------------


@pytest.fixture
async def xau(session: AsyncSession) -> Instrument:
    """An XAU/USD with demo candles and the 0.25 cost (the fxpro one only takes real candles,
    so a twelvedata copy carries the cost here: the rule is per instrument)."""
    gold = await make_instrument(session, "XAU/USD", "twelvedata", MarketType.commodity,
                                 price_precision=2, cost_per_unit=0.25)  # fmt: skip
    candles = generate_demo_candles(gold, minutes=MINUTES, end=END, rng=random.Random(5))
    await market_service.upsert_candles(session, gold.id, candles)
    await session.commit()
    return gold


@pytest.fixture
async def btc(session: AsyncSession) -> Instrument:
    coin = await make_instrument(session, price_precision=2, quantity_precision=4)
    candles = generate_demo_candles(coin, minutes=MINUTES, end=END, rng=random.Random(5))
    await market_service.upsert_candles(session, coin.id, candles)
    await session.commit()
    return coin


async def test_backtest_uses_the_instrument_cost(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client, xau, btc,
    make_user, monkeypatch,
) -> None:  # fmt: skip
    from app.services import backtest_service  # noqa: PLC0415

    monkeypatch.setattr(backtest_service, "enqueue", lambda _id: None)
    user = await make_user("costs@example.com")
    headers = bearer(create_access_token(user))
    config = {"fee_bps": 30, "slippage_bps": 20}  # ignored for XAU/USD
    gold_id = await submit(client, headers, xau, config=config)
    assert await run(session_factory, redis_client, gold_id) == BacktestStatus.completed
    gold = (await client.get(f"{BT}/{gold_id}", headers=headers)).json()
    assert (gold["cost_model"], gold["cost_per_unit"]) == ("fixed_per_unit", 0.25)
    assert gold["config"]["cost_per_unit"] == 0.25
    trades = (await session.scalars(
        select(BacktestTrade).where(BacktestTrade.backtest_id == uuid.UUID(gold_id))
    )).all()  # fmt: skip
    assert trades
    for t in trades:
        assert t.fees == pytest.approx(0.25 * t.quantity)  # the whole round trip, nothing else
    assert gold["metrics"]["total_fees"] == pytest.approx(sum(t.fees for t in trades), abs=1e-6)

    coin_id = await submit(client, headers, btc, config=config)
    assert await run(session_factory, redis_client, coin_id) == BacktestStatus.completed
    coin = (await client.get(f"{BT}/{coin_id}", headers=headers)).json()
    assert (coin["cost_model"], coin["cost_per_unit"]) == ("bps", None)
    assert "cost_per_unit" not in coin["config"] and coin["config"]["fee_bps"] == 30
    (first,) = (await session.scalars(
        select(BacktestTrade).where(BacktestTrade.backtest_id == uuid.UUID(coin_id))
        .order_by(BacktestTrade.number).limit(1)
    )).all()  # fmt: skip
    assert first.fees > 0 and first.fees != pytest.approx(0.25 * first.quantity)

    # the cost comes from the instrument, never from the request
    res = await client.post(BT, json=body(btc, config={"cost_per_unit": 0.1}), headers=headers)
    assert res.status_code == 422 and "set by the server" in res.text


async def test_backtest_entry_fills_at_the_chart_price(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client, xau, make_user,
    monkeypatch,
) -> None:  # fmt: skip
    """No slippage with the fixed cost: an entry is filled at the bar's open exactly."""
    from app.services import backtest_service  # noqa: PLC0415

    monkeypatch.setattr(backtest_service, "enqueue", lambda _id: None)
    user = await make_user("fills@example.com")
    headers = bearer(create_access_token(user))
    backtest_id = await submit(client, headers, xau, config={"slippage_bps": 50})
    assert await run(session_factory, redis_client, backtest_id) == BacktestStatus.completed
    trade = await session.scalar(
        select(BacktestTrade).where(BacktestTrade.backtest_id == uuid.UUID(backtest_id))
        .order_by(BacktestTrade.number).limit(1)
    )  # fmt: skip
    opens = await market_service.get_candles(
        session, xau.id, market_service.Timeframe.m1,
        start=trade.entry_time, end=trade.entry_time,
    )  # fmt: skip
    assert trade.entry_price == opens[0].open


# --- trade plans (calculator, live signals) ------------------------------------------------------


async def test_trade_plan_counts_the_cost(session: AsyncSession) -> None:
    """XAU/USD, USD account 10,000, risk 0.2 % = 20 USD, entry 2400, stop 2395: (5 + 0.25) x 100
    = 525 USD per lot -> 0.03 lots (0.04 without the cost)."""
    gold = await make_instrument(session, "XAU/USD", "fxpro", MarketType.commodity, **GOLD_SPECS,
                                 cost_per_unit=0.25)  # fmt: skip
    df = pd.DataFrame(
        {"open": [2400.0], "high": [2401.0], "low": [2399.0], "close": [2400.0], "volume": [1.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-10-19T14:00Z")]),
    )
    config = risk_service.validate_config(
        {"stop": {"type": "percent", "value": 1}, "sizing": {"mode": "risk", "risk_pct": 0.2}}
    )
    sizing = await risk_service.lot_sizing(session, gold, "USD", 2400.0)
    assert sizing.cost_per_unit == 0.25
    plan = risk_service.plan_dict(df, 1, config, 10_000, sizing, entry=2400.0, stop=2395.0)
    assert plan["cost_per_unit"] == 0.25 and plan["lots"] == 0.03
    assert plan["risk_amount"] == pytest.approx(20.0)  # the profile's 10 bps are not added
    assert plan["lots_risk_amount"] == pytest.approx(15.75)
    assert any("0.25 per unit" in w for w in plan["sizing_warnings"])

    gold.cost_per_unit = None
    await session.commit()
    await session.refresh(gold)
    plain = risk_service.plan_dict(
        df, 1, {**config, "fee_bps": 0}, 10_000,
        await risk_service.lot_sizing(session, gold, "USD", 2400.0), entry=2400.0, stop=2395.0,
    )  # fmt: skip
    assert plain["lots"] == 0.04 and "cost_per_unit" not in plain


# --- AI sizing -----------------------------------------------------------------------------------


@pytest.fixture
async def gold(session: AsyncSession) -> Instrument:
    return await make_instrument(session, "XAU/USD", "fxpro", market=MarketType.commodity,
                                 **GOLD_SPECS, cost_per_unit=0.25)  # fmt: skip


async def test_local_size_includes_the_cost_and_a_change_resizes(
    session: AsyncSession, gold: Instrument, make_user, local_mode
) -> None:
    """Balance 2,000 x 1 % = 20 USD; entry 2400, sl 2395: (5.00 + 0.25) x 100 = 525 USD per lot
    -> 0.0381 -> 0.03 lots, 15.75 USD at risk, margin 0.03 x 100 x 2400 / 100 = 72."""
    user = await make_user("cost-size@example.com")
    await profile(session, user)
    setup_row = await armed(session, gold)
    result = await size(session, setup_row, user)
    assert (result.lots, result.risk_amount, result.margin_required) == (0.03, 15.75, 72.0)
    assert result.feasible and result.source == "local" and not result.cached
    assert result.warnings == [LOCAL, COST_NOTE]
    stored = await session.get(AISetupSize, (SETUP_ID, user.id))
    assert stored.inputs["cost_per_unit"] == 0.25

    again = await size(session, setup_row, user)
    assert again.cached and again.lots == 0.03  # the same inputs: reused

    gold.cost_per_unit = 0.5  # (5.50) x 100 = 550 per lot -> 0.03 lots, 16.50 USD
    await session.commit()
    await session.refresh(gold)
    await session.refresh(setup_row)
    resized = await size(session, setup_row, user)
    assert not resized.cached and (resized.lots, resized.risk_amount) == (0.03, 16.5)
    stored = await session.get(AISetupSize, (SETUP_ID, user.id), populate_existing=True)
    assert stored.inputs["cost_per_unit"] == 0.5


async def test_size_request_carries_the_cost(
    session: AsyncSession, gold: Instrument, make_user, fake
) -> None:
    user = await make_user("cost-remote@example.com")
    await profile(session, user)
    setup_row = await armed(session, gold)
    result = await size(session, setup_row, user, client=client_for(fake))
    assert result.source == "remote"
    [(path, _, raw)] = fake.requests
    sent = json.loads(raw)
    assert path == "/v1/size" and sent["instrument_spec"]["cost_per_unit"] == 0.25


@pytest.fixture
def local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings  # noqa: PLC0415

    monkeypatch.setattr(get_settings(), "ai_size_mode", "local")


@pytest.fixture
def fake():
    from tests.test_ai_client import FakeAI  # noqa: PLC0415

    return FakeAI()
