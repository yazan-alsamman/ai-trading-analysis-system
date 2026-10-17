"""Helpers for the Y19 tests: experts with a profile and plans, subscribers through the real
demo checkout (page form -> signed event -> webhook handler)."""

import re
import uuid

from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import UserRole
from tests.utils import bearer

CARD_OK = "4242 4242 4242 4242"
CARD_DECLINED = "4000 0000 0000 0002"
CARD_FAIL_RENEWAL = "4000 0000 0000 9995"


async def make_person(make_user, session, name: str, role=UserRole.trader, full_name=None):
    user = await make_user(f"{name}@example.com", role=role)
    user.full_name = full_name or name.capitalize()
    await session.commit()
    return user, bearer(create_access_token(user))


async def make_expert(
    client: AsyncClient, make_user, session, name="expert", full_name=None, **profile
):
    user, headers = await make_person(make_user, session, name, UserRole.expert, full_name)
    body = {
        "headline": f"{name.capitalize()}: crypto swing trades",
        "bio": "## About\n\n10 years of **BTC** trading.",
        "markets": ["crypto", "gold"],
        "languages": ["ar", "en"],
        "response_time_hint": "within 24h",
        **profile,
    }
    res = await client.put("/api/v1/me/expert-profile", json=body, headers=headers)
    assert res.status_code == 200, res.text
    return user, headers


async def make_plan(client: AsyncClient, headers, **over) -> dict:
    body = {
        "name": "Monthly",
        "price": "29.00",
        "interval": "month",
        "trial_days": 0,
        "perks": {"premium_posts": True, "chat": True, "signals_feed": True},
        **over,
    }
    res = await client.post("/api/v1/me/plans", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


async def start_checkout(client: AsyncClient, headers, plan_id, **extra) -> dict:
    res = await client.post(
        "/api/v1/subscriptions/checkout", json={"plan_id": str(plan_id), **extra}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()


async def pay(client: AsyncClient, checkout: dict, card: str = CARD_OK, **form):
    data = {"card_number": card, "expiry": "12/39", "cvc": "123", "name": "Test User", **form}
    return await client.post(f"{checkout['checkout_path']}/confirm", data=data)


async def subscribe(client: AsyncClient, headers, plan_id, card: str = CARD_OK) -> dict:
    """The whole flow; returns the subscriber's subscription (GET /me/subscriptions)."""
    checkout = await start_checkout(client, headers, plan_id)
    res = await pay(client, checkout, card)
    assert res.status_code == 303, res.text
    subs = (await client.get("/api/v1/me/subscriptions", headers=headers)).json()
    return subs[0] if subs else {}


def page_title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html)
    return match.group(1) if match else ""


def new_client_id() -> str:
    return str(uuid.uuid4())
