"""B11: AI setup alerts through the outbox (written with the evaluation, dispatched with retries,
recipients, stale rule, content, explanations, sizes, preferences, live frames), follows, and
the admin views. ai-service, Telegram and FCM are fakes (no network)."""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import alerts, store
from app.ai import contract as c
from app.ai.client import AIServiceClient
from app.core.config import get_settings
from app.models.ai import (
    AIAlertFollow,
    AIModelVersion,
    AISetup,
    AISetupExplanation,
    AISetupOutbox,
    AISetupTake,
)
from app.models.instrument import Instrument, MarketType
from app.models.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationType,
    Platform,
    TelegramLink,
    UserDevice,
)
from app.models.user import User, UserRole
from app.notifications import preferences as prefs_mod
from app.notifications import service as notifications
from app.realtime.topics import ai_setups_topic
from app.tasks import celery_app
from tests.market_utils import make_instrument
from tests.notification_utils import TOKEN, service_account
from tests.test_ai_sizing import GOLD_SPECS, profile
from tests.test_ai_store import move, request_at, response, setup
from tests.test_signal_engine import Listener
from tests.utils import bearer

T0 = datetime(2026, 10, 19, 14, 15, tzinfo=UTC)
LOGGER = "app.ai.alerts"
EXPLAINED = {"ar": "الاتجاه صاعد والسعر اخترق النطاق.", "en": "Uptrend, the range broke."}


class FakeAI:
    """ai-service /v1/size (the B4 example) and /v1/explain (per language), with faults."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.explain_status = 200
        self.verified = True
        self.template_used = False
        self.size_status = 200

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.calls.append((request.url.path, body))
        if request.url.path == "/v1/explain":
            if self.explain_status == "timeout":
                raise httpx.ReadTimeout("slow", request=request)
            if self.explain_status != 200:
                return httpx.Response(self.explain_status, json={"detail": "nope"})
            text = EXPLAINED[body["lang"]]
            return httpx.Response(
                200,
                json={"text": text, "verified": self.verified, "template_used": self.template_used},
            )
        if self.size_status != 200:
            return httpx.Response(self.size_status, json={"detail": "nope"})
        return httpx.Response(
            200,
            json={
                "lots": 0.04,
                "risk_usd": 20.0,
                "margin_required": 96.0,
                "feasible": True,
                "warnings": [],
            },
        )

    def client(self) -> AIServiceClient:
        """One attempt per call, like the dispatcher's own client."""
        return AIServiceClient(
            "http://ai", transport=httpx.MockTransport(self.handler), backoff=0, max_retries=0
        )

    def count(self, path: str) -> int:
        return sum(1 for p, _ in self.calls if p == path)


@pytest.fixture
def fake() -> FakeAI:
    return FakeAI()


@pytest.fixture
def channels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Telegram and FCM configured on the server (nothing is actually sent here)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", TOKEN)
    monkeypatch.setattr(settings, "fcm_project_id", "test-project")
    monkeypatch.setattr(settings, "fcm_credentials_json", json.dumps(service_account()))


@pytest.fixture
async def gold(session: AsyncSession) -> Instrument:
    return await make_instrument(
        session, "XAU/USD", "fxpro", market=MarketType.commodity, price_precision=2, **GOLD_SPECS
    )


def soon(**delta) -> str:
    return c.iso_z(datetime.now(UTC) + timedelta(**(delta or {"hours": 1})))


async def new_setups(session, gold, *payloads, at: datetime = T0) -> store.ApplyResult:
    req = request_at(at)
    return await store.apply_evaluation(session, gold, req, response(req, new=list(payloads)))


def armed(setup_id: str = "xau-1", grade: str = "B", **changes) -> dict:
    fields = {"grade": grade, "valid_until": soon(), "horizon_until": soon(hours=5), **changes}
    return setup(setup_id, "ARMED", **fields)


async def transitions(session, gold, *moves, at: datetime = T0 + timedelta(minutes=15)):
    req = request_at(at)
    return await store.apply_evaluation(session, gold, req, response(req, transitions=list(moves)))


async def user_with_targets(make_user, session, email: str, *, chat: int, lang: str = "ar"):
    user = await make_user(email)
    session.add(TelegramLink(user_id=user.id, chat_id=chat, username=email.split("@")[0]))
    session.add(UserDevice(user_id=user.id, platform=Platform.android, token=f"fcm-{chat}"))
    await session.commit()
    if lang != "ar":
        row = await prefs_mod.get_or_create(session, user.id)
        row.language = lang
        await session.commit()
    await profile(session, user)  # 2,000 USD, 1 %: the B4 size
    return user


async def follow(session, user, gold, min_grade=None) -> None:
    session.add(
        AIAlertFollow(
            user_id=user.id, instrument_id=gold.id, profile="intraday", min_grade=min_grade
        )
    )
    await session.commit()


async def outbox(session) -> list[AISetupOutbox]:
    rows = await session.scalars(
        select(AISetupOutbox).order_by(AISetupOutbox.id).execution_options(populate_existing=True)
    )
    return list(rows.all())


async def inbox(session, user_id=None) -> list[Notification]:
    query = select(Notification).where(Notification.type == NotificationType.ai_setup)
    if user_id is not None:
        query = query.where(Notification.user_id == user_id)
    return list((await session.scalars(query.order_by(Notification.created_at))).all())


async def dispatch(session_factory, redis, fake: FakeAI, **kw) -> dict:
    return await alerts.dispatch(session_factory, redis, client=fake.client(), **kw)


# --- the outbox ----------------------------------------------------------------------------------


async def test_outbox_rows_per_change_never_developing(session: AsyncSession, gold) -> None:
    dev = setup("dev-1", "DEVELOPING", entry=None, sl=None, tp=None)
    await new_setups(session, gold, dev, armed("arm-1"))
    rows = await outbox(session)
    assert [(r.setup_id, r.from_state, r.to_state, r.status) for r in rows] == [
        ("arm-1", None, "ARMED", "pending")
    ]
    assert rows[0].reason == "new"  # born DEVELOPING: nothing
    assert rows[0].at == T0 and rows[0].attempts == 0

    moves = [
        move("dev-1", "DEVELOPING", "ARMED", T0 + timedelta(minutes=2)),
        move("arm-1", "ARMED", "ACTIVE", T0 + timedelta(minutes=3), reason="filled"),
    ]
    first = await transitions(session, gold, *moves)
    again = await transitions(session, gold, *moves)  # replayed
    assert len(first.state_changes) == 2 and again.state_changes == []
    rows = await outbox(session)
    assert [(r.setup_id, r.from_state, r.to_state, r.reason) for r in rows] == [
        ("arm-1", None, "ARMED", "new"),
        ("dev-1", "DEVELOPING", "ARMED", None),
        ("arm-1", "ARMED", "ACTIVE", "filled"),
    ]
    # even a state change reported twice by different responses: one row per (setup, state)
    assert await store.enqueue_alerts(session, [store.StateChange("arm-1", None, "ARMED", T0)]) == 0


async def test_outbox_rolls_back_with_the_evaluation(
    session: AsyncSession, gold, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = store.enqueue_alerts

    async def written_then_crash(s, changes):
        assert await original(s, changes) == 1  # the outbox row is written ...
        raise RuntimeError("crash before the commit")

    monkeypatch.setattr(store, "enqueue_alerts", written_then_crash)
    with pytest.raises(RuntimeError, match="crash before the commit"):
        await new_setups(session, gold, armed("lost-1"))
    await session.rollback()  # ... and goes with the evaluation
    assert await session.get(AISetup, "lost-1") is None
    assert await outbox(session) == []


# --- recipients ----------------------------------------------------------------------------------


async def test_armed_goes_to_matching_followers(
    session: AsyncSession, session_factory, redis_client, gold, make_user, fake, channels,
    notification_queue,
) -> None:  # fmt: skip
    picky = await user_with_targets(make_user, session, "picky@example.com", chat=11)
    keen = await user_with_targets(make_user, session, "keen@example.com", chat=12)
    await user_with_targets(make_user, session, "outsider@example.com", chat=13)
    await follow(session, picky, gold, min_grade="A")  # a B setup is not enough
    await follow(session, keen, gold, min_grade="B")
    await new_setups(session, gold, armed("xau-1", grade="B"))

    assert await dispatch(session_factory, redis_client, fake) == {"done": 1}
    [row] = await outbox(session)
    assert (row.status, row.attempts, row.last_error) == ("done", 0, None)
    [note] = await inbox(session)
    assert note.user_id == keen.id and note.dedup_key == "ai:xau-1:ARMED"
    assert note.severity.value == "warning"
    data = note.data
    assert (data["state"], data["direction"], data["grade"]) == ("ARMED", "buy", "B")
    assert data["transition"] == {
        "from": None, "to": "ARMED", "at": "2026-10-19T14:15:00Z", "reason": "new",
        "realized_r": None,
    }  # fmt: skip
    assert data["instrument"]["symbol"] == "XAU/USD" and data["instrument"]["price_precision"] == 2
    assert (data["entry"], data["sl"], data["tp"]) == (2400.0, 2395.0, 2410.0)
    assert data["size"] == {
        "lots": 0.04, "risk_amount": 20.0, "currency": "USD", "margin_required": 96.0,
        "feasible": True, "warnings": [], "source": "remote",
    }  # fmt: skip
    assert data["explanation"] == EXPLAINED["ar"]  # the user's language
    assert note.title == "إعداد شراء على XAU/USD: الدخول 2,400.00"
    deliveries = await session.scalars(
        select(NotificationDelivery).where(NotificationDelivery.notification_id == note.id)
    )
    assert sorted(d.channel.value for d in deliveries) == ["push", "telegram"]
    [(sent, _)] = notification_queue
    assert len(sent) == 2  # both enqueued after the commit
    assert fake.count("/v1/size") == 1 and fake.count("/v1/explain") == 1


async def test_after_armed_only_takers(
    session: AsyncSession, session_factory, redis_client, gold, make_user, fake, channels
) -> None:
    follower = await user_with_targets(make_user, session, "follower@example.com", chat=21)
    taker = await user_with_targets(make_user, session, "taker@example.com", chat=22)
    await follow(session, follower, gold)
    await new_setups(session, gold, armed("xau-1"), armed("xau-2"))
    for setup_id in ("xau-1", "xau-2"):
        session.add(AISetupTake(setup_id=setup_id, user_id=taker.id, lots=0.04, risk_amount=20.0))
    await session.commit()
    await dispatch(session_factory, redis_client, fake)  # the two ARMED, to the follower

    await transitions(
        session, gold,
        move("xau-1", "ARMED", "ACTIVE", T0 + timedelta(minutes=2)),
        move("xau-1", "ACTIVE", "CLOSED", T0 + timedelta(minutes=9), reason="tp_hit",
             realized_r=1.5),
        move("xau-2", "ARMED", "EXPIRED", T0 + timedelta(minutes=10), reason="not filled"),
    )  # fmt: skip
    assert await dispatch(session_factory, redis_client, fake) == {"done": 3}
    taker_notes = await inbox(session, taker.id)
    assert [n.data["state"] for n in taker_notes] == ["ACTIVE", "CLOSED", "EXPIRED"]
    closed = taker_notes[1].data
    assert (closed["realized_r"], closed["pnl"], closed["take"]["pnl"]) == (1.5, 30.0, 30.0)
    assert taker_notes[1].title == "أُغلق الإعداد: شراء XAU/USD +1.50R"
    assert (taker_notes[2].data["pnl"], taker_notes[2].data["reason"]) == (0.0, "not filled")
    assert [n.data["state"] for n in await inbox(session, follower.id)] == ["ARMED", "ARMED"]
    assert all(n.severity.value == "info" for n in taker_notes)


async def test_no_recipient_is_done_with_nothing(
    session: AsyncSession, session_factory, redis_client, gold, fake
) -> None:
    await new_setups(session, gold, armed("alone"))
    assert await dispatch(session_factory, redis_client, fake) == {"done": 1}
    assert (await outbox(session))[0].status == "done" and await inbox(session) == []
    assert fake.calls == []  # no size, no explanation: nobody to tell


# --- no late alerts ------------------------------------------------------------------------------


async def test_stale_armed_is_skipped_late_closed_is_sent(
    session: AsyncSession, session_factory, redis_client, gold, make_user, fake
) -> None:
    user = await user_with_targets(make_user, session, "late@example.com", chat=31)
    await follow(session, user, gold)
    await new_setups(
        session, gold,
        armed("old"),
        armed("expired", valid_until=c.iso_z(datetime.now(UTC) - timedelta(minutes=1))),
        armed("moved-on"),
    )  # fmt: skip
    await session.execute(
        update(AISetupOutbox)
        .where(AISetupOutbox.setup_id == "old")
        .values(created_at=func.now() - timedelta(seconds=901))
    )
    session.add(AISetupTake(setup_id="moved-on", user_id=user.id, lots=0.04, risk_amount=20.0))
    await session.commit()
    await transitions(session, gold, move("moved-on", "ARMED", "ACTIVE", T0 + timedelta(minutes=1)))
    await transitions(
        session, gold,
        move("moved-on", "ACTIVE", "CLOSED", T0 + timedelta(minutes=8), realized_r=-1.0),
        at=T0 + timedelta(minutes=30),
    )  # fmt: skip
    await session.execute(
        update(AISetupOutbox)
        .where(AISetupOutbox.setup_id == "moved-on", AISetupOutbox.to_state == "CLOSED")
        .values(created_at=func.now() - timedelta(hours=2))
    )
    await session.commit()

    result = await dispatch(session_factory, redis_client, fake)
    assert result == {"skipped": 3, "done": 2}
    reasons = {(r.setup_id, r.to_state): (r.status, r.last_error) for r in await outbox(session)}
    assert reasons[("old", "ARMED")][1].startswith("stale: 9")
    assert reasons[("expired", "ARMED")] == ("skipped", "stale: valid_until has passed")
    assert reasons[("moved-on", "ARMED")] == ("skipped", "stale: the setup is CLOSED now")
    notes = await inbox(session, user.id)
    assert [n.data["state"] for n in notes] == ["ACTIVE", "CLOSED"]  # the outcome always
    assert notes[1].data["late"] is True and notes[1].data["pnl"] == -20.0
    assert "(إشعار متأخر)" in notes[1].body
    assert fake.calls == []


# --- crash safety --------------------------------------------------------------------------------


async def test_failure_retries_then_succeeds_without_duplicates(
    session: AsyncSession, session_factory, redis_client, gold, make_user, fake, channels,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    user = await user_with_targets(make_user, session, "crash@example.com", chat=41)
    await follow(session, user, gold)
    await new_setups(session, gold, armed("xau-1"))
    real_prepare = notifications.prepare

    async def broken(*args, **kw):
        raise ConnectionError("database went away")

    monkeypatch.setattr(notifications, "prepare", broken)
    before = datetime.now(UTC)
    assert await dispatch(session_factory, redis_client, fake) == {"retry": 1}
    [row] = await outbox(session)
    assert (row.status, row.attempts) == ("pending", 1)
    assert row.last_error == "ConnectionError: database went away"
    assert row.next_attempt_at >= before + timedelta(seconds=2)  # backoff
    assert await dispatch(session_factory, redis_client, fake) == {}  # not due yet
    assert await inbox(session) == []

    monkeypatch.setattr(notifications, "prepare", real_prepare)
    later = row.next_attempt_at + timedelta(seconds=1)
    assert await dispatch(session_factory, redis_client, fake, now=later) == {"done": 1}
    deliveries = await session.scalar(select(func.count()).select_from(NotificationDelivery))
    # a crash after the commit of the inbox but before the row says done: the row runs again
    await session.execute(update(AISetupOutbox).values(status="pending"))
    await session.commit()
    assert await dispatch(session_factory, redis_client, fake, now=later) == {"done": 1}
    assert len(await inbox(session)) == 1  # dedup_key ai:xau-1:ARMED
    assert await session.scalar(select(func.count()).select_from(NotificationDelivery)) == (
        deliveries
    )


async def test_failed_after_max_attempts_and_admin_retry(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client, gold, make_user,
    admin_headers, fake, monkeypatch: pytest.MonkeyPatch, caplog,
) -> None:  # fmt: skip
    caplog.set_level(logging.ERROR, logger=LOGGER)
    user = await user_with_targets(make_user, session, "fails@example.com", chat=51)
    await follow(session, user, gold)
    await new_setups(session, gold, armed("xau-1"))
    real_prepare = notifications.prepare
    calls = []

    async def broken(s, r, items, now=None):
        if any(i.type == NotificationType.ai_setup for i in items):
            calls.append(1)
            raise ValueError("bad template")
        return await real_prepare(s, r, items, now)

    monkeypatch.setattr(notifications, "prepare", broken)
    now = datetime.now(UTC)
    for _ in range(8):  # each time just after the row's backoff (still under the 900 s age)
        await dispatch(session_factory, redis_client, fake, now=now)
        [row] = await outbox(session)
        now = row.next_attempt_at + timedelta(seconds=1)
    [row] = await outbox(session)
    assert (row.status, row.attempts, len(calls)) == ("failed", 8, 8)
    assert "failed for good" in caplog.text
    admin_note = await session.scalar(
        select(Notification).where(Notification.type == NotificationType.system)
    )
    assert admin_note.data["title"] == f"AI alert {row.id} failed"
    assert await dispatch(session_factory, redis_client, fake, now=now) == {}  # failed stays

    listed = await client.get("/api/v1/admin/ai/outbox?status=failed", headers=admin_headers)
    assert listed.json()["total"] == 1 and listed.json()["items"][0]["attempts"] == 8
    monkeypatch.setattr(alerts, "kick", lambda: None)
    res = await client.post(f"/api/v1/admin/ai/outbox/{row.id}/retry", headers=admin_headers)
    assert res.status_code == 200 and res.json()["status"] == "pending"
    assert res.json()["attempts"] == 8
    again = await client.post(f"/api/v1/admin/ai/outbox/{row.id}/retry", headers=admin_headers)
    assert again.status_code == 409
    monkeypatch.setattr(notifications, "prepare", real_prepare)
    assert await dispatch(session_factory, redis_client, fake) == {"done": 1}
    assert len(await inbox(session, user.id)) == 1


async def test_two_dispatchers_process_each_row_once(
    committed_session_factory, redis_client: Redis, fake
) -> None:
    """Real row locks (a pool of its own): two dispatchers at once share the rows."""
    factory = committed_session_factory
    async with factory() as session:
        instrument = await make_instrument(
            session, "XAU/USD", "fxpro", market=MarketType.commodity, **GOLD_SPECS
        )
        user = User(email="race@example.com", hashed_password="x", role=UserRole.trader)
        session.add(user)
        await session.commit()
        session.add(AIAlertFollow(user_id=user.id, instrument_id=instrument.id, profile="intraday"))
        await session.commit()
        await new_setups(session, instrument, *[armed(f"race-{i}") for i in range(6)])
    try:
        results = await asyncio.gather(
            alerts.dispatch(factory, redis_client, client=fake.client()),
            alerts.dispatch(factory, redis_client, client=fake.client()),
        )
        assert sum(r.get("done", 0) for r in results) == 6  # each row exactly once
        async with factory() as session:
            count = select(func.count()).select_from(Notification)
            assert await session.scalar(count.where(Notification.user_id == user.id)) == 6
            rows = await session.scalars(select(AISetupOutbox.status))
            assert list(rows) == ["done"] * 6
    finally:
        async with factory() as session:  # the model version this evaluation reported
            reported = response(request_at(T0)).versions.model
            await session.execute(delete(AIModelVersion).where(AIModelVersion.model_id == reported))
            await session.commit()


# --- explanations --------------------------------------------------------------------------------


async def test_explanations_stored_reused_and_per_language(
    session: AsyncSession, session_factory, redis_client, gold, make_user, fake
) -> None:
    arabic = await user_with_targets(make_user, session, "ar@example.com", chat=61)
    english = await user_with_targets(make_user, session, "en@example.com", chat=62, lang="en")
    for user in (arabic, english):
        await follow(session, user, gold)
    await new_setups(session, gold, armed("xau-1"))
    await dispatch(session_factory, redis_client, fake)
    assert fake.count("/v1/explain") == 2  # ar and en
    assert {b["lang"] for p, b in fake.calls if p == "/v1/explain"} == {"ar", "en"}
    assert (await inbox(session, english.id))[0].data["explanation"] == EXPLAINED["en"]
    assert (await inbox(session, english.id))[0].title == "BUY setup XAU/USD: entry 2,400.00"
    stored = await session.scalars(select(AISetupExplanation).order_by(AISetupExplanation.lang))
    assert [(e.lang, e.verified) for e in stored] == [("ar", True), ("en", True)]

    await session.execute(update(AISetupOutbox).values(status="pending"))  # handled again
    await session.commit()
    await dispatch(session_factory, redis_client, fake)
    assert fake.count("/v1/explain") == 2  # reused, not asked again


async def test_explain_unavailable_or_unverified(
    session: AsyncSession, session_factory, redis_client, gold, make_user, fake
) -> None:
    user = await user_with_targets(make_user, session, "noexplain@example.com", chat=71)
    await follow(session, user, gold)
    await new_setups(session, gold, armed("xau-1"), armed("xau-2"))
    fake.explain_status = "timeout"
    assert await dispatch(session_factory, redis_client, fake) == {"done": 2}
    assert fake.count("/v1/explain") == 1  # one attempt, then the run stops asking
    assert all("explanation" not in n.data for n in await inbox(session))
    assert await session.scalar(select(func.count()).select_from(AISetupExplanation)) == 0

    fake.explain_status, fake.verified = 200, False
    await new_setups(session, gold, armed("xau-3"))
    await dispatch(session_factory, redis_client, fake)
    note = (await inbox(session))[-1]
    assert note.data["setup_id"] == "xau-3" and "explanation" not in note.data
    assert note.data["explanation_status"] == "unavailable"
    # neither verified nor a template (B9, Fadi's rule): not stored, never sent
    assert await session.get(AISetupExplanation, ("xau-3", "ar")) is None

    fake.template_used = True  # not verified, but the fixed template: sent
    await new_setups(session, gold, armed("xau-5"))
    await dispatch(session_factory, redis_client, fake)
    note = (await inbox(session))[-1]
    assert note.data["setup_id"] == "xau-5" and note.data["explanation"]
    assert (await session.get(AISetupExplanation, ("xau-5", "ar"))).template_used is True
    fake.template_used = False

    fake.explain_status = 404
    await new_setups(session, gold, armed("xau-4"))
    assert await dispatch(session_factory, redis_client, fake) == {"done": 1}
    assert "explanation" not in (await inbox(session))[-1].data


# --- sizes and preferences -----------------------------------------------------------------------


async def test_sizes_never_block_the_alert(
    session: AsyncSession, session_factory, redis_client, gold, make_user, fake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    monkeypatch.setattr(get_settings(), "ai_size_mode", "local")
    ok = await user_with_targets(make_user, session, "ok@example.com", chat=81)
    small = await user_with_targets(make_user, session, "small@example.com", chat=82)
    broken = await user_with_targets(make_user, session, "broken@example.com", chat=83)
    await profile(session, small, balance=100)  # 1 USD at risk: below the minimum lot
    await profile(session, broken, currency="X")  # not a contract currency
    for user in (ok, small, broken):
        await follow(session, user, gold)
    await new_setups(session, gold, armed("xau-1"))
    assert await dispatch(session_factory, redis_client, fake) == {"done": 1}
    sizes = {n.user_id: n.data["size"] for n in await inbox(session)}
    assert sizes[ok.id]["lots"] == 0.04 and sizes[ok.id]["source"] == "local"
    assert sizes[small.id]["feasible"] is False and sizes[small.id]["lots"] == 0.0
    assert any("minimum" in w for w in sizes[small.id]["warnings"])
    assert sizes[broken.id]["error"].startswith("the risk profile cannot be used: currency")
    small_note = next(n for n in await inbox(session) if n.user_id == small.id)
    assert "لا يوجد حجم مناسب لحسابك" in small_note.body


async def test_preferences_apply(
    session: AsyncSession, session_factory, redis_client, gold, make_user, fake, channels
) -> None:
    quiet = await user_with_targets(make_user, session, "quiet@example.com", chat=91)
    no_telegram = await user_with_targets(make_user, session, "notg@example.com", chat=92)
    now = datetime.now(UTC)
    start, end = (
        (now - timedelta(hours=1)).strftime("%H:%M"),
        (now + timedelta(hours=1)).strftime("%H:%M"),
    )
    row = await prefs_mod.get_or_create(session, quiet.id)
    row.quiet_hours = {"start": start, "end": end, "tz": "UTC"}
    row = await prefs_mod.get_or_create(session, no_telegram.id)
    row.matrix = {"ai_setup": {"telegram": False, "email": False, "push": True}}
    await session.commit()
    for user in (quiet, no_telegram):
        await follow(session, user, gold)
    await new_setups(session, gold, armed("xau-1"))
    await dispatch(session_factory, redis_client, fake)

    async def deliveries(user):
        rows = await session.execute(
            select(NotificationDelivery.channel, NotificationDelivery.hold)
            .join(Notification, Notification.id == NotificationDelivery.notification_id)
            .where(Notification.user_id == user.id)
        )
        return sorted((ch.value, hold) for ch, hold in rows.all())

    assert await deliveries(quiet) == [("push", "quiet_hours"), ("telegram", "quiet_hours")]
    assert await deliveries(no_telegram) == [("push", None)]  # inbox + push only
    assert len(await inbox(session, no_telegram.id)) == 1
    assert await session.get(NotificationPreference, quiet.id) is not None


# --- live frames ---------------------------------------------------------------------------------


async def test_live_frame_once_after_commit(
    session: AsyncSession, session_factory, redis_client, gold, fake
) -> None:
    async with Listener(redis_client) as listener:
        await listener.listen(ai_setups_topic(gold.id))
        await new_setups(session, gold, armed("xau-1"))
        assert await listener.messages() == []  # the evaluation itself publishes nothing
        await dispatch(session_factory, redis_client, fake)
        [(topic, frame)] = await listener.messages()
        await dispatch(session_factory, redis_client, fake)
        assert await listener.messages() == []  # once per state change
    assert topic == f"ai:setups:{gold.id}"
    assert frame["type"] == "ai_setup" and frame["topic"] == topic
    assert frame["setup"]["setup_id"] == "xau-1" and frame["setup"]["state"] == "ARMED"
    assert frame["transition"] == {
        "setup_id": "xau-1", "from": None, "to": "ARMED", "at": "2026-10-19T14:15:00Z",
        "reason": "new", "realized_r": None,
    }  # fmt: skip


async def test_ws_topic(client, hub, session: AsyncSession, gold, make_user) -> None:
    from app.core.security import create_access_token
    from tests.ws_utils import recv_until, ws_connect

    user = await make_user("ws-ai@example.com")
    async with ws_connect(create_access_token(user)) as ws:
        await ws.send_text(
            json.dumps({"op": "subscribe", "topic": "ai_setups", "instrument_id": str(gold.id)})
        )
        msg = await recv_until(ws, lambda m: m["type"] != "heartbeat")
        assert msg == {"type": "subscribed", "topic": f"ai:setups:{gold.id}"}
        await ws.send_text(json.dumps({"op": "subscribe", "topic": "ai_setups"}))
        msg = await recv_until(ws, lambda m: m["type"] != "heartbeat")
        assert msg["type"] == "error" and "instrument_id" in msg["message"]


def test_beat_and_routes() -> None:
    schedule = celery_app.conf.beat_schedule
    assert schedule["ai-alerts-dispatch"]["task"] == "ai_alerts.dispatch"
    assert schedule["ai-alerts-dispatch"]["schedule"] == timedelta(seconds=30)
    assert schedule["notifications-sweep"]["task"] == "notifications.sweep"
    assert celery_app.amqp.router.route({}, "ai_alerts.dispatch")["queue"].name == "notifications"


# --- follows API ---------------------------------------------------------------------------------


async def test_follows_api(client: AsyncClient, session: AsyncSession, gold, make_user, login):
    await make_user("fa@example.com")
    await make_user("fb@example.com")
    a = bearer((await login("fa@example.com"))["access_token"])
    b = bearer((await login("fb@example.com"))["access_token"])
    url = f"/api/v1/me/ai/follows/{gold.id}/intraday"
    first = await client.put(url, headers=a)
    assert first.status_code == 200 and first.json()["min_grade"] is None
    again = await client.put(url, json={"min_grade": "B"}, headers=a)
    assert again.status_code == 200 and again.json()["min_grade"] == "B"
    assert again.json()["created_at"] == first.json()["created_at"]
    listed = (await client.get("/api/v1/me/ai/follows", headers=a)).json()
    assert [(f["instrument_id"], f["profile"], f["min_grade"]) for f in listed] == [
        (str(gold.id), "intraday", "B")
    ]
    assert (await client.get("/api/v1/me/ai/follows", headers=b)).json() == []  # isolated
    assert (await client.delete(url, headers=b)).status_code == 404
    assert (await client.put(url, json={"min_grade": "E"}, headers=a)).status_code == 422
    bad_profile = f"/api/v1/me/ai/follows/{gold.id}/scalping"
    assert (await client.put(bad_profile, headers=a)).status_code == 422
    unknown = f"/api/v1/me/ai/follows/{uuid.uuid4()}/intraday"
    assert (await client.put(unknown, headers=a)).status_code == 404
    assert (await client.delete(url, headers=a)).status_code == 204
    assert (await client.delete(url, headers=a)).status_code == 404
    assert (await client.get("/api/v1/me/ai/follows")).status_code == 401


# --- admin and status ----------------------------------------------------------------------------


async def test_admin_views_and_status(
    client: AsyncClient, session: AsyncSession, session_factory, redis_client, gold, admin_headers,
    fake,
) -> None:  # fmt: skip
    await new_setups(session, gold, armed("xau-1"), armed("xau-2"))
    await dispatch(session_factory, redis_client, fake)
    await transitions(session, gold, move("xau-1", "ARMED", "ACTIVE", T0 + timedelta(minutes=3)))
    status = (await client.get("/api/v1/admin/system/status", headers=admin_headers)).json()
    assert status["ai_alerts"]["outbox"] == {"pending": 1, "done": 2, "skipped": 0, "failed": 0}
    assert status["ai_alerts"]["oldest_pending_seconds"] >= 0
    assert "ai_alerts.dispatch" in status["celery"]["tasks"]
    detail = (await client.get("/api/v1/admin/ai/setups/xau-1", headers=admin_headers)).json()
    assert [(o["to_state"], o["status"]) for o in detail["outbox"]] == [
        ("ARMED", "done"),
        ("ACTIVE", "pending"),
    ]
    assert "sizes" in detail and "takes_count" in detail and "events" in detail
    page = (await client.get("/api/v1/admin/ai/outbox?limit=2", headers=admin_headers)).json()
    assert page["total"] == 3 and [i["to_state"] for i in page["items"]] == ["ACTIVE", "ARMED"]
    res = await client.post(f"/api/v1/admin/ai/outbox/{page['items'][0]['id']}/retry",
                            headers=admin_headers)  # fmt: skip
    assert res.status_code == 409  # only failed rows
    assert (
        await client.post("/api/v1/admin/ai/outbox/999999/retry", headers=admin_headers)
    ).status_code == 404
