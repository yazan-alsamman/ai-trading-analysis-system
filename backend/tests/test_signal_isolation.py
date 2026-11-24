"""Private-signal isolation (B12, P0-04): a ``custom:<uuid>`` signal is visible only to users
who may use the strategy (its owner, or anyone once it is public) and to admins, on every path:
GET /signals (rows and total), trade plans, the notification inbox, post/chat attachments, the
experts feed and the ``signals:{instrument_id}`` WebSocket topic."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.candle import Timeframe
from app.models.strategy import Signal, SignalSide, UserStrategy
from app.models.user import UserRole
from app.realtime.hub import WebSocketHub
from app.realtime.topics import signals_topic
from app.services import signal_engine, strategy_resolver
from app.services.signal_engine import Job
from tests.custom_utils import MINE, make_custom, rsi_reversal_replica
from tests.expert_utils import make_expert, make_person, make_plan, subscribe
from tests.market_utils import make_instrument
from tests.strategy_utils import RSI1, activate, add_closes
from tests.utils import bearer
from tests.ws_utils import recv_until, ws_connect

T0 = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
CLOSES = [10.0, 9.0, 8.0, 9.0, 8.0, 9.0]  # RSI(1) crosses 30 upward on bars 3 and 5
BAR3, BAR5 = T0 + timedelta(minutes=3), T0 + timedelta(minutes=5)
SIGNALS = "/api/v1/signals"
PLANS = "/api/v1/me/signal-plans"


@pytest.fixture
async def alice(client: AsyncClient, make_user, session: AsyncSession):
    """An expert (can make strategies public and sell a signals feed)."""
    return await make_expert(client, make_user, session, "alice")


@pytest.fixture
async def bob(make_user, session: AsyncSession):
    """An analyst (can write posts)."""
    return await make_person(make_user, session, "bob", UserRole.analyst)


@pytest.fixture
async def admin(make_user):
    user = await make_user("root@example.com", role=UserRole.admin)
    return user, bearer(create_access_token(user))


async def activate_custom(session: AsyncSession, user, instrument, custom) -> UserStrategy:
    resolved = await strategy_resolver.get(session, custom.key, user)
    row = UserStrategy(
        user_id=user.id,
        strategy_key=resolved.key,
        params={},
        params_hash=resolved.params_hash,
        instrument_id=instrument.id,
        timeframe=Timeframe.m1,
    )
    session.add(row)
    await session.commit()
    return row


async def _keys(client: AsyncClient, headers, url: str = SIGNALS, **params) -> tuple[list, int]:
    res = await client.get(url, params={"limit": 100, **params}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    items = body["items"]
    keys = sorted((i["signal"] if "signal" in i else i)["strategy_key"] for i in items)
    return keys, body["total"]


async def _set_visibility(client: AsyncClient, headers, custom, visibility: str) -> None:
    res = await client.patch(
        f"{MINE}/{custom.id}", json={"visibility": visibility}, headers=headers
    )
    assert res.status_code == 200, res.text


async def _subscribe_signals(ws, instrument) -> None:
    await ws.send_text(
        json.dumps({"op": "subscribe", "topic": "signals", "instrument_id": str(instrument.id)})
    )
    msg = await recv_until(ws, lambda m: m["type"] in ("subscribed", "error"))
    assert msg == {"type": "subscribed", "topic": signals_topic(instrument.id)}


async def _live_signals(ws, wait: float = 0.6) -> list[str]:
    """Strategy keys of the ``signals:{id}`` frames received within ``wait`` seconds."""
    keys, loop = [], asyncio.get_running_loop()
    deadline = loop.time() + wait
    while (left := deadline - loop.time()) > 0:
        try:
            msg = json.loads(await ws.receive_text(timeout=left))
        except TimeoutError:
            break
        if msg.get("type") == "signal" and msg["topic"].startswith("signals:"):
            keys.append(msg["signal"]["strategy_key"])
    return sorted(keys)


async def test_private_signal_is_isolated_everywhere_until_made_public(
    client: AsyncClient,
    hub: WebSocketHub,
    session: AsyncSession,
    session_factory,
    redis_client: Redis,
    alice,
    bob,
    admin,
) -> None:
    (a, ah), (b, bh), (_, rh) = alice, bob, admin
    btc = await make_instrument(session, "BTC/USDT")
    secret = await make_custom(session, a, "Secret RSI", rsi_reversal_replica(length=1))
    await activate_custom(session, a, btc, secret)
    await activate(session, b, btc, params=RSI1)  # a global strategy, visible to everyone
    await add_closes(session, btc.id, T0, CLOSES)
    both = sorted([secret.key, "rsi_reversal"])

    async with (
        ws_connect(create_access_token(a)) as wa,
        ws_connect(create_access_token(b)) as wb,
        ws_connect(create_access_token(admin[0])) as wr,
    ):
        for ws in (wa, wb, wr):
            await _subscribe_signals(ws, btc)
        result = await signal_engine.evaluate(
            session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR3)
        )
        assert (result.inserted, result.published, result.errors) == (2, 2, [])
        got = await asyncio.gather(*(_live_signals(ws) for ws in (wa, wb, wr)))
    # the global one is broadcast once and reaches everyone; the private one only A and admins
    assert got == [both, ["rsi_reversal"], both]

    # REST: B's page and total skip it; filtering by its key finds nothing
    assert await _keys(client, ah) == (both, 2)
    assert await _keys(client, bh) == (["rsi_reversal"], 1)
    assert await _keys(client, bh, strategy_key=secret.key) == ([], 0)
    assert await _keys(client, rh) == (both, 2)  # admins see everything (moderation)
    # plans: A has a plan for the private signal, B only for the global one
    assert await _keys(client, ah, PLANS) == ([secret.key], 1)
    assert await _keys(client, bh, PLANS) == (["rsi_reversal"], 1)

    # made public: B sees the earlier signal, and the next one is broadcast to B
    await _set_visibility(client, ah, secret, "public")
    assert await _keys(client, bh) == (both, 2)
    async with ws_connect(create_access_token(b)) as wb:
        await _subscribe_signals(wb, btc)
        await signal_engine.evaluate(session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR5))
        assert await _live_signals(wb) == both
    assert (await _keys(client, bh))[1] == 4


async def test_made_private_hides_earlier_signals_plans_and_notifications(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client: Redis, alice, bob
) -> None:
    (a, ah), (b, bh) = alice, bob
    btc = await make_instrument(session, "BTC/USDT")
    shared = await make_custom(session, a, "Shared RSI", rsi_reversal_replica(length=1))
    await _set_visibility(client, ah, shared, "public")
    await session.refresh(shared)
    await activate_custom(session, a, btc, shared)
    await activate_custom(session, b, btc, shared)  # B runs A's public strategy
    await add_closes(session, btc.id, T0, CLOSES)
    result = await signal_engine.evaluate(
        session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR3)
    )
    assert (result.inserted, result.plans, result.notifications) == (1, 2, 2)
    inbox = "/api/v1/me/notifications"
    assert await _keys(client, bh) == ([shared.key], 1)
    assert await _keys(client, bh, PLANS) == ([shared.key], 1)
    assert (await client.get(inbox, headers=bh)).json()["total"] == 1
    [signal_id] = [s.id for s in await _signal_rows(session, btc)]
    post = {"title": "My trade", "body": "Look", "attachments": []}
    post["attachments"] = [{"type": "signal", "id": str(signal_id)}]
    res = await client.post("/api/v1/posts", json=post, headers=bh)
    assert res.status_code == 201, res.text
    post_id = res.json()["id"]

    # A makes it private again: B's activation stops and everything derived is hidden from B
    await _set_visibility(client, ah, shared, "private")
    assert await _keys(client, bh) == ([], 0)
    assert await _keys(client, bh, PLANS) == ([], 0)
    assert (await client.get(inbox, headers=bh)).json()["total"] == 0
    assert (await client.get(f"{inbox}/unread-count", headers=bh)).json()["count"] == 0
    [attachment] = (await client.get(f"/api/v1/posts/{post_id}", headers=bh)).json()["attachments"]
    assert attachment == {"type": "signal", "id": str(signal_id), "available": False}
    res = await client.post("/api/v1/posts", json=post, headers=bh)  # cannot attach it again
    assert res.status_code == 422
    # A still sees all of it, and the attachment of B's post
    assert await _keys(client, ah) == ([shared.key], 1)
    assert await _keys(client, ah, PLANS) == ([shared.key], 1)
    [attachment] = (await client.get(f"/api/v1/posts/{post_id}", headers=ah)).json()["attachments"]
    assert attachment["available"] is True and attachment["strategy_key"] == shared.key


async def _signal_rows(session: AsyncSession, instrument) -> list[Signal]:
    return list(await session.scalars(select(Signal).where(Signal.instrument_id == instrument.id)))


def _signal(instrument, key: str, minute: int) -> Signal:
    return Signal(
        instrument_id=instrument.id,
        timeframe=Timeframe.m1,
        strategy_key=key,
        params={},
        params_hash="h",
        bar_time=T0 + timedelta(minutes=minute),
        side=SignalSide.buy,
        strength=0.5,
        price=100.0,
        reason="x",
        details={},
    )


async def test_pagination_has_no_holes_or_wrong_totals(
    client: AsyncClient, session: AsyncSession, alice, bob
) -> None:
    (a, ah), (_, bh) = alice, bob
    btc = await make_instrument(session, "BTC/USDT")
    secret = await make_custom(session, a, "Secret", rsi_reversal_replica(length=1))
    gone = f"custom:{'0' * 8}-0000-0000-0000-{'0' * 12}"  # a deleted strategy's old signals
    keys = [secret.key if m % 3 else "rsi_reversal" for m in range(30)] + [gone]
    session.add_all([_signal(btc, key, m) for m, key in enumerate(keys)])
    await session.commit()
    visible_to_b = [m for m, key in enumerate(keys) if key == "rsi_reversal"]  # 10 rows

    seen, offset = [], 0
    while True:
        res = await client.get(SIGNALS, params={"limit": 3, "offset": offset}, headers=bh)
        body = res.json()
        assert body["total"] == len(visible_to_b)
        if not body["items"]:
            break
        assert len(body["items"]) == min(3, len(visible_to_b) - offset)  # full pages
        seen += [i["bar_time"] for i in body["items"]]
        offset += 3
    expected = [(T0 + timedelta(minutes=m)).isoformat() for m in reversed(visible_to_b)]
    assert [datetime.fromisoformat(t).isoformat() for t in seen] == expected
    res = await client.get(SIGNALS, params={"limit": 3, "offset": 0}, headers=ah)
    assert res.json()["total"] == 30  # A's own and the global ones; not the deleted strategy's


async def test_experts_feed_perk(
    client: AsyncClient, make_user, session: AsyncSession, alice
) -> None:
    """The feed is unchanged: signals of the expert's **public** custom strategies the expert runs,
    for subscribers with the ``signals_feed`` perk (403 without it)."""
    a, ah = alice
    btc = await make_instrument(session, "BTC/USDT")
    secret = await make_custom(session, a, "Secret", rsi_reversal_replica(length=1))
    await activate_custom(session, a, btc, secret)
    session.add(_signal(btc, secret.key, 3))
    await session.commit()
    feed = await make_plan(client, ah)
    posts_only = await make_plan(
        client,
        ah,
        name="Posts only",
        perks={"premium_posts": True, "chat": False, "signals_feed": False},
    )
    _, sh = await make_person(make_user, session, "subscriber")
    _, nh = await make_person(make_user, session, "noperk")
    await subscribe(client, sh, feed["id"])
    await subscribe(client, nh, posts_only["id"])
    url = f"/api/v1/experts/{a.id}/signals"

    assert (await client.get(url, headers=sh)).json()["total"] == 0  # private: not in the feed
    assert await _keys(client, sh) == ([], 0)
    await _set_visibility(client, ah, secret, "public")
    res = (await client.get(url, headers=sh)).json()
    assert [(i["strategy_key"], i["strategy_name"]) for i in res["items"]] == [
        (secret.key, "Secret")
    ]
    assert (await client.get(url, headers=nh)).status_code == 403  # no signals_feed perk
