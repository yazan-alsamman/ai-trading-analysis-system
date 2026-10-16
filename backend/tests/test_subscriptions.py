"""Subscriptions with the demo provider: checkout -> demo page -> signed event -> webhook
handler; declined and unknown cards, expired checkouts, webhook signatures and idempotency;
renewals, failed renewals and the grace period, trial end, cancel/resume, refunds, price
changes, the fast-forward tool and the hourly task; admin views."""

import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.expert import CheckoutSession, Invoice, PaymentEvent, Subscription
from app.models.notification import Notification, NotificationType
from app.payments import service
from app.payments.entitlements import entitlements
from app.payments.provider import DemoProvider, sign
from tests.expert_utils import (
    CARD_DECLINED,
    CARD_FAIL_RENEWAL,
    make_expert,
    make_person,
    make_plan,
    page_title,
    pay,
    start_checkout,
    subscribe,
)

SUBS = "/api/v1/me/subscriptions"
WEBHOOK = "/api/v1/payments/webhook/demo"


@pytest.fixture
async def expert(client, make_user, session):
    return await make_expert(client, make_user, session, full_name="Sami Expert")


@pytest.fixture
async def trader(make_user, session):
    return await make_person(make_user, session, "trader", full_name="Omar Trader")


async def _types(session: AsyncSession, user) -> list[str]:
    rows = await session.scalars(
        select(Notification.type)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at)
    )
    return [str(t) for t in rows]


async def _sub(session: AsyncSession, sub_id) -> Subscription:
    return await session.get(Subscription, uuid.UUID(str(sub_id)), populate_existing=True)


async def _ff(client, admin_headers, sub_id, to="period_end"):
    res = await client.post(
        f"/api/v1/admin/subscriptions/{sub_id}/fast-forward", json={"to": to}, headers=admin_headers
    )
    assert res.status_code == 200, res.text
    return res.json()


# --- checkout ------------------------------------------------------------------------------------


async def test_checkout_trial_flow(
    client: AsyncClient, session: AsyncSession, expert, trader
) -> None:
    expert_user, eh = expert
    user, th = trader
    plan = await make_plan(client, eh, trial_days=7)
    checkout = await start_checkout(client, th, plan["id"])
    assert checkout["checkout_url"] == checkout["checkout_path"]  # no PUBLIC_BASE_URL
    assert checkout["checkout_path"] == f"/api/v1/pay/demo/{checkout['checkout_id']}"
    page = await client.get(checkout["checkout_path"])
    assert page.status_code == 200 and page_title(page.text) == "Demo payment — no real money"
    assert "Free for 7 days, then 29.00 USD / month" in page.text
    res = await pay(client, checkout)
    assert res.status_code == 303
    assert res.headers["location"] == (
        f"/api/v1/pay/demo/{checkout['checkout_id']}/done"
        f"?checkout_id={checkout['checkout_id']}&status=succeeded"
    )
    done = await client.get(res.headers["location"])
    assert "Payment successful" in done.text and "trialing" in done.text
    [sub] = (await client.get(SUBS, headers=th)).json()
    assert (sub["status"], sub["price"], sub["interval"]) == ("trialing", "29.00", "month")
    assert sub["payment_method"] == {"brand": "visa", "last4": "4242", "behavior": "ok"}
    assert "4242424242424242" not in json.dumps(sub)
    period = datetime.fromisoformat(sub["current_period_end"]) - datetime.fromisoformat(
        sub["current_period_start"]
    )
    assert period == timedelta(days=7) and sub["next_charge_at"] == sub["current_period_end"]
    [invoice] = sub["invoices"]
    assert (invoice["kind"], invoice["amount"], invoice["status"]) == ("trial", "0.00", "paid")
    assert invoice["number"].startswith(f"INV-{datetime.now(UTC).year}-")
    assert await _types(session, user) == ["subscription_started"]
    assert await _types(session, expert_user) == ["new_subscriber"]
    row = await session.get(CheckoutSession, uuid.UUID(checkout["checkout_id"]))
    assert (row.status, row.subscription_id) == ("completed", uuid.UUID(sub["id"]))
    # the same page again: already paid
    again = await pay(client, checkout)
    assert again.status_code == 409 and "Already paid" in again.text
    # one live subscription per expert
    res = await client.post(
        "/api/v1/subscriptions/checkout", json={"plan_id": plan["id"]}, headers=th
    )
    assert res.status_code == 409


async def test_declined_unknown_and_expired(
    client: AsyncClient, session: AsyncSession, expert, trader
) -> None:
    _, eh = expert
    _, th = trader
    plan = await make_plan(client, eh)
    checkout = await start_checkout(client, th, plan["id"])
    bad = await pay(client, checkout, "1234 5678 9012 3456")
    assert bad.status_code == 422 and "Unknown card" in bad.text
    bad = await pay(client, checkout, expiry="01/20")
    assert bad.status_code == 422 and "expiry" in bad.text
    res = await pay(client, checkout, CARD_DECLINED)
    assert res.status_code == 303 and res.headers["location"].endswith("status=failed")
    assert "card_declined" in (await client.get(res.headers["location"])).text
    assert (await client.get(SUBS, headers=th)).json() == []
    row = await session.get(CheckoutSession, uuid.UUID(checkout["checkout_id"]))
    assert (row.status, row.failure_reason) == ("canceled", "card_declined")
    # expired: 30 minutes later
    checkout = await start_checkout(client, th, plan["id"])
    await session.execute(
        update(CheckoutSession)
        .where(CheckoutSession.id == uuid.UUID(checkout["checkout_id"]))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()
    page = await client.get(checkout["checkout_path"])
    assert page.status_code == 409 and "Checkout expired" in page.text
    assert (await pay(client, checkout)).status_code == 409
    assert (await client.get(SUBS, headers=th)).json() == []


async def test_checkout_rules(client: AsyncClient, expert, trader, monkeypatch) -> None:
    expert_user, eh = expert
    _, th = trader
    plan = await make_plan(client, eh)
    own = await client.post(
        "/api/v1/subscriptions/checkout", json={"plan_id": plan["id"]}, headers=eh
    )
    assert own.status_code == 400  # no self-subscription
    missing = await client.post(
        "/api/v1/subscriptions/checkout", json={"plan_id": str(uuid.uuid4())}, headers=th
    )
    assert missing.status_code == 404
    evil = await client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_id": plan["id"], "return_url": "https://evil.example/steal"},
        headers=th,
    )
    assert evil.status_code == 422
    settings = get_settings()
    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173")
    monkeypatch.setattr(settings, "public_base_url", "http://187.127.76.76:8080")
    checkout = await start_checkout(
        client, th, plan["id"], return_url="http://localhost:5173/billing/done"
    )
    assert checkout["checkout_url"] == (
        f"http://187.127.76.76:8080/api/v1/pay/demo/{checkout['checkout_id']}"
    )
    res = await pay(client, checkout)
    assert res.headers["location"].startswith("http://localhost:5173/billing/done?checkout_id=")
    await client.patch(f"/api/v1/me/plans/{plan['id']}", json={"is_active": False}, headers=eh)
    res = await client.post(
        "/api/v1/subscriptions/checkout", json={"plan_id": plan["id"]}, headers=th
    )
    assert res.status_code == 404  # inactive plan


# --- webhook -------------------------------------------------------------------------------------


async def test_webhook_signature_and_idempotency(
    client: AsyncClient, session: AsyncSession, expert, trader
) -> None:
    _, eh = expert
    user, th = trader
    plan = await make_plan(client, eh)
    checkout = await start_checkout(client, th, plan["id"])
    provider = DemoProvider()
    data = {
        "checkout_id": checkout["checkout_id"],
        "payment_method": {"brand": "visa", "last4": "4242", "behavior": "ok"},
        "charge_ref": "demo_ch_x",
    }
    body, headers = await provider.event("checkout.completed", data)
    # tampered body, wrong secret, old timestamp: 401
    tampered = body.replace(b"4242", b"0000")
    assert (await client.post(WEBHOOK, content=tampered, headers=headers)).status_code == 401
    bad = {"Demo-Signature": sign("wrong-secret", body)}
    assert (await client.post(WEBHOOK, content=body, headers=bad)).status_code == 401
    from app.payments.provider import demo_secret

    old = {"Demo-Signature": sign(await demo_secret(), body, int(time.time()) - 3600)}
    res = await client.post(WEBHOOK, content=body, headers=old)
    assert res.status_code == 401 and "tolerance" in res.json()["detail"]
    assert (await client.post(WEBHOOK, content=body)).status_code == 401  # no header
    assert (
        await client.post("/api/v1/payments/webhook/stripe", content=body, headers=headers)
    ).status_code == 404
    # valid, then the same event again: processed once
    first = await client.post(WEBHOOK, content=body, headers=headers)
    second = await client.post(WEBHOOK, content=body, headers=headers)
    assert first.json()["status"] == "processed" and second.json()["status"] == "duplicate"
    assert len((await client.get(SUBS, headers=th)).json()) == 1
    assert len((await session.scalars(select(PaymentEvent))).all()) == 1
    # a different event for the same checkout changes nothing either (checkout completed)
    body2, headers2 = await provider.event("checkout.completed", data)
    assert (await client.post(WEBHOOK, content=body2, headers=headers2)).json()["status"] == (
        "processed"
    )
    assert len((await client.get(SUBS, headers=th)).json()) == 1


# --- renewals ------------------------------------------------------------------------------------


async def test_renewal_success_and_fees(
    client: AsyncClient, session: AsyncSession, expert, trader, admin_headers
) -> None:
    _, eh = expert
    user, th = trader
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"])
    assert sub["status"] == "active"
    [initial] = sub["invoices"]
    assert (initial["kind"], initial["amount"]) == ("initial", "29.00")
    row = await session.scalar(select(Invoice).where(Invoice.id == uuid.UUID(initial["id"])))
    assert (row.platform_fee, row.expert_amount) == (Decimal("5.80"), Decimal("23.20"))
    old_end = sub["current_period_end"]
    result = await _ff(client, admin_headers, sub["id"])
    assert result["outcome"] == "renewed" and result["subscription"]["status"] == "active"
    [sub] = (await client.get(SUBS, headers=th)).json()
    renewal = sub["invoices"][0]
    assert (renewal["kind"], renewal["status"], renewal["amount"]) == ("renewal", "paid", "29.00")
    start = datetime.fromisoformat(sub["current_period_start"])
    end = datetime.fromisoformat(sub["current_period_end"])
    # fast-forward ended the period now: the new one starts now and lasts a calendar month
    assert abs(start - datetime.now(UTC)) < timedelta(minutes=1)
    assert (end.month - start.month) % 12 == 1 and old_end
    assert "subscription_renewed" in await _types(session, user)


async def test_failed_renewal_grace_then_expired(
    client: AsyncClient, session: AsyncSession, expert, trader, admin_headers
) -> None:
    expert_user, eh = expert
    user, th = trader
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"], CARD_FAIL_RENEWAL)
    assert sub["status"] == "active"  # 9995: succeeds now
    result = await _ff(client, admin_headers, sub["id"])
    assert result["outcome"] == "past_due"
    [sub] = (await client.get(SUBS, headers=th)).json()
    failed = sub["invoices"][0]
    assert (failed["status"], failed["failure_reason"]) == (
        "failed",
        "card_declined: insufficient funds",
    )
    assert sub["status"] == "past_due" and sub["grace_ends_at"] is not None
    grace = datetime.fromisoformat(sub["grace_ends_at"]) - datetime.now(UTC)
    assert timedelta(days=2, hours=23) < grace <= timedelta(days=3)
    # still entitled during the grace period
    assert (await entitlements(session, user, expert_user.id))["chat"] is True
    note = await session.scalar(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == NotificationType.subscription_payment_failed,
        )
    )
    assert note.severity == "warning" and "insufficient funds" in note.body
    result = await _ff(client, admin_headers, sub["id"], "grace_end")
    assert result["outcome"] == "expired" and result["subscription"]["status"] == "expired"
    assert (await entitlements(session, user, expert_user.id))["chat"] is False
    assert (await _types(session, user))[-1] == "subscription_canceled"
    # ended: a new checkout is possible again
    await start_checkout(client, th, plan["id"])


async def test_invoice_payment_failed_event(
    client: AsyncClient, session: AsyncSession, expert, trader
) -> None:
    _, eh = expert
    user, th = trader
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"])
    row = await _sub(session, sub["id"])
    invoice = Invoice(
        number="INV-TEST-000001",
        subscription_id=row.id,
        user_id=row.user_id,
        expert_id=row.expert_id,
        kind="renewal",
        amount=row.price,
        currency="USD",
        status="open",
        period_start=row.current_period_end,
        period_end=row.current_period_end + timedelta(days=30),
        provider="demo",
    )
    session.add(invoice)
    await session.commit()
    body, headers = await DemoProvider().event(
        "invoice.payment_failed", {"invoice_id": str(invoice.id), "reason": "expired_card"}
    )
    assert (await client.post(WEBHOOK, content=body, headers=headers)).status_code == 200
    row = await _sub(session, sub["id"])
    assert row.status == "past_due"
    await session.refresh(invoice)
    assert (invoice.status, invoice.failure_reason) == ("failed", "expired_card")


async def test_trial_end_charges_the_plan(
    client: AsyncClient, expert, trader, admin_headers
) -> None:
    _, eh = expert
    _, th = trader
    plan = await make_plan(client, eh, trial_days=7, price="99.00", interval="year")
    sub = await subscribe(client, th, plan["id"])
    assert sub["status"] == "trialing"
    assert (await _ff(client, admin_headers, sub["id"]))["outcome"] == "renewed"
    [sub] = (await client.get(SUBS, headers=th)).json()
    assert sub["status"] == "active" and sub["invoices"][0]["amount"] == "99.00"
    start = datetime.fromisoformat(sub["current_period_start"])
    end = datetime.fromisoformat(sub["current_period_end"])
    assert end.year == start.year + 1 and (end.month, end.day) == (start.month, start.day)


async def test_cancel_resume_and_end(
    client: AsyncClient, session: AsyncSession, expert, trader, admin_headers
) -> None:
    expert_user, eh = expert
    user, th = trader
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"])
    url = f"{SUBS}/{sub['id']}"
    res = await client.post(f"{url}/cancel", headers=th)
    assert res.json()["cancel_at_period_end"] is True and res.json()["next_charge_at"] is None
    assert res.json()["status"] == "active"  # access until the period ends
    res = await client.post(f"{url}/resume", headers=th)
    assert res.json()["cancel_at_period_end"] is False and res.json()["next_charge_at"]
    await client.post(f"{url}/cancel", headers=th)
    result = await _ff(client, admin_headers, sub["id"])
    assert result["outcome"] == "canceled" and result["subscription"]["ended_at"]
    [sub] = (await client.get(SUBS, headers=th)).json()
    assert sub["status"] == "canceled" and len(sub["invoices"]) == 1  # nothing charged
    assert (await client.post(f"{url}/resume", headers=th)).status_code == 409
    assert (await client.post(f"{url}/cancel", headers=eh)).status_code == 404  # not yours
    assert (await entitlements(session, user, expert_user.id))["premium_posts"] is False


async def test_refund_ends_access(
    client: AsyncClient, session: AsyncSession, expert, trader, admin_headers
) -> None:
    expert_user, eh = expert
    user, th = trader
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"])
    invoice_id = sub["invoices"][0]["id"]
    assert (
        await client.post(f"/api/v1/admin/invoices/{invoice_id}/refund", headers=th)
    ).status_code == 403
    res = await client.post(f"/api/v1/admin/invoices/{invoice_id}/refund", headers=admin_headers)
    assert res.status_code == 200 and res.json()["status"] == "refunded"
    [sub] = (await client.get(SUBS, headers=th)).json()
    assert sub["status"] == "canceled" and sub["ended_at"]
    assert (await entitlements(session, user, expert_user.id))["chat"] is False
    note = await session.scalar(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == NotificationType.subscription_canceled,
        )
    )
    assert "استرداد" in note.body and "INV-" in note.body  # default language: Arabic
    again = await client.post(f"/api/v1/admin/invoices/{invoice_id}/refund", headers=admin_headers)
    assert again.status_code == 409


async def test_price_change_keeps_existing_price(
    client: AsyncClient, make_user, session, expert, trader, admin_headers
) -> None:
    _, eh = expert
    _, th = trader
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"])
    res = await client.patch(f"/api/v1/me/plans/{plan['id']}", json={"price": "39.00"}, headers=eh)
    assert res.json()["price"] == "39.00"
    assert (await client.get(SUBS, headers=th)).json()[0]["price"] == "29.00"
    _, nh = await make_person(make_user, session, "newcomer")
    assert (await subscribe(client, nh, plan["id"]))["price"] == "39.00"
    # the existing subscription moves to the new price at its next renewal
    await _ff(client, admin_headers, sub["id"])
    [renewed] = (await client.get(SUBS, headers=th)).json()
    assert renewed["price"] == "39.00" and renewed["invoices"][0]["amount"] == "39.00"


async def test_fast_forward_is_demo_only(
    client: AsyncClient, expert, trader, admin_headers, monkeypatch
) -> None:
    _, eh = expert
    _, th = trader
    sub = await subscribe(client, th, (await make_plan(client, eh))["id"])
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    url = f"/api/v1/admin/subscriptions/{sub['id']}/fast-forward"
    res = await client.post(url, json={}, headers=admin_headers)
    assert res.status_code == 403 and "disabled in production" in res.json()["detail"]
    monkeypatch.setattr(settings, "payment_demo_tools", True)
    assert (await client.post(url, json={}, headers=admin_headers)).status_code == 200
    assert (await client.post(url, json={}, headers=th)).status_code == 403  # admins only


async def test_hourly_task(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client, expert, trader
) -> None:
    _, eh = expert
    _, th = trader
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"])
    await session.execute(
        update(Subscription)
        .where(Subscription.id == uuid.UUID(sub["id"]))
        .values(current_period_end=datetime.now(UTC) - timedelta(minutes=5))
    )
    session.add(
        CheckoutSession(
            user_id=(await _sub(session, sub["id"])).user_id,
            plan_id=uuid.UUID(plan["id"]),
            provider="demo",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    await session.commit()
    counts = await service.renew_due(session_factory, redis_client)
    assert counts == {"renewed": 1, "checkouts_expired": 1}
    assert await service.renew_due(session_factory, redis_client) == {}
    assert (await _sub(session, sub["id"])).status == "active"


async def test_admin_views(client: AsyncClient, expert, trader, admin_headers) -> None:
    expert_user, eh = expert
    _, th = trader
    plan = await make_plan(client, eh)
    sub = await subscribe(client, th, plan["id"], CARD_FAIL_RENEWAL)
    await _ff(client, admin_headers, sub["id"])
    page = (
        await client.get(
            "/api/v1/admin/subscriptions",
            params={"status": "past_due", "expert_id": str(expert_user.id)},
            headers=admin_headers,
        )
    ).json()
    assert page["total"] == 1 and page["items"][0]["user"]["display_name"] == "Omar Trader"
    assert "email" not in json.dumps(page)
    stats = (await client.get("/api/v1/admin/payments/stats", headers=admin_headers)).json()
    assert stats["invoices"]["paid"] == {"count": 1, "amount": "29.00"}
    assert stats["invoices"]["failed"] == {"count": 1, "amount": "29.00"}
    assert stats["platform_fees"] == "5.80" and stats["subscriptions"]["past_due"] == 1
    assert stats["mrr"] == "29.00"
    assert (await client.get("/api/v1/admin/payments/stats", headers=th)).status_code == 403
