"""B10: AI risk settings (mapping onto the risk profile), sizing of AI setups (ai-service
/v1/size with the local B4 fallback, caching, batch), the daily-loss and drawdown guards, and
taken trades with their close-out. ai-service is a fake (no network)."""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import contract as c
from app.ai import sizing, store
from app.ai.client import AIServiceClient
from app.core.config import get_settings
from app.models.ai import AISetup, AISetupSize, AISetupTake
from app.models.instrument import Instrument, MarketType
from app.models.risk import RiskProfile
from app.models.user import User
from app.schemas.risk import RiskProfileUpdate
from app.services import risk_service
from tests.market_utils import make_instrument
from tests.test_ai_client import FakeAI
from tests.test_ai_store import move, request_at, response, setup
from tests.utils import bearer

NOW = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
T0 = datetime(2026, 10, 19, 14, 15, tzinfo=UTC)
SETUP_ID = "xau-b4-buy"
GOLD_SPECS = {
    "contract_size": 100,
    "tick_size": 0.01,
    "lot_step": 0.01,
    "min_lot": 0.01,
    "max_lot": 100,
    "price_basis": "bid",
    "quote_currency": "USD",
}


# --- fixtures ------------------------------------------------------------------------------------


@pytest.fixture
async def gold(session: AsyncSession) -> Instrument:
    return await make_instrument(
        session, "XAU/USD", "fxpro", market=MarketType.commodity, **GOLD_SPECS
    )


async def armed(session: AsyncSession, gold: Instrument, setup_id: str = SETUP_ID, **changes):
    """An ARMED buy setup: entry 2400.00, sl 2395.00, tp 2410.00 (the B4 hand example)."""
    req = request_at(T0)
    prices = {"entry": 2400.0, "sl": 2395.0, "tp": 2410.0, **changes}
    payload = setup(setup_id, "ARMED", **prices)
    await store.apply_evaluation(session, gold, req, response(req, new=[payload]))
    return await session.get(AISetup, setup_id, populate_existing=True)


async def profile(
    session: AsyncSession, user: User, *, balance=2000.0, currency="USD", **changes
) -> RiskProfile:
    data = RiskProfileUpdate(account_size=balance, quote_currency=currency, **changes)
    return await risk_service.update(session, user, data)


@pytest.fixture
def local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ai_size_mode", "local")


@pytest.fixture
def fake() -> FakeAI:
    return FakeAI()


@pytest.fixture
def ai(fake: FakeAI, monkeypatch: pytest.MonkeyPatch):
    """The API's ai-service client goes to the fake (backoff 0)."""
    monkeypatch.setattr(
        sizing, "AIServiceClient", lambda: AIServiceClient("http://ai", transport=fake, backoff=0)
    )
    return fake


def client_for(fake: FakeAI) -> AIServiceClient:
    return AIServiceClient("http://ai", transport=fake, backoff=0)


# --- mapping -------------------------------------------------------------------------------------


def _profile(config: dict, **kw) -> RiskProfile:
    return RiskProfile(
        user_id=uuid.uuid4(),
        account_size=kw.get("balance", 2000.0),
        quote_currency=kw.get("currency", "USD"),
        leverage=kw.get("leverage", 100.0),
        config=config,
    )


@pytest.mark.parametrize(
    ("template", "risk", "daily", "drawdown"),
    [
        ("conservative", (0.5, "config"), (3.0, "default"), (10.0, "config")),
        ("balanced", (1.0, "config"), (3.0, "default"), (10.0, "default")),
        ("aggressive", (2.0, "config"), (3.0, "default"), (10.0, "default")),
    ],
)
def test_template_mapping(template, risk, daily, drawdown) -> None:
    inputs = risk_service.ai_risk_inputs(_profile(risk_service.templates()[template]))
    assert inputs.account == c.Account(balance=2000, currency="USD", leverage=100)
    got = inputs.risk
    assert (got.risk_per_trade_pct, inputs.sources["risk_per_trade_pct"]) == risk
    assert (got.daily_loss_limit_pct, inputs.sources["daily_loss_limit_pct"]) == daily
    assert (got.max_drawdown_pct, inputs.sources["max_drawdown_pct"]) == drawdown
    assert inputs.warnings == []
    assert inputs.sources["balance"] == inputs.sources["leverage"] == "profile"


def test_non_risk_sizing_and_configured_guards() -> None:
    config = risk_service.validate_config(
        {
            **risk_service.templates()["balanced"],
            "sizing": {"mode": "fraction", "value": 1.0},
            "guards": {"max_daily_loss_pct": 2, "max_drawdown_pct": 8},
        }
    )
    inputs = risk_service.ai_risk_inputs(_profile(config))
    assert inputs.risk.risk_per_trade_pct == 1.0
    assert inputs.sources["risk_per_trade_pct"] == "default"
    assert inputs.warnings == ["sizing mode is not risk-based; used 1%"]
    assert (inputs.risk.daily_loss_limit_pct, inputs.risk.max_drawdown_pct) == (2.0, 8.0)
    assert inputs.sources["daily_loss_limit_pct"] == inputs.sources["max_drawdown_pct"] == "config"


async def test_profile_api_leverage_and_ai_risk(
    client: AsyncClient, session: AsyncSession, make_user, login
) -> None:
    user = await make_user("b10-profile@example.com")
    headers = bearer((await login("b10-profile@example.com"))["access_token"])
    body = (await client.get("/api/v1/me/risk-profile", headers=headers)).json()
    assert body["leverage"] == 100 and body["account_size"] == 10_000
    assert body["ai_risk"] == {
        "balance": 10_000.0,
        "currency": "USDT",
        "leverage": 100.0,
        "risk_per_trade_pct": 1.0,
        "daily_loss_limit_pct": 3.0,
        "max_drawdown_pct": 10.0,
        "sources": {
            "balance": "profile",
            "currency": "profile",
            "leverage": "profile",
            "risk_per_trade_pct": "config",
            "daily_loss_limit_pct": "default",
            "max_drawdown_pct": "default",
        },
        "warnings": [],
        "error": None,
    }
    row = await session.get(RiskProfile, user.id)
    assert row.balance_set_at is None

    res = await client.put("/api/v1/me/risk-profile", json={"leverage": 30}, headers=headers)
    assert res.status_code == 200 and res.json()["leverage"] == 30
    assert res.json()["ai_risk"]["leverage"] == 30
    for bad in (0, -1, 10_001, "x"):
        res = await client.put("/api/v1/me/risk-profile", json={"leverage": bad}, headers=headers)
        assert res.status_code == 422 and res.json()["detail"][0]["loc"] == ["body", "leverage"]
    await session.refresh(row)
    assert row.balance_set_at is None  # the balance did not change

    res = await client.put("/api/v1/me/risk-profile", json={"account_size": 2000}, headers=headers)
    assert res.status_code == 200
    await session.refresh(row)
    first = row.balance_set_at
    assert first is not None
    await client.put("/api/v1/me/risk-profile", json={"account_size": 2000}, headers=headers)
    await session.refresh(row)
    assert row.balance_set_at == first  # same value: unchanged


# --- local sizing --------------------------------------------------------------------------------


async def size(session, setup_row, user, **kw) -> sizing.SizeResult:
    return await sizing.size_setup_for_user(session, setup_row, user, now=NOW, **kw)


async def test_b4_example_locally(
    session: AsyncSession, gold: Instrument, make_user, local_mode
) -> None:
    user = await make_user("b4@example.com")
    await profile(session, user)
    result = await size(session, await armed(session, gold), user)
    assert (result.lots, result.risk_amount, result.feasible) == (0.04, 20.0, True)
    assert (result.margin_required, result.source, result.warnings) == (96.0, "local", [])
    stored = await session.get(AISetupSize, (SETUP_ID, user.id))
    assert (stored.lots, stored.risk_usd, stored.source) == (0.04, 20.0, "local")
    assert stored.inputs["account"] == {"balance": 2000.0, "currency": "USD", "leverage": 100.0}


@pytest.mark.parametrize(
    ("balance", "currency", "leverage", "changes", "expected"),
    [
        # a sell: sl above entry
        (2000, "USD", 100, {"direction": "sell", "sl": 2405.0, "tp": 2390.0}, (0.04, 20.0, 96.0)),
        # 29.90 at risk / 500 per lot = 0.0598 -> always down to 0.05
        (2990, "USD", 100, {}, (0.05, 25.0, 120.0)),
        # leverage 1: the full notional
        (2000, "USD", 1, {}, (0.04, 20.0, 9600.0)),
        # 1,000,000 x 1 % / 500 = 20 lots, within max_lot
        (1_000_000, "USD", 100, {}, (20.0, 10_000.0, 48_000.0)),
    ],
)
async def test_local_sizing_cases(
    session: AsyncSession,
    gold,
    make_user,
    local_mode,
    balance,
    currency,
    leverage,
    changes,
    expected,
) -> None:
    user = await make_user(f"case-{balance}-{leverage}@example.com")
    await profile(session, user, balance=balance, currency=currency, leverage=leverage)
    result = await size(session, await armed(session, gold, **changes), user)
    assert (result.lots, result.risk_amount, result.margin_required) == expected
    assert result.feasible


async def test_below_min_lot_and_above_max_lot(
    session: AsyncSession, gold, make_user, local_mode
) -> None:
    small = await make_user("small@example.com")
    await profile(session, small, balance=100)  # 1 USD at risk; 0.01 lot risks 5 USD
    result = await size(session, await armed(session, gold), small)
    assert (result.lots, result.feasible, result.risk_amount) == (0.0, False, 0.0)
    assert any("minimum 0.01 lots would risk 5.00 USD" in w for w in result.warnings)

    whale = await make_user("whale@example.com")
    await profile(session, whale, balance=10_000_000)  # 100,000 at risk = 200 lots
    result = await size(session, await armed(session, gold), whale)
    assert (result.lots, result.feasible) == (100.0, True)
    assert "capped at the maximum of 100 lots" in result.warnings


async def test_currencies(session: AsyncSession, gold, make_user, local_mode) -> None:
    tether = await make_user("usdt@example.com")
    await profile(session, tether, currency="USDT")
    result = await size(session, await armed(session, gold), tether)
    assert (result.lots, result.risk_amount, result.margin_required) == (0.04, 20.0, 96.0)
    assert result.warnings == ["USD, USDT and USDC treated as the same dollar (1:1)"]

    euro = await make_user("eur@example.com")
    await profile(session, euro, currency="EUR")  # no EUR/USD market: no rate
    result = await size(session, await armed(session, gold), euro)
    assert (result.lots, result.feasible, result.margin_required) == (0.0, False, None)
    assert "no conversion rate from USD to EUR" in result.warnings
    assert "no conversion rate from USD to EUR: the margin is unknown" in result.warnings


async def test_unpriced_setup_and_missing_specs(
    session: AsyncSession, gold, make_user, local_mode
) -> None:
    user = await make_user("unpriced@example.com")
    req = request_at(T0)
    developing = setup("dev-1", "DEVELOPING", entry=None, sl=None, tp=None)
    await store.apply_evaluation(session, gold, req, response(req, new=[developing]))
    with pytest.raises(sizing.NotPriced):
        await size(session, await session.get(AISetup, "dev-1"), user)
    bare = await make_instrument(session, "XAG/USD", "fxpro", market=MarketType.commodity)
    await store.apply_evaluation(session, bare, req, response(req, new=[setup("silver", "ARMED")]))
    with pytest.raises(sizing.NoSpecs, match="has no contract_size"):
        await size(session, await session.get(AISetup, "silver"), user)


# --- ai-service path -----------------------------------------------------------------------------


async def test_ai_service_answer_is_stored(
    session: AsyncSession, gold, make_user, fake: FakeAI
) -> None:
    user = await make_user("remote@example.com")
    await profile(session, user)
    row = await armed(session, gold)
    result = await size(session, row, user, client=client_for(fake))
    assert (result.lots, result.risk_amount, result.margin_required) == (0.04, 20.0, 96.0)
    assert (result.source, result.feasible) == ("ai-service", True)
    [(path, request_id, body)] = fake.requests
    assert path == "/v1/size" and request_id == SETUP_ID
    sent = json.loads(body)
    assert sent["setup"] == row.last_payload  # echoed exactly
    assert sent["account"] == {"balance": 2000.0, "currency": "USD", "leverage": 100.0}
    assert sent["risk"] == {
        "risk_per_trade_pct": 1.0,
        "daily_loss_limit_pct": 3.0,
        "max_drawdown_pct": 10.0,
    }
    assert sent["instrument_spec"]["contract_size"] == 100
    assert (await session.get(AISetupSize, (SETUP_ID, user.id))).source == "ai-service"


async def test_unavailable_falls_back_in_auto_only(
    session: AsyncSession, gold, make_user, fake: FakeAI, monkeypatch
) -> None:
    user = await make_user("fallback@example.com")
    await profile(session, user)
    row = await armed(session, gold)
    fake.faults = ["timeout", 500, 503]
    result = await size(session, row, user, client=client_for(fake))
    assert (result.source, result.lots, result.risk_amount) == ("local", 0.04, 20.0)
    assert "ai-service is unavailable; sized by the backend" in result.warnings
    assert len(fake.requests) == 3  # the client's retries, then the fallback

    monkeypatch.setattr(get_settings(), "ai_size_mode", "remote")
    fake.faults = [500, 500, 500]
    with pytest.raises(sizing.SizeUnavailable) as err:
        await size(session, row, user, client=client_for(fake))
    assert err.value.status == 503


async def test_404_falls_back_and_422_does_not(
    session: AsyncSession, gold, make_user, fake: FakeAI
) -> None:
    user = await make_user("contract@example.com")
    await profile(session, user)
    row = await armed(session, gold)
    fake.faults = [404]
    result = await size(session, row, user, client=client_for(fake))
    assert result.source == "local" and result.lots == 0.04
    assert "ai-service has no /v1/size yet (404); sized by the backend" in result.warnings

    await profile(session, user, balance=2100)  # new inputs: computed again
    fake.faults = [422]
    with pytest.raises(sizing.SizeContractError) as err:
        await size(session, row, user, client=client_for(fake))
    assert err.value.status == 502
    stored = await session.get(AISetupSize, (SETUP_ID, user.id), populate_existing=True)
    assert stored.inputs["account"]["balance"] == 2000.0  # the failed call stored nothing


# --- caching -------------------------------------------------------------------------------------


async def test_same_inputs_are_reused(session: AsyncSession, gold, make_user, fake: FakeAI) -> None:
    user = await make_user("cache@example.com")
    await profile(session, user)
    row = await armed(session, gold)
    first = await size(session, row, user, client=client_for(fake))
    again = await size(session, row, user, client=client_for(fake))
    assert len(fake.requests) == 1 and again.cached and again.lots == first.lots

    await profile(session, user, balance=2500)
    await size(session, row, user, client=client_for(fake))
    assert len(fake.requests) == 2

    # ARMED -> ACTIVE: a new payload, sized again
    req = request_at(T0 + timedelta(minutes=15))
    trans = [move(SETUP_ID, "ARMED", "ACTIVE", T0 + timedelta(minutes=5))]
    await store.apply_evaluation(session, gold, req, response(req, transitions=trans))
    row = await session.get(AISetup, SETUP_ID, populate_existing=True)
    await size(session, row, user, client=client_for(fake))
    assert len(fake.requests) == 3
    assert json.loads(fake.requests[-1][2])["setup"]["state"] == "ACTIVE"


# --- guards --------------------------------------------------------------------------------------


async def closed_take(session, gold, user, pnl: float, closed_at: datetime, risk=20.0) -> None:
    setup_id = f"done-{uuid.uuid4().hex[:8]}"
    session.add(
        AISetup(
            setup_id=setup_id,
            instrument_id=gold.id,
            profile="intraday",
            direction="buy",
            state="CLOSED",
            last_payload={"setup_id": setup_id, "state": "CLOSED", "direction": "buy"},
            first_request_id="r",
            last_request_id="r",
        )
    )
    await session.flush()
    session.add(
        AISetupTake(
            setup_id=setup_id,
            user_id=user.id,
            lots=0.04,
            risk_amount=risk,
            closed_at=closed_at,
            realized_r=pnl / risk,
            pnl=pnl,
            close_reason="tp_hit" if pnl > 0 else "sl_hit",
        )
    )
    await session.commit()


async def test_daily_loss_guard(session: AsyncSession, gold, make_user, fake: FakeAI) -> None:
    user = await make_user("daily@example.com")
    await profile(session, user)  # 2,000 USD, 1 %, daily limit 3 % (default) = 60 USD
    row = await armed(session, gold)
    await closed_take(session, gold, user, -80.0, NOW - timedelta(days=1))  # yesterday: ignored
    await closed_take(session, gold, user, -40.0, NOW - timedelta(hours=1))  # -2R = 2 %
    result = await size(session, row, user, client=client_for(fake))
    assert result.feasible and result.lots == 0.04 and len(fake.requests) == 1

    await closed_take(session, gold, user, -40.0, NOW - timedelta(minutes=30))  # 4 % today
    result = await size(session, row, user, client=client_for(fake))
    assert (result.feasible, result.lots, result.risk_amount) == (False, 0.0, 0.0)
    assert sizing.DAILY_LOSS in result.warnings
    assert "lost 80.00 USD today (4.00% of the balance), the limit is 3%" in result.warnings
    assert len(fake.requests) == 1  # no ai-service call


async def test_drawdown_guard_and_balance_reset(
    session: AsyncSession, gold, make_user, fake: FakeAI
) -> None:
    user = await make_user("drawdown@example.com")
    config = {**risk_service.templates()["balanced"], "guards": {"max_drawdown_pct": 5}}
    row_profile = await profile(session, user, config=config)  # 5 % of 2,000 = 100 USD
    row_profile.balance_set_at = NOW - timedelta(days=10)  # the balance was set before the takes
    await session.commit()
    row = await armed(session, gold)
    days = [NOW - timedelta(days=d) for d in (3, 2, 1)]  # before today: no daily loss
    await closed_take(session, gold, user, +20.0, days[0])  # +1R: running +20, peak 20
    await closed_take(session, gold, user, -60.0, days[1])  # -3R: running -40, down 60 (3 %)
    assert (await size(session, row, user, client=client_for(fake))).feasible
    await closed_take(session, gold, user, -60.0, days[2])  # -3R: running -100, down 120 (6 %)
    result = await size(session, row, user, client=client_for(fake))
    assert not result.feasible and sizing.DRAWDOWN in result.warnings
    assert "down 120.00 USD from the best point (6.00% of the balance)" in " ".join(result.warnings)
    assert len(fake.requests) == 1

    await profile(session, user, balance=1900, config=config)  # a new balance: a new start
    result = await size(session, row, user, client=client_for(fake))
    assert result.feasible and len(fake.requests) == 2


# --- takes ---------------------------------------------------------------------------------------


async def test_take_flow_and_close_out(
    client: AsyncClient, session: AsyncSession, gold, make_user, login, local_mode
) -> None:
    alice = await make_user("taker@example.com")
    await make_user("other-taker@example.com")
    ah = bearer((await login("taker@example.com"))["access_token"])
    bh = bearer((await login("other-taker@example.com"))["access_token"])
    await profile(session, alice)
    await armed(session, gold)
    res = await client.get(f"/api/v1/ai/setups/{SETUP_ID}/size", headers=ah)
    assert res.status_code == 200 and res.json()["taken"] is False

    url = f"/api/v1/ai/setups/{SETUP_ID}/take"
    first = await client.post(url, headers=ah)
    assert first.status_code == 201, first.text
    assert (first.json()["lots"], first.json()["risk_amount"]) == (0.04, 20.0)  # stored size
    again = await client.post(url, json={"lots": 1}, headers=ah)
    assert again.status_code == 200 and again.json() == first.json()  # unchanged
    assert (await client.get(f"/api/v1/ai/setups/{SETUP_ID}/size", headers=ah)).json()["taken"]

    # bob takes 0.10 lot without a stored size: risk from the specs (0.10 x 500 = 50 USD)
    res = await client.post(url, json={"lots": 0.1, "entry_price": 2400.5}, headers=bh)
    assert res.status_code == 201 and res.json()["risk_amount"] == 50.0
    assert (await client.delete(url, headers=bh)).status_code == 204
    assert (await client.delete(url, headers=bh)).status_code == 404  # nothing left to undo
    await client.post(url, json={"lots": 0.1}, headers=bh)

    # ARMED -> ACTIVE -> CLOSED at +1.5R: pnl = 1.5 x 20 = 30 for alice, 75 for bob
    req = request_at(T0 + timedelta(minutes=15))
    trans = [
        move(SETUP_ID, "ARMED", "ACTIVE", T0 + timedelta(minutes=3)),
        move(SETUP_ID, "ACTIVE", "CLOSED", T0 + timedelta(minutes=12), reason="tp_hit",
             realized_r=1.5),
    ]  # fmt: skip
    resp = response(req, transitions=trans)
    await store.apply_evaluation(session, gold, req, resp)
    take = await session.get(AISetupTake, (SETUP_ID, alice.id), populate_existing=True)
    assert (take.realized_r, take.pnl, take.close_reason) == (1.5, 30.0, "tp_hit")
    assert take.closed_at == T0 + timedelta(minutes=12)
    take.pnl = 31.0  # a replayed transition must not touch a closed take
    await session.commit()
    await store.apply_evaluation(session, gold, req, resp)
    take = await session.get(AISetupTake, (SETUP_ID, alice.id), populate_existing=True)
    assert take.pnl == 31.0

    trades = (await client.get("/api/v1/me/ai/trades", headers=ah)).json()
    assert trades["total"] == 1
    [trade] = trades["items"]
    assert (trade["setup_id"], trade["state"], trade["realized_r"]) == (SETUP_ID, "CLOSED", 1.5)
    bob_trades = (await client.get("/api/v1/me/ai/trades", headers=bh)).json()
    assert [t["pnl"] for t in bob_trades["items"]] == [75.0]  # only his own

    assert (await client.delete(url, headers=ah)).status_code == 409  # final: kept
    assert (await client.post(url, headers=ah)).status_code == 200  # still the same take

    await make_user("carol-taker@example.com")
    ch = bearer((await login("carol-taker@example.com"))["access_token"])
    assert (await client.get("/api/v1/me/ai/trades", headers=ch)).json()["total"] == 0
    assert (await client.delete(url, headers=ch)).status_code == 404  # not hers to undo
    assert (await session.get(AISetupTake, (SETUP_ID, alice.id))) is not None


async def test_take_rules(
    client: AsyncClient, session: AsyncSession, gold, make_user, login, local_mode
) -> None:
    await make_user("rules@example.com")
    headers = bearer((await login("rules@example.com"))["access_token"])
    req = request_at(T0)
    new = [
        setup("dev", "DEVELOPING", entry=None, sl=None, tp=None),
        setup("gone", "EXPIRED"),
        setup("exp-armed", "ARMED"),
    ]
    await store.apply_evaluation(session, gold, req, response(req, new=new))
    for setup_id in ("dev", "gone"):
        res = await client.post(f"/api/v1/ai/setups/{setup_id}/take", headers=headers)
        assert res.status_code == 409, res.text
        res = await client.get(f"/api/v1/ai/setups/{setup_id}/size", headers=headers)
        assert res.status_code == 409
    assert (await client.post("/api/v1/ai/setups/nope/take", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/ai/setups/nope/size", headers=headers)).status_code == 404

    # EXPIRED closes the take with 0
    assert (
        await client.post("/api/v1/ai/setups/exp-armed/take", json={"lots": 0.02}, headers=headers)
    ).status_code == 201
    req2 = request_at(T0 + timedelta(minutes=15))
    trans = [move("exp-armed", "ARMED", "EXPIRED", T0 + timedelta(minutes=14))]
    await store.apply_evaluation(session, gold, req2, response(req2, transitions=trans))
    [trade] = (await client.get("/api/v1/me/ai/trades", headers=headers)).json()["items"]
    assert (trade["realized_r"], trade["pnl"], trade["close_reason"]) == (0.0, 0.0, "expired")
    assert trade["state"] == "EXPIRED"


# --- batch ---------------------------------------------------------------------------------------


class SlowFakeAI(FakeAI):
    """Counts the requests in flight at once."""

    def __init__(self) -> None:
        super().__init__()
        self.in_flight = self.peak = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(0.05)
            return await super().handle_async_request(request)
        finally:
            self.in_flight -= 1


async def test_batch_sizing(
    session: AsyncSession, gold, make_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_size_concurrency", 2)
    users = [await make_user(f"batch{i}@example.com") for i in range(5)]
    for user in users[:4]:
        await profile(session, user)
    await profile(session, users[4], currency="X")  # not a currency the contract accepts
    fake = SlowFakeAI()
    row = await armed(session, gold)
    results = await sizing.size_setup_for_users(
        session, row, [u.id for u in users], client=client_for(fake), now=NOW
    )
    ok = [r for r in results.values() if isinstance(r, sizing.SizeResult)]
    assert len(ok) == 4 and all(r.lots == 0.04 and r.source == "ai-service" for r in ok)
    error = results[users[4].id]
    assert isinstance(error, sizing.ProfileError)
    assert str(error).startswith("the risk profile cannot be used: currency: String should")
    assert len(fake.requests) == 4 and fake.peak == 2  # bounded concurrency
    stored = await session.scalars(select(AISetupSize).where(AISetupSize.setup_id == SETUP_ID))
    assert len(list(stored)) == 4


# --- permissions and admin -----------------------------------------------------------------------


async def test_size_endpoint_and_admin_detail(
    client: AsyncClient, session: AsyncSession, gold, make_user, login, admin_headers, ai: FakeAI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    user = await make_user("api-size@example.com")
    headers = bearer((await login("api-size@example.com"))["access_token"])
    await profile(session, user)
    await armed(session, gold)
    url = f"/api/v1/ai/setups/{SETUP_ID}/size"
    assert (await client.get(url)).status_code == 401
    res = await client.get(url, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["lots"], body["risk_amount"], body["source"]) == (0.04, 20.0, "ai-service")
    assert body["inputs"] == {
        "balance": 2000.0,
        "currency": "USD",
        "leverage": 100.0,
        "risk_per_trade_pct": 1.0,
        "daily_loss_limit_pct": 3.0,
        "max_drawdown_pct": 10.0,
        "sources": {
            "balance": "profile",
            "currency": "profile",
            "leverage": "profile",
            "risk_per_trade_pct": "config",
            "daily_loss_limit_pct": "default",
            "max_drawdown_pct": "default",
        },
    }
    assert body["taken"] is False and "computed_at" in body

    # remote mode: unavailable -> 503; a 422 from ai-service -> 502 (no fallback)
    await profile(session, user, balance=2200)
    monkeypatch.setattr(get_settings(), "ai_size_mode", "remote")
    ai.faults = ["timeout", "timeout", "timeout"]
    assert (await client.get(url, headers=headers)).status_code == 503
    monkeypatch.setattr(get_settings(), "ai_size_mode", "auto")
    ai.faults = [422]
    res = await client.get(url, headers=headers)
    assert res.status_code == 502 and "outside the contract" in res.json()["detail"]

    detail = (await client.get(f"/api/v1/admin/ai/setups/{SETUP_ID}", headers=admin_headers)).json()
    assert detail["takes_count"] == 0 and detail["setup_id"] == SETUP_ID
    [brief] = detail["sizes"]
    assert (brief["user_id"], brief["lots"], brief["source"]) == (str(user.id), 0.04, "ai-service")
    assert "events" in detail and "last_payload" in detail
