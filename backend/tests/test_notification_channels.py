"""Notification channels with fake providers: Telegram (linking, /stop, blocked bot, 429,
escaping), email (parts, RTL, retries then failed), push (devices, token cache, invalid
token), retries/backoff, the circuit breaker, secrets, the webhook and the bot service."""

import asyncio
import json
import logging
import smtplib
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.notification import (
    DeliveryStatus,
    NotificationDelivery,
    NotificationType,
    TelegramLink,
    UserDevice,
)
from app.notifications import breaker, service, telegram_bot, telegram_link, templates
from app.notifications import preferences as prefs
from app.notifications.channels import push as push_channel
from app.notifications.preferences import PreferencesIn
from tests.notification_utils import (
    SIGNAL_DATA,
    TOKEN,
    FakeFcm,
    FakeTelegram,
    install_smtp,
    item,
    service_account,
)
from tests.utils import bearer

DEVICES = "/api/v1/me/devices"


@pytest.fixture
async def alice(make_user):
    user = await make_user("alice@example.com")
    return user, bearer(create_access_token(user))


@pytest.fixture
def telegram(monkeypatch) -> FakeTelegram:
    fake = FakeTelegram()
    monkeypatch.setattr(get_settings(), "telegram_bot_token", TOKEN)
    monkeypatch.setattr(service, "telegram_client", fake.client)
    monkeypatch.setattr(telegram_link, "client_factory", fake.client)
    return fake


@pytest.fixture
def smtp(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_from", "alerts@trading.test")
    monkeypatch.setattr(settings, "smtp_password", "smtp-SECRET-pw")
    return install_smtp(monkeypatch)


@pytest.fixture
def fcm(monkeypatch) -> FakeFcm:
    fake = FakeFcm()
    settings = get_settings()
    monkeypatch.setattr(settings, "fcm_project_id", "test-project")
    monkeypatch.setattr(settings, "fcm_credentials_json", json.dumps(service_account()))
    monkeypatch.setattr(service, "fcm_client", fake.factory())
    return fake


async def _rows(session: AsyncSession) -> list[NotificationDelivery]:
    rows = await session.scalars(
        select(NotificationDelivery)
        .order_by(NotificationDelivery.created_at)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


async def _send_all(session_factory, redis, prepared) -> dict:
    return await service.send_deliveries(session_factory, redis, prepared.send_ids)


# --- Telegram ---------------------------------------------------------------------------------


async def test_link_code_flow(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client, alice, telegram
) -> None:
    user, headers = alice
    res = await client.post("/api/v1/me/notifications/telegram/link", headers=headers)
    assert res.status_code == 200
    data = res.json()
    code = data["code"]
    assert data["deep_link"] == f"https://t.me/TradingTestBot?start={code}"
    assert data["expires_in"] == 600 and await redis_client.ttl(f"notif:tg:link:{code}") > 590

    client_ = telegram.client()
    update = {
        "message": {"chat": {"id": 555}, "from": {"username": "alice_tg"}, "text": f"/start {code}"}
    }  # noqa: E501
    assert (
        await telegram_link.handle_update(session_factory, redis_client, update, client_)
        == "linked"
    )
    link = await session.get(TelegramLink, user.id, populate_existing=True)
    assert (link.chat_id, link.username) == (555, "alice_tg")
    assert telegram.sent()[-1]["text"].startswith("✅")
    # the code is single-use
    assert (
        await telegram_link.handle_update(session_factory, redis_client, update, client_)
        == "bad_code"
    )
    # an expired code (Redis TTL passed) is the same as an unknown one
    other = await telegram_link.create_code(redis_client, user.id)
    await redis_client.delete(f"notif:tg:link:{other}")
    expired = {"message": {"chat": {"id": 555}, "text": f"/start {other}"}}
    assert (
        await telegram_link.handle_update(session_factory, redis_client, expired, client_)
        == "bad_code"
    )
    status_ = {"message": {"chat": {"id": 555}, "text": "/status"}}
    assert (
        await telegram_link.handle_update(session_factory, redis_client, status_, client_)
        == "status"
    )
    assert "al***@example.com" in telegram.sent()[-1]["text"]
    channels = (await client.get("/api/v1/me/notifications/channels", headers=headers)).json()
    assert channels["telegram"]["linked"] is True and channels["telegram"]["username"] == "alice_tg"
    # /stop unlinks; the app can unlink too
    stop = {"message": {"chat": {"id": 555}, "text": "/stop"}}
    assert (
        await telegram_link.handle_update(session_factory, redis_client, stop, client_)
        == "unlinked"
    )
    assert await session.get(TelegramLink, user.id, populate_existing=True) is None
    await telegram_link.link(session, user.id, 555, None)
    assert (
        await client.delete("/api/v1/me/notifications/telegram", headers=headers)
    ).status_code == 204
    assert await session.get(TelegramLink, user.id, populate_existing=True) is None


async def test_link_needs_telegram_on_the_server(client: AsyncClient, alice) -> None:
    _, headers = alice
    res = await client.post("/api/v1/me/notifications/telegram/link", headers=headers)
    assert res.status_code == 409


async def test_telegram_send_escapes_html(
    session: AsyncSession, session_factory, redis_client, alice, telegram
) -> None:
    user, _ = alice
    await telegram_link.link(session, user.id, 777, None)
    data = {"title": "<b>Hi</b> & bye", "body": "a < b > c"}
    prepared = await service.notify(session, item(user.id, data=data))
    assert await _send_all(session_factory, redis_client, prepared) == {"sent": 1}
    [message] = telegram.sent()
    assert message["chat_id"] == 777 and message["parse_mode"] == "HTML"
    assert message["text"] == "<b>&lt;b&gt;Hi&lt;/b&gt; &amp; bye</b>\na &lt; b &gt; c"
    [row] = await _rows(session)
    assert row.status == DeliveryStatus.sent and row.provider_message_id and row.attempts == 1
    # sending again changes nothing (idempotent)
    assert await _send_all(session_factory, redis_client, prepared) == {"noop": 1}
    assert len(telegram.sent()) == 1


async def test_blocked_bot_unlinks(
    session: AsyncSession, session_factory, redis_client, alice, telegram
) -> None:
    user, _ = alice
    await telegram_link.link(session, user.id, 778, None)
    telegram.responses["sendMessage"] = [
        (
            403,
            {
                "ok": False,
                "error_code": 403,
                "description": "Forbidden: bot was blocked by the user",
            },
        )
    ]
    prepared = await service.notify(session, item(user.id))
    await _send_all(session_factory, redis_client, prepared)
    [row] = await _rows(session)
    assert row.status == DeliveryStatus.failed and "403" in row.last_error
    assert await session.get(TelegramLink, user.id, populate_existing=True) is None


async def test_telegram_429_uses_retry_after(
    session: AsyncSession, session_factory, redis_client, alice, telegram, notification_queue
) -> None:
    user, _ = alice
    await telegram_link.link(session, user.id, 779, None)
    telegram.responses["sendMessage"] = [
        (
            429,
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests: retry after 17",
                "parameters": {"retry_after": 17},
            },
        )  # noqa: E501
    ]
    prepared = await service.notify(session, item(user.id))
    notification_queue.clear()
    assert await _send_all(session_factory, redis_client, prepared) == {"retry": 1}
    [row] = await _rows(session)
    assert row.status == DeliveryStatus.pending and row.attempts == 1 and "429" in row.last_error
    assert notification_queue == [([row.id], 17.0)]  # retried after retry_after, not backoff
    assert await breaker.state(redis_client, "telegram") == {
        "open": False,
        "open_seconds_left": 0,
        "consecutive_failures": 0,  # rate limits do not count toward the breaker
    }
    assert await _send_all(session_factory, redis_client, prepared) == {"sent": 1}


async def test_bot_service_idles_without_a_token(caplog) -> None:
    caplog.set_level(logging.INFO, logger="telegram-bot")
    task = asyncio.create_task(telegram_bot.main())
    await asyncio.sleep(0.2)
    assert not task.done()  # running and idle: the deploy waits for every service to run
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "TELEGRAM_BOT_TOKEN is empty" in caplog.text


async def test_webhook(client: AsyncClient, alice, telegram, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_mode", "webhook")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "hook-SECRET")
    calls = []

    async def fake_handle(factory, redis, update, client_=None):
        calls.append(update)

    monkeypatch.setattr(telegram_link, "handle_update", fake_handle)
    update = {"update_id": 1, "message": {"chat": {"id": 1}, "text": "/status"}}
    url = "/api/v1/telegram/webhook/hook-SECRET"
    ok = await client.post(
        url, json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "hook-SECRET"}
    )
    assert ok.status_code == 200 and calls == [update]
    assert (await client.post(url, json=update)).status_code == 404  # header missing
    bad = "/api/v1/telegram/webhook/wrong"
    assert (
        await client.post(bad, json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
    ).status_code == 404  # noqa: E501
    monkeypatch.setattr(settings, "telegram_mode", "polling")
    res = await client.post(
        url, json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "hook-SECRET"}
    )
    assert res.status_code == 404 and len(calls) == 1


# --- email ------------------------------------------------------------------------------------


async def test_email_parts_and_rtl(
    session: AsyncSession, session_factory, redis_client, alice, smtp
) -> None:
    user, _ = alice
    prepared = await service.notify(
        session, item(user.id, type=NotificationType.security, data={"event": "password_changed"})
    )
    assert await _send_all(session_factory, redis_client, prepared) == {"sent": 1}
    [message] = smtp.sent
    assert message["To"] == "alice@example.com" and message["From"] == "alerts@trading.test"
    assert message["Subject"] == "تم تغيير كلمة المرور"
    text = message.get_body(("plain",)).get_content()
    html = message.get_body(("html",)).get_content()
    assert "تم تغيير كلمة المرور وتسجيل الخروج" in text
    assert 'dir="rtl"' in html and 'lang="ar"' in html and "text-align:right" in html
    await prefs.update(session, user.id, PreferencesIn(language="en"))
    subject, text, html = templates.email(*templates.inbox("signal", SIGNAL_DATA, "en"), "en")
    assert subject == "BUY signal: BTC/USDT 1h" and 'dir="ltr"' in html
    assert "<p" in html and "Stop: 36,365.22" in text


async def test_smtp_failures_retry_then_fail(
    session: AsyncSession, session_factory, redis_client, alice, smtp, notification_queue, caplog
) -> None:
    user, _ = alice
    smtp.fail = ConnectionRefusedError("smtp.test:587 refused, password smtp-SECRET-pw")
    prepared = await service.notify(
        session, item(user.id, type=NotificationType.security, data={"event": "password_changed"})
    )
    countdowns = []
    for _ in range(get_settings().notification_max_attempts):
        notification_queue.clear()
        await _send_all(session_factory, redis_client, prepared)
        countdowns += [c for _, c in notification_queue]
        await redis_client.delete("notif:breaker:email:open")  # keep the breaker out of this test
    [row] = await _rows(session)
    assert row.status == DeliveryStatus.failed and row.attempts == 5
    assert row.last_error == "smtp: ConnectionRefusedError"
    assert len(countdowns) == 4  # 4 retries after attempts 1-4, then failed
    for attempt, countdown in enumerate(countdowns, start=1):
        base = min(300, 2**attempt)
        assert base <= countdown <= base * 1.5  # exponential backoff with jitter
    assert "smtp-SECRET-pw" not in caplog.text and "smtp-SECRET-pw" not in row.last_error


async def test_smtp_permanent_error(
    session: AsyncSession, session_factory, redis_client, alice, smtp
) -> None:
    user, _ = alice
    smtp.fail = smtplib.SMTPRecipientsRefused({"alice@example.com": (550, b"no such user")})
    prepared = await service.notify(
        session, item(user.id, type=NotificationType.security, data={"event": "password_changed"})
    )
    await _send_all(session_factory, redis_client, prepared)
    [row] = await _rows(session)
    assert (row.status, row.attempts, row.last_error) == (
        DeliveryStatus.failed,
        1,
        "smtp: recipient refused [550]",
    )


# --- push -------------------------------------------------------------------------------------


async def test_devices_api(client: AsyncClient, alice, make_user) -> None:
    _, headers = alice
    body = {"token": "fcm-token-AAAAAAAA-0001", "platform": "android", "app_version": "1.0.0"}
    res = await client.post(DEVICES, json=body, headers=headers)
    assert res.status_code == 201
    device = res.json()
    assert device["token_suffix"] == "AAA-0001" and "token" not in device
    refreshed = await client.post(DEVICES, json={**body, "app_version": "1.1.0"}, headers=headers)
    assert refreshed.status_code == 200 and refreshed.json()["id"] == device["id"]
    assert refreshed.json()["app_version"] == "1.1.0"
    assert len((await client.get(DEVICES, headers=headers)).json()) == 1
    other = await make_user("other@example.com")
    other_headers = bearer(create_access_token(other))
    assert (
        await client.delete(f"{DEVICES}/{device['id']}", headers=other_headers)
    ).status_code == 404
    # the same token signed in to another account moves there
    moved = await client.post(DEVICES, json=body, headers=other_headers)
    assert moved.status_code == 200 and (await client.get(DEVICES, headers=headers)).json() == []
    assert (
        await client.delete(f"{DEVICES}/{device['id']}", headers=other_headers)
    ).status_code == 204
    bad = await client.post(DEVICES, json={**body, "platform": "symbian"}, headers=headers)
    assert bad.status_code == 422


async def test_push_payload_token_cache_and_invalid_token(
    session: AsyncSession, session_factory, redis_client, alice, fcm
) -> None:
    user, _ = alice
    assert push_channel.enabled()
    phone = UserDevice(user_id=user.id, platform="android", token="fcm-phone-token-123456")
    tablet = UserDevice(user_id=user.id, platform="ios", token="fcm-tablet-token-654321")
    session.add_all([phone, tablet])
    await session.commit()
    signal = item(user.id, type=NotificationType.signal, data=SIGNAL_DATA)
    prepared = await service.notify(session, signal)
    assert await _send_all(session_factory, redis_client, prepared) == {"sent": 2}
    assert fcm.token_requests == 1  # the OAuth token is cached in Redis for the second send
    assert fcm.headers == ["Bearer ya29.test"] * 2
    message = fcm.messages[0]["message"]
    assert message["token"] in {"fcm-phone-token-123456", "fcm-tablet-token-654321"}
    assert message["notification"]["title"] == "إشارة شراء: BTC/USDT 1h"
    assert message["data"] == {
        "notification_id": str(prepared.notifications[0]["id"]),
        "type": "signal",
        "screen": "signal",
        "signal_id": SIGNAL_DATA["signal"]["id"],
    }
    assert message["android"]["priority"] == "high"
    # FCM says the token is gone: the device row is deleted
    fcm.responses = [
        (404, {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}})
    ]
    prepared = await service.notify(session, item(user.id))
    results = await _send_all(session_factory, redis_client, prepared)
    assert results == {"failed": 1, "sent": 1}
    left = list(await session.scalars(select(UserDevice).execution_options(populate_existing=True)))
    assert len(left) == 1
    assert fcm.token_requests == 1


def test_push_disabled_with_bad_credentials(monkeypatch, caplog) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "fcm_project_id", "p")
    monkeypatch.setattr(settings, "fcm_credentials_json", "/no/such/file.json")
    assert push_channel.enabled() is False
    monkeypatch.setattr(settings, "fcm_credentials_json", "")
    assert push_channel.enabled() is False


# --- retries, circuit breaker, secrets --------------------------------------------------------


async def test_circuit_breaker_opens_and_recovers(
    session: AsyncSession,
    session_factory,
    redis_client: Redis,
    alice,
    telegram,
    notification_queue,
    caplog,
) -> None:
    user, _ = alice
    await telegram_link.link(session, user.id, 900, None)
    telegram.error = httpx.ConnectError(
        "connection refused to https://api.telegram.org/bot" + TOKEN
    )
    caplog.set_level(logging.WARNING)
    for n in range(get_settings().notification_breaker_failures):
        prepared = await service.notify(
            session, item(user.id, data={"title": f"T{n}", "body": "."})
        )
        await _send_all(session_factory, redis_client, prepared)
    state = await breaker.state(redis_client, "telegram")
    assert state["open"] is True and state["open_seconds_left"] > 0
    assert caplog.text.count("telegram circuit opened") == 1  # logged once
    # while open: held, no call to Telegram, no task
    calls = len(telegram.calls)
    notification_queue.clear()
    prepared = await service.notify(session, item(user.id, data={"title": "Held", "body": "."}))
    assert await _send_all(session_factory, redis_client, prepared) == {"held": 1}
    assert len(telegram.calls) == calls
    held = [r for r in await _rows(session) if r.hold == "circuit_open"]
    assert len(held) == 1
    # the period ends and Telegram is back: released, sent, the circuit closes
    await redis_client.delete("notif:breaker:telegram:open")
    telegram.error = None
    notification_queue.clear()
    assert (
        await service.release_circuit_holds(
            session_factory, now=datetime.now(UTC) + timedelta(hours=1)
        )
        == 1
    )  # noqa: E501
    assert notification_queue == [([held[0].id], None)]
    assert await service.send_deliveries(session_factory, redis_client, [held[0].id]) == {"sent": 1}
    assert (await breaker.state(redis_client, "telegram"))["consecutive_failures"] == 0
    # no secret anywhere
    for row in await _rows(session):
        assert TOKEN not in (row.last_error or "")
    assert TOKEN not in caplog.text
    assert {r.last_error for r in await _rows(session) if r.last_error} == {
        "telegram sendMessage: ConnectError"
    }  # noqa: E501


def test_error_messages_never_carry_secrets(monkeypatch) -> None:
    from app.notifications.channels import TransientError

    monkeypatch.setattr(get_settings(), "telegram_bot_token", TOKEN)
    assert TOKEN not in str(TransientError(f"failed https://api.telegram.org/bot{TOKEN}/x"))


async def test_digest_on_email(
    session: AsyncSession, session_factory, redis_client, alice, smtp
) -> None:
    user, _ = alice
    await prefs.update(
        session,
        user.id,
        PreferencesIn(
            matrix={"system": {"email": True, "telegram": False, "push": False}},
            quiet_hours={"start": "00:00", "end": "23:59", "tz": "UTC"},
            language="en",
        ),
    )
    for n in range(3):
        await service.notify(session, item(user.id, data={"title": f"Update {n}", "body": "."}))
    rows = await _rows(session)
    assert [r.hold for r in rows] == ["quiet_hours"] * 3
    counts = await service.send_digests(
        session_factory, redis_client, now=rows[0].release_at + timedelta(minutes=1)
    )  # noqa: E501
    assert counts == {"digests": 1, "items": 3}
    [message] = smtp.sent
    assert message["Subject"] == "3 notifications"
    assert "• Update 0" in message.get_body(("plain",)).get_content()
    assert all(r.status == DeliveryStatus.sent for r in await _rows(session))
    assert uuid.UUID(str(rows[0].id))
