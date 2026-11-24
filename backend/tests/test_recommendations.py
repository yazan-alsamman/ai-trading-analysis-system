"""Y17: recommendations. What is actionable now (active activations only, age, open outcome,
followed AI setups, stored plans, score and its order, the prior), the Wilson bound, the strategy
ranking (lower bound, insufficient history last, already_active, B12, backtests), the Redis
cache, the optional notification line and validation."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.ai import AIAlertFollow, AISetup, AISetupSize
from app.models.backtest import Backtest, BacktestStatus
from app.models.candle import Timeframe
from app.models.prediction import SignalOutcome
from app.models.risk import SignalPlan
from app.models.strategy import Signal, SignalSide, UserStrategy
from app.notifications import templates
from app.services import (
    prediction_service,
    recommendation_service,
    risk_service,
    signal_engine,
    strategy_resolver,
)
from app.services.recommendation_service import wilson_lower
from app.services.signal_engine import Job
from tests.custom_utils import make_custom, rsi_reversal_replica
from tests.market_utils import make_instrument
from tests.test_predictions import ai_setup
from tests.utils import bearer

NOW = datetime(2026, 3, 10, 12, 30, 20, tzinfo=UTC)
LAST_1H = datetime(2026, 3, 10, 11, 0, tzinfo=UTC)  # the last closed 1h bar at NOW
HISTORY = datetime(2026, 1, 5, tzinfo=UTC)
approx = pytest.approx


@pytest.fixture(autouse=True)
async def _no_cache(redis_client):
    async def clear():
        async for key in redis_client.scan_iter(f"{recommendation_service.CACHE_PREFIX}*"):
            await redis_client.delete(key)

    await clear()
    yield
    await clear()


@pytest.fixture
async def people(make_user):
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    return (alice, bearer(create_access_token(alice))), (bob, bearer(create_access_token(bob)))


@pytest.fixture
async def gold(session: AsyncSession):
    return await make_instrument(session, "XAU/USD", source="test", cost_per_unit=0.25)


async def sig(
    session: AsyncSession,
    instrument,
    bar_time: datetime,
    *,
    key: str = "ma_crossover",
    params_hash: str = "h1",
    timeframe: Timeframe = Timeframe.h1,
    side: str = "buy",
) -> Signal:
    row = Signal(
        instrument_id=instrument.id,
        timeframe=timeframe,
        strategy_key=key,
        params={},
        params_hash=params_hash,
        bar_time=bar_time,
        side=SignalSide(side),
        strength=0.6,
        price=2400.0,
        reason="test",
        details={},
        created_at=bar_time + timeframe.interval,
    )
    session.add(row)
    await session.commit()
    return row


async def history(
    session: AsyncSession,
    instrument,
    key: str,
    wins: int,
    losses: int,
    *,
    gaps: int = 0,
    timeframe: Timeframe = Timeframe.h1,
) -> None:
    """Resolved Y16 predictions of ``key`` on this market (old signals with outcome rows)."""
    results = [True] * wins + [False] * losses + [None] * gaps
    for i, correct in enumerate(results):
        row = await sig(
            session, instrument, HISTORY + timedelta(hours=i), key=key, params_hash=f"old{i}",
            timeframe=timeframe,
        )  # fmt: skip
        session.add(
            SignalOutcome(
                signal_id=row.id,
                horizon_bars=10,
                correct=correct,
                return_pct=(0.5 if correct else -0.3) if correct is not None else None,
                cost_per_unit=0.25,
                note="gap" if correct is None else None,
            )
        )
    await session.commit()


async def activate(session, user, instrument, key="ma_crossover", params_hash="h1", **kw):
    row = UserStrategy(
        user_id=user.id,
        strategy_key=key,
        params={},
        params_hash=params_hash,
        instrument_id=instrument.id,
        timeframe=kw.pop("timeframe", Timeframe.h1),
        **kw,
    )
    session.add(row)
    await session.commit()
    return row


# --- the numbers ---------------------------------------------------------------------------------


def test_wilson_lower_bound_by_hand() -> None:
    assert wilson_lower(0, 0) == 0.0
    # p = 0.5, n = 10: (0.5 + 0.19208 - 1.96 * sqrt(0.025 + 0.009604)) / 1.38416
    assert wilson_lower(5, 10) == approx(0.236590, abs=1e-6)
    # p = 0.58, n = 100: (0.58 + 0.019208 - 1.96 * sqrt(0.002436 + 0.00009604)) / 1.038416
    assert wilson_lower(58, 100) == approx(0.482063, abs=1e-6)
    assert wilson_lower(0, 10) == 0.0 and wilson_lower(10, 10) == approx(0.722460, abs=1e-6)


def test_score_formula() -> None:
    enough = recommendation_service.track_record({"tp_hit": 70, "sl_hit": 50, "resolved": 125})
    assert enough["hit_rate_lower"] == approx(0.493879, abs=1e-6)
    # the worked example of docs/recommendations.md: 0.4939 x 0.85 + 0.05
    value, reasons = recommendation_service.score(enough, 1, True)
    assert value == approx(round(0.493879 * 0.85 + 0.05, 4))
    assert reasons == [
        "track record: 70 of 120 hit (58%), 95% lower bound 49%",
        "1 bar old: x0.85",
        "risk profile complete: +0.05",
    ]
    thin = recommendation_service.track_record({"tp_hit": 15, "sl_hit": 4})
    value, reasons = recommendation_service.score(thin, 0, False)
    assert value == 0.5  # the neutral prior, however good 15 of 19 looks
    assert reasons[0] == "not enough history (19 of 20 decided): neutral prior 0.5"
    assert reasons[1:] == ["on the last closed bar", "risk profile uses defaults: no bonus"]
    empty = recommendation_service.track_record(None)
    assert (empty["decided"], empty["hit_rate"], empty["hit_rate_lower"]) == (0, None, None)


# --- GET /me/recommendations ---------------------------------------------------------------------


async def test_what_is_actionable_now(
    session: AsyncSession, redis_client, people, gold, monkeypatch: pytest.MonkeyPatch
) -> None:
    (alice, _), (bob, _) = people
    other = await make_instrument(session, "BTC/USDT")
    mine = await activate(session, alice, gold)
    await activate(session, alice, gold, key="rsi_reversal", params_hash="h2", is_active=False)
    await activate(session, bob, gold, key="macd_cross", params_hash="h3")
    await history(session, gold, "ma_crossover", 18, 12, gaps=3)  # lower bound 0.4232

    fresh = await sig(session, gold, LAST_1H)  # age 0, with a plan
    older = await sig(session, gold, LAST_1H - timedelta(hours=2))  # age 2, no plan
    edge = await sig(session, gold, LAST_1H - timedelta(hours=3))  # age 3: still in
    await sig(session, gold, LAST_1H - timedelta(hours=4))  # age 4: too old
    done = await sig(session, gold, LAST_1H - timedelta(hours=1))  # already resolved
    session.add(SignalOutcome(signal_id=done.id, horizon_bars=10, correct=True, cost_per_unit=0))
    await sig(session, gold, LAST_1H, key="rsi_reversal", params_hash="h2")  # inactive activation
    await sig(session, gold, LAST_1H, params_hash="zz")  # another setup of the same strategy
    await sig(session, gold, LAST_1H, key="macd_cross", params_hash="h3")  # bob's
    plan = {"side": "long", "entry": 2400.0, "stop": 2390.0, "lots": 0.03}
    session.add(SignalPlan(signal_id=fresh.id, user_id=alice.id, user_strategy_id=mine.id,
                           plan=plan))  # fmt: skip

    # AI: alice follows gold intraday; 15m bars, the last closed one ends at 12:30
    session.add(AIAlertFollow(user_id=alice.id, instrument_id=gold.id, profile="intraday"))
    t15 = datetime(2026, 3, 10, 12, 30, tzinfo=UTC)
    await ai_setup(session, gold, "arm-1", ["ARMED"], start=t15)  # age 0
    await ai_setup(session, gold, "act-1", ["ARMED", "ACTIVE"], start=t15 - timedelta(minutes=30))
    await ai_setup(session, gold, "closed-1", ["ARMED", "ACTIVE", "CLOSED"], realized_r=1.0)
    await ai_setup(session, other, "btc-1", ["ARMED"], start=t15)  # not followed
    await ai_setup(session, gold, "secret-1", ["ARMED"], start=t15)  # not readable (below)
    session.add(
        AISetupSize(
            setup_id="arm-1", user_id=alice.id, lots=0.04, risk_usd=20.0, margin_required=96.0,
            feasible=True, warnings=[], inputs={"account": {"currency": "USD"}}, source="local",
        )
    )  # fmt: skip
    await session.commit()
    original = strategy_resolver.readable_ai_setups
    monkeypatch.setattr(
        strategy_resolver,
        "readable_ai_setups",
        lambda user: AISetup.setup_id != "secret-1" if user.id == alice.id else original(user),
    )

    items = await recommendation_service.for_user(session, redis_client, alice, 50, now=NOW)
    by_id = {i["id"]: i for i in items}
    assert set(by_id) == {
        f"sig:{fresh.id}", f"sig:{older.id}", f"sig:{edge.id}", "ai:arm-1", "ai:act-1"
    }  # fmt: skip

    lower = wilson_lower(19, 31)  # the history and the resolved `done` signal
    f = by_id[f"sig:{fresh.id}"]
    assert (f["source"], f["symbol"], f["timeframe"], f["strategy_key"]) == (
        "strategy", "XAU/USD", "1h", "ma_crossover"
    )  # fmt: skip
    assert (f["age_bars"], f["user_strategy_id"], f["direction"]) == (0, mine.id, "buy")
    assert f["plan"] == plan and f["plan_missing_reason"] is None
    assert f["track_record"] == {
        "resolved": 31,
        "decided": 31,
        "hit_rate": 19 / 31,
        "hit_rate_lower": approx(lower),
        "mean_return_pct": approx((18 * 0.5 - 12 * 0.3) / 30),  # `done` has no return
        "mean_realized_r": None,
    }  # the 3 gaps are left out
    assert f["score"] == approx(round(lower, 4))
    o = by_id[f"sig:{older.id}"]
    assert (o["age_bars"], o["plan"], o["plan_missing_reason"]) == (2, None, "no_plan_stored")
    assert o["score"] == approx(round(lower * 0.85**2, 4))

    a = by_id["ai:arm-1"]
    assert (a["source"], a["timeframe"], a["strategy_key"], a["age_bars"]) == (
        "ai", "15m", "intraday", 0
    )  # fmt: skip
    assert a["plan"]["lots"] == 0.04 and a["plan"]["currency"] == "USD"
    assert a["track_record"]["decided"] == 1  # closed-1: still under the minimum
    assert a["score"] == 0.5 and "not enough history" in a["score_reasons"][0]  # the prior
    act = by_id["ai:act-1"]
    assert (act["age_bars"], act["plan"], act["plan_missing_reason"]) == (2, None, "not_sized_yet")
    assert act["score"] == approx(round(0.5 * 0.85**2, 4))

    # best score first, then newest
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)
    assert [i["id"] for i in items] == [
        "ai:arm-1", f"sig:{fresh.id}", "ai:act-1", f"sig:{older.id}", f"sig:{edge.id}"
    ]  # fmt: skip
    assert (
        await recommendation_service.for_user(session, redis_client, alice, 2, now=NOW)
        == (items[:2])
    )
    # bob only has his own activation's signal; he follows nothing
    bobs = await recommendation_service.for_user(session, redis_client, bob, 50, now=NOW)
    assert [i["strategy_key"] for i in bobs] == ["macd_cross"]


async def test_risk_bonus_and_private_strategy(
    session: AsyncSession, redis_client, people, gold
) -> None:
    (alice, _), (bob, _) = people
    profile = await risk_service.get_or_create(session, alice)
    profile.config = risk_service.validate_config(
        {**profile.config, "guards": {"max_daily_loss_pct": 3, "max_drawdown_pct": 10}}
    )
    await session.commit()
    assert recommendation_service.risk_profile_complete(profile)
    assert not recommendation_service.risk_profile_complete(None)
    fresh = await sig(session, gold, LAST_1H)
    await activate(session, alice, gold)
    [item] = await recommendation_service.for_user(session, redis_client, alice, 10, now=NOW)
    assert item["id"] == f"sig:{fresh.id}" and item["score"] == 0.55  # 0.5 prior + 0.05
    assert item["score_reasons"][-1] == "risk profile complete: +0.05"

    # bob activated alice's custom strategy while it was public; now it is private again (B12)
    custom = await make_custom(session, alice, "Mine", rsi_reversal_replica())
    await activate(session, bob, gold, key=custom.key, params_hash="c1")
    await sig(session, gold, LAST_1H, key=custom.key, params_hash="c1")
    assert await recommendation_service.for_user(session, redis_client, bob, 10, now=NOW) == []


async def test_endpoint(client: AsyncClient, session: AsyncSession, people, gold) -> None:
    (alice, ah), _ = people
    now = datetime.now(UTC)
    bar = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    row = await sig(session, gold, bar)
    await activate(session, alice, gold)
    res = await client.get("/api/v1/me/recommendations", headers=ah)
    assert res.status_code == 200, res.text
    [item] = res.json()
    assert item["id"] == f"sig:{row.id}" and item["age_bars"] in (0, 1)
    assert item["plan_missing_reason"] == "no_plan_stored" and 0 <= item["score"] <= 1
    detail = await client.get(f"/api/v1/predictions/{item['id']}", headers=ah)  # Y16 link
    assert detail.status_code == 200 and detail.json()["outcome"] == "open"
    url = "/api/v1/me/recommendations"
    assert (await client.get(url, params={"limit": 51}, headers=ah)).status_code == 422
    assert (await client.get(url)).status_code == 401


# --- GET /recommendations/strategies -------------------------------------------------------------


async def test_strategy_ranking(client: AsyncClient, session: AsyncSession, people, gold) -> None:
    (alice, ah), (bob, bh) = people
    mine = await make_custom(session, alice, "Mine", rsi_reversal_replica())  # private
    bobs = await make_custom(session, bob, "Bobs", rsi_reversal_replica())  # private
    await history(session, gold, "ma_crossover", 18, 12)  # 0.4232
    await history(session, gold, "rsi_reversal", 24, 6)  # 0.6269
    await history(session, gold, mine.key, 30, 10)  # 0.5981
    await history(session, gold, "macd_cross", 4, 1)  # insufficient (5 < 20)
    await history(session, gold, "ma_crossover", 40, 0, timeframe=Timeframe.m15)  # other tf
    await activate(session, alice, gold)  # ma_crossover, active
    await activate(session, alice, gold, key="rsi_reversal", params_hash="h2", is_active=False)
    for status, finished, ret in (
        (BacktestStatus.completed, NOW - timedelta(days=3), 4.0),
        (BacktestStatus.completed, NOW - timedelta(days=1), 7.5),  # the latest completed
        (BacktestStatus.failed, NOW, None),
    ):
        session.add(
            Backtest(
                user_id=alice.id, instrument_id=gold.id, timeframe=Timeframe.h1,
                strategy_key="ma_crossover", params={}, params_hash="h1", config={},
                range_start=NOW - timedelta(days=30), range_end=NOW, status=status,
                finished_at=finished,
                metrics={"total_return_pct": ret, "win_rate_pct": 55.0, "max_drawdown_pct": -6.2}
                if ret is not None else None,
            )
        )  # fmt: skip
    await session.commit()

    url = "/api/v1/recommendations/strategies"
    params = {"instrument_id": str(gold.id), "timeframe": "1h", "limit": 20}
    res = await client.get(url, params=params, headers=ah)
    assert res.status_code == 200, res.text
    ranked = res.json()
    keys = [e["strategy_key"] for e in ranked]
    assert keys[:4] == ["rsi_reversal", mine.key, "ma_crossover", "macd_cross"]
    assert bobs.key not in keys  # another user's private strategy (B12)
    assert [e["rank"] for e in ranked] == list(range(1, len(ranked) + 1))
    assert len(ranked) == 6 + 1  # the built-in catalog and alice's own custom strategy
    by_key = {e["strategy_key"]: e for e in ranked}
    assert by_key["rsi_reversal"]["hit_rate_lower"] == approx(wilson_lower(24, 30))
    assert by_key["rsi_reversal"]["insufficient_history"] is False
    assert by_key["macd_cross"]["insufficient_history"] is True  # last group, most history first
    assert all(e["insufficient_history"] for e in ranked[3:])
    assert by_key[mine.key]["kind"] == "custom" and by_key[mine.key]["name"] == "Mine"
    assert by_key["ma_crossover"]["already_active"] is True
    assert by_key["rsi_reversal"]["already_active"] is False  # inactive
    backtest = by_key["ma_crossover"]["backtest"]
    assert (backtest["total_return_pct"], backtest["win_rate_pct"]) == (7.5, 55.0)
    assert backtest["max_drawdown_pct"] == -6.2 and by_key["rsi_reversal"]["backtest"] is None
    assert by_key["ma_crossover"]["mean_return_pct"] == approx((18 * 0.5 - 12 * 0.3) / 30)

    # bob: same stats (served from the cache), his own already_active and strategies
    await activate(session, bob, gold, key="macd_cross", params_hash="h9")
    bob_ranked = (await client.get(url, params=params, headers=bh)).json()
    bob_keys = {e["strategy_key"]: e for e in bob_ranked}
    assert mine.key not in bob_keys and bobs.key in bob_keys
    assert bob_keys["macd_cross"]["already_active"] is True
    assert bob_keys["ma_crossover"]["already_active"] is False
    assert bob_keys["ma_crossover"]["backtest"] is None  # alice's backtest is hers
    assert (await client.get(url, params={**params, "limit": 2}, headers=ah)).json() == ranked[:2]


async def test_cache(
    session: AsyncSession, redis_client, people, gold, monkeypatch: pytest.MonkeyPatch
) -> None:
    (alice, _), (bob, _) = people
    await history(session, gold, "ma_crossover", 18, 12)
    calls = []
    original = prediction_service.track_records

    async def counting(s, pairs):
        calls.append(sorted(pairs))
        return await original(s, pairs)

    monkeypatch.setattr(prediction_service, "track_records", counting)
    first = await recommendation_service.strategies(
        session, redis_client, alice, gold.id, Timeframe.h1, 20
    )
    assert len(calls) == 1
    ttl = await redis_client.ttl(f"{recommendation_service.CACHE_PREFIX}{gold.id}:1h")
    assert 0 < ttl <= get_settings().recommendation_cache_seconds
    await activate(session, bob, gold)
    second = await recommendation_service.strategies(
        session, redis_client, bob, gold.id, Timeframe.h1, 20
    )
    assert len(calls) == 1  # served from Redis
    a = {e["strategy_key"]: e for e in first}
    b = {e["strategy_key"]: e for e in second}
    assert a["ma_crossover"]["hit_rate"] == b["ma_crossover"]["hit_rate"] == 0.6
    assert (a["ma_crossover"]["already_active"], b["ma_crossover"]["already_active"]) == (
        False,
        True,
    )  # fmt: skip  (never cached: per user)
    raw = await redis_client.get(f"{recommendation_service.CACHE_PREFIX}{gold.id}:1h")
    assert "already_active" not in raw and str(alice.id) not in raw
    await recommendation_service.strategies(session, redis_client, bob, gold.id, Timeframe.m15, 5)
    assert len(calls) == 2  # another timeframe: its own entry


async def test_validation(client: AsyncClient, people, gold) -> None:
    (_, ah), _ = people
    url = "/api/v1/recommendations/strategies"
    assert (await client.get(url, params={"timeframe": "1h"}, headers=ah)).status_code == 422
    assert (
        await client.get(url, params={"instrument_id": str(gold.id)}, headers=ah)
    ).status_code == 422
    bad_tf = {"instrument_id": str(gold.id), "timeframe": "2h"}
    assert (await client.get(url, params=bad_tf, headers=ah)).status_code == 422
    unknown = {"instrument_id": str(uuid.uuid4()), "timeframe": "1h"}
    assert (await client.get(url, params=unknown, headers=ah)).status_code == 404
    too_many = {"instrument_id": str(gold.id), "timeframe": "1h", "limit": 21}
    assert (await client.get(url, params=too_many, headers=ah)).status_code == 422
    assert (await client.get(url, params=unknown)).status_code == 401


# --- the notification line -----------------------------------------------------------------------


async def test_notification_line(
    session: AsyncSession, redis_client, people, monkeypatch: pytest.MonkeyPatch
) -> None:
    (alice, _), _ = people
    gold = await make_instrument(session, "XAU/USD", source="test", price_precision=2)
    await history(session, gold, "rsi_reversal", 70, 50, timeframe=Timeframe.m15)
    signal_id = uuid.uuid4()
    row = {
        "id": signal_id, "instrument_id": gold.id, "timeframe": Timeframe.m15,
        "strategy_key": "rsi_reversal", "params": {}, "params_hash": "h", "bar_time": NOW,
        "side": "buy", "strength": 1.0, "price": 2400.0, "reason": "r", "details": {},
    }  # fmt: skip
    activation = signal_engine.Activation(uuid.uuid4(), alice.id, "rsi_reversal", "h", True, None)
    by_user = {(signal_id, alice.id): [(activation, None)]}
    job = Job(gold.id, Timeframe.m15, NOW)

    async def notify() -> dict:
        result = signal_engine.EvaluationResult(job)
        prepared = await signal_engine._notifications(
            session, redis_client, job, [row], by_user, [], result
        )
        await session.rollback()  # nothing kept: the same dedup key again
        [note] = prepared.notifications
        return note["data"]

    off = await notify()  # the default: unchanged
    assert "track_record" not in off
    _, body_off = templates.inbox("signal", off, "en")
    assert "Track record" not in body_off

    monkeypatch.setattr(get_settings(), "recommendations_notify", True)
    on = await notify()
    assert on["track_record"]["decided"] == 120 and on["track_record"]["symbol"] == "XAU/USD"
    _, body_on = templates.inbox("signal", on, "en")
    line = (
        "Track record: this strategy hit 58% of 120 signals on XAU/USD 15m "
        "(past results, not a guarantee)"
    )
    assert body_on.splitlines() == [*body_off.splitlines()[:2], line, *body_off.splitlines()[2:]]
    _, ar = templates.inbox("signal", on, "ar")
    assert "أصابت هذه الاستراتيجية 58% من 120 إشارة على XAU/USD 15m" in ar

    # a strategy without a track record on this market: no line
    by_user_new = by_user  # (alice is expired by the rollbacks)
    fresh = {**row, "strategy_key": "macd_cross"}
    result = signal_engine.EvaluationResult(job)
    prepared = await signal_engine._notifications(
        session, redis_client, job, [fresh], by_user_new, [], result
    )
    await session.rollback()
    assert "track_record" not in prepared.notifications[0]["data"]
