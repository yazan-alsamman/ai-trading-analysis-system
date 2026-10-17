"""Step 8: an expert plan -> demo checkout with 4242 -> trialing -> a chat message delivered over
the WebSocket -> a premium post unlocked for the subscriber and locked for others."""

import json
import uuid
from urllib.parse import urlsplit

import httpx

from tests_e2e.conftest import BASE, recv_until, run, ws_connect


def test_subscription_chat_premium(http, make_account):
    expert, trader = make_account("expert"), make_account("trader")
    analyst = make_account("analyst")
    res = http.put(
        "/me/expert-profile",
        json={"headline": "E2E expert", "markets": ["crypto"], "languages": ["en"]},
        headers=expert.h,
    )
    assert res.status_code == 200, res.text
    res = http.post(
        "/me/plans",
        json={
            "name": "E2E monthly",
            "price": "29.00",
            "interval": "month",
            "trial_days": 7,
            "perks": {"premium_posts": True, "chat": True, "signals_feed": True},
        },
        headers=expert.h,
    )
    assert res.status_code == 201, res.text
    res = http.post("/subscriptions/checkout", json={"plan_id": res.json()["id"]}, headers=trader.h)
    assert res.status_code == 201, res.text
    checkout = res.json()
    assert urlsplit(checkout["checkout_url"]).path == checkout["checkout_path"]  # absolute URL
    assert "Demo payment" in httpx.get(BASE + checkout["checkout_path"]).text
    paid = httpx.post(
        BASE + checkout["checkout_path"] + "/confirm",
        data={"card_number": "4242 4242 4242 4242", "expiry": "12/39", "cvc": "123", "name": "E2E"},
    )
    assert paid.status_code == 303 and "status=succeeded" in paid.headers["location"]
    [sub] = http.get("/me/subscriptions", headers=trader.h).json()
    assert sub["status"] == "trialing"
    res = http.post("/conversations", json={"expert_id": expert.id}, headers=trader.h)
    assert res.status_code == 201, res.text
    conv = res.json()["id"]

    async def chat() -> dict:
        async with ws_connect(trader.token) as ws:
            await ws.send(json.dumps({"op": "subscribe", "topic": "chat", "conversation_id": conv}))
            await recv_until(ws, lambda m: m.get("type") == "subscribed")
            res = http.post(
                f"/conversations/{conv}/messages",
                json={"body": "Welcome!", "client_id": str(uuid.uuid4())},
                headers=expert.h,
            )
            assert res.status_code == 201, res.text
            return await recv_until(ws, lambda m: m.get("type") == "chat_message")

    msg = run(chat())
    assert msg["message"]["body"] == "Welcome!" and msg["message"]["sender_id"] == expert.id
    res = http.post(
        "/posts",
        json={
            "title": "E2E premium",
            "body": "Full analysis for subscribers. " * 20,
            "visibility": "subscribers",
        },
        headers=expert.h,
    )
    assert res.status_code == 201, res.text
    post_id = res.json()["id"]
    assert http.get(f"/posts/{post_id}", headers=trader.h).json()["locked"] is False
    assert http.get(f"/posts/{post_id}", headers=analyst.h).json()["locked"] is True
