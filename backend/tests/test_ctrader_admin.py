"""B1: linking the cTrader account (OAuth: connect, callback, a pasted code, the account) and the
admin feed endpoints (status without tokens, the manual backfill), admins only."""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.feeds.ctrader import credentials, linking
from app.models.feed import FeedCredential
from tests.test_ctrader_feed import fake_module

BASE = "/api/v1/admin/feeds/ctrader"


@pytest.fixture
async def fake(redis_client: Redis, monkeypatch: pytest.MonkeyPatch):
    server = fake_module.FakeCTrader(tick_rate=0)
    url = await server.start()
    settings = get_settings()
    monkeypatch.setattr(settings, "ctrader_client_id", fake_module.CLIENT_ID)
    monkeypatch.setattr(settings, "ctrader_client_secret", fake_module.CLIENT_SECRET)
    monkeypatch.setattr(settings, "ctrader_ws_url", url)
    monkeypatch.setattr(settings, "ctrader_env", "demo")
    monkeypatch.setattr(settings, "ctrader_account_id", None)
    monkeypatch.setattr(settings, "public_base_url", "")
    monkeypatch.setattr(credentials, "HTTP_TRANSPORT", server.token_transport())
    keys = [k async for k in redis_client.scan_iter(match=linking.STATE_KEY + "*")]
    if keys:
        await redis_client.delete(*keys)
    yield server
    await server.stop()


async def test_only_admins(client: AsyncClient, trader_headers) -> None:
    for method, url, body in (
        ("get", BASE, None),
        ("get", f"{BASE}/connect", None),
        ("post", f"{BASE}/code", {"code": "x", "state": "y"}),
        ("patch", BASE, {"account_id": 1}),
        (
            "post",
            f"{BASE}/backfill",
            {"from": "2026-01-01T00:00:00Z", "to": "2026-01-02T00:00:00Z"},
        ),
    ):
        assert (
            await client.request(method, url, json=body, headers=trader_headers)
        ).status_code == 403
        assert (await client.request(method, url, json=body)).status_code == 401


async def test_connect_needs_the_app_credentials(
    client: AsyncClient, admin_headers, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "ctrader_client_id", "")
    res = await client.get(f"{BASE}/connect", headers=admin_headers)
    assert res.status_code == 409


async def test_link_through_the_callback(
    client: AsyncClient, session: AsyncSession, admin_headers, fake
) -> None:
    res = await client.get(f"{BASE}/connect", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["redirect_uri"] == "http://187.127.76.76:8080/api/v1/admin/feeds/ctrader/callback"
    query = parse_qs(urlparse(body["url"]).query)
    assert urlparse(body["url"]).netloc == "id.ctrader.com"
    assert query["scope"] == ["accounts"] and query["state"] == [body["state"]]
    assert query["client_id"] == [fake_module.CLIENT_ID]
    assert query["redirect_uri"] == [body["redirect_uri"]]
    assert fake_module.CLIENT_SECRET not in res.text

    # a mismatched state is refused (and the code is not used)
    code = fake.new_code()
    res = await client.get(f"{BASE}/callback", params={"code": code, "state": "forged"})
    assert res.status_code == 400 and code in fake.codes

    res = await client.get(f"{BASE}/callback", params={"code": code, "state": body["state"]})
    assert res.status_code == 200, res.text
    linked = res.json()
    assert linked["linked"] and linked["account_id"] == fake_module.ACCOUNT_ID  # the demo one
    assert {a["account_id"] for a in linked["accounts"]} == {
        fake_module.ACCOUNT_ID,
        fake_module.LIVE_ACCOUNT_ID,
    }
    row = await session.get(FeedCredential, "ctrader", populate_existing=True)
    tokens = credentials.tokens_of(row)
    assert credentials.Tokens  # stored, encrypted, and never in the answer
    assert tokens.access_token not in res.text and tokens.refresh_token not in res.text
    assert tokens.access_token not in row.access_token_enc
    assert (row.scope, row.env) == ("accounts", "demo")
    # the state is single use
    again = await client.get(f"{BASE}/callback", params={"code": "x", "state": body["state"]})
    assert again.status_code == 400

    status = await client.get(BASE, headers=admin_headers)
    assert status.status_code == 200
    data = status.json()
    assert data["linked"] and data["link"]["account_id"] == fake_module.ACCOUNT_ID
    assert data["enabled"] is False and data["connected"] is False
    assert tokens.access_token not in status.text and tokens.refresh_token not in status.text
    system = await client.get("/api/v1/admin/system/status", headers=admin_headers)
    assert system.json()["feeds"]["ctrader"]["linked"] is True
    assert tokens.access_token not in system.text


async def test_callback_without_state(client: AsyncClient, admin_headers, fake) -> None:
    """cTrader's docs do not promise to send state back: accepted only when exactly one link
    was started (and consumed); otherwise the code is pasted by hand."""
    res = await client.get(f"{BASE}/callback", params={"code": fake.new_code()})
    assert res.status_code == 400 and "paste the code" in res.json()["detail"]
    await client.get(f"{BASE}/connect", headers=admin_headers)
    res = await client.get(f"{BASE}/callback", params={"code": fake.new_code()})
    assert res.status_code == 200, res.text


async def test_pasted_code_and_choosing_the_account(
    client: AsyncClient, admin_headers, fake, monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "ctrader_env", "live")  # one live account: chosen
    state = (await client.get(f"{BASE}/connect", headers=admin_headers)).json()["state"]
    res = await client.post(
        f"{BASE}/code", json={"code": fake.new_code(), "state": state}, headers=admin_headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["account_id"] == fake_module.LIVE_ACCOUNT_ID
    res = await client.patch(BASE, json={"account_id": 999}, headers=admin_headers)
    assert res.status_code == 422
    res = await client.patch(
        BASE, json={"account_id": fake_module.ACCOUNT_ID}, headers=admin_headers
    )
    assert res.status_code == 200 and res.json() == {"account_id": fake_module.ACCOUNT_ID}
    # a refused code: 502, nothing stored
    state = (await client.get(f"{BASE}/connect", headers=admin_headers)).json()["state"]
    res = await client.post(
        f"{BASE}/code", json={"code": "not-a-code", "state": state}, headers=admin_headers
    )
    assert res.status_code == 502


async def test_backfill_endpoint(client: AsyncClient, admin_headers, monkeypatch) -> None:
    sent = []

    class Result:
        id = str(uuid.uuid4())

    from app.tasks import celery_app  # noqa: PLC0415

    monkeypatch.setattr(
        celery_app, "send_task", lambda name, args: sent.append((name, args)) or Result()
    )
    now = datetime.now(UTC)
    for body in (
        {"from": "2026-01-02T00:00:00Z", "to": "2026-01-01T00:00:00Z"},
        {"from": (now - timedelta(days=500)).isoformat(), "to": now.isoformat()},
        {
            "from": (now + timedelta(days=1)).isoformat(),
            "to": (now + timedelta(days=2)).isoformat(),
        },
    ):
        assert (
            await client.post(f"{BASE}/backfill", json=body, headers=admin_headers)
        ).status_code == 422
    body = {"from": (now - timedelta(days=365)).isoformat(), "to": now.isoformat()}
    res = await client.post(f"{BASE}/backfill", json=body, headers=admin_headers)
    assert res.status_code == 202, res.text
    assert res.json()["days"] == pytest.approx(365, abs=0.01)
    [(name, args)] = sent
    assert name == "feeds.ctrader_backfill" and len(args) == 2
