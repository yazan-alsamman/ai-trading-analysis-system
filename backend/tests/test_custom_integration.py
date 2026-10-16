"""Custom strategies used like global ones: the resolver's access rules, preview, backtests
(snapshot in the config), /me/strategies activations and the live signal engine (edits,
deletion, visibility, dedup across users)."""

import random
import uuid
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
import trading_strategies as ts
from fastapi import HTTPException
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.backtest import BacktestStatus
from app.models.candle import Timeframe
from app.models.custom_strategy import Visibility
from app.models.strategy import Signal, UserStrategy
from app.models.user import UserRole
from app.realtime.topics import signals_topic, user_topic
from app.schemas.custom_strategies import CustomStrategyReplace, CustomStrategyUpdate
from app.services import (
    backtest_service,
    custom_strategy_service,
    market_service,
    signal_engine,
    strategy_resolver,
)
from app.services.seed_service import generate_demo_candles
from app.services.signal_engine import Job
from tests.custom_utils import (
    MA_REPLICA,
    MINE,
    composite,
    create,
    make_custom,
    rsi_below,
    rsi_reversal_replica,
)
from tests.market_utils import make_instrument
from tests.strategy_utils import RSI1, activate, add_closes
from tests.test_signal_engine import Listener
from tests.utils import bearer

END = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
MINUTES = 3_000
T0 = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
# RSI(1): nan 0 0 100 0 100 -> crosses 30 upward on bars 3 and 5
CLOSES = [10.0, 9.0, 8.0, 9.0, 8.0, 9.0]
BAR3, BAR5 = T0 + timedelta(minutes=3), T0 + timedelta(minutes=5)
RSI1_REPLICA = rsi_reversal_replica(length=1)


@pytest.fixture
async def instrument(session: AsyncSession):
    instrument = await make_instrument(session, price_precision=2, quantity_precision=4)
    candles = generate_demo_candles(instrument, minutes=MINUTES, end=END, rng=random.Random(5))
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()
    return instrument


@pytest.fixture
async def alice(make_user):
    user = await make_user("alice@example.com", role=UserRole.analyst)
    return user, bearer(create_access_token(user))


@pytest.fixture
async def bob(make_user):
    user = await make_user("bob@example.com")
    return user, bearer(create_access_token(user))


# --- resolver ---------------------------------------------------------------------------------


async def test_resolver_access(session: AsyncSession, alice, bob) -> None:
    a, _ = alice
    b, _ = bob
    private = await make_custom(session, a, "Private", MA_REPLICA)
    public = await make_custom(session, a, "Public", rsi_below(30), visibility=Visibility.public)

    own = await strategy_resolver.get(session, private.key, a)
    assert own.key == private.key and own.params == {} and own.custom.id == private.id
    assert own.params_hash == private.definition_hash and own.strategy.title == "Private"
    assert own.snapshot["kind"] == "builder"
    assert (await strategy_resolver.get(session, public.key, b)).custom.id == public.id
    for key in (private.key, f"custom:{uuid.uuid4()}", "custom:not-a-uuid", "custom:"):
        with pytest.raises(HTTPException) as exc:
            await strategy_resolver.get(session, key, b)
        assert exc.value.status_code == 404, key
    with pytest.raises(HTTPException) as exc:
        await strategy_resolver.get(session, private.key, a, {"length": 3})
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        await strategy_resolver.get(session, "nope", a)
    assert exc.value.status_code == 422
    glob = await strategy_resolver.get(session, "rsi_reversal", b, {"length": 3})
    assert glob.params_hash == ts.params_hash("rsi_reversal", {"length": 3}) and glob.custom is None

    await custom_strategy_service.delete(session, a, public.id)
    with pytest.raises(HTTPException) as exc:
        await strategy_resolver.get(session, public.key, b)
    assert exc.value.status_code == 404


async def test_composite_members_use_the_owners_access(session: AsyncSession, alice, bob) -> None:
    a, _ = alice
    b, _ = bob
    shared = await make_custom(session, a, "Shared", rsi_below(30), visibility=Visibility.public)
    secret = await make_custom(session, a, "Secret", MA_REPLICA)
    combo = await make_custom(session, b, "Bob's", composite("macd_cross", shared.key))
    resolved = await strategy_resolver.get(session, combo.key, b)
    assert set(resolved.snapshot["members"]) == {shared.key}
    with pytest.raises(HTTPException) as exc:  # Bob cannot use Alice's private one
        await make_custom(session, b, "Nope", composite("macd_cross", secret.key))
    assert exc.value.status_code == 422
    assert "unknown or inaccessible" in exc.value.detail[0]["msg"]


# --- preview ----------------------------------------------------------------------------------


async def _preview(client, headers, key, instrument, **extra):
    body = {"instrument_id": str(instrument.id), "timeframe": "1m", "limit": 5000, **extra}
    return await client.post(f"/api/v1/strategies/{key}/preview", json=body, headers=headers)


async def test_preview_custom_equals_global_and_library(
    client: AsyncClient, session: AsyncSession, alice, instrument
) -> None:
    _, headers = alice
    replica = await create(client, headers, "EMA replica", MA_REPLICA)
    custom = await _preview(client, headers, replica["key"], instrument)
    glob = await _preview(client, headers, "ma_crossover", instrument)
    assert custom.status_code == glob.status_code == 200, custom.text
    data = custom.json()
    assert data["strategy_key"] == replica["key"] and data["params"] == {}
    assert data["params_hash"] == replica["definition_hash"]
    times = [(s["time"], s["side"]) for s in data["signals"]]
    assert times == [(s["time"], s["side"]) for s in glob.json()["signals"]] and len(times) > 20
    assert {s["reason"] for s in data["signals"]} == {"builder_buy", "builder_sell"}
    assert [i["name"] for i in data["indicators"]] == ["ema", "ema"]

    rows = await market_service.get_candles(session, instrument.id, Timeframe.m1, limit=5000)
    df = pd.DataFrame(
        {k: [getattr(r, k) for r in rows] for k in ("open", "high", "low", "close", "volume")},
        index=pd.DatetimeIndex([r.ts for r in rows]),
    )
    out = ts.BuilderStrategy(MA_REPLICA).generate(df)
    expected = [int(t.timestamp()) for t, s in out["signal"].items() if s != 0]
    assert [t for t, _ in times] == expected
    assert [s["details"] for s in data["signals"]] == [d for d in out["details"] if d is not None]


async def test_preview_access_and_params(client: AsyncClient, alice, bob, instrument) -> None:
    _, a_headers = alice
    _, b_headers = bob
    private = await create(client, a_headers, "Private", MA_REPLICA)
    public = await create(client, a_headers, "Public", rsi_below(45), visibility="public")
    assert (await _preview(client, b_headers, private["key"], instrument)).status_code == 404
    res = await _preview(client, b_headers, public["key"], instrument, limit=300)
    assert res.status_code == 200 and res.json()["bars"] == 300
    res = await _preview(client, a_headers, private["key"], instrument, params={"fast": 3})
    assert res.status_code == 422
    assert res.json()["detail"] == "Custom strategies take no params (params must be empty)"


# --- backtests --------------------------------------------------------------------------------


@pytest.fixture
def queued(monkeypatch) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    monkeypatch.setattr(backtest_service, "enqueue", ids.append)
    return ids


def bt_body(instrument, key: str, **over) -> dict:
    return {
        "instrument_id": str(instrument.id),
        "timeframe": "1m",
        "strategy_key": key,
        # from the first candle: no warm-up history before the range, so the global strategy
        # (which reads ADX too, a longer history) and its replica see exactly the same bars
        "start": (END - timedelta(minutes=MINUTES)).isoformat(),
        "end": END.isoformat(),
        **over,
    }


async def _run(client, headers, session_factory, queued, body) -> dict:
    res = await client.post("/api/v1/backtests", json=body, headers=headers)
    assert res.status_code == 202, res.text
    backtest_id = uuid.UUID(res.json()["id"])
    assert queued[-1] == backtest_id
    assert await backtest_service.execute(session_factory, None, backtest_id) == (
        BacktestStatus.completed
    )
    return (await client.get(f"/api/v1/backtests/{backtest_id}", headers=headers)).json()


async def test_backtest_custom_equals_global_and_keeps_its_snapshot(
    client: AsyncClient, session_factory, alice, instrument, queued
) -> None:
    user, headers = alice
    replica = await create(client, headers, "EMA replica", MA_REPLICA)
    custom = await _run(
        client, headers, session_factory, queued, bt_body(instrument, replica["key"])
    )
    glob = await _run(client, headers, session_factory, queued, bt_body(instrument, "ma_crossover"))
    assert custom["metrics"] == glob["metrics"] and custom["metrics"]["trades"] > 5
    assert custom["markers"] == glob["markers"]
    assert custom["strategy_key"] == replica["key"] and custom["params"] == {}
    assert custom["params_hash"] == replica["definition_hash"]
    snapshot = custom["config"]["strategy"]
    assert snapshot["key"] == replica["key"] and snapshot["name"] == "EMA replica"
    assert snapshot["version"] == 1 and snapshot["kind"] == "builder"
    assert snapshot["definition"] == replica["definition"] and snapshot["members"] == {}
    assert "strategy" not in glob["config"]

    # edit the strategy: the finished backtest still reads the same
    res = await client.put(
        f"{MINE}/{replica['id']}",
        json={"version": 1, "definition": rsi_below(30)},
        headers=headers,
    )
    assert res.status_code == 200
    after_edit = (await client.get(f"/api/v1/backtests/{custom['id']}", headers=headers)).json()
    assert after_edit == custom

    # delete it: still readable (and in the list), trades too
    assert (await client.delete(f"{MINE}/{replica['id']}", headers=headers)).status_code == 204
    after_delete = (await client.get(f"/api/v1/backtests/{custom['id']}", headers=headers)).json()
    assert after_delete == custom
    trades = await client.get(f"/api/v1/backtests/{custom['id']}/trades", headers=headers)
    assert trades.json()["total"] == custom["metrics"]["trades"]
    listed = await client.get(
        "/api/v1/backtests", params={"strategy_key": replica["key"]}, headers=headers
    )
    assert listed.json()["total"] == 1
    assert user.id is not None


async def test_queued_backtest_runs_the_snapshot_after_an_edit_or_delete(
    client: AsyncClient, session_factory, alice, instrument, queued
) -> None:
    _, headers = alice
    member = await create(client, headers, "EMA replica", MA_REPLICA)
    combo_def = composite("rsi_reversal", member["key"], mode="any", window=2)
    combo = await create(client, headers, "Combo", combo_def)
    reference = await _run(
        client, headers, session_factory, queued, bt_body(instrument, combo["key"])
    )
    assert set(reference["config"]["strategy"]["members"]) == {member["key"]}

    res = await client.post(
        "/api/v1/backtests", json=bt_body(instrument, combo["key"]), headers=headers
    )
    pending = uuid.UUID(res.json()["id"])
    # the member changes and the composite is deleted before the worker picks it up
    await client.put(
        f"{MINE}/{member['id']}", json={"version": 1, "definition": rsi_below(45)}, headers=headers
    )
    assert (await client.delete(f"{MINE}/{combo['id']}", headers=headers)).status_code == 204
    assert (
        await backtest_service.execute(session_factory, None, pending) == BacktestStatus.completed
    )
    late = (await client.get(f"/api/v1/backtests/{pending}", headers=headers)).json()
    assert late["metrics"] == reference["metrics"]


async def test_backtest_access(client: AsyncClient, alice, bob, instrument, queued) -> None:
    _, a_headers = alice
    _, b_headers = bob
    private = await create(client, a_headers, "Private", MA_REPLICA)
    res = await client.post(
        "/api/v1/backtests", json=bt_body(instrument, private["key"]), headers=b_headers
    )
    assert res.status_code == 404
    res = await client.post(
        "/api/v1/backtests",
        json=bt_body(instrument, private["key"], config={"strategy": {}}),
        headers=a_headers,
    )
    assert res.status_code == 422 and "set by the server" in res.json()["detail"]
    assert queued == []


# --- activations ------------------------------------------------------------------------------


async def test_activate_custom(client: AsyncClient, session: AsyncSession, alice, bob) -> None:
    _, a_headers = alice
    _, b_headers = bob
    btc = await make_instrument(session, "BTC/USDT")
    private = await create(client, a_headers, "Private", MA_REPLICA)
    public = await create(client, a_headers, "Public", rsi_below(30), visibility="public")
    base = {"instrument_id": str(btc.id), "timeframe": "1h"}

    res = await client.post(
        "/api/v1/me/strategies", json={**base, "strategy_key": private["key"]}, headers=a_headers
    )
    assert res.status_code == 201, res.text
    row = res.json()
    assert (row["strategy_key"], row["params"], row["params_hash"]) == (
        private["key"],
        {},
        private["definition_hash"],
    )
    res = await client.post(
        "/api/v1/me/strategies", json={**base, "strategy_key": private["key"]}, headers=a_headers
    )
    assert res.status_code == 409  # same setup twice
    res = await client.post(
        "/api/v1/me/strategies",
        json={**base, "strategy_key": private["key"], "params": {"x": 1}},
        headers=a_headers,
    )
    assert res.status_code == 422
    res = await client.patch(
        f"/api/v1/me/strategies/{row['id']}", json={"params": {"x": 1}}, headers=a_headers
    )
    assert res.status_code == 422
    res = await client.post(
        "/api/v1/me/strategies", json={**base, "strategy_key": private["key"]}, headers=b_headers
    )
    assert res.status_code == 404
    res = await client.post(
        "/api/v1/me/strategies", json={**base, "strategy_key": public["key"]}, headers=b_headers
    )
    assert res.status_code == 201 and res.json()["params_hash"] == public["definition_hash"]
    detail = (await client.get(f"{MINE}/{private['id']}", headers=a_headers)).json()
    assert detail["usage"]["activations"] == 1


# --- live signal engine -----------------------------------------------------------------------


async def _signals(session: AsyncSession, instrument_id) -> list[Signal]:
    rows = await session.scalars(
        select(Signal)
        .where(Signal.instrument_id == instrument_id)
        .order_by(Signal.bar_time, Signal.strategy_key)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


async def _activation(session: AsyncSession, row_id) -> UserStrategy:
    return await session.get(UserStrategy, row_id, populate_existing=True)


async def activate_custom(session, user, instrument, custom, notify: bool = True) -> UserStrategy:
    resolved = await strategy_resolver.get(session, custom.key, user)
    row = UserStrategy(
        user_id=user.id,
        strategy_key=resolved.key,
        params={},
        params_hash=resolved.params_hash,
        instrument_id=instrument.id,
        timeframe=Timeframe.m1,
        notify=notify,
    )
    session.add(row)
    await session.commit()
    return row


async def test_custom_activation_produces_a_signal_end_to_end(
    session: AsyncSession, session_factory, redis_client: Redis, alice
) -> None:
    user, _ = alice
    btc = await make_instrument(session, "BTC/USDT")
    custom = await make_custom(session, user, "RSI(1) reversal", RSI1_REPLICA)
    activation = await activate_custom(session, user, btc, custom)
    await add_closes(session, btc.id, T0, CLOSES[:4])

    async with Listener(redis_client) as listener:
        await listener.listen(signals_topic(btc.id), user_topic(user.id))
        result = await signal_engine.evaluate(
            session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR3)
        )
        messages = await listener.messages()
    assert (result.status, result.setups, result.signals, result.inserted) == ("done", 1, 1, 1)
    assert result.errors == []
    [row] = await _signals(session, btc.id)
    assert (row.strategy_key, row.params, row.params_hash, row.bar_time) == (
        custom.key,
        {},
        custom.definition_hash,
        BAR3,
    )
    assert (row.side.value, row.reason, row.strength, row.price) == ("buy", "builder_buy", 1.0, 9.0)
    assert row.details["true"] == 2 and row.details["conditions"][0]["left"] == 0.0
    by_topic = dict(messages)
    assert by_topic[user_topic(user.id)]["user_strategy_ids"] == [str(activation.id)]
    assert by_topic[signals_topic(btc.id)]["signal"]["strategy_key"] == custom.key


async def test_global_and_custom_share_one_candle_load(
    session: AsyncSession, session_factory, redis_client: Redis, alice, monkeypatch
) -> None:
    user, _ = alice
    btc = await make_instrument(session, "BTC/USDT")
    custom = await make_custom(session, user, "RSI(1) reversal", RSI1_REPLICA)
    await activate_custom(session, user, btc, custom)
    await activate(session, user, btc, params=RSI1)  # the global strategy, same rules
    await add_closes(session, btc.id, T0, CLOSES[:4])
    loads = []
    original = market_service.get_candles

    async def counting(*args, **kwargs):
        loads.append(kwargs.get("limit"))
        return await original(*args, **kwargs)

    monkeypatch.setattr(market_service, "get_candles", counting)
    result = await signal_engine.evaluate(
        session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR3)
    )
    assert len(loads) == 1  # candles loaded once for both
    assert (result.setups, result.inserted) == (2, 2)
    rows = await _signals(session, btc.id)
    assert {r.strategy_key for r in rows} == {"rsi_reversal", custom.key}
    assert {(r.bar_time, r.side.value) for r in rows} == {(BAR3, "buy")}


async def test_editing_a_definition_changes_the_hash_from_the_next_bar(
    session: AsyncSession, session_factory, redis_client: Redis, alice
) -> None:
    user, _ = alice
    btc = await make_instrument(session, "BTC/USDT")
    custom = await make_custom(session, user, "RSI(1) reversal", RSI1_REPLICA)
    activation = await activate_custom(session, user, btc, custom)
    await add_closes(session, btc.id, T0, CLOSES)
    old_hash = custom.definition_hash
    await signal_engine.evaluate(session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR3))

    edited = rsi_reversal_replica(length=1, low=30, high=80)  # sell level only
    await custom_strategy_service.replace(
        session, user, custom.id, CustomStrategyReplace(version=1, definition=edited)
    )
    new_hash = (await strategy_resolver.get(session, custom.key, user)).params_hash
    assert new_hash != old_hash
    assert (await _activation(session, activation.id)).params_hash == new_hash
    await signal_engine.evaluate(session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR5))
    first, second = await _signals(session, btc.id)
    assert (first.bar_time, first.params_hash) == (BAR3, old_hash)  # old signals keep theirs
    assert (second.bar_time, second.params_hash) == (BAR5, new_hash)


async def test_public_strategy_is_one_setup_for_all_users(
    session: AsyncSession, session_factory, redis_client: Redis, alice, bob, make_user
) -> None:
    author, _ = alice
    b, _ = bob
    carol = await make_user("carol@example.com")
    btc = await make_instrument(session, "BTC/USDT")
    custom = await make_custom(
        session, author, "Shared", RSI1_REPLICA, visibility=Visibility.public
    )
    rows = [await activate_custom(session, u, btc, custom) for u in (b, carol)]
    await add_closes(session, btc.id, T0, CLOSES[:4])
    async with Listener(redis_client) as listener:
        await listener.listen(user_topic(b.id), user_topic(carol.id))
        result = await signal_engine.evaluate(
            session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR3)
        )
        messages = await listener.messages()
    assert (result.setups, result.signals, result.inserted) == (1, 1, 1)
    assert (result.published, result.user_messages) == (1, 2)
    assert {t for t, _ in messages} == {user_topic(b.id), user_topic(carol.id)}
    assert len(await _signals(session, btc.id)) == 1
    assert {r.params_hash for r in rows} == {custom.definition_hash}


async def test_member_edit_rehashes_composites_and_their_activations(
    session: AsyncSession, alice, bob
) -> None:
    a, _ = alice
    b, _ = bob
    btc = await make_instrument(session, "BTC/USDT")
    member = await make_custom(session, a, "Member", rsi_below(30), visibility=Visibility.public)
    inner = await make_custom(session, b, "Inner", composite("macd_cross", member.key))
    outer = await make_custom(session, b, "Outer", composite("rsi_reversal", inner.key))
    activations = [await activate_custom(session, b, btc, c) for c in (inner, outer)]
    before = {c.key: c.definition_hash for c in (inner, outer)}

    await custom_strategy_service.replace(
        session, a, member.id, CustomStrategyReplace(version=1, definition=rsi_below(20))
    )
    for custom, activation in zip((inner, outer), activations, strict=True):
        await session.refresh(custom)
        assert custom.definition_hash != before[custom.key] and custom.version == 1
        assert (await _activation(session, activation.id)).params_hash == custom.definition_hash
        resolved = await strategy_resolver.get(session, custom.key, b)
        assert resolved.params_hash == custom.definition_hash


async def test_private_or_deleted_strategy_deactivates_other_users_setups(
    session: AsyncSession, session_factory, redis_client: Redis, alice, bob
) -> None:
    a, _ = alice
    b, _ = bob
    btc = await make_instrument(session, "BTC/USDT")
    shared = await make_custom(session, a, "Shared", RSI1_REPLICA, visibility=Visibility.public)
    own = await activate_custom(session, a, btc, shared)
    theirs = await activate_custom(session, b, btc, shared)
    combo = await make_custom(session, b, "Combo", composite("macd_cross", shared.key))
    combo_activation = await activate_custom(session, b, btc, combo)

    await custom_strategy_service.patch(
        session, a, shared.id, CustomStrategyUpdate(visibility=Visibility.private)
    )
    assert (await _activation(session, own.id)).is_active is True  # the author's own
    assert (await _activation(session, theirs.id)).is_active is False
    assert (await _activation(session, combo_activation.id)).is_active is False

    # the engine refuses a broken composite even if an activation were still active
    row = await _activation(session, combo_activation.id)
    row.is_active = True
    await session.commit()
    await add_closes(session, btc.id, T0, CLOSES[:4])
    result = await signal_engine.evaluate(
        session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR3)
    )
    assert result.setups == 1 and result.inserted == 1  # only Alice's own setup ran
    assert any("unknown or inaccessible" in e for e in result.errors)

    await custom_strategy_service.delete(session, a, shared.id)
    assert (await _activation(session, own.id)).is_active is False
    assert len(await _signals(session, btc.id)) == 1  # signals are kept
