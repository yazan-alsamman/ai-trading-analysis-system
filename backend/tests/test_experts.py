"""Expert profiles and plans, the directory, premium (subscribers) posts, the signals feed,
entitlements and the earnings view."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Timeframe
from app.models.custom_strategy import CustomStrategy, Visibility
from app.models.notification import Notification, NotificationType
from app.models.risk import SignalPlan
from app.models.strategy import Signal, SignalSide, UserStrategy
from app.models.user import UserRole
from app.payments.entitlements import entitlements
from app.social import notify
from tests.expert_utils import make_expert, make_person, make_plan, subscribe
from tests.market_utils import make_instrument

POSTS = "/api/v1/posts"


@pytest.fixture
async def expert(client, make_user, session):
    return await make_expert(client, make_user, session, full_name="Sami Expert")


@pytest.fixture
async def trader(make_user, session):
    return await make_person(make_user, session, "trader", full_name="Omar Trader")


async def _ff(client, admin_headers, sub_id):
    res = await client.post(
        f"/api/v1/admin/subscriptions/{sub_id}/fast-forward", json={}, headers=admin_headers
    )
    assert res.status_code == 200, res.text
    return res.json()


# --- profile and plans ---------------------------------------------------------------------------


async def test_profile_rules(client: AsyncClient, make_user, session, trader) -> None:
    _, th = trader
    body = {"headline": "Me", "markets": ["crypto"]}
    assert (await client.put("/api/v1/me/expert-profile", json=body, headers=th)).status_code == 403
    _, eh = await make_person(make_user, session, "pro", UserRole.expert)
    assert (await client.get("/api/v1/me/expert-profile", headers=eh)).status_code == 404
    for bad in (
        {"headline": "x", "bio": "<script>alert(1)</script>"},
        {"headline": "x", "markets": ["lottery"]},
        {"headline": "x", "languages": ["xx"]},
        {"headline": ""},
    ):
        res = await client.put("/api/v1/me/expert-profile", json=bad, headers=eh)
        assert res.status_code == 422, bad
    plan = {"name": "P", "price": "10", "interval": "month"}
    assert (await client.post("/api/v1/me/plans", json=plan, headers=eh)).status_code == 404
    res = await client.put(
        "/api/v1/me/expert-profile",
        json={"headline": "Gold and FX", "markets": ["forex", "gold", "forex"]},
        headers=eh,
    )
    assert res.status_code == 200 and res.json()["markets"] == ["forex", "gold"]


async def test_plans_limit_and_updates(client: AsyncClient, expert) -> None:
    _, eh = expert
    plans = [
        await make_plan(client, eh, name=f"P{i}", price=f"{10 * (i + 1)}.00") for i in range(3)
    ]
    res = await client.post(
        "/api/v1/me/plans", json={"name": "P4", "price": "5", "interval": "month"}, headers=eh
    )
    assert res.status_code == 409 and "3 active plans" in res.json()["detail"]
    inactive = await make_plan(client, eh, name="Draft", is_active=False)
    assert (
        await client.patch(
            f"/api/v1/me/plans/{inactive['id']}", json={"is_active": True}, headers=eh
        )
    ).status_code == 409
    assert (
        await client.delete(f"/api/v1/me/plans/{plans[0]['id']}", headers=eh)
    ).status_code == 204
    res = await client.patch(
        f"/api/v1/me/plans/{inactive['id']}", json={"is_active": True}, headers=eh
    )
    assert res.status_code == 200
    assert (
        await client.patch(f"/api/v1/me/plans/{inactive['id']}", json={"price": None}, headers=eh)
    ).status_code == 422
    for bad in ({"trial_days": 31}, {"price": "-1"}, {"name": "<b>x</b>"}):
        body = {"name": "B", "price": "1", "interval": "month", **bad}
        assert (await client.post("/api/v1/me/plans", json=body, headers=eh)).status_code == 422
    mine = (await client.get("/api/v1/me/plans", headers=eh)).json()
    assert len(mine) == 4 and sum(p["is_active"] for p in mine) == 3


# --- directory -----------------------------------------------------------------------------------


async def test_directory_and_detail(
    client: AsyncClient, make_user, session, expert, trader
) -> None:
    e1, eh = expert
    e2, e2h = await make_expert(
        client, make_user, session, "fx", full_name="Lina FX", markets=["forex"], languages=["en"]
    )
    await make_expert(client, make_user, session, "hidden", is_listed=False)
    cheap = await make_plan(client, eh, name="Basic", price="9.99")
    await make_plan(client, eh, name="Pro", price="49.00", interval="year")
    await make_plan(client, e2h, price="15.00")
    _, th = trader
    await subscribe(client, th, cheap["id"])
    await client.post(f"/api/v1/users/{e2.id}/follow", headers=th)

    async def names(**params):
        res = await client.get("/api/v1/experts", params=params, headers=th)
        assert res.status_code == 200, res.text
        return [e["display_name"] for e in res.json()["items"]]

    assert await names() == ["Sami Expert", "Lina FX"]  # most subscribers first; unlisted out
    assert await names(market="forex") == ["Lina FX"]
    assert await names(language="ar") == ["Sami Expert"]
    assert await names(q="lina") == ["Lina FX"]
    assert await names(q="swing") == ["Sami Expert", "Lina FX"]  # headline
    page = (await client.get("/api/v1/experts", headers=th)).json()
    sami, lina = page["items"]
    assert (sami["subscribers_count"], sami["is_subscribed"], sami["rating"]) == (1, True, None)
    assert sami["cheapest_plan"]["name"] == "Basic" and sami["cheapest_plan"]["price"] == "9.99"
    assert (lina["followers_count"], lina["is_subscribed"]) == (1, False)
    assert "example.com" not in json.dumps(page)
    detail = (await client.get(f"/api/v1/experts/{e1.id}", headers=th)).json()
    assert [p["name"] for p in detail["plans"]] == ["Basic", "Pro"]
    assert detail["entitlements"] == {"premium_posts": True, "chat": True, "signals_feed": True}
    assert detail["bio"].startswith("## About")
    other = (await client.get(f"/api/v1/experts/{e2.id}", headers=th)).json()
    assert other["entitlements"] == {"premium_posts": False, "chat": False, "signals_feed": False}
    assert (await client.get(f"/api/v1/experts/{uuid.uuid4()}", headers=th)).status_code == 404
    _, hidden_h = await make_person(make_user, session, "notexpert")
    assert (await client.get(f"/api/v1/experts/{e1.id}", headers=hidden_h)).status_code == 200


# --- premium posts -------------------------------------------------------------------------------


async def test_subscriber_posts_teaser_and_comments(
    client: AsyncClient,
    make_user,
    session: AsyncSession,
    expert,
    trader,
    admin_headers,
    monkeypatch,
) -> None:
    e, eh = expert
    _, th = trader
    sub_user, sh = await make_person(make_user, session, "subscriber", full_name="Rana Sub")
    analyst, ah = await make_person(make_user, session, "analyst", UserRole.analyst)
    plan = await make_plan(client, eh)
    await subscribe(client, sh, plan["id"])
    for h in (th, sh):
        await client.post(f"/api/v1/users/{e.id}/follow", headers=h)
    queued = []
    monkeypatch.setattr(notify, "enqueue_new_post", queued.append)
    body = "## Weekly plan\n\n" + "Long BTC above 64k. " * 30
    res = await client.post(
        POSTS,
        json={"title": "Premium: BTC week ahead", "body": body, "visibility": "subscribers"},
        headers=eh,
    )
    assert res.status_code == 201 and not res.json()["locked"]
    post = res.json()
    bad = await client.post(
        POSTS, json={"title": "x", "body": "y", "visibility": "subscribers"}, headers=ah
    )
    assert bad.status_code == 422 and "only experts" in bad.text
    # non-subscriber: teaser in the feed and by id
    feed = (await client.get(POSTS, headers=th)).json()["items"]
    [teaser] = [p for p in feed if p["id"] == post["id"]]
    assert teaser["locked"] and teaser["title"] == "Premium: BTC week ahead"
    assert len(teaser["body"]) <= 201 and teaser["body"].endswith("…")
    assert teaser["attachments"] == [] and teaser["author"]["display_name"] == "Sami Expert"
    one = (await client.get(f"{POSTS}/{post['id']}", headers=th)).json()
    assert one["locked"] and one["body"] == teaser["body"]
    # the subscriber, the expert and admins see it all
    for h in (sh, eh, admin_headers):
        full = (await client.get(f"{POSTS}/{post['id']}", headers=h)).json()
        assert not full["locked"] and full["body"] == body.strip()
    # comments: open for the subscriber, hidden and closed for others
    url = f"{POSTS}/{post['id']}/comments"
    assert (await client.post(url, json={"body": "Thanks!"}, headers=sh)).status_code == 201
    assert (await client.get(url, headers=th)).json() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }
    res = await client.post(url, json={"body": "let me see"}, headers=th)
    assert res.status_code == 403 and "subscribers" in res.json()["detail"]
    assert (await client.get(url, headers=sh)).json()["total"] == 1
    # new_post goes to subscribers only (the follower without a subscription gets nothing)
    from app.core.redis import get_redis

    assert (
        await notify.fanout_new_post(lambda: _same(session), get_redis(), uuid.UUID(post["id"]))
        == 1
    )
    rows = await session.execute(
        select(Notification.user_id).where(Notification.type == NotificationType.new_post)
    )
    assert [r[0] for r in rows.all()] == [sub_user.id]


class _same:
    """A session factory handing out the test session (fan-out opens several)."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return None


# --- signals feed --------------------------------------------------------------------------------


async def test_signals_feed(
    client: AsyncClient, make_user, session: AsyncSession, expert, trader
) -> None:
    e, eh = expert
    _, th = trader
    no_feed, nh = await make_person(make_user, session, "nofeed")
    btc = await make_instrument(session, "BTC/USDT")
    public = CustomStrategy(
        user_id=e.id,
        name="EMA trend",
        kind="builder",
        definition={},
        definition_hash="h",
        visibility=Visibility.public,
    )
    private = CustomStrategy(
        user_id=e.id, name="Secret", kind="builder", definition={}, definition_hash="h"
    )
    session.add_all([public, private])
    await session.commit()
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    rows = []
    for strategy in (public, private):
        key = f"custom:{strategy.id}"
        session.add(
            UserStrategy(
                user_id=e.id,
                strategy_key=key,
                params={},
                params_hash="h",
                instrument_id=btc.id,
                timeframe=Timeframe.h1,
            )
        )
        signal = Signal(
            instrument_id=btc.id,
            timeframe=Timeframe.h1,
            strategy_key=key,
            params={},
            params_hash="h",
            bar_time=now,
            side=SignalSide.buy,
            strength=0.8,
            price=64000,
            reason="builder_buy",
            details={},
        )
        rows.append(signal)
    other = Signal(
        instrument_id=btc.id,
        timeframe=Timeframe.h1,
        strategy_key="rsi_reversal",
        params={},
        params_hash="h",
        bar_time=now - timedelta(hours=1),
        side=SignalSide.sell,
        strength=0.5,
        price=63000,
        reason="x",
        details={},
    )
    session.add_all([*rows, other])
    await session.commit()
    session.add(
        SignalPlan(signal_id=rows[0].id, user_id=e.id, plan={"entry_ref": 64000, "stop": 63500})
    )
    await session.commit()
    plan = await make_plan(client, eh)
    no_perk = await make_plan(
        client,
        eh,
        name="Posts only",
        perks={"premium_posts": True, "chat": False, "signals_feed": False},
    )
    await subscribe(client, th, plan["id"])
    await subscribe(client, nh, no_perk["id"])
    url = f"/api/v1/experts/{e.id}/signals"
    res = (await client.get(url, headers=th)).json()
    assert res["total"] == 1
    [item] = res["items"]
    assert (item["strategy_name"], item["side"], item["price"]) == ("EMA trend", "buy", 64000.0)
    assert item["plan"] == {"entry_ref": 64000, "stop": 63500}
    assert item["instrument"]["symbol"] == "BTC/USDT"
    assert (await client.get(url, headers=nh)).status_code == 403  # no signals_feed perk
    _, stranger = await make_person(make_user, session, "stranger")
    assert (await client.get(url, headers=stranger)).status_code == 403
    assert (await client.get(url, headers=eh)).json()["total"] == 1  # the expert sees it
    assert no_feed.id


async def test_entitlements_rules(
    client: AsyncClient, make_user, session: AsyncSession, expert, trader
) -> None:
    e, eh = expert
    t, th = trader
    admin, _ = await make_person(make_user, session, "boss", UserRole.admin)
    assert await entitlements(session, e, e.id) == {
        "premium_posts": True,
        "chat": True,
        "signals_feed": True,
    }
    assert all((await entitlements(session, admin, e.id)).values())
    assert not any((await entitlements(session, t, e.id)).values())
    plan = await make_plan(
        client, eh, perks={"premium_posts": True, "chat": False, "signals_feed": False}
    )
    await subscribe(client, th, plan["id"])
    assert await entitlements(session, t, e.id) == {
        "premium_posts": True,
        "chat": False,
        "signals_feed": False,
    }


# --- earnings ------------------------------------------------------------------------------------


async def test_earnings_math(
    client: AsyncClient, make_user, session: AsyncSession, expert, admin_headers
) -> None:
    e, eh = expert
    monthly = await make_plan(client, eh, name="Monthly", price="30.00")
    yearly = await make_plan(client, eh, name="Yearly", price="120.00", interval="year")
    trial = await make_plan(client, eh, name="Trial", price="30.00", trial_days=7)
    people = [await make_person(make_user, session, n, full_name=f"Sub {n}") for n in "abcd"]
    await subscribe(client, people[0][1], monthly["id"])
    await subscribe(client, people[1][1], yearly["id"])
    await subscribe(client, people[2][1], trial["id"])
    d = await subscribe(client, people[3][1], monthly["id"])
    await client.post(f"/api/v1/me/subscriptions/{d['id']}/cancel", headers=people[3][1])
    await _ff(client, admin_headers, d["id"])  # ended now (canceled at period end)
    earnings = (await client.get("/api/v1/me/earnings", headers=eh)).json()
    assert earnings["active_subscribers"] == 3
    assert earnings["by_status"] == {"active": 2, "trialing": 1}
    assert earnings["mrr"] == "40.00"  # 30 + 120/12; trials excluded
    assert (earnings["ended_30d"], earnings["churn_30d_pct"]) == (1, 25.0)
    [month] = earnings["months"]
    assert month["month"] == datetime.now(UTC).strftime("%Y-%m")
    assert (month["gross"], month["platform_fee"], month["net"]) == ("180.00", "36.00", "144.00")
    assert month["invoices"] == 4  # three paid charges + the 0.00 trial invoice
    names = {i["subscriber"] for i in earnings["recent_invoices"]}
    assert names == {"Sub a", "Sub b", "Sub c", "Sub d"}
    text = json.dumps(earnings)
    assert "example.com" not in text and str(people[0][0].id) not in text
    _, th = people[0]
    assert (await client.get("/api/v1/me/earnings", headers=th)).status_code == 403
