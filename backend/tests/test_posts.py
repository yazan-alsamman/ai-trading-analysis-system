"""Posts, comments, likes, follows, profiles, moderation and their notifications."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.backtest import Backtest, BacktestStatus
from app.models.candle import Timeframe
from app.models.custom_strategy import CustomStrategy, Visibility
from app.models.notification import Notification, NotificationType
from app.models.social import Comment, Post
from app.models.strategy import Signal, SignalSide
from app.models.user import User, UserRole
from app.models.workspace import Workspace
from app.social import markdown, notify
from app.social import service as social
from tests.conftest import TEST_DATABASE_URL
from tests.market_utils import make_instrument
from tests.utils import bearer

POSTS = "/api/v1/posts"


@pytest.fixture
def users(make_user):
    async def _make(name: str, role: UserRole = UserRole.trader, full_name: str | None = None):
        user = await make_user(f"{name}@example.com", role=role)
        if full_name:
            user.full_name = full_name
        return user, bearer(create_access_token(user))

    return _make


@pytest.fixture
async def analyst(users, session):
    user, h = await users("analyst", UserRole.analyst)
    user.full_name = "Lina Analyst"
    await session.commit()
    return user, h


@pytest.fixture
async def trader(users, session):
    user, h = await users("trader")
    user.full_name = "Omar Trader"
    await session.commit()
    return user, h


@pytest.fixture
async def admin(users):
    return await users("admin", UserRole.admin)


async def _post(client, headers, **over) -> dict:
    body = {"title": "BTC outlook", "body": "## Plan\n\nBuy the **dip**.", **over}
    res = await client.post(POSTS, json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


async def _notes(session: AsyncSession, user: User, type_=None) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == user.id)
    if type_ is not None:
        query = query.where(Notification.type == type_)
    rows = await session.scalars(
        query.order_by(Notification.created_at).execution_options(populate_existing=True)
    )
    return list(rows.all())


# --- input rules ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "hello <script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "a <!-- comment -->",
        "[click](javascript:alert(1))",
        "[click]( JaVaScRiPt:alert(1))",
        "[click](java\tscript:alert(1))",
        "[click](&#106;avascript:alert(1))",
        "[x](data:text/html;base64,AAAA)",
        "<javascript:alert(1)>",
        "[ref]: vbscript:msgbox\n\n[x][ref]",
    ],
)
def test_markdown_rejects_html_and_script_links(text: str) -> None:
    with pytest.raises(ValueError):
        markdown.check(text)


@pytest.mark.parametrize(
    "text",
    [
        "Price < 30k and > 20k, RSI<30",
        "[chart](https://example.com/c?x=1) and [rel](/posts/1) and <https://a.io>",
        "Code: `<b>bold</b>` and\n\n```html\n<div onclick=x>javascript:</div>\n```",
        "mail [me](mailto:a@b.co)",
    ],
)
def test_markdown_accepts_normal_text(text: str) -> None:
    assert markdown.check(text) == text


# --- posts ---------------------------------------------------------------------------------------


async def test_roles_and_create(client: AsyncClient, session, analyst, trader, users) -> None:
    res = await client.post(POSTS, json={"title": "t", "body": "b"}, headers=trader[1])
    assert res.status_code == 403
    expert = await users("expert", UserRole.expert)
    post = await _post(client, expert[1], direction="bullish", timeframe="1h")
    assert post["author"]["role"] == "expert" and post["author"]["display_name"].startswith("user-")
    assert (post["status"], post["visibility"], post["likes_count"]) == ("published", "public", 0)
    assert post["can_edit"] and not post["liked_by_me"]
    bad = await client.post(
        POSTS, json={"title": "x", "body": "<iframe src=x></iframe>"}, headers=analyst[1]
    )
    assert bad.status_code == 422 and "raw HTML" in bad.text
    bad = await client.post(
        POSTS,
        json={"title": "x", "body": "ok", "instrument_id": str(uuid.uuid4())},
        headers=analyst[1],
    )
    assert bad.status_code == 422
    assert (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).json()["id"] == post["id"]


async def test_post_roles_are_configurable(client, analyst, trader, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "post_roles", "trader,admin")
    assert (
        await client.post(POSTS, json={"title": "t", "body": "b"}, headers=analyst[1])
    ).status_code == 403
    assert (
        await client.post(POSTS, json={"title": "t", "body": "b"}, headers=trader[1])
    ).status_code == 201


async def test_attachments_access_rules(
    client: AsyncClient, session: AsyncSession, analyst, trader, users
) -> None:
    author, h = analyst
    other, _ = trader
    btc = await make_instrument(session, "BTC/USDT")
    now = datetime.now(UTC)

    def backtest(owner):
        return Backtest(
            user_id=owner.id,
            instrument_id=btc.id,
            timeframe=Timeframe.h1,
            strategy_key="ma_crossover",
            params={},
            params_hash="h",
            config={},
            range_start=now - timedelta(days=30),
            range_end=now,
            status=BacktestStatus.completed,
            metrics={"total_return_pct": 12.5, "sharpe": 1.1, "trades": 9, "secret": 1},
        )

    def strategy(owner, visibility):
        return CustomStrategy(
            user_id=owner.id,
            name=f"S {uuid.uuid4().hex[:6]}",
            kind="builder",
            definition={},
            definition_hash="h",
            visibility=visibility,
        )

    own_bt, other_bt = backtest(author), backtest(other)
    own_cs, public_cs, private_cs = (
        strategy(author, Visibility.private),
        strategy(other, Visibility.public),
        strategy(other, Visibility.private),
    )
    shared_ws = Workspace(
        user_id=other.id, name="W", position=0, state={}, is_shared=True, share_slug="slug123"
    )
    private_ws = Workspace(user_id=author.id, name="P", position=1, state={})
    signal = Signal(
        instrument_id=btc.id,
        timeframe=Timeframe.h1,
        strategy_key="rsi_reversal",
        params={},
        params_hash="h",
        bar_time=now,
        side=SignalSide.buy,
        strength=0.7,
        price=60000,
        reason="x",
        details={},
    )
    session.add_all(
        [own_bt, other_bt, own_cs, public_cs, private_cs, shared_ws, private_ws, signal]
    )
    await session.commit()

    def refs(*pairs):
        return [{"type": t, "id": str(i)} for t, i in pairs]

    bad = await client.post(
        POSTS,
        json={
            "title": "t",
            "body": "b",
            "attachments": refs(
                ("backtest", other_bt.id),
                ("custom_strategy", private_cs.id),
                ("shared_workspace", private_ws.id),
                ("signal", uuid.uuid4()),
            ),
        },
        headers=h,
    )
    assert bad.status_code == 422
    assert [e["loc"][2] for e in bad.json()["detail"]] == [0, 1, 2, 3]
    post = await _post(
        client,
        h,
        attachments=refs(
            ("backtest", own_bt.id),
            ("custom_strategy", own_cs.id),
            ("custom_strategy", public_cs.id),
            ("shared_workspace", shared_ws.id),
            ("signal", signal.id),
        ),
    )
    seen = (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).json()["attachments"]
    bt, mine, public, ws, sig = seen
    assert bt["available"] and bt["symbol"] == "BTC/USDT" and bt["timeframe"] == "1h"
    assert bt["metrics"]["total_return_pct"] == 12.5 and "secret" not in bt["metrics"]
    assert "owner_id" not in bt
    # the author's private strategy: readers only see that something is attached
    assert mine == {"type": "custom_strategy", "id": str(own_cs.id), "available": False}
    assert public["available"] and public["key"] == f"custom:{public_cs.id}"
    assert ws["available"] and ws["share_slug"] == "slug123"
    assert sig["available"] and sig["side"] == "buy" and sig["price"] == 60000
    own_view = (await client.get(f"{POSTS}/{post['id']}", headers=h)).json()["attachments"]
    assert own_view[1]["available"] and own_view[1]["name"] == own_cs.name
    # unsharing later hides it
    shared_ws.is_shared = False
    await session.commit()
    seen = (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).json()["attachments"]
    assert seen[3] == {"type": "shared_workspace", "id": str(shared_ws.id), "available": False}


async def test_edit_window_and_soft_delete(
    client: AsyncClient, session: AsyncSession, analyst, trader, admin
) -> None:
    post = await _post(client, analyst[1])
    url = f"{POSTS}/{post['id']}"
    assert (await client.patch(url, json={"title": "x"}, headers=trader[1])).status_code == 403
    res = await client.patch(url, json={"title": "BTC outlook v2"}, headers=analyst[1])
    assert res.status_code == 200 and res.json()["edited_at"] is not None
    assert (await client.patch(url, json={"title": None}, headers=analyst[1])).status_code == 422
    await session.execute(
        update(Post)
        .where(Post.id == uuid.UUID(post["id"]))
        .values(created_at=datetime.now(UTC) - timedelta(hours=25))
    )
    await session.commit()
    res = await client.patch(url, json={"body": "late"}, headers=analyst[1])
    assert res.status_code == 403 and "24 hours" in res.json()["detail"]
    assert not (await client.get(url, headers=analyst[1])).json()["can_edit"]
    assert (await client.patch(url, json={"body": "fixed"}, headers=admin[1])).status_code == 200
    assert (await client.delete(url, headers=trader[1])).status_code == 403
    assert (await client.delete(url, headers=analyst[1])).status_code == 204
    assert (await client.get(url, headers=analyst[1])).status_code == 404
    assert (await client.get(url, headers=admin[1])).json()["status"] == "deleted"
    assert (await client.get(POSTS, headers=trader[1])).json()["total"] == 0


async def test_feed_visibility_and_following(client: AsyncClient, analyst, trader, users) -> None:
    other_analyst = await users("other", UserRole.analyst)
    public = await _post(client, analyst[1], title="public")
    followers_only = await _post(client, analyst[1], title="for followers", visibility="followers")
    await _post(client, other_analyst[1], title="someone else")

    async def titles(headers, **params):
        res = await client.get(POSTS, params=params, headers=headers)
        assert res.status_code == 200, res.text
        return [p["title"] for p in res.json()["items"]]

    assert await titles(trader[1]) == ["someone else", "public"]
    assert (
        await client.get(f"{POSTS}/{followers_only['id']}", headers=trader[1])
    ).status_code == 404
    assert await titles(trader[1], scope="following") == []
    res = await client.post(f"/api/v1/users/{analyst[0].id}/follow", headers=trader[1])
    assert res.json() == {"following": True, "followers_count": 1}
    await client.post(f"/api/v1/users/{analyst[0].id}/follow", headers=trader[1])  # idempotent
    assert await titles(trader[1]) == ["someone else", "for followers", "public"]
    assert await titles(trader[1], scope="following") == ["for followers", "public"]
    assert await titles(trader[1], author_id=str(other_analyst[0].id)) == ["someone else"]
    assert await titles(analyst[1], scope="following") == []
    assert (
        await client.get(f"{POSTS}/{followers_only['id']}", headers=trader[1])
    ).status_code == 200
    res = await client.delete(f"/api/v1/users/{analyst[0].id}/follow", headers=trader[1])
    assert res.json() == {"following": False, "followers_count": 0}
    assert await titles(trader[1]) == ["someone else", "public"]
    assert public["id"]


async def test_follow_rules_and_lists(client: AsyncClient, analyst, trader, users) -> None:
    other_trader = await users("t2")
    me = trader[1]
    assert (
        await client.post(f"/api/v1/users/{trader[0].id}/follow", headers=me)
    ).status_code == 400
    assert (
        await client.post(f"/api/v1/users/{other_trader[0].id}/follow", headers=me)
    ).status_code == 400
    assert (
        await client.post(f"/api/v1/users/{uuid.uuid4()}/follow", headers=me)
    ).status_code == 404
    await client.post(f"/api/v1/users/{analyst[0].id}/follow", headers=me)
    following = (await client.get("/api/v1/me/following", headers=me)).json()
    assert [f["user"]["display_name"] for f in following["items"]] == ["Lina Analyst"]
    followers = (await client.get("/api/v1/me/followers", headers=analyst[1])).json()
    assert followers["total"] == 1 and followers["items"][0]["user"]["role"] == "trader"
    assert "email" not in str(followers)


async def test_likes_are_idempotent_and_batched(
    client: AsyncClient, session: AsyncSession, analyst, trader, users, redis_client
) -> None:
    post = await _post(client, analyst[1])
    url = f"{POSTS}/{post['id']}/like"
    assert (await client.post(url, headers=trader[1])).json() == {"liked": True, "likes_count": 1}
    assert (await client.post(url, headers=trader[1])).json() == {"liked": True, "likes_count": 1}
    others = [await users(f"fan{i}") for i in range(2)]
    for _, h in others:
        await client.post(url, headers=h)
    await client.post(url, headers=analyst[1])  # own like: counted, no notification
    assert (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).json()["likes_count"] == 4
    liked = await _notes(session, analyst[0], NotificationType.post_liked)
    assert len(liked) == 1  # one row per post and day, updated by every like
    assert liked[0].title == "أعجب 3 من المستخدمين بمنشورك"  # default language: Arabic
    assert liked[0].data["count"] == 3
    assert await session.scalar(
        select(Notification.id).where(Notification.type == NotificationType.post_liked)
    )
    # in-app only: never a delivery row
    from app.models.notification import NotificationDelivery

    assert (await session.scalars(select(NotificationDelivery))).all() == []
    assert (await client.delete(url, headers=trader[1])).json() == {
        "liked": False,
        "likes_count": 3,
    }
    assert (await client.delete(url, headers=trader[1])).json() == {
        "liked": False,
        "likes_count": 3,
    }
    assert not (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).json()["liked_by_me"]


async def test_concurrent_likes_keep_the_counter_exact(redis_client: Redis, migrated_db) -> None:
    """Twenty users like at the same moment, each on its own connection (committed data)."""
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=20, max_overflow=0)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tag = uuid.uuid4().hex[:8]
    pw = hash_password("Passw0rd123")
    try:
        async with factory() as s:
            author = User(
                email=f"author-{tag}@example.com", hashed_password=pw, role=UserRole.analyst
            )
            fans = [User(email=f"fan{i}-{tag}@example.com", hashed_password=pw) for i in range(20)]
            s.add_all([author, *fans])
            await s.commit()
            post = Post(author_id=author.id, title="t", body="b")
            s.add(post)
            await s.commit()

        async def like(fan):
            async with factory() as s:
                p = await s.get(Post, post.id)
                return await social.like(s, redis_client, fan, p)

        await asyncio.gather(*(like(f) for f in fans), *(like(f) for f in fans[:5]))
        async with factory() as s:
            stored = await s.get(Post, post.id)
            assert stored.likes_count == 20
            note = await s.scalar(select(Notification).where(Notification.user_id == author.id))
            # the batched count is recomputed by each like; concurrent ones may see a few less
            assert 1 <= note.data["count"] <= 20
    finally:
        async with factory() as s:
            await s.execute(delete(User).where(User.email.like(f"%-{tag}@example.com")))
            await s.commit()
        await engine.dispose()


# --- comments ------------------------------------------------------------------------------------


async def test_threads_depth_and_placeholders(
    client: AsyncClient, session: AsyncSession, analyst, trader, users, admin
) -> None:
    post = await _post(client, analyst[1])
    url = f"{POSTS}/{post['id']}/comments"
    top = (await client.post(url, json={"body": "Nice"}, headers=trader[1])).json()
    reply = (
        await client.post(url, json={"body": "Thanks", "parent_id": top["id"]}, headers=analyst[1])
    ).json()
    deep = (
        await client.post(
            url, json={"body": "Reply to reply", "parent_id": reply["id"]}, headers=trader[1]
        )
    ).json()
    assert reply["parent_id"] == top["id"] and deep["parent_id"] == top["id"]  # max depth 2
    second = (await client.post(url, json={"body": "Second"}, headers=trader[1])).json()
    page = (await client.get(url, headers=trader[1])).json()
    assert page["total"] == 2
    [t1, t2] = page["items"]
    assert [r["body"] for r in t1["replies"]] == ["Thanks", "Reply to reply"]
    assert (t1["replies_count"], t1["more_replies"], t2["id"]) == (2, False, second["id"])
    assert (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).json()[
        "comments_count"
    ] == 4
    # soft delete: placeholder keeps the thread readable
    assert (
        await client.delete(f"/api/v1/comments/{top['id']}", headers=analyst[1])
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/comments/{top['id']}", headers=trader[1])
    ).status_code == 204
    t1 = (await client.get(url, headers=analyst[1])).json()["items"][0]
    assert (t1["status"], t1["body"], t1["author"]) == ("deleted", None, None)
    assert len(t1["replies"]) == 2
    assert (await session.get(Comment, uuid.UUID(top["id"]))).body == ""
    assert (
        await client.post(url, json={"body": "x", "parent_id": top["id"]}, headers=trader[1])
    ).status_code == 409
    # editing: own comments any time; not someone else's
    res = await client.patch(
        f"/api/v1/comments/{second['id']}", json={"body": "Edited"}, headers=trader[1]
    )
    assert res.status_code == 200 and res.json()["edited_at"] is not None
    assert (
        await client.patch(
            f"/api/v1/comments/{second['id']}", json={"body": "no"}, headers=analyst[1]
        )
    ).status_code == 403
    assert (await client.post(url, json={"body": "<b>x</b>"}, headers=trader[1])).status_code == 422
    assert (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).json()[
        "comments_count"
    ] == 3


async def test_more_replies_are_paginated(client, analyst, trader) -> None:
    post = await _post(client, analyst[1])
    url = f"{POSTS}/{post['id']}/comments"
    top = (await client.post(url, json={"body": "top"}, headers=trader[1])).json()
    for i in range(23):
        await client.post(url, json={"body": f"r{i}", "parent_id": top["id"]}, headers=analyst[1])
    thread = (await client.get(url, headers=trader[1])).json()["items"][0]
    assert (len(thread["replies"]), thread["replies_count"], thread["more_replies"]) == (
        20,
        23,
        True,
    )
    rest = (
        await client.get(url, params={"parent_id": top["id"], "offset": 20}, headers=trader[1])
    ).json()
    assert [r["body"] for r in rest["items"]] == ["r20", "r21", "r22"] and rest["total"] == 23


async def test_comment_notifications(
    client: AsyncClient, session: AsyncSession, analyst, trader, users
) -> None:
    third = await users("third")
    post = await _post(client, analyst[1], title="ETH view")
    url = f"{POSTS}/{post['id']}/comments"
    top = (await client.post(url, json={"body": "What about ETH?"}, headers=trader[1])).json()
    [to_author] = await _notes(session, analyst[0], NotificationType.comment_reply)
    assert to_author.title == "Omar Trader علّق على منشورك"
    assert to_author.data["kind"] == "post" and to_author.data["comment_id"] == top["id"]
    # the author answers: the trader is notified, the author (commenter) is not
    await client.post(url, json={"body": "Soon", "parent_id": top["id"]}, headers=analyst[1])
    [to_trader] = await _notes(session, trader[0], NotificationType.comment_reply)
    assert to_trader.title == "Lina Analyst ردّ على تعليقك"
    assert len(await _notes(session, analyst[0], NotificationType.comment_reply)) == 1
    # a third user replies to the trader: trader (comment) and author (post) both hear
    await client.post(url, json={"body": "+1", "parent_id": top["id"]}, headers=third[1])
    assert len(await _notes(session, trader[0], NotificationType.comment_reply)) == 2
    assert len(await _notes(session, analyst[0], NotificationType.comment_reply)) == 2


async def test_new_post_fanout_to_followers(
    client: AsyncClient,
    session: AsyncSession,
    session_factory,
    redis_client,
    analyst,
    trader,
    users,
    monkeypatch,
) -> None:
    queued = []
    monkeypatch.setattr(notify, "enqueue_new_post", queued.append)
    fan2 = await users("fan2")
    for _, h in (trader, fan2):
        await client.post(f"/api/v1/users/{analyst[0].id}/follow", headers=h)
    btc = await make_instrument(session, "BTC/USDT")
    post = await _post(client, analyst[1], instrument_id=str(btc.id), direction="bearish")
    assert queued == [uuid.UUID(post["id"])]
    assert await notify.fanout_new_post(session_factory, redis_client, queued[0]) == 2
    assert await notify.fanout_new_post(session_factory, redis_client, queued[0]) == 0  # dedup
    [note] = await _notes(session, trader[0], NotificationType.new_post)
    assert note.title == "Lina Analyst نشر تحليلاً: BTC outlook"
    assert note.body.startswith("BTC/USDT · هابط")
    assert await _notes(session, analyst[0], NotificationType.new_post) == []


async def test_rate_limits(client: AsyncClient, analyst, trader, admin, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "posts_per_day", 2)
    monkeypatch.setattr(settings, "comments_per_hour", 2)
    monkeypatch.setattr(settings, "reports_per_day", 1)
    p1 = await _post(client, analyst[1])
    p2 = await _post(client, analyst[1])
    res = await client.post(POSTS, json={"title": "t", "body": "b"}, headers=analyst[1])
    assert res.status_code == 429 and int(res.headers["Retry-After"]) > 80_000
    await client.delete(f"{POSTS}/{p2['id']}", headers=analyst[1])  # deleting does not refill
    assert (
        await client.post(POSTS, json={"title": "t", "body": "b"}, headers=analyst[1])
    ).status_code == 429
    url = f"{POSTS}/{p1['id']}/comments"
    for _ in range(2):
        assert (await client.post(url, json={"body": "c"}, headers=trader[1])).status_code == 201
    assert (await client.post(url, json={"body": "c"}, headers=trader[1])).status_code == 429
    report = {"target_type": "post", "target_id": p1["id"], "reason": "spam spam"}
    assert (await client.post("/api/v1/reports", json=report, headers=trader[1])).status_code == 201
    # the same report again is not counted
    assert (await client.post("/api/v1/reports", json=report, headers=trader[1])).status_code == 200
    other = await _post(client, admin[1])
    report = {"target_type": "post", "target_id": other["id"], "reason": "spam spam"}
    assert (await client.post("/api/v1/reports", json=report, headers=trader[1])).status_code == 429


def test_create_endpoints_cost_two() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert paths["/api/v1/posts"]["post"]["x-rate-limit-cost"] == 2
    assert paths["/api/v1/posts/{post_id}/comments"]["post"]["x-rate-limit-cost"] == 2
    assert paths["/api/v1/reports"]["post"]["x-rate-limit-cost"] == 2
    assert "x-rate-limit-cost" not in paths["/api/v1/posts"]["get"]


async def test_reports_and_moderation(
    client: AsyncClient, session: AsyncSession, analyst, trader, users, admin
) -> None:
    reporter2 = await users("r2")
    post = await _post(client, analyst[1], title="Pump it")
    comment = (
        await client.post(
            f"{POSTS}/{post['id']}/comments", json={"body": "spam link"}, headers=trader[1]
        )
    ).json()
    own = {"target_type": "post", "target_id": post["id"], "reason": "mine"}
    assert (await client.post("/api/v1/reports", json=own, headers=analyst[1])).status_code == 400
    missing = {"target_type": "comment", "target_id": str(uuid.uuid4()), "reason": "xxx"}
    assert (
        await client.post("/api/v1/reports", json=missing, headers=trader[1])
    ).status_code == 404
    body = {"target_type": "post", "target_id": post["id"], "reason": "pump and dump"}
    r1 = (await client.post("/api/v1/reports", json=body, headers=trader[1])).json()
    await client.post("/api/v1/reports", json=body, headers=reporter2[1])
    c_report = (
        await client.post(
            "/api/v1/reports",
            json={"target_type": "comment", "target_id": comment["id"], "reason": "spam"},
            headers=analyst[1],
        )
    ).json()
    assert (await client.get("/api/v1/admin/reports", headers=trader[1])).status_code == 403
    listing = (await client.get("/api/v1/admin/reports", headers=admin[1])).json()
    assert listing["total"] == 3
    by_id = {r["id"]: r for r in listing["items"]}
    assert by_id[r1["id"]]["open_reports_on_target"] == 2
    assert by_id[r1["id"]]["target"]["title"] == "Pump it"
    assert by_id[r1["id"]]["reporter"]["display_name"] == "Omar Trader"
    # hide the post: both reports resolved, the author notified, the post gone from feeds
    res = await client.post(
        f"/api/v1/admin/reports/{r1['id']}/resolve",
        json={"action": "hide", "note": "market manipulation"},
        headers=admin[1],
    )
    assert res.status_code == 200 and res.json()["resolution"] == "hide"
    again = await client.post(
        f"/api/v1/admin/reports/{r1['id']}/resolve", json={"action": "dismiss"}, headers=admin[1]
    )
    assert again.status_code == 409
    assert (await client.get("/api/v1/admin/reports", headers=admin[1])).json()["total"] == 1
    assert (await client.get(POSTS, headers=trader[1])).json()["total"] == 0
    assert (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).status_code == 404
    mine = (await client.get(f"{POSTS}/{post['id']}", headers=analyst[1])).json()
    assert mine["status"] == "hidden" and not mine["can_edit"]
    assert (await client.get(POSTS, headers=analyst[1])).json()["items"][0]["status"] == "hidden"
    [hidden] = await _notes(session, analyst[0], NotificationType.content_hidden)
    assert hidden.title == "تم إخفاء منشورك من قبل الإشراف"
    assert "market manipulation" in hidden.body and hidden.severity == "warning"
    # dismiss the comment report: nothing changes
    res = await client.post(
        f"/api/v1/admin/reports/{c_report['id']}/resolve",
        json={"action": "dismiss"},
        headers=admin[1],
    )
    assert res.json()["resolution"] == "dismiss"
    assert (await session.get(Comment, uuid.UUID(comment["id"]))).status == "published"
    assert await _notes(session, trader[0], NotificationType.content_hidden) == []
    resolved = (await client.get("/api/v1/admin/reports?status=resolved", headers=admin[1])).json()
    assert resolved["total"] == 3


async def test_hidden_comment_placeholder(
    client: AsyncClient, session, analyst, trader, admin
) -> None:
    post = await _post(client, analyst[1])
    comment = (
        await client.post(
            f"{POSTS}/{post['id']}/comments", json={"body": "rude"}, headers=trader[1]
        )
    ).json()
    report = (
        await client.post(
            "/api/v1/reports",
            json={"target_type": "comment", "target_id": comment["id"], "reason": "rude"},
            headers=analyst[1],
        )
    ).json()
    await client.post(
        f"/api/v1/admin/reports/{report['id']}/resolve", json={"action": "hide"}, headers=admin[1]
    )
    url = f"{POSTS}/{post['id']}/comments"
    seen = (await client.get(url, headers=analyst[1])).json()["items"][0]
    assert (seen["status"], seen["body"]) == ("hidden", None)
    assert seen["author"]["display_name"] == "Omar Trader"
    own = (await client.get(url, headers=trader[1])).json()["items"][0]
    assert own["body"] == "rude"
    assert (await client.get(f"{POSTS}/{post['id']}", headers=trader[1])).json()[
        "comments_count"
    ] == 0
    [note] = await _notes(session, trader[0], NotificationType.content_hidden)
    assert note.data["target_type"] == "comment" and note.data["reason"] == "rude"


async def test_profile_has_no_private_data(
    client: AsyncClient, session: AsyncSession, analyst, trader
) -> None:
    author, h = analyst
    await _post(client, h, title="public one")
    await _post(client, h, title="for followers", visibility="followers")
    session.add_all(
        [
            CustomStrategy(
                user_id=author.id,
                name="Shared",
                kind="builder",
                definition={},
                definition_hash="h",
                visibility=Visibility.public,
            ),
            CustomStrategy(
                user_id=author.id,
                name="Secret",
                kind="builder",
                definition={},
                definition_hash="h",
                visibility=Visibility.private,
            ),
        ]
    )
    await session.commit()
    await client.post(f"/api/v1/users/{author.id}/follow", headers=trader[1])
    profile = (await client.get(f"/api/v1/users/{author.id}/profile", headers=trader[1])).json()
    assert profile["display_name"] == "Lina Analyst" and profile["role"] == "analyst"
    assert (profile["posts_count"], profile["followers_count"], profile["following_count"]) == (
        2,
        1,
        0,
    )
    assert profile["is_following"] and profile["followable"]
    assert [p["title"] for p in profile["recent_posts"]] == ["for followers", "public one"]
    assert [s["name"] for s in profile["public_strategies"]] == ["Shared"]
    text = str(profile)
    assert "example.com" not in text and str(trader[0].id) not in text
    assert "hashed_password" not in text and "email" not in text
    own = (await client.get(f"/api/v1/users/{trader[0].id}/profile", headers=trader[1])).json()
    assert not own["followable"]
    assert (
        await client.get(f"/api/v1/users/{uuid.uuid4()}/profile", headers=trader[1])
    ).status_code == 404


async def test_api_keys_cannot_post(client: AsyncClient, analyst) -> None:
    from tests.api_key_utils import create_key, xkey

    key = await create_key(client, analyst[1], scopes=("news:read",))
    res = await client.get(POSTS, headers=xkey(key["key"]))
    assert res.status_code == 403
