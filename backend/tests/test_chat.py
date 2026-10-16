"""Expert chat: rights (subscribers with the chat perk, read-only after the end, block),
sending, client_id idempotency, history pagination, edit window, tombstones, read markers and
unread counts, input rules, rate limits, reports; the WebSocket topic (authorization, live
messages, typing and its rate limit); notifications only when away, collapsed per 5 minutes."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import presence
from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.chat import Message
from app.models.notification import Notification, NotificationType
from app.models.user import UserRole
from app.realtime.hub import WebSocketHub
from tests.expert_utils import make_expert, make_person, make_plan, new_client_id, subscribe
from tests.ws_utils import recv_until, ws_connect

CONV = "/api/v1/conversations"


@pytest.fixture
async def setup(client: AsyncClient, make_user, session: AsyncSession):
    """An expert with a chat plan, a subscriber with an open conversation."""
    expert, eh = await make_expert(client, make_user, session, full_name="Sami Expert")
    trader, th = await make_person(make_user, session, "trader", full_name="Omar Trader")
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"])
    res = await client.post(CONV, json={"expert_id": str(expert.id)}, headers=th)
    assert res.status_code == 201, res.text
    return {
        "expert": expert,
        "eh": eh,
        "trader": trader,
        "th": th,
        "conv": res.json(),
        "sub": sub,
        "plan": plan,
    }


async def _send(client, conv_id, headers, body="hello", client_id=None, **extra):
    return await client.post(
        f"{CONV}/{conv_id}/messages",
        json={"body": body, "client_id": client_id or new_client_id(), **extra},
        headers=headers,
    )


async def _notes(session: AsyncSession, user) -> list[Notification]:
    rows = await session.scalars(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.type == NotificationType.chat_message)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


# --- rights --------------------------------------------------------------------------------------


async def test_who_can_open(client: AsyncClient, make_user, session, setup) -> None:
    expert = setup["expert"]
    _, stranger = await make_person(make_user, session, "stranger")
    res = await client.post(CONV, json={"expert_id": str(expert.id)}, headers=stranger)
    assert res.status_code == 403 and "chat perk" in res.json()["detail"]
    again = await client.post(CONV, json={"expert_id": str(expert.id)}, headers=setup["th"])
    assert again.status_code == 200 and again.json()["id"] == setup["conv"]["id"]
    conv = setup["conv"]
    assert (conv["my_role"], conv["can_send"], conv["other"]["display_name"]) == (
        "subscriber",
        True,
        "Sami Expert",
    )
    # a plan without the chat perk
    posts_only = await make_plan(
        client, setup["eh"], name="Posts", perks={"premium_posts": True, "chat": False}
    )
    _, ph = await make_person(make_user, session, "reader")
    await subscribe(client, ph, posts_only["id"])
    assert (
        await client.post(CONV, json={"expert_id": str(expert.id)}, headers=ph)
    ).status_code == 403
    # an expert who does not take chats
    other, oh = await make_expert(client, make_user, session, "quiet", chat_enabled=False)
    plan = await make_plan(client, oh)
    await subscribe(client, ph, plan["id"])
    assert (
        await client.post(CONV, json={"expert_id": str(other.id)}, headers=ph)
    ).status_code == 403
    assert (
        await client.post(CONV, json={"expert_id": str(uuid.uuid4())}, headers=ph)
    ).status_code == 404
    # a stranger cannot read it
    assert (
        await client.get(f"{CONV}/{setup['conv']['id']}/messages", headers=stranger)
    ).status_code == 404


async def test_send_history_idempotency_and_pagination(client: AsyncClient, setup) -> None:
    cid = setup["conv"]["id"]
    client_id = new_client_id()
    first = await _send(client, cid, setup["th"], "first", client_id)
    assert first.status_code == 201 and first.json()["client_id"] == client_id
    retry = await _send(client, cid, setup["th"], "first (retried)", client_id)
    assert retry.status_code == 200 and retry.json()["id"] == first.json()["id"]
    assert retry.json()["body"] == "first"
    for i in range(4):
        who = setup["eh"] if i % 2 else setup["th"]
        assert (await _send(client, cid, who, f"m{i}")).status_code == 201
    page = (await client.get(f"{CONV}/{cid}/messages?limit=2", headers=setup["eh"])).json()
    assert [m["body"] for m in page["items"]] == ["m3", "m2"] and page["next_before"]
    assert page["items"][0]["client_id"] is not None  # the expert sent m3
    assert page["items"][1]["client_id"] is None  # not the viewer's
    page = (
        await client.get(
            f"{CONV}/{cid}/messages", params={"before": page["next_before"]}, headers=setup["eh"]
        )
    ).json()
    assert [m["body"] for m in page["items"]] == ["m1", "m0", "first"]
    assert page["next_before"] is None
    for bad in ("<b>bold</b>", "[x](javascript:alert(1))", "", "x" * 4001):
        assert (await _send(client, cid, setup["th"], bad)).status_code == 422


async def test_edit_window_and_tombstones(client: AsyncClient, session, setup) -> None:
    cid = setup["conv"]["id"]
    msg = (await _send(client, cid, setup["th"], "typo")).json()
    res = await client.patch(
        f"/api/v1/messages/{msg['id']}", json={"body": "fixed"}, headers=setup["th"]
    )
    assert res.status_code == 200 and res.json()["edited_at"] and res.json()["body"] == "fixed"
    assert (
        await client.patch(f"/api/v1/messages/{msg['id']}", json={"body": "x"}, headers=setup["eh"])
    ).status_code == 403
    await session.execute(
        update(Message)
        .where(Message.id == uuid.UUID(msg["id"]))
        .values(created_at=datetime.now(UTC) - timedelta(minutes=16))
    )
    await session.commit()
    res = await client.patch(
        f"/api/v1/messages/{msg['id']}", json={"body": "late"}, headers=setup["th"]
    )
    assert res.status_code == 403 and "15 minutes" in res.json()["detail"]
    assert (
        await client.delete(f"/api/v1/messages/{msg['id']}", headers=setup["eh"])
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/messages/{msg['id']}", headers=setup["th"])
    ).status_code == 204
    [tomb] = (await client.get(f"{CONV}/{cid}/messages", headers=setup["eh"])).json()["items"]
    assert (tomb["deleted"], tomb["body"], tomb["id"]) == (True, None, msg["id"])
    assert (await session.get(Message, uuid.UUID(msg["id"]), populate_existing=True)).body == ""


async def test_read_markers_and_unread(client: AsyncClient, setup) -> None:
    cid = setup["conv"]["id"]
    for i in range(3):
        await _send(client, cid, setup["th"], f"q{i}")
    [conv] = (await client.get(CONV, headers=setup["eh"])).json()
    assert (conv["unread"], conv["my_role"], conv["last_message"]["excerpt"]) == (3, "expert", "q2")
    assert conv["other"]["display_name"] == "Omar Trader"
    [mine] = (await client.get(CONV, headers=setup["th"])).json()
    assert mine["unread"] == 0  # own messages are never unread
    page = (await client.get(f"{CONV}/{cid}/messages", headers=setup["eh"])).json()
    res = await client.post(
        f"{CONV}/{cid}/read", json={"message_id": page["items"][1]["id"]}, headers=setup["eh"]
    )
    assert res.status_code == 200
    assert (await client.get(CONV, headers=setup["eh"])).json()[0]["unread"] == 1
    await client.post(f"{CONV}/{cid}/read", headers=setup["eh"])
    assert (await client.get(CONV, headers=setup["eh"])).json()[0]["unread"] == 0
    # markers never move back
    await client.post(
        f"{CONV}/{cid}/read", json={"message_id": page["items"][2]["id"]}, headers=setup["eh"]
    )
    assert (await client.get(CONV, headers=setup["eh"])).json()[0]["unread"] == 0
    assert (await client.get(CONV, headers=setup["th"])).json()[0]["other_last_read_at"]


async def test_read_only_after_the_subscription_ends(
    client: AsyncClient, setup, admin_headers
) -> None:
    cid = setup["conv"]["id"]
    await _send(client, cid, setup["th"], "before")
    invoice = setup["sub"]["invoices"][0]["id"]
    await client.post(f"/api/v1/admin/invoices/{invoice}/refund", headers=admin_headers)
    res = await _send(client, cid, setup["th"], "after")
    assert res.status_code == 403 and "read only" in res.json()["detail"]
    conv = (await client.get(f"{CONV}/{cid}", headers=setup["th"])).json()
    assert conv["can_send"] is False and "ended" in conv["read_only_reason"]
    assert (
        len((await client.get(f"{CONV}/{cid}/messages", headers=setup["th"])).json()["items"]) == 1
    )
    assert (await _send(client, cid, setup["eh"], "the expert can still reply")).status_code == 201
    # admins read every conversation but do not write
    assert (await client.get(f"{CONV}/{cid}/messages", headers=admin_headers)).status_code == 200
    assert (await _send(client, cid, admin_headers, "hi")).status_code == 403


async def test_block_and_admin_list(client: AsyncClient, setup, admin_headers) -> None:
    cid = setup["conv"]["id"]
    res = await client.post(f"{CONV}/{cid}/block", headers=setup["eh"])
    assert res.json()["status"] == "blocked" and res.json()["blocked_by_me"]
    for h in (setup["th"], setup["eh"]):
        assert (await _send(client, cid, h)).status_code == 403
    assert (await client.post(f"{CONV}/{cid}/unblock", headers=setup["th"])).status_code == 403
    blocked = (
        await client.get("/api/v1/admin/conversations?status=blocked", headers=admin_headers)
    ).json()
    assert blocked["total"] == 1 and blocked["items"][0]["expert"]["display_name"] == "Sami Expert"
    assert (await client.get("/api/v1/admin/conversations", headers=setup["th"])).status_code == 403
    assert (await client.post(f"{CONV}/{cid}/unblock", headers=setup["eh"])).json()[
        "status"
    ] == "open"
    assert (await _send(client, cid, setup["th"])).status_code == 201


async def test_report_and_hide_a_message(
    client: AsyncClient, session, setup, admin_headers, make_user
) -> None:
    cid = setup["conv"]["id"]
    msg = (await _send(client, cid, setup["eh"], "buy my course at scam.example")).json()
    report = {"target_type": "message", "target_id": msg["id"], "reason": "spam link"}
    _, stranger = await make_person(make_user, session, "stranger")
    assert (await client.post("/api/v1/reports", json=report, headers=stranger)).status_code == 404
    assert (
        await client.post("/api/v1/reports", json=report, headers=setup["eh"])
    ).status_code == 400
    res = await client.post("/api/v1/reports", json=report, headers=setup["th"])
    assert res.status_code == 201
    listing = (await client.get("/api/v1/admin/reports", headers=admin_headers)).json()
    [item] = listing["items"]
    assert item["target"]["conversation_id"] == cid and "scam" in item["target"]["excerpt"]
    await client.post(
        f"/api/v1/admin/reports/{res.json()['id']}/resolve",
        json={"action": "hide"},
        headers=admin_headers,
    )
    [tomb] = (await client.get(f"{CONV}/{cid}/messages", headers=setup["th"])).json()["items"]
    assert tomb["deleted"] and tomb["body"] is None
    note = await session.scalar(
        select(Notification).where(
            Notification.user_id == setup["expert"].id,
            Notification.type == NotificationType.content_hidden,
        )
    )
    assert note.title == "تم إخفاء رسالتك في المحادثة من قبل الإشراف"


async def test_rate_limits(client: AsyncClient, setup, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "chat_messages_per_minute", 3)
    cid = setup["conv"]["id"]
    codes = [(await _send(client, cid, setup["th"], f"m{i}")).status_code for i in range(4)]
    if codes[-1] == 201:  # the minute changed in between: one more try in the new minute
        codes = [(await _send(client, cid, setup["th"], f"n{i}")).status_code for i in range(4)]
    assert 429 in codes
    res = await _send(client, cid, setup["th"], "again")
    assert res.status_code == 429 and int(res.headers["Retry-After"]) <= 60
    monkeypatch.setattr(settings, "chat_messages_per_minute", 1000)
    monkeypatch.setattr(settings, "chat_messages_per_day", 1)
    res = await _send(client, cid, setup["eh"], "expert")
    assert res.status_code in (201, 429)
    res = await _send(client, cid, setup["eh"], "expert 2")
    assert res.status_code == 429 and "per day" in res.json()["detail"]


# --- notifications -------------------------------------------------------------------------------


async def test_notification_only_when_away_and_collapsed(
    client: AsyncClient, session: AsyncSession, setup, redis_client: Redis
) -> None:
    cid = setup["conv"]["id"]
    trader = setup["trader"]
    await _send(client, cid, setup["eh"], "Hi Omar, welcome!")
    [note] = await _notes(session, trader)
    assert note.title == "رسالة جديدة من Sami Expert" and note.data["count"] == 1
    assert note.body == "Hi Omar, welcome!"
    # within 5 minutes: the same inbox row is updated (no new notification, no new delivery)
    await _send(client, cid, setup["eh"], "Here is the plan")
    await _send(client, cid, setup["eh"], "And the levels")
    [note] = await _notes(session, trader)
    assert note.data["count"] == 3 and note.title == "رسائل جديدة من Sami Expert: 3"
    assert note.read_at is None and note.data["excerpt"] == "And the levels"
    # while the trader looks at the conversation: nothing
    await presence.mark(redis_client, cid, trader.id)
    await redis_client.delete(f"chat:notify:{cid}:{trader.id}")
    await _send(client, cid, setup["eh"], "while you are here")
    assert len(await _notes(session, trader)) == 1
    await presence.clear(redis_client, cid, trader.id)
    # away again, window over: a new notification
    await _send(client, cid, setup["eh"], "are you there?")
    assert len(await _notes(session, trader)) == 2
    # the sender never gets one
    assert await _notes(session, setup["expert"]) == []


# --- WebSocket -----------------------------------------------------------------------------------


async def test_websocket_topic_messages_typing_presence(
    client: AsyncClient, session, setup, hub: WebSocketHub, make_user, redis_client
) -> None:
    cid = setup["conv"]["id"]
    expert, trader = setup["expert"], setup["trader"]
    stranger, _ = await make_person(make_user, session, "stranger")
    sub = {"op": "subscribe", "topic": "chat", "conversation_id": cid}
    async with ws_connect(create_access_token(stranger)) as ws:
        await ws.send_json(sub)
        err = await recv_until(ws, lambda m: m["type"] == "error")
        assert err["code"] == "forbidden"
        await ws.send_json({"op": "typing", "conversation_id": cid})
        assert (await recv_until(ws, lambda m: m["type"] == "error"))["code"] == "forbidden"
    async with (
        ws_connect(create_access_token(trader)) as tws,
        ws_connect(create_access_token(expert)) as ews,
    ):
        for ws in (tws, ews):
            await ws.send_json(sub)
            assert (await recv_until(ws, lambda m: m["type"] == "subscribed"))["topic"] == (
                f"chat:{cid}"
            )
        assert await presence.present(redis_client, cid, trader.id)
        res = await _send(client, cid, setup["eh"], "live!")
        live = await recv_until(tws, lambda m: m["type"] == "chat_message")
        assert live["message"]["id"] == res.json()["id"] and live["message"]["body"] == "live!"
        assert live["topic"] == f"chat:{cid}"
        # the trader is looking: no notification
        assert await _notes(session, trader) == []
        # typing: once per 3 s
        await tws.send_json({"op": "typing", "conversation_id": cid})
        await tws.send_json({"op": "typing", "conversation_id": cid})
        typing = await recv_until(ews, lambda m: m["type"] == "chat_typing")
        assert typing["user_id"] == str(trader.id)
        await client.post(f"{CONV}/{cid}/read", headers=setup["th"])
        read = await recv_until(ews, lambda m: m["type"] == "chat_read")
        assert read["user_id"] == str(trader.id)
        typings = await redis_client.exists(f"chat:typing:{cid}:{trader.id}")
        assert typings == 1
        msg_id = res.json()["id"]
        await client.patch(
            f"/api/v1/messages/{msg_id}", json={"body": "live (edited)"}, headers=setup["eh"]
        )
        upd = await recv_until(tws, lambda m: m["type"] == "chat_message_updated")
        assert upd["message"]["body"] == "live (edited)"
    # disconnected: presence cleared, the next message notifies
    assert not await presence.present(redis_client, cid, trader.id)
    await _send(client, cid, setup["eh"], "after you left")
    assert len(await _notes(session, trader)) == 1
    count = await session.scalar(select(func.count()).select_from(Message))
    assert count == 2


async def test_typing_rate_limit_counts_one(client, session, setup, hub, redis_client) -> None:
    cid = setup["conv"]["id"]
    sub = {"op": "subscribe", "topic": "chat", "conversation_id": cid}
    async with (
        ws_connect(create_access_token(setup["trader"])) as tws,
        ws_connect(create_access_token(setup["expert"])) as ews,
    ):
        for ws in (tws, ews):
            await ws.send_json(sub)
            await recv_until(ws, lambda m: m["type"] == "subscribed")
        for _ in range(5):
            await tws.send_json({"op": "typing", "conversation_id": cid})
        await recv_until(ews, lambda m: m["type"] == "chat_typing")
        await _send(client, cid, setup["eh"], "marker")
        seen = []
        while True:
            msg = await recv_until(ews, lambda m: m["type"] in ("chat_typing", "chat_message"))
            if msg["type"] == "chat_message":
                break
            seen.append(msg)
        assert seen == []  # the other four typing events were dropped


async def test_admin_may_watch(client, session, setup, hub, make_user) -> None:
    admin, _ = await make_person(make_user, session, "boss", UserRole.admin)
    async with ws_connect(create_access_token(admin)) as ws:
        await ws.send_json(
            {"op": "subscribe", "topic": "chat", "conversation_id": setup["conv"]["id"]}
        )
        assert (await recv_until(ws, lambda m: m["type"] in ("subscribed", "error")))["type"] == (
            "subscribed"
        )
