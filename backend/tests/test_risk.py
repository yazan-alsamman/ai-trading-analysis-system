"""Risk management API: profiles (lazy creation, templates, validation), activation overrides,
per-user trade plans on live signals (two users, an invalid plan, WebSocket, idempotency,
failures), /me/signal-plans, backtests with risk rules and the profile snapshot, the
position-size calculator, workspace custom overlays and API key scopes."""

import json
import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import trading_backtest as tb
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.candle import Timeframe
from app.models.instrument import MarketType
from app.models.risk import RiskProfile, SignalPlan
from app.models.user import UserRole
from app.realtime.topics import signals_topic, user_topic
from app.schemas.market import CandleIn
from app.schemas.risk import RiskProfileUpdate
from app.services import (
    backtest_service,
    custom_strategy_service,
    market_service,
    risk_service,
    signal_engine,
    strategy_resolver,
)
from app.services.seed_service import generate_demo_candles
from app.services.signal_engine import Job
from tests.api_key_utils import create_key, xkey
from tests.custom_utils import MA_REPLICA, make_custom, rsi_below
from tests.market_utils import make_instrument
from tests.strategy_utils import RSI1, activate, add_closes
from tests.test_signal_engine import Listener
from tests.utils import bearer

PROFILE = "/api/v1/me/risk-profile"
SIZE = "/api/v1/risk/position-size"
PLANS = "/api/v1/me/signal-plans"
T0 = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
DIP = [10.0, 9.0, 8.0, 9.0]  # RSI(1) crosses 30 upward on bar 3 -> rsi_reversal buy
BAR = T0 + timedelta(minutes=3)
PERCENT_RULES = {
    "stop": {"type": "percent", "value": 2},
    "take_profit": {"type": "r_multiple", "value": 2},
    "sizing": {"mode": "risk", "risk_pct": 1},
}


@pytest.fixture
async def alice(make_user):
    user = await make_user("alice@example.com", role=UserRole.analyst)
    return user, bearer(create_access_token(user))


@pytest.fixture
async def bob(make_user):
    user = await make_user("bob@example.com")
    return user, bearer(create_access_token(user))


# --- profiles ----------------------------------------------------------------------------------


async def test_profile_is_created_on_first_read(
    client: AsyncClient, session: AsyncSession, alice
) -> None:
    user, headers = alice
    assert await session.get(RiskProfile, user.id) is None
    res = await client.get(PROFILE, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert (data["account_size"], data["quote_currency"], data["template"]) == (
        10_000.0,
        "USDT",
        "balanced",
    )
    assert data["config"] == tb.validate_risk_config(tb.TEMPLATES["balanced"])
    again = (await client.get(PROFILE, headers=headers)).json()
    assert again == data
    count = await session.scalar(select(func.count()).select_from(RiskProfile))
    assert count == 1


async def test_put_template_config_and_account(client: AsyncClient, alice) -> None:
    _, headers = alice
    res = await client.put(PROFILE, json={"template": "conservative"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["template"] == "conservative"
    assert data["config"]["sizing"]["risk_pct"] == 0.5
    assert data["config"]["guards"]["max_drawdown_pct"] == 10
    res = await client.put(
        PROFILE,
        json={"config": PERCENT_RULES, "account_size": 2500, "quote_currency": "USDC"},
        headers=headers,
    )
    data = res.json()
    assert (data["template"], data["account_size"], data["quote_currency"]) == (None, 2500, "USDC")
    assert data["config"]["stop"] == {"type": "percent", "value": 2.0}
    # a config equal to a template is recognised as that template
    res = await client.put(PROFILE, json={"config": tb.TEMPLATES["aggressive"]}, headers=headers)
    assert res.json()["template"] == "aggressive" and res.json()["account_size"] == 2500


@pytest.mark.parametrize(
    ("body", "loc", "fragment"),
    [
        (
            {"config": {"stop": {"type": "atr", "multiplier": 0}}},
            ["body", "config", "stop", "multiplier"],
            "greater than 0",
        ),
        ({"config": {"sizing": {"mode": "risk"}}}, ["body", "config", "sizing", "mode"], "stop"),
        ({"config": {"leverage": 3}}, ["body", "config", "leverage"], "unknown field"),
        ({"template": "yolo"}, ["body", "template"], "Input should be"),
        ({"account_size": 0}, ["body", "account_size"], "greater than 0"),
        ({"quote_currency": "usdt"}, ["body", "quote_currency"], "pattern"),
        ({"template": "balanced", "config": {}}, ["body"], "either config or template"),
    ],
)
async def test_put_validation_with_paths(client: AsyncClient, alice, body, loc, fragment) -> None:
    _, headers = alice
    res = await client.put(PROFILE, json=body, headers=headers)
    assert res.status_code == 422
    first = res.json()["detail"][0]
    assert first["loc"] == loc and fragment in first["msg"]
    if loc[:2] == ["body", "config"]:
        assert first["path"] == ".".join(str(p) for p in loc[2:])


async def test_schema(client: AsyncClient, alice) -> None:
    _, headers = alice
    data = (await client.get("/api/v1/risk/schema", headers=headers)).json()
    assert set(data["templates"]) == {"conservative", "balanced", "aggressive"}
    assert data["default_template"] == "balanced"
    assert {"stop", "trailing", "take_profit", "sizing", "guards"} <= set(
        data["json_schema"]["properties"]
    )


# --- activation overrides ------------------------------------------------------------------------


async def test_override_on_activation(client: AsyncClient, session: AsyncSession, alice) -> None:
    _, headers = alice
    btc = await make_instrument(session, "BTC/USDT")
    base = {"strategy_key": "rsi_reversal", "instrument_id": str(btc.id), "timeframe": "1h"}
    res = await client.post(
        "/api/v1/me/strategies", json={**base, "risk_override": PERCENT_RULES}, headers=headers
    )
    assert res.status_code == 201, res.text
    row = res.json()
    assert row["risk_override"] == tb.validate_risk_config(PERCENT_RULES)
    url = f"/api/v1/me/strategies/{row['id']}"
    bad = await client.patch(url, json={"risk_override": {"stop": {"type": "x"}}}, headers=headers)
    assert bad.status_code == 422
    assert bad.json()["detail"][0]["loc"] == ["body", "risk_override", "stop"]
    cleared = await client.patch(url, json={"risk_override": None}, headers=headers)
    assert cleared.status_code == 200 and cleared.json()["risk_override"] is None


def test_override_precedence() -> None:
    profile = RiskProfile(
        account_size=5_000, quote_currency="EUR", config={"x": "profile"}, template=None
    )
    assert risk_service.effective({"x": "override"}, profile) == (
        {"x": "override"},
        5_000,
        "EUR",
        "override",
    )
    assert risk_service.effective(None, profile) == ({"x": "profile"}, 5_000, "EUR", "profile")
    config, size, currency, source = risk_service.effective(None, None)
    assert (config, size, currency, source) == (
        risk_service.default_config(),
        10_000.0,
        "USDT",
        "default",
    )


# --- live plans ----------------------------------------------------------------------------------


async def _set_profile(session, user, **data) -> None:
    await risk_service.update(session, user, RiskProfileUpdate(**data))


async def _plans(session: AsyncSession) -> list[SignalPlan]:
    rows = await session.scalars(
        select(SignalPlan).order_by(SignalPlan.created_at).execution_options(populate_existing=True)
    )
    return list(rows.all())


async def test_two_users_get_their_own_plans_on_one_signal(
    session: AsyncSession, session_factory, redis_client: Redis, alice, bob, make_user
) -> None:
    a, _ = alice
    b, _ = bob
    carol = await make_user("carol@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    await _set_profile(session, a, config=PERCENT_RULES, account_size=5_000)
    await _set_profile(session, b, template="balanced")  # ATR(14): not enough bars -> invalid
    a_row = await activate(session, a, btc, params=RSI1)
    b_row = await activate(session, b, btc, params=RSI1)
    c_row = await activate(session, carol, btc, params=RSI1, notify=False)
    await add_closes(session, btc.id, T0, DIP)

    async with Listener(redis_client) as listener:
        await listener.listen(signals_topic(btc.id), *(user_topic(u.id) for u in (a, b, carol)))
        result = await signal_engine.evaluate(
            session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR)
        )
        messages = dict(await listener.messages())
    assert (result.inserted, result.plans, result.user_messages) == (1, 3, 2)
    assert result.errors == []

    plans = {p.user_id: p for p in await _plans(session)}
    assert set(plans) == {a.id, b.id, carol.id}
    pa, pb = plans[a.id].plan, plans[b.id].plan
    # Alice: 2 % stop from the 9.0 close, 2 R target, 1 % of 5,000 at risk (fees included)
    per_unit = 0.18 + (9.0 + 8.82) * 0.001
    assert (pa["side"], pa["entry_ref"], pa["stop"], pa["invalid_reason"]) == (
        "long",
        9.0,
        8.82,
        None,
    )
    assert pa["targets"] == [{"price": 9.36, "r": 2.0, "close_pct": 100.0}]
    assert pa["quantity"] == pytest.approx(50 / per_unit, rel=1e-9)
    assert (pa["risk_amount"], pa["risk_pct"], pa["rr"]) == (50.0, 1.0, 2.0)
    assert (pa["account_size"], pa["risk_source"]) == (5_000, "profile")
    # Bob: the ATR stop cannot be computed on 4 bars -> a flagged plan, still stored and sent
    assert pb["invalid_reason"] == "stop_unavailable" and pb["quantity"] == 0
    assert plans[carol.id].plan["risk_source"] == "default"
    assert plans[a.id].user_strategy_id == a_row.id and plans[b.id].user_strategy_id == b_row.id

    msg_a, msg_b = messages[user_topic(a.id)], messages[user_topic(b.id)]
    assert msg_a["plan"] == pa and msg_a["plans"] == [
        {"user_strategy_id": str(a_row.id), "plan": pa}
    ]
    assert msg_b["plan"]["invalid_reason"] == "stop_unavailable"
    assert msg_a["signal"]["id"] == msg_b["signal"]["id"]
    assert user_topic(carol.id) not in messages and c_row.notify is False  # stored, not sent
    assert "plan" not in messages[signals_topic(btc.id)]  # the market topic stays user-free

    # re-running the job: nothing new
    await redis_client.delete(Job(btc.id, Timeframe.m1, BAR).lock_key)
    again = await signal_engine.evaluate(
        session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR)
    )
    assert (again.inserted, again.plans) == (0, 0)
    assert len(await _plans(session)) == 3


async def test_override_wins_and_a_failing_plan_blocks_nothing(
    session: AsyncSession, session_factory, redis_client: Redis, alice, bob, monkeypatch
) -> None:
    a, _ = alice
    b, _ = bob
    btc = await make_instrument(session, "BTC/USDT")
    row = await activate(session, a, btc, params=RSI1)
    row.risk_override = tb.validate_risk_config({**PERCENT_RULES, "fee_bps": 0})
    await session.commit()
    await activate(session, b, btc, params=RSI1)
    await add_closes(session, btc.id, T0, DIP)
    original = risk_service.plan_dict

    def flaky(df, side, config, size, *args, **kw):
        if config.get("stop") is None or config["stop"]["type"] == "atr":  # Bob's default
            raise RuntimeError("boom")
        return original(df, side, config, size, *args, **kw)

    monkeypatch.setattr(risk_service, "plan_dict", flaky)
    result = await signal_engine.evaluate(
        session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR)
    )
    assert result.inserted == 1 and result.plans == 1
    assert any("boom" in e for e in result.errors)
    [plan] = await _plans(session)
    assert plan.user_id == a.id and plan.plan["risk_source"] == "override"
    assert plan.plan["quantity"] == pytest.approx(10_000 * 0.01 / 0.18)  # no fees


async def test_signal_plans_unique_even_after_the_activation_is_deleted(
    session: AsyncSession, alice
) -> None:
    a, _ = alice
    btc = await make_instrument(session, "BTC/USDT")
    signal_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO signals (id, instrument_id, timeframe, strategy_key, params, "
            "params_hash, bar_time, side, strength, price, reason, details) VALUES "
            "(:id, :i, '1m', 'x', '{}', 'h', now(), 'buy', 1, 1, 'r', '{}')"
        ),
        {"id": signal_id, "i": btc.id},
    )
    session.add(SignalPlan(signal_id=signal_id, user_id=a.id, user_strategy_id=None, plan={}))
    await session.commit()
    session.add(SignalPlan(signal_id=signal_id, user_id=a.id, user_strategy_id=None, plan={}))
    with pytest.raises(IntegrityError):  # NULLS NOT DISTINCT
        await session.commit()
    await session.rollback()


async def test_my_signal_plans(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client, alice, bob
) -> None:
    a, a_headers = alice
    b, b_headers = bob
    btc = await make_instrument(session, "BTC/USDT")
    await activate(session, a, btc, params=RSI1)
    await add_closes(session, btc.id, T0, DIP)
    await signal_engine.evaluate(session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR))
    page = (await client.get(PLANS, headers=a_headers)).json()
    assert page["total"] == 1
    [item] = page["items"]
    assert item["signal"]["strategy_key"] == "rsi_reversal" and item["signal"]["side"] == "buy"
    assert item["plan"]["side"] == "long" and item["user_strategy_id"]
    assert (await client.get(PLANS, headers=b_headers)).json()["total"] == 0
    for params, total in (
        ({"strategy_key": "rsi_reversal"}, 1),
        ({"strategy_key": "macd_cross"}, 0),
        ({"timeframe": "1h"}, 0),
        ({"instrument_id": str(btc.id), "since": "2026-03-02T12:03:00"}, 1),
        ({"since": "2026-03-02T12:04:00Z"}, 0),
    ):
        res = await client.get(PLANS, params=params, headers=a_headers)
        assert res.json()["total"] == total, params


# --- backtests -----------------------------------------------------------------------------------

END = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def history(session: AsyncSession):
    instrument = await make_instrument(session, price_precision=2, quantity_precision=4)
    candles = generate_demo_candles(instrument, minutes=3_000, end=END, rng=random.Random(5))
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    return instrument


@pytest.fixture
def queued(monkeypatch) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    monkeypatch.setattr(backtest_service, "enqueue", ids.append)
    return ids


async def _backtest(client, headers, session_factory, instrument, config) -> dict:
    body = {
        "instrument_id": str(instrument.id),
        "timeframe": "1m",
        "strategy_key": "ma_crossover",
        "params": {"fast": 5, "slow": 20},
        "start": (END - timedelta(minutes=2_600)).isoformat(),
        "end": END.isoformat(),
        "config": config,
    }
    res = await client.post("/api/v1/backtests", json=body, headers=headers)
    assert res.status_code == 202, res.text
    backtest_id = uuid.UUID(res.json()["id"])
    assert await backtest_service.execute(session_factory, None, backtest_id) is not None
    return (await client.get(f"/api/v1/backtests/{backtest_id}", headers=headers)).json()


async def test_backtest_with_the_risk_profile(
    client: AsyncClient, session: AsyncSession, session_factory, alice, history, queued
) -> None:
    user, headers = alice
    await _set_profile(session, user, template="balanced", account_size=20_000)
    data = await _backtest(client, headers, session_factory, history, {"risk_profile": True})
    assert data["status"] == "completed", data["error"]
    config = data["config"]
    profile = config["risk_profile"]
    assert (profile["template"], profile["account_size"]) == ("balanced", 20_000)
    assert config["initial_capital"] == 20_000
    assert config["stop"] == {"type": "atr", "length": 14, "multiplier": 2.0}
    assert config["take_profit"]["levels"][0] == {"r": 1.0, "close_pct": 50.0}
    m = data["metrics"]
    # 1 % risk, but a 2 x ATR stop on 1m bars is tight: most entries hit the 100 % equity cap
    assert m["trades"] > 3 and m["avg_r"] is not None and 0 < m["avg_risk_pct"] <= 1 + 1e-9
    assert "partial_tp" in m["exits_by_reason"] and "skipped_entries" in m
    assert any("Partial TP" in mk["text"] for mk in data["markers"])
    trades = (await client.get(f"/api/v1/backtests/{data['id']}/trades", headers=headers)).json()
    first = trades["items"][0]
    assert first["initial_stop"] and first["risk_amount"] and first["r_multiple"] is not None
    assert first["fills"] and {"time", "price", "quantity", "reason"} <= set(first["fills"][0])
    csv_text = (
        await client.get(f"/api/v1/backtests/{data['id']}/trades.csv", headers=headers)
    ).text
    assert csv_text.splitlines()[0].endswith("initial_stop,risk_amount,r_multiple")

    # the profile changes later: the backtest keeps what it ran with
    await _set_profile(session, user, template="aggressive")
    again = (await client.get(f"/api/v1/backtests/{data['id']}", headers=headers)).json()
    assert again["config"] == config
    # request fields win over the profile; a Y11 stop_loss_pct replaces the profile's stop
    over = await _backtest(
        client,
        headers,
        session_factory,
        history,
        {"risk_profile": True, "initial_capital": 1_000, "exits": {"stop_loss_pct": 3}},
    )
    assert over["status"] == "failed" or over["config"]["initial_capital"] == 1_000
    assert over["config"]["stop"] == {"type": "percent", "value": 3.0}
    assert over["config"]["trailing"]["type"] == "atr"  # still the (now aggressive) profile


async def test_backtest_with_explicit_risk_rules(
    client: AsyncClient, session_factory, alice, history, queued
) -> None:
    _, headers = alice
    config = {
        "stop": {"type": "atr", "length": 14, "multiplier": 2},
        "trailing": {"type": "atr", "length": 14, "multiplier": 3},
        "sizing": {"mode": "risk", "risk_pct": 1},
        "guards": {"max_drawdown_pct": 5},
        "check_entry_bar": False,
    }
    data = await _backtest(client, headers, session_factory, history, config)
    assert data["status"] == "completed"
    assert data["config"]["check_entry_bar"] is False and "risk_profile" not in data["config"]
    exits = data["metrics"]["exits_by_reason"]
    assert set(exits) <= set(tb.EXIT_REASONS) and exits.get("trailing_stop", 0) > 0
    assert any("Trail" in mk["text"] for mk in data["markers"])


# --- calculator ----------------------------------------------------------------------------------


async def test_position_size_calculator(client: AsyncClient, session: AsyncSession, alice) -> None:
    user, headers = alice
    btc = await make_instrument(session, "BTC/USDT")
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    candles = generate_demo_candles(btc, minutes=400, end=now, rng=random.Random(3))
    await market_service.upsert_candles(session, btc.id, candles)
    await session.commit()
    base = {"instrument_id": str(btc.id), "timeframe": "1m", "side": "buy"}

    res = await client.post(SIZE, json=base, headers=headers)  # the profile: balanced, 10,000
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["bar_time"] == (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    plan = data["plan"]
    assert plan["invalid_reason"] is None and 0 < plan["risk_pct"] <= 1 + 1e-9
    # 1 % at risk, or capped at 100 % of the account (a tight ATR stop on 1m bars)
    capped = plan["notional"] * 1.001 == pytest.approx(10_000, rel=1e-6)
    assert capped or plan["risk_pct"] == pytest.approx(1)
    assert plan["entry_ref"] == pytest.approx(candles[-2].close)  # the last *closed* bar
    assert len(plan["targets"]) == 2 and plan["rr"] == pytest.approx(1)

    explicit = {
        **base,
        "entry": 100,
        "stop": 98,
        "account_size": 1_000,
        "config": {"sizing": {"mode": "risk", "risk_pct": 2}, "fee_bps": 0},
    }
    data = (await client.post(SIZE, json=explicit, headers=headers)).json()
    plan = data["plan"]
    assert (plan["entry_ref"], plan["stop"], plan["quantity"], plan["risk_amount"]) == (
        100.0,
        98.0,
        10.0,  # 2 % of 1,000 = 20 at risk, 2 per unit
        20.0,
    )
    assert data["config"]["stop"] is None and data["account_size"] == 1_000
    wrong = (await client.post(SIZE, json={**explicit, "stop": 101}, headers=headers)).json()
    assert wrong["plan"]["invalid_reason"] == "stop_wrong_side"
    res = await client.post(
        SIZE, json={**base, "config": {"sizing": {"mode": "risk"}}}, headers=headers
    )
    assert res.status_code == 422 and res.json()["detail"][0]["path"] == "sizing.mode"
    other = await make_instrument(session, "ETH/USDT")
    res = await client.post(SIZE, json={**base, "instrument_id": str(other.id)}, headers=headers)
    assert res.status_code == 422 and "No closed candles" in res.text
    res = await client.post(
        SIZE, json={**base, "instrument_id": str(uuid.uuid4())}, headers=headers
    )
    assert res.status_code == 404
    assert user.id


# --- API keys ------------------------------------------------------------------------------------


async def test_api_key_scopes(client: AsyncClient, session: AsyncSession, alice) -> None:
    _, headers = alice
    btc = await make_instrument(session, "BTC/USDT")
    with_scope = await create_key(client, headers, ["strategies:read"])
    without = await create_key(client, headers, ["market:read"], name="other")
    body = {"instrument_id": str(btc.id), "timeframe": "1m", "side": "buy"}
    for method, path, payload in (("GET", "/api/v1/risk/schema", None), ("POST", SIZE, body)):
        res = await client.request(method, path, json=payload, headers=xkey(with_scope["key"]))
        assert res.status_code in (200, 422), (path, res.text)  # 422: no candles for this market
        res = await client.request(method, path, json=payload, headers=xkey(without["key"]))
        assert res.status_code == 403
    for method, path in (("GET", PROFILE), ("PUT", PROFILE), ("GET", PLANS)):
        res = await client.request(method, path, json={}, headers=xkey(with_scope["key"]))
        assert res.status_code == 403, path
    assert (await client.get(PROFILE)).status_code == 401


# --- workspaces with custom strategy overlays ----------------------------------------------------


def _state(strategies: list[dict]) -> dict:
    return {
        "layout": {"type": "1x1"},
        "active_panel": "p1",
        "panels": [{"id": "p1", "strategies": strategies}],
    }


async def test_workspace_custom_overlays(
    client: AsyncClient, session: AsyncSession, alice, bob
) -> None:
    a, a_headers = alice
    b, b_headers = bob
    mine = await make_custom(session, b, "Mine", MA_REPLICA)
    public = await make_custom(session, a, "Shared", rsi_below(30), visibility="public")
    private = await make_custom(session, a, "Secret", rsi_below(20))
    ws = "/api/v1/me/workspaces"

    ok = _state(
        [
            {"id": "s1", "strategy_key": mine.key},
            {"id": "s2", "strategy_key": public.key.upper().replace("CUSTOM:", "custom:")},
        ]
    )
    res = await client.post(ws, json={"name": "Custom", "state": ok}, headers=b_headers)
    assert res.status_code == 201, res.text
    created = res.json()
    overlays = created["state"]["panels"][0]["strategies"]
    assert [s["strategy_key"] for s in overlays] == [mine.key, public.key]
    assert [s["unavailable"] for s in overlays] == [False, False]

    bad = _state([{"id": "s1", "strategy_key": private.key}])
    res = await client.post(ws, json={"name": "Bad", "state": bad}, headers=b_headers)
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == [
        "body", "state", "panels", 0, "strategies", 0, "strategy_key"
    ]  # fmt: skip
    params = _state([{"id": "s1", "strategy_key": mine.key, "params": {"fast": 3}}])
    res = await client.post(ws, json={"name": "Params", "state": params}, headers=b_headers)
    assert res.status_code == 422 and "take no params" in res.text

    # the author makes it private: flagged on read, and the workspace can still be saved
    await custom_strategy_service.patch(
        session, a, public.id, custom_strategy_service.CustomStrategyUpdate(visibility="private")
    )
    read = (await client.get(f"{ws}/{created['id']}", headers=b_headers)).json()
    flags = [s["unavailable"] for s in read["state"]["panels"][0]["strategies"]]
    assert flags == [False, True]
    res = await client.put(
        f"{ws}/{created['id']}",
        json={"version": read["version"], "state": read["state"]},
        headers=b_headers,
    )
    assert res.status_code == 200, res.text
    assert a.id and b.id


# --- one batch of custom setups per beat run ----------------------------------------------------


async def test_tick_resolves_custom_setups_in_one_batch(
    session: AsyncSession, session_factory, redis_client, alice, monkeypatch
) -> None:
    user, _ = alice
    btc = await make_instrument(session, "BTC/USDT")
    eth = await make_instrument(session, "ETH/USDT")
    shared = await make_custom(session, user, "RSI(1)", rsi_below(30, length=1))
    for instrument in (btc, eth):
        resolved = await strategy_resolver.get(session, shared.key, user)
        await activate(session, user, instrument, params=RSI1)  # a global one too
        from app.models.strategy import UserStrategy

        session.add(
            UserStrategy(
                user_id=user.id,
                strategy_key=shared.key,
                params={},
                params_hash=resolved.params_hash,
                instrument_id=instrument.id,
                timeframe=Timeframe.m1,
            )
        )
    await session.commit()
    calls = []
    original = strategy_resolver.engine_snapshots

    async def counting(s, keys):
        calls.append(sorted(keys))
        return await original(s, keys)

    monkeypatch.setattr(strategy_resolver, "engine_snapshots", counting)
    jobs = [Job(btc.id, Timeframe.m1, BAR), Job(eth.id, Timeframe.m1, BAR)]
    by_job = await signal_engine.custom_snapshots(session, jobs)
    assert calls == [[shared.key]]  # one batch for both jobs
    assert set(by_job) == {(btc.id, Timeframe.m1), (eth.id, Timeframe.m1)}

    # an evaluation given the snapshots does not resolve custom strategies again
    await add_closes(session, btc.id, T0, DIP)
    result = await signal_engine.evaluate(
        session_factory, redis_client, jobs[0], by_job[(btc.id, Timeframe.m1)]
    )
    assert calls == [[shared.key]] and result.setups == 2 and result.errors == []
    json.dumps(by_job[(btc.id, Timeframe.m1)])  # travels as a Celery argument


# --- lots on instruments with contract specs (B4) -------------------------------------------------

GOLD_SPECS = {
    "contract_size": 100.0,
    "tick_size": 0.01,
    "lot_step": 0.01,
    "min_lot": 0.01,
    "max_lot": 100.0,
    "quote_currency": "USD",
}
FX_SPECS = {**GOLD_SPECS, "contract_size": 100_000.0}
# 1 % risk without fees and with room for leverage, as in the hand-computed examples
RISK_1PCT = {"sizing": {"mode": "risk", "risk_pct": 1, "max_position_pct": 1000}, "fee_bps": 0}


async def _flat_market(session: AsyncSession, symbol: str, source: str, price: float, **kw):
    quote = symbol.partition("/")[2]
    instrument = await make_instrument(
        session, symbol, source, MarketType.forex, **{"quote_currency": quote, **kw}
    )
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    bars = [
        CandleIn(
            ts=now - timedelta(minutes=m), open=price, high=price, low=price, close=price, volume=1
        )
        for m in range(5)
    ]
    await market_service.upsert_candles(session, instrument.id, bars)
    await session.commit()
    return instrument


def _size(instrument, entry: float, stop: float, account_size: float) -> dict:
    return {
        "instrument_id": str(instrument.id),
        "timeframe": "1m",
        "side": "buy",
        "entry": entry,
        "stop": stop,
        "account_size": account_size,
        "config": RISK_1PCT,
    }


async def _plan(client: AsyncClient, headers, body: dict) -> dict:
    res = await client.post(SIZE, json=body, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["plan"]


async def test_position_size_lots_hand_computed(
    client: AsyncClient, session: AsyncSession, alice
) -> None:
    user, headers = alice
    await _set_profile(session, user, quote_currency="USD")
    gold = await _flat_market(session, "XAU/USD", "fxpro", 2400.0, **GOLD_SPECS)
    jpy = await _flat_market(
        session, "USD/JPY", "twelvedata", 150.0, **{**FX_SPECS, "quote_currency": "JPY"}
    )
    eur = await _flat_market(session, "EUR/USD", "twelvedata", 1.085, **FX_SPECS)

    # XAU/USD: 1 % of 2,000 USD = 20 USD; 5.00 x 100 oz = 500 USD per lot -> 0.04 lots
    plan = await _plan(client, headers, _size(gold, 2400, 2395, 2_000))
    assert (plan["quantity"], plan["lots"], plan["lots_feasible"]) == (4.0, 0.04, True)
    assert (plan["risk_amount"], plan["lots_risk_amount"], plan["conversion_rate"]) == (
        20.0,
        20.0,
        1.0,
    )
    assert plan["sizing_warnings"] == []

    # USD/JPY: 1 % of 10,000 USD = 100 USD; 0.5 x 100,000 / 150 = 333.33 USD per lot -> 0.30
    plan = await _plan(client, headers, _size(jpy, 150, 149.5, 10_000))
    assert plan["quantity"] == pytest.approx(30_000)  # 200 before the fix (150x too small)
    assert (plan["lots"], plan["lots_feasible"]) == (0.3, True)
    assert plan["conversion_rate"] == pytest.approx(1 / 150)
    assert plan["risk_amount"] == pytest.approx(100) and plan["risk_pct"] == pytest.approx(1)

    # EUR/USD: 1 % of 10,000 = 100 USD; 0.002 x 100,000 = 200 USD per lot -> 0.50
    plan = await _plan(client, headers, _size(eur, 1.085, 1.083, 10_000))
    assert (plan["lots"], plan["lots_feasible"]) == (0.5, True)

    # min lot: 1 % of 100 USD = 1 USD, but 0.01 lot of gold already risks 5 USD
    plan = await _plan(client, headers, _size(gold, 2400, 2395, 100))
    assert (plan["lots"], plan["lots_feasible"]) == (0.0, False)
    assert plan["sizing_warnings"] == ["below the minimum of 0.01 lots"]
    assert plan["quantity"] == pytest.approx(0.2)  # the old field is still there


async def test_position_size_currency_conversion(
    client: AsyncClient, session: AsyncSession, alice
) -> None:
    user, headers = alice
    gold = await _flat_market(session, "XAU/USD", "fxpro", 2400.0, **GOLD_SPECS)

    # the default profile is in USDT: counted as USD, and the plan says so
    plan = await _plan(client, headers, _size(gold, 2400, 2395, 2_000))
    assert (plan["lots"], plan["conversion_rate"]) == (0.04, 1.0)
    assert plan["sizing_warnings"] == ["USD, USDT and USDC treated as the same dollar (1:1)"]

    # a EUR account converts with the latest EUR/USD close: 1 USD = 1 / 1.08 EUR
    await _set_profile(session, user, quote_currency="EUR")
    await _flat_market(session, "EUR/USD", "twelvedata", 1.08)
    plan = await _plan(client, headers, _size(gold, 2400, 2395, 2_000))
    assert plan["conversion_rate"] == pytest.approx(1 / 1.08)
    # 20 EUR at risk, 500 USD = 462.96 EUR per lot -> 0.0432 -> 0.04
    assert (plan["lots"], plan["sizing_warnings"]) == (0.04, [])
    assert plan["risk_amount"] == pytest.approx(20)

    # no GBP market: never assumed 1
    await _set_profile(session, user, quote_currency="GBP")
    plan = await _plan(client, headers, _size(gold, 2400, 2395, 2_000))
    assert (plan["lots"], plan["lots_feasible"], plan["conversion_rate"]) == (0.0, False, None)
    assert "no conversion rate from USD" in plan["sizing_warnings"][0]

    # instruments without specs keep the old plan (lots null)
    plain = await _flat_market(session, "XAG/USD", "twelvedata", 30.0)
    plan = await _plan(client, headers, _size(plain, 30, 29, 2_000))
    assert (plan["lots"], plan["lots_feasible"], plan["sizing_warnings"]) == (None, None, [])


async def test_live_plans_have_lots(
    session: AsyncSession, session_factory, redis_client: Redis, alice, bob
) -> None:
    a, _ = alice
    b, _ = bob
    pair = await make_instrument(
        session, "USD/JPY", "twelvedata", MarketType.forex, **{**FX_SPECS, "quote_currency": "JPY"}
    )
    await _set_profile(session, a, config=PERCENT_RULES, account_size=5_000, quote_currency="USD")
    await _set_profile(session, b, config=PERCENT_RULES, account_size=5_000, quote_currency="GBP")
    await activate(session, a, pair, params=RSI1)
    await activate(session, b, pair, params=RSI1)
    await add_closes(session, pair.id, T0, DIP)

    result = await signal_engine.evaluate(
        session_factory, redis_client, Job(pair.id, Timeframe.m1, BAR)
    )
    assert (result.inserted, result.plans, result.errors) == (1, 2, [])
    plans = {p.user_id: p.plan for p in await _plans(session)}
    pa, pb = plans[a.id], plans[b.id]
    # entry 9.0 (USD/JPY at 9 in this test): 1 USD = 9 JPY, so 1 % of 5,000 USD = 450 JPY
    per_unit = 0.18 + (9.0 + 8.82) * 0.001
    assert pa["conversion_rate"] == pytest.approx(1 / 9)
    assert pa["quantity"] == pytest.approx(450 / per_unit, rel=1e-9)
    assert pa["risk_amount"] == pytest.approx(50) and pa["risk_pct"] == pytest.approx(1)
    assert (pa["lots"], pa["lots_feasible"]) == (0.02, True)  # 2,275 USD / 100,000
    # GBP account: no rate, flagged; the quantity is the unconverted one
    assert (pb["lots"], pb["lots_feasible"]) == (0.0, False)
    assert "no conversion rate" in pb["sizing_warnings"][0]
