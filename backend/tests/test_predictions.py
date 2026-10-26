"""Y16: prediction tracking. The strategy-signal resolver (cost rule, sells, open signals, data
gaps, weekends, idempotence, batches), the AI outcome mapping, the list, detail and stats
endpoints (filters, pagination, Brier and calibration), B12 isolation and the admin view."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.ai import AISetup, AISetupEvent, AISetupTake
from app.models.candle import Timeframe
from app.models.prediction import SignalOutcome
from app.models.strategy import Signal, SignalSide
from app.models.user import UserRole
from app.services import market_service, prediction_resolver, strategy_resolver
from app.services.seed_service import FXPRO_SESSION_CALENDAR
from app.tasks import celery_app
from tests.custom_utils import make_custom, rsi_reversal_replica
from tests.market_utils import make_instrument
from tests.strategy_utils import add_closes
from tests.utils import bearer

T0 = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 1, tzinfo=UTC)
URL = "/api/v1/predictions"
approx = pytest.approx


@pytest.fixture(autouse=True)
async def _no_resolver_status(redis_client):
    await redis_client.delete(prediction_resolver.STATUS_KEY)
    yield
    await redis_client.delete(prediction_resolver.STATUS_KEY)


async def signal(
    session: AsyncSession,
    instrument,
    bar_time: datetime,
    side: str,
    price: float,
    *,
    key: str = "ma_crossover",
    timeframe: Timeframe = Timeframe.m1,
    created_at: datetime | None = None,
) -> Signal:
    row = Signal(
        instrument_id=instrument.id,
        timeframe=timeframe,
        strategy_key=key,
        params={},
        params_hash=uuid.uuid4().hex,
        bar_time=bar_time,
        side=SignalSide(side),
        strength=0.7,
        price=price,
        reason="test",
        details={},
        created_at=created_at or bar_time + timedelta(minutes=1),
    )
    session.add(row)
    await session.commit()
    return row


async def outcomes(session: AsyncSession) -> dict[uuid.UUID, SignalOutcome]:
    rows = await session.scalars(select(SignalOutcome).execution_options(populate_existing=True))
    return {r.signal_id: r for r in rows}


async def resolve(session: AsyncSession, **kw) -> prediction_resolver.RunResult:
    kw.setdefault("now", LATER)
    kw.setdefault("horizon", 3)
    return await prediction_resolver.resolve_signals(session, **kw)


# --- the resolver --------------------------------------------------------------------------------


@pytest.fixture
async def gold(session: AsyncSession):
    """A 24/7 gold with Fadi's fixed cost (0.25 per oz) and 1m closes by hand."""
    gold = await make_instrument(session, "XAU/USD", source="test", cost_per_unit=0.25)
    closes = [2400.00, 2400.30, 2400.10, 2400.20, 2401.00, 2402.00, 2400.50, 2399.00]
    await add_closes(session, gold.id, T0, closes)  # 12:00 ... 12:07
    return gold


async def test_cost_rule_buy_and_sell(session: AsyncSession, gold) -> None:
    small = await signal(session, gold, T0, "buy", 2400.00)  # bars 1-3: exit 2400.20
    enough = await signal(session, gold, T0 + timedelta(minutes=3), "buy", 2400.20)  # exit 2400.50
    short = await signal(session, gold, T0 + timedelta(minutes=4), "sell", 2401.00)  # exit 2399.00
    pending = await signal(session, gold, T0 + timedelta(minutes=5), "buy", 2402.00)  # needs 12:08

    result = await resolve(session)
    assert (result.resolved, result.gaps) == (3, 0)
    rows = await outcomes(session)
    assert pending.id not in rows  # its horizon is not closed yet: open

    a = rows[small.id]  # up 0.20 < the 0.25 cost: not correct
    assert (a.horizon_bars, a.exit_ts, a.exit_price) == (3, T0 + timedelta(minutes=3), 2400.20)
    assert a.return_pct == approx(0.20 / 2400 * 100) and a.correct is False
    assert a.cost_per_unit == 0.25 and a.note is None
    # add_closes wicks: high = max(open, close) + 0.1, low = min(open, close) - 0.1
    assert a.mfe_pct == approx(0.40 / 2400 * 100)  # 2400.40 on bar 1
    assert a.mae_pct == approx(-0.10 / 2400 * 100)  # 2399.90 on bar 1

    b = rows[enough.id]  # up 0.30 > 0.25
    assert b.exit_price == 2400.50 and b.correct is True
    assert b.return_pct == approx(0.30 / 2400.20 * 100)

    c = rows[short.id]  # a sell, down 2.00
    assert c.exit_price == 2399.00 and c.correct is True
    assert c.return_pct == approx(2.0 / 2401 * 100)  # signed in its direction
    assert c.mfe_pct == approx((2401 - 2398.9) / 2401 * 100)  # low 2398.90 on bar 7
    assert c.mae_pct == approx((2401 - 2402.1) / 2401 * 100)  # high 2402.10 on bar 5


async def test_without_a_cost_any_rise_is_correct(session: AsyncSession) -> None:
    btc = await make_instrument(session, "BTC/USDT")
    await add_closes(session, btc.id, T0, [100.0, 100.1, 100.0, 100.01])
    row = await signal(session, btc, T0, "buy", 100.0)
    await resolve(session)
    out = (await outcomes(session))[row.id]
    assert out.cost_per_unit == 0.0 and out.correct is True  # +0.01 > 0


async def test_rerun_does_nothing_and_batches(session: AsyncSession, gold) -> None:
    rows = [await signal(session, gold, T0 + timedelta(minutes=m), "buy", 2400.0) for m in range(5)]
    assert (await resolve(session, batch=2)).resolved == 2
    assert set(await outcomes(session)) == {rows[0].id, rows[1].id}  # oldest first
    assert (await resolve(session, batch=2)).resolved == 2
    assert (await resolve(session, batch=2)).resolved == 1
    assert (await resolve(session, batch=2)).resolved == 0  # done: nothing more
    first = (await outcomes(session))[rows[0].id].resolved_at
    assert (await resolve(session)).resolved == 0
    assert len(await outcomes(session)) == 5
    assert (await outcomes(session))[rows[0].id].resolved_at == first  # never rewritten


async def test_overlapping_runs_insert_nothing_twice(
    session: AsyncSession, gold, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = await signal(session, gold, T0, "buy", 2400.0)
    assert (await resolve(session)).resolved == 1
    before = (await outcomes(session))[row.id].resolved_at
    # a second run that picked the same signal before the first one committed
    monkeypatch.setattr(prediction_resolver, "_no_outcome", lambda: Signal.id.is_not(None))
    assert (await resolve(session)).resolved == 0  # ON CONFLICT DO NOTHING
    assert (await outcomes(session))[row.id].resolved_at == before


async def test_a_gap_is_resolved_without_a_result(session: AsyncSession) -> None:
    eth = await make_instrument(session, "ETH/USDT")
    candles = await add_closes(session, eth.id, T0, [10.0, 10.5, 10.6, 10.7])
    await session.execute(
        delete(market_service._RELATIONS[Timeframe.m1]).where(
            market_service._RELATIONS[Timeframe.m1].c.ts == candles[2].ts
        )
    )
    await session.commit()
    row = await signal(session, eth, T0, "buy", 10.0)
    result = await resolve(session)
    assert (result.resolved, result.gaps) == (1, 1)
    out = (await outcomes(session))[row.id]
    assert out.correct is None and out.exit_price is None and out.return_pct is None
    assert out.note == "gap: 1 of 3 bars missing (first 2026-03-02T12:02:00Z)"


async def test_a_weekend_is_not_a_gap(session: AsyncSession) -> None:
    """FxPro hours: closed Fri 16:55 to Sun 18:00 New York (20:55 to 22:00 UTC in October)."""
    fx = await make_instrument(
        session, "XAU/USD", source="fxpro", session_calendar=FXPRO_SESSION_CALENDAR,
        cost_per_unit=0.25,
    )  # fmt: skip
    friday = datetime(2026, 10, 23, 20, 52, tzinfo=UTC)
    await add_closes(session, fx.id, friday, [2400.0, 2400.0, 2401.0])  # 20:52 ... 20:54
    row = await signal(session, fx, friday + timedelta(minutes=1), "buy", 2400.0)  # 20:53

    saturday = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    result = await resolve(session, now=saturday)
    assert (result.resolved, result.waiting) == (0, 1)  # the market is closed: still open

    sunday = datetime(2026, 10, 25, 22, 0, tzinfo=UTC)
    await add_closes(session, fx.id, sunday, [2401.0, 2402.0, 2402.5])  # 22:00 ... 22:02
    assert (await resolve(session, now=sunday + timedelta(hours=1))).resolved == 1
    out = (await outcomes(session))[row.id]
    # the horizon: 20:54 (Fri), 22:00 and 22:01 (Sun): no gap
    assert out.exit_ts == sunday + timedelta(minutes=1) and out.exit_price == 2402.0
    assert out.correct is True and out.note is None


async def test_status_in_redis_and_beat(
    session_factory, redis_client, session, gold, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "prediction_horizon_bars", 3)
    await signal(session, gold, T0, "buy", 2400.0)
    result = await prediction_resolver.run(session_factory, redis_client, now=LATER)
    assert result.resolved == 1
    state = await prediction_resolver.read_status(redis_client)
    assert state["last_status"] == "ok" and state["last_resolved"] == 1
    assert state["horizon_bars"] == 3

    entry = celery_app.conf.beat_schedule["predictions-resolve-signals"]
    assert entry["task"] == "predictions.resolve_signals"
    assert entry["schedule"] == timedelta(seconds=300)
    route = celery_app.amqp.router.route({}, "predictions.resolve_signals")
    assert route["queue"].name == "maintenance"  # off the live worker


async def test_horizon_is_stored_per_row(session: AsyncSession, gold) -> None:
    first = await signal(session, gold, T0, "buy", 2400.0)
    await resolve(session, horizon=3)
    second = await signal(session, gold, T0 + timedelta(minutes=1), "buy", 2400.3)
    await resolve(session, horizon=2)  # a later change of the setting
    rows = await outcomes(session)
    assert (rows[first.id].horizon_bars, rows[second.id].horizon_bars) == (3, 2)
    assert rows[first.id].exit_ts == T0 + timedelta(minutes=3)  # history unchanged


# --- AI setups -----------------------------------------------------------------------------------


async def ai_setup(
    session: AsyncSession,
    instrument,
    setup_id: str,
    path: list[str],
    *,
    realized_r: float | None = None,
    probability: float | None = None,
    start: datetime = T0,
) -> AISetup:
    """A setup that went through ``path`` (one event per state, a minute apart)."""
    row = AISetup(
        setup_id=setup_id,
        instrument_id=instrument.id,
        profile="intraday",
        direction="buy",
        state=path[-1],
        entry=2400.0,
        sl=2395.0,
        tp=2410.0,
        r_multiple=2.0,
        probability=probability,
        realized_r=realized_r,
        last_payload={},
        model_version=None,
        first_request_id="req-1",
        last_request_id="req-1",
        created_at=start,
        updated_at=start + timedelta(minutes=len(path)),
    )
    session.add(row)
    previous = None
    for i, state in enumerate(path):
        session.add(
            AISetupEvent(
                setup_id=setup_id,
                from_state=previous,
                to_state=state,
                at=start + timedelta(minutes=i),
                realized_r=realized_r if state == "CLOSED" else None,
                request_id="req-1",
            )
        )
        previous = state
    await session.commit()
    return row


@pytest.fixture
async def people(make_user):
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    return (alice, bearer(create_access_token(alice))), (bob, bearer(create_access_token(bob)))


async def get(client: AsyncClient, headers, url: str = URL, **params) -> dict:
    res = await client.get(url, params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


async def test_ai_outcome_mapping(
    client: AsyncClient, session: AsyncSession, people, caplog
) -> None:
    (alice, ah), (_, bh) = people
    gold = await make_instrument(session, "XAU/USD", source="test")
    paths = {
        "armed": (["ARMED"], None, "open"),
        "active": (["DEVELOPING", "ARMED", "ACTIVE"], None, "open"),
        "win": (["ARMED", "ACTIVE", "CLOSED"], 1.8, "tp_hit"),
        "loss": (["ARMED", "ACTIVE", "CLOSED"], -1.0, "sl_hit"),
        "flat": (["ARMED", "ACTIVE", "CLOSED"], 0.0, "sl_hit"),
        "expired": (["ARMED", "EXPIRED"], None, "expired"),
        "untriggered": (["DEVELOPING", "ARMED", "INVALIDATED"], None, "expired"),
        "odd": (["ARMED", "ACTIVE", "INVALIDATED"], None, "expired"),  # not expected: a warning
    }
    for i, (setup_id, (path, r, _)) in enumerate(paths.items()):
        await ai_setup(session, gold, setup_id, path, realized_r=r, start=T0 + timedelta(hours=i))
    await ai_setup(session, gold, "never", ["DEVELOPING"])  # not published
    await ai_setup(session, gold, "dropped", ["DEVELOPING", "INVALIDATED"])  # not published
    session.add(AISetupTake(setup_id="win", user_id=alice.id, lots=0.1, risk_amount=20))
    await session.commit()

    body = await get(client, ah, source="ai", limit=50)
    assert body["total"] == len(paths)
    got = {i["id"]: i for i in body["items"]}
    assert {k: got[f"ai:{k}"]["outcome"] for k in paths} == {k: v[2] for k, v in paths.items()}
    assert [i["id"] for i in body["items"]][:2] == ["ai:odd", "ai:untriggered"]  # newest first
    assert "AI setup odd was INVALIDATED after ACTIVE" in caplog.text

    win = got["ai:win"]
    assert (win["source"], win["symbol"], win["timeframe"], win["strategy_key"]) == (
        "ai", "XAU/USD", "15m", "intraday"
    )  # fmt: skip
    assert (win["realized_r"], win["risk_reward"], win["probability"]) == (1.8, 2.0, None)
    assert win["taken_by_user"] is True and got["ai:loss"]["taken_by_user"] is False
    assert win["generated_at"] == "2026-03-02T14:00:00Z"  # the ARMED event
    assert win["resolved_at"] == "2026-03-02T14:02:00Z"  # the CLOSED event
    assert got["ai:active"]["generated_at"] == "2026-03-02T13:01:00Z"  # born DEVELOPING
    assert got["ai:active"]["resolved_at"] is None
    bob_view = await get(client, bh, source="ai", outcome="tp_hit")
    assert [(i["id"], i["taken_by_user"]) for i in bob_view["items"]] == [("ai:win", False)]

    detail = await get(client, ah, f"{URL}/ai:win")
    assert detail["ai"]["state"] == "CLOSED" and detail["ai"]["entry"] == 2400.0
    assert [e["to_state"] for e in detail["ai"]["events"]] == ["ARMED", "ACTIVE", "CLOSED"]
    assert detail["ai"]["events"][-1]["realized_r"] == 1.8 and detail["signal"] is None

    stats = await get(client, ah, f"{URL}/stats", source="ai")
    assert (stats["total"], stats["open"], stats["resolved"]) == (8, 2, 6)
    assert (stats["tp_hit_count"], stats["sl_hit_count"], stats["expired_count"]) == (1, 2, 3)
    assert stats["hit_rate"] == approx(1 / 3)  # expired rows are not in the rate
    assert stats["mean_realized_r"] == approx((1.8 - 1.0 + 0.0) / 3)
    assert stats["mean_return_pct"] is None
    # v1: no probabilities, so nothing is invented
    assert (stats["with_probability"], stats["brier_score"], stats["calibration"]) == (0, None, [])
    assert stats["by_strategy"] == [
        {"source": "ai", "strategy_key": "intraday", "total": 8, "resolved": 6,
         "hit_rate": approx(1 / 3)},
    ]  # fmt: skip


async def test_brier_and_calibration_by_hand(
    client: AsyncClient, session: AsyncSession, people
) -> None:
    (_, ah), _ = people
    gold = await make_instrument(session, "XAU/USD", source="test")
    closed = ["ARMED", "ACTIVE", "CLOSED"]
    for i, (p, r) in enumerate([(0.8, 2.0), (0.6, -1.0), (0.65, 1.5), (0.15, -1.0)]):
        await ai_setup(session, gold, f"p{i}", closed, realized_r=r, probability=p,
                       start=T0 + timedelta(hours=i))  # fmt: skip
    await ai_setup(session, gold, "p-open", ["ARMED"], probability=0.9)  # open: not counted
    await ai_setup(session, gold, "p-exp", ["ARMED", "EXPIRED"], probability=0.3)  # expired

    stats = await get(client, ah, f"{URL}/stats")
    assert stats["with_probability"] == 4
    assert stats["mean_predicted"] == approx((0.8 + 0.6 + 0.65 + 0.15) / 4)
    # (0.8-1)^2 + (0.6-0)^2 + (0.65-1)^2 + (0.15-0)^2 = 0.04 + 0.36 + 0.1225 + 0.0225
    assert stats["brier_score"] == approx(0.545 / 4)
    assert stats["calibration"] == [
        {"from": 0.1, "to": 0.2, "count": 1, "mean_predicted": approx(0.15),
         "observed_rate": 0.0},
        {"from": 0.6, "to": 0.7, "count": 2, "mean_predicted": approx(0.625),
         "observed_rate": 0.5},
        {"from": 0.8, "to": 0.9, "count": 1, "mean_predicted": approx(0.8),
         "observed_rate": 1.0},
    ]  # fmt: skip
    assert stats["hit_rate"] == 0.5


# --- the list, filters, stats over signals -------------------------------------------------------


async def test_signals_in_the_list_and_stats(
    client: AsyncClient, session: AsyncSession, people, gold
) -> None:
    (_, ah), _ = people
    eth = await make_instrument(session, "ETH/USDT")
    await add_closes(session, eth.id, T0, [10.0, 10.5, 10.6, 10.7])
    ok = await signal(session, gold, T0 + timedelta(minutes=3), "buy", 2400.20)  # correct
    small = await signal(session, gold, T0, "buy", 2400.00, key="rsi_reversal")  # cost: wrong
    still = await signal(session, gold, T0 + timedelta(minutes=5), "buy", 2402.0)  # open
    gap = await signal(session, eth, T0, "buy", 10.0)
    await session.execute(
        delete(market_service._RELATIONS[Timeframe.m1]).where(
            market_service._RELATIONS[Timeframe.m1].c.instrument_id == eth.id,
            market_service._RELATIONS[Timeframe.m1].c.ts == T0 + timedelta(minutes=2),
        )
    )
    await session.commit()
    await resolve(session)

    body = await get(client, ah, source="strategy")
    assert body["total"] == 4
    got = {i["id"]: i for i in body["items"]}
    assert got[f"sig:{ok.id}"]["outcome"] == "tp_hit"
    assert got[f"sig:{small.id}"]["outcome"] == "sl_hit"
    assert got[f"sig:{still.id}"]["outcome"] == "open"
    assert got[f"sig:{still.id}"]["resolved_at"] is None
    assert got[f"sig:{gap.id}"]["outcome"] == "expired"
    assert got[f"sig:{gap.id}"]["note"].startswith("gap: 1 of 3")
    item = got[f"sig:{ok.id}"]
    assert (item["timeframe"], item["strategy_key"], item["direction"]) == (
        "1m",
        "ma_crossover",
        "buy",
    )
    assert item["probability"] is None and item["realized_r"] is None  # strength is no probability
    assert item["return_pct"] == approx(0.30 / 2400.20 * 100)

    stats = await get(client, ah, f"{URL}/stats", source="strategy")
    # the gap is left out of everything
    assert (stats["total"], stats["resolved"], stats["open"]) == (3, 2, 1)
    assert (stats["excluded_count"], stats["expired_count"]) == (1, 0)
    assert stats["hit_rate"] == 0.5 and stats["mean_realized_r"] is None
    assert stats["mean_return_pct"] == approx((0.30 / 2400.20 + 0.20 / 2400) * 100 / 2)
    assert stats["by_strategy"] == [
        {"source": "strategy", "strategy_key": "ma_crossover", "total": 2, "resolved": 1,
         "hit_rate": 1.0},
        {"source": "strategy", "strategy_key": "rsi_reversal", "total": 1, "resolved": 1,
         "hit_rate": 0.0},
    ]  # fmt: skip

    detail = await get(client, ah, f"{URL}/sig:{ok.id}")
    out = detail["signal"]["outcome"]
    assert detail["signal"]["price"] == 2400.20 and detail["ai"] is None
    assert (out["horizon_bars"], out["exit_price"], out["correct"]) == (3, 2400.5, True)
    assert out["mfe_pct"] == approx((2402.1 - 2400.2) / 2400.2 * 100)
    assert out["cost_per_unit"] == 0.25
    assert (await get(client, ah, f"{URL}/sig:{still.id}"))["signal"]["outcome"] is None


async def test_filters_pagination_and_404(
    client: AsyncClient, session: AsyncSession, people, gold
) -> None:
    (_, ah), _ = people
    btc = await make_instrument(session, "BTC/USDT")
    for m in range(5):
        await signal(session, gold, T0 + timedelta(minutes=m), "buy", 2400.0)
    await signal(session, btc, T0, "sell", 100.0, key="rsi_reversal", timeframe=Timeframe.h1)
    await ai_setup(session, gold, "xau-1", ["ARMED"], start=T0 + timedelta(days=1))
    await resolve(session)

    everything = await get(client, ah, limit=200)
    assert everything["total"] == 7 and everything["items"][0]["id"] == "ai:xau-1"
    pages = [await get(client, ah, limit=3, offset=o) for o in (0, 3, 6)]
    assert [len(p["items"]) for p in pages] == [3, 3, 1]
    assert [i["id"] for p in pages for i in p["items"]] == [i["id"] for i in everything["items"]]

    async def total(**params) -> int:
        return (await get(client, ah, **params))["total"]

    assert await total(instrument_id=str(btc.id)) == 1
    assert await total(timeframe="1h") == 1
    assert await total(timeframe="15m") == 1  # the AI setup
    assert await total(strategy_key="ma_crossover") == 5
    assert await total(strategy_key="intraday") == 1
    assert await total(profile="intraday") == 1
    assert await total(profile="intraday", source="strategy") == 0
    assert await total(outcome="open") == 2  # the AI setup and the 1h signal (no 1h candles)
    assert await total(**{"from": "2026-03-02T12:03:00Z", "to": "2026-03-02T12:05:00Z"}) == 3
    assert (await client.get(URL, params={"limit": 201}, headers=ah)).status_code == 422
    assert (await client.get(URL, params={"outcome": "won"}, headers=ah)).status_code == 422

    for unknown in ("ai:nope", f"sig:{uuid.uuid4()}", "sig:not-a-uuid", "xyz", "ai:" + "x" * 200):
        res = await client.get(f"{URL}/{unknown}", headers=ah)
        assert res.status_code in (404, 422), unknown
        assert res.status_code == 404 or len(unknown) > 140
    assert (await client.get(URL)).status_code == 401


# --- B12 -----------------------------------------------------------------------------------------


async def test_isolation(
    client: AsyncClient, session: AsyncSession, people, gold, make_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    (alice, ah), (_, bh) = people
    admin = await make_user("root@example.com", role=UserRole.admin)
    rh = bearer(create_access_token(admin))
    private = await make_custom(session, alice, "Mine", rsi_reversal_replica())
    hidden = await signal(session, gold, T0, "buy", 2400.0, key=private.key)
    shown = await signal(session, gold, T0 + timedelta(minutes=3), "buy", 2400.2)
    await ai_setup(session, gold, "visible-1", ["ARMED", "EXPIRED"])
    await ai_setup(session, gold, "secret-1", ["ARMED", "ACTIVE", "CLOSED"], realized_r=2.0)
    await resolve(session)
    # an AI setup bob may not read (the B12 hook; every setup is readable in v1)
    original = strategy_resolver.readable_ai_setups

    def readable(user):
        if user.id == alice.id or user.role == UserRole.admin:
            return original(user)
        return AISetup.setup_id != "secret-1"

    monkeypatch.setattr(strategy_resolver, "readable_ai_setups", readable)

    async def ids(headers) -> set[str]:
        return {i["id"] for i in (await get(client, headers, limit=200))["items"]}

    everything = {f"sig:{hidden.id}", f"sig:{shown.id}", "ai:visible-1", "ai:secret-1"}
    assert await ids(ah) == everything
    assert await ids(rh) == everything  # admins see every signal
    assert await ids(bh) == {f"sig:{shown.id}", "ai:visible-1"}
    assert (await get(client, bh))["total"] == 2
    for gone in (f"sig:{hidden.id}", "ai:secret-1"):
        assert (await client.get(f"{URL}/{gone}", headers=bh)).status_code == 404
        assert (await client.get(f"{URL}/{gone}", headers=ah)).status_code == 200

    bob_stats = await get(client, bh, f"{URL}/stats")
    assert (bob_stats["total"], bob_stats["tp_hit_count"], bob_stats["expired_count"]) == (2, 1, 1)
    assert {s["strategy_key"] for s in bob_stats["by_strategy"]} == {"ma_crossover", "intraday"}
    alice_stats = await get(client, ah, f"{URL}/stats")
    assert alice_stats["total"] == 4
    assert private.key in {s["strategy_key"] for s in alice_stats["by_strategy"]}
    filtered = await get(client, bh, f"{URL}/stats", strategy_key=private.key)
    assert filtered["total"] == 0 and filtered["by_strategy"] == []


# --- admin ---------------------------------------------------------------------------------------


async def test_admin_resolver_status(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client, people, gold,
    make_user, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    (_, ah), _ = people
    admin = await make_user("root@example.com", role=UserRole.admin)
    rh = bearer(create_access_token(admin))
    url = "/api/v1/admin/predictions/resolver"
    assert (await client.get(url, headers=ah)).status_code == 403

    empty = await get(client, rh, url)
    assert (empty["last_run_at"], empty["backlog"], empty["resolved_total"]) == (None, 0, 0)
    assert (empty["horizon_bars"], empty["batch"], empty["interval_seconds"]) == (10, 500, 300)

    await signal(session, gold, T0 - timedelta(minutes=20), "buy", 2400.0)  # no candles: a gap
    await signal(session, gold, T0 + timedelta(minutes=6), "buy", 2400.5)  # not due
    await prediction_resolver.run(session_factory, redis_client, now=LATER)
    body = await get(client, rh, url)
    assert body["last_status"] == "ok" and body["last_error"] is None
    assert (body["last_resolved"], body["last_gaps"]) == (1, 1)
    assert (body["backlog"], body["resolved_total"]) == (1, 1)
    assert body["last_run_at"] == "2026-04-01T00:00:00Z"

    async def broken(*_a, **_k):
        raise RuntimeError("database went away")

    monkeypatch.setattr(prediction_resolver, "resolve_signals", broken)
    with pytest.raises(RuntimeError):
        await prediction_resolver.run(session_factory, redis_client, now=LATER)
    body = await get(client, rh, url)
    assert body["last_status"] == "error"
    assert body["last_error"] == "RuntimeError: database went away"
    assert body["last_resolved"] == 1  # the last good run stays visible
    assert await session.scalar(select(func.count()).select_from(SignalOutcome)) == 1
