"""Notifications: notify() (idempotency, inbox, WebSocket), the inbox API, preferences (matrix,
filters, quiet hours, hourly cap, digests, critical bypass), producers (signal engine,
backtests, security events), retention, admin broadcast and stats, test messages."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.backtest import Backtest, BacktestStatus
from app.models.candle import Timeframe
from app.models.notification import (
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationType,
    Severity,
    TelegramLink,
)
from app.models.user import UserRole
from app.notifications import preferences as prefs
from app.notifications import service, templates
from app.notifications.preferences import PreferencesIn, Prefs, quiet_until
from app.realtime.topics import user_topic
from app.services import backtest_service, signal_engine
from app.services.signal_engine import Job
from tests.api_key_utils import create_key, xkey
from tests.market_utils import make_instrument
from tests.notification_utils import SIGNAL_DATA, TOKEN, FakeTelegram, item
from tests.strategy_utils import RSI1, activate, add_closes
from tests.test_signal_engine import Listener
from tests.utils import bearer

INBOX = "/api/v1/me/notifications"
PREFS = "/api/v1/me/notification-preferences"
T0 = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
DIP = [10.0, 9.0, 8.0, 9.0]  # RSI(1) crosses 30 upward on bar 3 -> rsi_reversal buy
BAR = T0 + timedelta(minutes=3)


@pytest.fixture
async def alice(make_user):
    user = await make_user("alice@example.com", role=UserRole.analyst)
    return user, bearer(create_access_token(user))


@pytest.fixture
async def bob(make_user):
    user = await make_user("bob@example.com")
    return user, bearer(create_access_token(user))


@pytest.fixture
def telegram(monkeypatch) -> FakeTelegram:
    """Telegram configured on the server, every call answered by the fake."""
    fake = FakeTelegram()
    monkeypatch.setattr(get_settings(), "telegram_bot_token", TOKEN)
    monkeypatch.setattr(service, "telegram_client", fake.client)
    return fake


async def _link(session, user, chat_id=1001) -> None:
    session.add(TelegramLink(user_id=user.id, chat_id=chat_id, username="alice"))
    await session.commit()


async def _deliveries(session: AsyncSession) -> list[NotificationDelivery]:
    rows = await session.scalars(
        select(NotificationDelivery)
        .order_by(NotificationDelivery.created_at)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


# --- notify() ---------------------------------------------------------------------------------


async def test_notify_is_idempotent_and_publishes(
    session: AsyncSession, redis_client: Redis, alice, notification_queue
) -> None:
    user, _ = alice
    async with Listener(redis_client) as listener:
        await listener.listen(user_topic(user.id))
        first = await service.notify(session, item(user.id, dedup_key="broadcast:1"))
        again = await service.notify(session, item(user.id, dedup_key="broadcast:1"))
        messages = await listener.messages(notifications=True)
    assert len(first.notifications) == 1 and again.notifications == []
    assert await session.scalar(select(func.count()).select_from(Notification)) == 1
    [(topic, msg)] = messages
    assert topic == user_topic(user.id) and msg["type"] == "notification"
    note = msg["notification"]
    assert (note["type"], note["title"], note["body"], note["severity"]) == (
        "system",
        "Hello",
        "World",
        "info",
    )
    assert note["read_at"] is None and note["id"] == str(first.notifications[0]["id"])
    # defaults: system -> telegram and push, but nothing linked: no deliveries, nothing queued
    assert first.deliveries == [] and notification_queue == []


async def test_disabled_channels_are_skipped_with_a_reason(
    session: AsyncSession, alice, notification_queue
) -> None:
    user, _ = alice
    await _link(session, user)
    prepared = await service.notify(session, item(user.id))
    [delivery] = await _deliveries(session)
    assert (delivery.channel.value, delivery.status, delivery.last_error) == (
        "telegram",
        DeliveryStatus.skipped,
        "channel disabled on server",
    )
    assert prepared.send_ids == [] and notification_queue == []  # no retries, no tasks


# --- inbox API --------------------------------------------------------------------------------


async def test_inbox_api(client: AsyncClient, session: AsyncSession, alice, bob) -> None:
    user, headers = alice
    other, other_headers = bob
    await service.notify(session, item(user.id, data={"title": "First", "body": "1"}))
    await service.notify(
        session,
        item(user.id, type=NotificationType.security, data={"event": "password_changed"}),
    )
    await service.notify(session, item(other.id))
    page = (await client.get(INBOX, headers=headers)).json()
    assert page["total"] == 2
    assert [n["type"] for n in page["items"]] == ["security", "system"]  # newest first
    assert page["items"][0]["title"] == "تم تغيير كلمة المرور"  # Arabic by default
    only = (await client.get(INBOX, params={"type": "system"}, headers=headers)).json()
    assert only["total"] == 1
    assert (await client.get(f"{INBOX}/unread-count", headers=headers)).json() == {"count": 2}

    first_id = page["items"][1]["id"]
    assert (await client.post(f"{INBOX}/{first_id}/read", headers=headers)).status_code == 204
    unread = (await client.get(INBOX, params={"unread": True}, headers=headers)).json()
    assert unread["total"] == 1
    assert (await client.post(f"{INBOX}/{first_id}/read", headers=other_headers)).status_code == 404
    assert (await client.post(f"{INBOX}/read-all", headers=headers)).status_code == 204
    assert (await client.get(f"{INBOX}/unread-count", headers=headers)).json() == {"count": 0}
    assert (await client.delete(f"{INBOX}/{first_id}", headers=other_headers)).status_code == 404
    assert (await client.delete(f"{INBOX}/{first_id}", headers=headers)).status_code == 204
    assert (await client.get(INBOX, headers=headers)).json()["total"] == 1
    assert (await client.get(INBOX)).status_code == 401
    key = await create_key(client, headers, ["signals:read"])
    for path in (INBOX, PREFS, "/api/v1/me/devices", f"{INBOX}/channels"):
        res = await client.get(path, headers=xkey(key["key"]))
        assert res.status_code == 403, path


# --- preferences ------------------------------------------------------------------------------


async def test_preferences_api(client: AsyncClient, alice) -> None:
    _, headers = alice
    data = (await client.get(PREFS, headers=headers)).json()
    assert data["matrix"]["signal"] == {"telegram": True, "email": False, "push": True}
    assert data["matrix"]["security"] == {"telegram": False, "email": True, "push": False}
    assert data["matrix"]["backtest_completed"] == {
        "telegram": False,
        "email": False,
        "push": True,
    }
    assert (data["language"], data["quiet_hours"], data["max_per_hour"]["email"]) == (
        "ar",
        None,
        30,
    )
    body = {
        "matrix": {"signal": {"email": True}},
        "min_signal_strength": 0.5,
        "only_valid_plans": True,
        "quiet_hours": {"start": "23:00", "end": "07:00", "tz": "Asia/Damascus"},
        "language": "en",
        "max_per_hour": {"telegram": 5},
    }
    res = await client.put(PREFS, json=body, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["matrix"]["signal"] == {"telegram": True, "email": True, "push": True}
    assert data["max_per_hour"] == {"telegram": 5, "email": 30, "push": 30}
    assert data["quiet_hours"]["tz"] == "Asia/Damascus" and data["language"] == "en"
    for bad, loc in (
        ({"quiet_hours": {"start": "23:00", "end": "07:00", "tz": "Mars/Base"}}, "tz"),
        ({"quiet_hours": {"start": "25:00", "end": "07:00"}}, "start"),
        ({"max_per_hour": {"telegram": 0}}, "max_per_hour"),
        ({"matrix": {"signal": {"sms": True}}}, "sms"),
        ({"language": "fr"}, "language"),
        ({"min_signal_strength": 2}, "min_signal_strength"),
        ({"colour": "red"}, "colour"),
    ):
        res = await client.put(PREFS, json=bad, headers=headers)
        assert res.status_code == 422, bad
        assert loc in [str(x) for x in res.json()["detail"][0]["loc"]], res.json()


@pytest.mark.parametrize(
    ("now", "quiet", "expected"),
    [
        # 23:00-07:00 Damascus (UTC+3): 22:30 UTC = 01:30 local -> until 07:00 local = 04:00 UTC
        ("2026-03-02T22:30:00+00:00", ("23:00", "07:00", "Asia/Damascus"), "2026-03-03T04:00"),
        # 20:30 UTC = 23:30 local, after the start -> the next morning
        ("2026-03-02T20:30:00+00:00", ("23:00", "07:00", "Asia/Damascus"), "2026-03-03T04:00"),
        ("2026-03-02T12:00:00+00:00", ("23:00", "07:00", "Asia/Damascus"), None),
        # same-day window in New York (UTC-5 in March before DST): 13:00-14:00 local
        ("2026-03-02T18:30:00+00:00", ("13:00", "14:00", "America/New_York"), "2026-03-02T19:00"),
        ("2026-03-02T19:00:00+00:00", ("13:00", "14:00", "America/New_York"), None),
    ],
)
def test_quiet_hours(now: str, quiet: tuple, expected: str | None) -> None:
    start, end, tz = quiet
    result = quiet_until({"start": start, "end": end, "tz": tz}, datetime.fromisoformat(now))
    assert (result.strftime("%Y-%m-%dT%H:%M") if result else None) == expected


def test_signal_filters() -> None:
    p = Prefs.of(None)
    strict = Prefs(**{**p.__dict__, "min_signal_strength": 0.5, "only_valid_plans": True})
    weak = {**SIGNAL_DATA, "signal": {**SIGNAL_DATA["signal"], "strength": 0.4}}
    invalid = {**SIGNAL_DATA, "plan": {**SIGNAL_DATA["plan"], "invalid_reason": "no_equity"}}
    strong = {**SIGNAL_DATA, "signal": {**SIGNAL_DATA["signal"], "strength": 0.9}}
    assert p.passes_filters("signal", weak)
    assert not strict.passes_filters("signal", weak)
    assert not strict.passes_filters("signal", {**invalid, "signal": strong["signal"]})
    assert strict.passes_filters("signal", strong)
    assert strict.passes_filters("system", {})  # filters are for signals only


async def test_preferences_route_deliveries(
    session: AsyncSession, alice, telegram, notification_queue
) -> None:
    user, _ = alice
    await _link(session, user)
    off = PreferencesIn(matrix={"system": {"telegram": False}}).stored()
    await prefs.update(
        session, user.id, PreferencesIn(**{**off, "matrix": {"system": {"telegram": False}}})
    )
    await service.notify(session, item(user.id))
    assert await _deliveries(session) == []
    await prefs.update(session, user.id, PreferencesIn(min_signal_strength=0.5))
    weak = {**SIGNAL_DATA, "signal": {**SIGNAL_DATA["signal"], "strength": 0.4}}
    await service.notify(session, item(user.id, type=NotificationType.signal, data=weak))
    assert await _deliveries(session) == []  # filtered (still in the inbox)
    strong = {**SIGNAL_DATA, "signal": {**SIGNAL_DATA["signal"], "strength": 0.9}}
    await service.notify(session, item(user.id, type=NotificationType.signal, data=strong))
    [delivery] = await _deliveries(session)
    assert delivery.status == DeliveryStatus.pending and delivery.hold is None
    assert notification_queue == [([delivery.id], None)]
    assert await session.scalar(select(func.count()).select_from(Notification)) == 3


async def test_quiet_hours_cap_digest_and_critical(
    session: AsyncSession, session_factory, redis_client, alice, telegram, monkeypatch
) -> None:
    user, _ = alice
    await _link(session, user)
    await prefs.update(session, user.id, PreferencesIn(max_per_hour={"telegram": 2}, language="en"))
    # hourly cap 2: the third and fourth are held for the digest
    for n in range(4):
        await service.notify(session, item(user.id, data={"title": f"News {n}", "body": "."}))
    rows = await _deliveries(session)
    assert [r.hold for r in rows] == [None, None, "hourly_cap", "hourly_cap"]
    assert all(r.release_at.minute == 0 for r in rows[2:])
    # the hour ends: one digest with both titles
    later = rows[2].release_at + timedelta(seconds=1)
    counts = await service.send_digests(session_factory, redis_client, now=later)
    assert counts["digests"] == 1 and counts["items"] == 2
    [message] = telegram.sent()
    assert message["text"].startswith("<b>2 notifications</b>")
    assert "• News 2" in message["text"] and "• News 3" in message["text"]
    rows = await _deliveries(session)
    assert [r.status for r in rows[2:]] == [DeliveryStatus.sent] * 2

    # quiet hours: held until their end; a critical event goes out immediately
    await prefs.update(
        session,
        user.id,
        PreferencesIn(quiet_hours={"start": "00:00", "end": "23:59", "tz": "UTC"}, language="en"),
    )
    await redis_client.delete(*[k async for k in redis_client.scan_iter("notif:cap:*")])
    await service.notify(session, item(user.id, data={"title": "Quiet", "body": "."}))
    critical = item(
        user.id,
        type=NotificationType.security,
        severity=Severity.critical,
        data={"event": "account_locked", "minutes": 15},
    )
    prepared = await service.notify(session, critical)
    rows = await _deliveries(session)
    quiet_row = next(r for r in rows if r.hold == "quiet_hours")
    assert quiet_row.release_at.strftime("%H:%M") == "23:59"
    critical_rows = [r for r in rows if r.id in prepared.send_ids]
    assert len(critical_rows) == 0  # security -> telegram is off by default


async def test_critical_bypasses_quiet_hours(session: AsyncSession, alice, telegram) -> None:
    user, _ = alice
    await _link(session, user)
    await prefs.update(
        session,
        user.id,
        PreferencesIn(
            quiet_hours={"start": "00:00", "end": "23:59", "tz": "UTC"},
            matrix={"security": {"telegram": True}},
            max_per_hour={"telegram": 1},
        ),
    )
    for _ in range(3):
        await service.notify(
            session,
            item(
                user.id,
                type=NotificationType.security,
                severity=Severity.critical,
                data={"event": "account_locked", "minutes": 15},
            ),
        )
    rows = [r for r in await _deliveries(session) if r.channel.value == "telegram"]
    assert len(rows) == 3 and all(r.hold is None for r in rows)  # no quiet hours, no cap


# --- producers --------------------------------------------------------------------------------


async def test_signal_engine_notifies_users_with_notify(
    session: AsyncSession, session_factory, redis_client: Redis, alice, bob, make_user
) -> None:
    a, _ = alice
    b, _ = bob
    carol = await make_user("carol@example.com")
    btc = await make_instrument(session, "BTC/USDT", price_precision=2, quantity_precision=4)
    await activate(session, a, btc, params=RSI1)
    await activate(session, b, btc, params=RSI1)
    await activate(session, carol, btc, params=RSI1, notify=False)
    await prefs.update(session, b.id, PreferencesIn(language="en"))
    await add_closes(session, btc.id, T0, DIP)
    async with Listener(redis_client) as listener:
        await listener.listen(user_topic(a.id), user_topic(b.id), user_topic(carol.id))
        result = await signal_engine.evaluate(
            session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR)
        )
        messages = await listener.messages(notifications=True)
    assert (result.inserted, result.notifications) == (1, 2)
    kinds = sorted((t, m["type"]) for t, m in messages)
    assert kinds == sorted(
        [
            (user_topic(a.id), "signal"),
            (user_topic(a.id), "notification"),
            (user_topic(b.id), "signal"),
            (user_topic(b.id), "notification"),
        ]
    )  # carol (notify = false): nothing
    notes = {
        n.user_id: n
        for n in await session.scalars(
            select(Notification).execution_options(populate_existing=True)
        )
    }
    assert set(notes) == {a.id, b.id}
    note_a, note_b = notes[a.id], notes[b.id]
    assert note_a.dedup_key.startswith("signal:") and note_a.type == NotificationType.signal
    assert note_a.title == "إشارة شراء: BTC/USDT 1m"
    assert note_b.title == "BUY signal: BTC/USDT 1m"
    # the default (balanced) rules need an ATR(14): 4 bars are not enough -> a flagged plan
    assert note_b.body.endswith(
        "No valid trade plan: the stop cannot be computed yet (not enough history)"
    )
    assert note_b.data["plan"]["invalid_reason"] == "stop_unavailable"
    assert len(note_b.data["user_strategy_ids"]) == 1
    # a re-run stores nothing new
    await redis_client.delete(Job(btc.id, Timeframe.m1, BAR).lock_key)
    again = await signal_engine.evaluate(
        session_factory, redis_client, Job(btc.id, Timeframe.m1, BAR)
    )
    assert again.notifications == 0
    assert await session.scalar(select(func.count()).select_from(Notification)) == 2


async def test_one_notification_per_signal_and_user(session: AsyncSession, alice) -> None:
    user, _ = alice
    btc = await make_instrument(session, "BTC/USDT")
    a1, a2 = uuid.uuid4(), uuid.uuid4()
    activation = signal_engine.Activation
    signal_id = uuid.uuid4()
    row = {
        "id": signal_id,
        "instrument_id": btc.id,
        "timeframe": Timeframe.m1,
        "strategy_key": "rsi_reversal",
        "params": {},
        "params_hash": "h",
        "bar_time": BAR,
        "side": "buy",
        "strength": 1.0,
        "price": 9.0,
        "reason": "r",
        "details": {},
    }
    by_user = {
        (signal_id, user.id): [
            (activation(a1, user.id, "rsi_reversal", "h", True, None), {"side": "long"}),
            (activation(a2, user.id, "rsi_reversal", "h", True, None), {"side": "long"}),
        ]
    }
    result = signal_engine.EvaluationResult(Job(btc.id, Timeframe.m1, BAR))
    prepared = await signal_engine._notifications(
        session, None, result.job, [row], by_user, [], result
    )
    [note] = prepared.notifications
    assert note["data"]["user_strategy_ids"] == [str(a1), str(a2)]
    assert len(note["data"]["plans"]) == 2


def test_signal_rendering_in_both_languages() -> None:
    title, body = templates.inbox("signal", SIGNAL_DATA, "en")
    assert title == "BUY signal: BTC/USDT 1h"
    assert body.splitlines() == [
        "Strategy: Moving Average Crossover · strength 0.42",
        "Price: 36,446.94",
        "",
        "Trade plan (10,000 USDT account):",
        "Entry ≈ 36,446.94",
        "Stop: 36,365.22",
        "Target 1: 36,610.38 (2.0R, close 100%)",
        "Size: 0.2741 (9,990.01 USDT)",
        "Risk: 42.36 USDT (0.42%) · R:R 2.00",
    ]
    title, body = templates.inbox("signal", SIGNAL_DATA, "ar")
    assert title == "إشارة شراء: BTC/USDT 1h"
    assert "وقف الخسارة: 36,365.22" in body and "المخاطرة: 42.36 USDT (0.42%)" in body
    invalid = {**SIGNAL_DATA, "plan": {**SIGNAL_DATA["plan"], "invalid_reason": "stop_unavailable"}}
    assert templates.inbox("signal", invalid, "en")[1].endswith(
        "No valid trade plan: the stop cannot be computed yet (not enough history)"
    )


async def test_backtest_events(session: AsyncSession, session_factory, alice) -> None:
    user, _ = alice
    btc = await make_instrument(session, "BTC/USDT")
    row = Backtest(
        user_id=user.id,
        instrument_id=btc.id,
        timeframe=Timeframe.h1,
        strategy_key="ma_crossover",
        params={},
        params_hash="h",
        config={},
        range_start=T0 - timedelta(days=10),
        range_end=T0,
        status=BacktestStatus.running,
    )
    session.add(row)
    await session.commit()
    assert await backtest_service.fail(session_factory, None, row.id, "Internal error: boom")
    await backtest_service._notify(
        session_factory, None, row, "backtest_completed", metrics={"total_return_pct": 12.3}
    )
    notes = {
        n.type: n
        for n in await session.scalars(
            select(Notification).execution_options(populate_existing=True)
        )
    }
    failed = notes[NotificationType.backtest_failed]
    assert failed.title == "فشل الاختبار التاريخي: Moving Average Crossover على BTC/USDT 1h"
    assert failed.severity == Severity.warning and "boom" in failed.body
    assert failed.dedup_key == f"backtest:{row.id}:backtest_failed"
    done = notes[NotificationType.backtest_completed]
    assert "+12.30%" in done.body and done.severity == Severity.success
    assert done.data["backtest_id"] == str(row.id)


async def test_security_events(
    client: AsyncClient,
    session: AsyncSession,
    make_user,
    login,
    rate_limits,
    frozen_clock,
    monkeypatch,
) -> None:
    # under the per-email login limit (5 / minute), so the lockout is reached in one minute
    monkeypatch.setattr(get_settings(), "login_lockout_failures", 3)
    user = await make_user("sec@example.com")
    headers = {"User-Agent": "Phone/1.0"}

    async def notes(event=None):
        rows = await session.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .execution_options(populate_existing=True)
        )
        return [n for n in rows if event is None or n.data.get("event") == event]

    async def do_login(agent: str, password="Passw0rd123"):
        return await client.post(
            "/api/v1/auth/login",
            json={"email": "sec@example.com", "password": password},
            headers={"User-Agent": agent},
        )

    assert (await do_login("Phone/1.0")).status_code == 200  # first sign-in: silent
    assert (await do_login("Phone/1.0")).status_code == 200  # known: silent
    assert await notes() == []
    token = (await do_login("Laptop/2.0")).json()["access_token"]  # new device
    [new_login] = await notes("new_login")
    assert new_login.severity == Severity.warning and new_login.data["user_agent"] == "Laptop/2.0"
    auth = bearer(token)

    key = (
        await client.post(
            "/api/v1/me/api-keys", json={"name": "bot", "scopes": ["market:read"]}, headers=auth
        )
    ).json()  # noqa: E501
    await client.delete(f"/api/v1/me/api-keys/{key['id']}", headers=auth)
    created, revoked = await notes("api_key_created"), await notes("api_key_revoked")
    assert created[0].data["key_name"] == "bot" and len(revoked) == 1
    res = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": "Passw0rd123", "new_password": "NewPassw0rd456"},
        headers=auth,
    )
    assert res.status_code == 204
    assert len(await notes("password_changed")) == 1

    frozen_clock.advance(61)  # a fresh per-email login budget (5 / minute)
    for _ in range(get_settings().login_lockout_failures):  # wrong passwords until locked
        await do_login("Phone/1.0", password="wrong-password")
    [locked] = await notes("account_locked")
    assert locked.severity == Severity.critical
    assert headers  # the same agent all along


async def test_retention(session: AsyncSession, session_factory, alice) -> None:
    user, _ = alice
    now = datetime.now(UTC)
    cases = {
        "old-read": (now - timedelta(days=91), True),
        "new-read": (now - timedelta(days=30), True),
        "old-unread": (now - timedelta(days=181), False),
        "mid-unread": (now - timedelta(days=100), False),
    }
    for key in cases:
        await service.notify(session, item(user.id, dedup_key=key))
    for key, (created, read) in cases.items():
        await session.execute(
            update(Notification)
            .where(Notification.dedup_key == key)
            .values(created_at=created, read_at=created if read else None)
        )
    await session.commit()
    assert await service.cleanup(session_factory) == 2
    left = set(await session.scalars(select(Notification.dedup_key)))
    assert left == {"new-read", "mid-unread"}


# --- admin, test messages, channels -----------------------------------------------------------


async def test_admin_broadcast_and_stats(
    client: AsyncClient,
    session: AsyncSession,
    session_factory,
    admin_headers,
    alice,
    bob,
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(service, "enqueue_broadcast", lambda *args: calls.append(args))
    body = {"title": "Maintenance", "body": "Tonight 02:00", "roles": ["analyst"]}
    res = await client.post(
        "/api/v1/admin/notifications/broadcast", json=body, headers=admin_headers
    )
    assert res.status_code == 202 and res.json()["recipients"] == 1
    [(broadcast_id, title, text, severity, roles)] = calls
    for _ in range(2):  # the task twice: nothing duplicated
        sent = await service.broadcast(
            session_factory, None, broadcast_id, title, text, severity, roles
        )
    assert sent == 0
    rows = list(
        await session.scalars(
            select(Notification).where(Notification.type == NotificationType.system)
        )
    )
    assert len(rows) == 1 and rows[0].title == "Maintenance"
    _, bob_headers = bob
    assert (
        await client.post("/api/v1/admin/notifications/broadcast", json=body, headers=bob_headers)
    ).status_code == 403  # noqa: E501
    stats = (await client.get("/api/v1/admin/notifications/stats", headers=admin_headers)).json()
    assert set(stats["channels"]) == {"telegram", "email", "push"}
    assert stats["channels"]["telegram"]["circuit"] == {
        "open": False,
        "open_seconds_left": 0,
        "consecutive_failures": 0,
    }
    assert stats["notifications"] >= 1 and "queue_length" in stats


async def test_test_message_and_channels(
    client: AsyncClient, session: AsyncSession, alice, rate_limits
) -> None:
    user, headers = alice
    res = await client.post(f"{INBOX}/test", json={"channel": "in_app"}, headers=headers)
    assert res.status_code == 201 and res.json()["deliveries"] == []
    assert int(res.headers["ratelimit-remaining"]) == 300 - 5  # cost 5 (analyst tier)
    res = await client.post(f"{INBOX}/test", json={"channel": "telegram"}, headers=headers)
    assert res.status_code == 409 and "not linked" in res.json()["detail"]
    res = await client.post(f"{INBOX}/test", json={"channel": "push"}, headers=headers)
    assert res.status_code == 409
    res = await client.post(f"{INBOX}/test", json={"channel": "email"}, headers=headers)
    [delivery] = res.json()["deliveries"]
    assert (delivery["channel"], delivery["target"], delivery["status"]) == (
        "email",
        "alice@example.com",
        "skipped",  # SMTP not configured
    )
    channels = (await client.get(f"{INBOX}/channels", headers=headers)).json()
    assert channels["in_app"]["enabled_on_server"] is True
    assert channels["telegram"] == {
        "enabled_on_server": False,
        "linked": False,
        "username": None,
        "mode": "polling",
        "address": None,
        "devices": None,
    }
    assert channels["email"]["address"] == "alice@example.com" and channels["push"]["devices"] == 0
    notes = (await client.get(INBOX, headers=headers)).json()
    assert notes["items"][0]["title"] == "إشعار تجريبي"
    assert user.email
