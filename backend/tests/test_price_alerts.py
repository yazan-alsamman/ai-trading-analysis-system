"""Price alerts: every condition on hand-built 1m bars (gaps, the forming bucket), once vs
every + cooldown, dedup per bar, expiry, the API (validation, limits, ownership, history),
notification content in Arabic and English, the tick task and the evaluation time with 1,000
alerts on 3 instruments."""

import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts import engine
from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.notification import Notification, NotificationPreference, NotificationType
from app.models.price_alert import PriceAlert
from app.models.user import UserRole
from app.notifications.preferences import PreferencesIn
from app.realtime.topics import user_topic
from app.schemas.market import CandleIn
from app.services import market_service
from app.tasks import alerts as alert_tasks
from tests.market_utils import make_instrument
from tests.test_signal_engine import Listener
from tests.utils import bearer

ALERTS = "/api/v1/me/price-alerts"
T0 = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
B = T0 + timedelta(minutes=3)  # the bar evaluated in most tests
# (open, high, low, close) of T0, T0+1, T0+2, B
BARS = [
    (100.0, 100.5, 99.5, 100.0),
    (100.0, 101.0, 99.0, 100.8),
    (100.8, 102.0, 100.5, 101.9),
    (101.9, 103.0, 101.5, 102.5),
]


@pytest.fixture(autouse=True)
async def _clean_alert_locks(redis_client: Redis):
    keys = [k async for k in redis_client.scan_iter(match="lock:alerts:*")]
    if keys:
        await redis_client.delete(*keys)
    yield
    keys = [k async for k in redis_client.scan_iter(match="lock:alerts:*")]
    if keys:
        await redis_client.delete(*keys)


@pytest.fixture
async def trader(make_user):
    user = await make_user("trader@example.com")
    return user, bearer(create_access_token(user))


@pytest.fixture
async def btc(session: AsyncSession):
    return await make_instrument(session, "BTC/USDT", price_precision=2)


async def _bars(session, instrument, bars, start=T0, skip=()):
    candles = [
        CandleIn(ts=start + timedelta(minutes=i), open=o, high=h, low=lo, close=c, volume=1)
        for i, (o, h, lo, c) in enumerate(bars)
        if i not in skip
    ]
    await market_service.upsert_candles(session, instrument.id, candles)
    await session.commit()


async def _alert(session, user, instrument, condition, value, **over) -> PriceAlert:
    row = PriceAlert(
        user_id=user.id,
        instrument_id=instrument.id,
        condition=condition,
        value=value,
        created_at=over.pop("created_at", T0 - timedelta(hours=1)),
        **over,
    )
    session.add(row)
    await session.commit()
    return row


async def _run(session_factory, redis, bar=B, now=None):
    return await engine.evaluate(session_factory, redis, bar, now=now or bar + timedelta(minutes=1))


async def _fired(session: AsyncSession) -> dict[str, dict]:
    rows = await session.scalars(
        select(Notification).where(Notification.type == NotificationType.price_alert)
    )
    return {n.data["alert_id"]: n for n in rows}


async def test_every_condition(
    session: AsyncSession, session_factory, redis_client, trader, btc
) -> None:
    user, _ = trader
    await _bars(session, btc, BARS)
    a = {
        "above": await _alert(session, user, btc, "above", 102.9),
        "above_no": await _alert(session, user, btc, "above", 103.1),
        "below": await _alert(session, user, btc, "below", 101.6),
        "below_no": await _alert(session, user, btc, "below", 101.4),
        "cross_up": await _alert(session, user, btc, "crosses_above", 102.0),
        "cross_up_no": await _alert(session, user, btc, "crosses_above", 101.0),  # already above
        "cross_down_no": await _alert(session, user, btc, "crosses_below", 102.0),
        "move": await _alert(session, user, btc, "change_pct", 2.0, window_minutes=3),
        "move_no": await _alert(session, user, btc, "change_pct", 3.0, window_minutes=3),
        "move_no_ref": await _alert(session, user, btc, "change_pct", 0.1, window_minutes=10),
    }
    run = await _run(session_factory, redis_client)
    assert (run.status, run.alerts, run.instruments, run.fired, run.notifications) == (
        "done",
        10,
        1,
        4,
        4,
    )
    fired = await _fired(session)
    assert set(fired) == {str(a[k].id) for k in ("above", "below", "cross_up", "move")}
    data = {k: fired[str(a[k].id)].data for k in ("above", "below", "cross_up", "move")}
    assert data["above"]["price"] == 103.0 and data["below"]["price"] == 101.5
    assert data["cross_up"]["price"] == 102.5 and data["cross_up"]["previous_close"] == 101.9
    assert data["move"]["reference_close"] == 100.0 and data["move"]["change_pct"] == 2.5
    assert data["above"]["bar_time"] == B.isoformat()
    assert all(fired[str(a[k].id)].severity == "warning" for k in data)
    assert fired[str(a["above"].id)].dedup_key == f"price_alert:{a['above'].id}:{B.isoformat()}"


async def test_crosses_below_and_moves_down(session, session_factory, redis_client, trader, btc):
    user, _ = trader
    down = [(100, 100, 100, 100), (100, 100, 99, 99.5), (99.5, 99.6, 97, 97.4)]
    await _bars(session, btc, down)
    cross = await _alert(session, user, btc, "crosses_below", 98.0)
    move = await _alert(session, user, btc, "change_pct", 2.5, window_minutes=2)
    run = await _run(session_factory, redis_client, bar=T0 + timedelta(minutes=2))
    assert run.fired == 2
    fired = await _fired(session)
    assert fired[str(move.id)].data["change_pct"] == -2.6
    assert fired[str(cross.id)].data["price"] == 97.4


async def test_gaps_and_the_forming_bucket(session, session_factory, redis_client, trader, btc):
    user, _ = trader
    # T0+2 is missing: the previous close comes from T0+1; the forming bar B+1 spikes to 200
    await _bars(session, btc, [*BARS, (102.5, 200.0, 102.0, 199.0)], skip=(2,))
    cross = await _alert(session, user, btc, "crosses_above", 101.0)  # 100.8 -> 102.5
    spike = await _alert(session, user, btc, "above", 150.0)
    run = await _run(session_factory, redis_client)
    assert run.fired == 1
    assert set(await _fired(session)) == {str(cross.id)}
    # a bar without a candle (gap) fires nothing
    gap = await _run(session_factory, redis_client, bar=T0 + timedelta(minutes=2))
    assert (gap.no_bar, gap.fired) == (1, 0)
    assert spike.is_active


async def test_once_and_every_with_cooldown(session, session_factory, redis_client, trader, btc):
    user, _ = trader
    flat = [(103.0, 103.5, 102.8, 103.2)] * 12
    await _bars(session, btc, flat)
    once = await _alert(session, user, btc, "above", 103.0)
    every = await _alert(session, user, btc, "above", 103.0, repeat="every", cooldown_minutes=5)
    fired_at = []
    for minute in range(11):
        run = await _run(session_factory, redis_client, bar=T0 + timedelta(minutes=minute))
        if run.fired:
            fired_at.append((minute, run.fired, run.deactivated))
    # minute 0: both fire, once is switched off; then every 5 minutes (cooldown from bar end)
    assert fired_at == [(0, 2, 1), (5, 1, 0), (10, 1, 0)]
    await session.refresh(once)
    await session.refresh(every)
    assert (once.is_active, once.trigger_count) == (False, 1)
    assert (every.is_active, every.trigger_count) == (True, 3)
    assert every.last_triggered_at == T0 + timedelta(minutes=11)


async def test_dedup_per_bar(session, session_factory, redis_client, trader, btc):
    user, _ = trader
    await _bars(session, btc, BARS)
    alert = await _alert(session, user, btc, "above", 100.0, repeat="every", cooldown_minutes=1)
    first = await _run(session_factory, redis_client)
    again = await _run(session_factory, redis_client)
    assert (first.notifications, again.status) == (1, "already_done")
    await redis_client.delete(f"lock:alerts:{B.isoformat()}")  # e.g. a redelivered task
    alert.last_triggered_at = None  # even if the alert were eligible again
    await session.commit()
    third = await _run(session_factory, redis_client)
    assert (third.fired, third.notifications) == (1, 0)  # the dedup key stops it
    await session.refresh(alert)
    assert alert.trigger_count == 1
    assert len(await _fired(session)) == 1


async def test_expiry_and_creation_time(session, session_factory, redis_client, trader, btc):
    user, _ = trader
    await _bars(session, btc, BARS)
    expired = await _alert(session, user, btc, "above", 100.0, expires_at=B)
    late = await _alert(session, user, btc, "above", 100.0, created_at=B + timedelta(minutes=2))
    run = await _run(session_factory, redis_client, now=B + timedelta(minutes=1))
    assert (run.expired, run.alerts, run.fired) == (1, 1, 0)  # late: created after the bar
    await session.refresh(expired)
    assert not expired.is_active and late.is_active


async def test_notification_text_in_both_languages(
    session, session_factory, redis_client, trader, btc, make_user
):
    ar_user, _ = trader
    en_user = await make_user("en@example.com")
    session.add(NotificationPreference(user_id=en_user.id, **PreferencesIn(language="en").stored()))
    await session.commit()
    await _bars(session, btc, BARS)
    await _alert(session, ar_user, btc, "crosses_above", 102.0, note="هدف أول")
    await _alert(session, en_user, btc, "change_pct", 2.0, window_minutes=3, note="breakout")
    async with Listener(redis_client) as listener:
        await listener.listen(user_topic(en_user.id))
        await _run(session_factory, redis_client)
        messages = await listener.messages(notifications=True)
    notes = {n.user_id: n for n in (await _fired(session)).values()}
    ar, en = notes[ar_user.id], notes[en_user.id]
    assert ar.title == "تنبيه سعر: BTC/USDT اخترق صعوداً 102.00"
    assert ar.body.splitlines() == [
        "السعر: 102.50 (شمعة الدقيقة 2026-03-02 12:03 UTC)",
        "الشرط: الإغلاق اخترق صعوداً 102.00 (الإغلاق السابق 101.90)",
        "ملاحظة: هدف أول",
        "تم إيقاف هذا التنبيه (يعمل مرة واحدة).",
    ]
    assert en.title == "Price alert: BTC/USDT moved +2.50% in 3 min"
    assert en.body.splitlines()[:3] == [
        "Price: 102.50 (1m bar 2026-03-02 12:03 UTC)",
        "Rule: move ≥ 2.00% in 3 min (from 100.00)",
        "Note: breakout",
    ]
    types = sorted(m["type"] for _, m in messages)
    assert types == ["notification", "price_alert"]
    alert_msg = next(m for _, m in messages if m["type"] == "price_alert")
    assert alert_msg["notification_id"] == str(en.id) and alert_msg["price"] == 102.5


# --- API -----------------------------------------------------------------------------------------


async def test_api_create_validate_and_warn(client: AsyncClient, session, trader, btc) -> None:
    _, h = trader
    await _bars(session, btc, BARS)
    res = await client.post(
        ALERTS,
        json={"instrument_id": str(btc.id), "condition": "above", "value": 100, "note": "x"},
        headers=h,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert (body["current_price"], body["would_trigger_now"]) == (102.5, True)
    assert body["instrument"] == {"id": str(btc.id), "symbol": "BTC/USDT"}
    assert (body["repeat"], body["cooldown_minutes"], body["is_active"]) == ("once", None, True)
    res = await client.post(
        ALERTS,
        json={"instrument_id": str(btc.id), "condition": "below", "value": 90, "repeat": "every"},
        headers=h,
    )
    assert (res.json()["would_trigger_now"], res.json()["cooldown_minutes"]) == (False, 60)
    for bad in (
        {"condition": "change_pct", "value": 2},
        {"condition": "above", "value": 2, "window_minutes": 5},
        {"condition": "above", "value": -1},
        {"condition": "change_pct", "value": 150, "window_minutes": 5},
        {"condition": "above", "value": 1, "cooldown_minutes": 5},
        {"condition": "above", "value": 1, "expires_at": "2020-01-01T00:00:00Z"},
        {"condition": "sideways", "value": 1},
    ):
        res = await client.post(ALERTS, json={"instrument_id": str(btc.id), **bad}, headers=h)
        assert res.status_code == 422, bad
    res = await client.post(
        ALERTS,
        json={"instrument_id": str(uuid.uuid4()), "condition": "above", "value": 1},
        headers=h,
    )
    assert res.status_code == 404


async def test_api_limits_ownership_update_delete(
    client: AsyncClient, session, trader, btc, make_user, monkeypatch
) -> None:
    _, h = trader
    monkeypatch.setattr(get_settings(), "price_alert_limit_trader", 2)
    body = {"instrument_id": str(btc.id), "condition": "above", "value": 1}
    first = (await client.post(ALERTS, json=body, headers=h)).json()
    await client.post(ALERTS, json=body, headers=h)
    res = await client.post(ALERTS, json=body, headers=h)
    assert res.status_code == 400 and "At most 2" in res.json()["detail"]
    # deactivating frees a slot; reactivating over the limit is refused
    url = f"{ALERTS}/{first['id']}"
    assert (await client.patch(url, json={"is_active": False}, headers=h)).json()[
        "is_active"
    ] is False
    assert (await client.post(ALERTS, json=body, headers=h)).status_code == 201
    assert (await client.patch(url, json={"is_active": True}, headers=h)).status_code == 400
    # switching condition re-validates the whole alert
    res = await client.patch(url, json={"condition": "change_pct"}, headers=h)
    assert res.status_code == 422
    res = await client.patch(url, json={"condition": "change_pct", "window_minutes": 15}, headers=h)
    assert (res.json()["condition"], res.json()["window_minutes"]) == ("change_pct", 15)
    res = await client.patch(url, json={"condition": "below"}, headers=h)
    assert res.json()["window_minutes"] is None
    res = await client.patch(url, json={"repeat": "every"}, headers=h)
    assert res.json()["cooldown_minutes"] == 60
    # someone else's alert does not exist for you
    other = await make_user("other@example.com", role=UserRole.analyst)
    oh = bearer(create_access_token(other))
    assert (await client.patch(url, json={"note": "x"}, headers=oh)).status_code == 404
    assert (await client.delete(url, headers=oh)).status_code == 404
    assert (await client.get(ALERTS, headers=oh)).json()["total"] == 0
    listing = (await client.get(ALERTS, params={"is_active": True}, headers=h)).json()
    assert listing["total"] == 2
    assert (await client.delete(url, headers=h)).status_code == 204
    assert (await client.get(ALERTS, headers=h)).json()["total"] == 2


async def test_history(client, session, session_factory, redis_client, trader, btc) -> None:
    user, h = trader
    await _bars(session, btc, BARS)
    alert = await _alert(session, user, btc, "above", 102.9, note="tp1")
    await _run(session_factory, redis_client)
    page = (await client.get(f"{ALERTS}/history", headers=h)).json()
    [item] = page["items"]
    assert item["alert_id"] == str(alert.id) and item["symbol"] == "BTC/USDT"
    assert (item["condition"], item["value"], item["price"], item["note"]) == (
        "above",
        102.9,
        103.0,
        "tp1",
    )
    assert item["bar_time"].startswith("2026-03-02T12:03")
    other = (
        await client.get(f"{ALERTS}/history", params={"alert_id": str(uuid.uuid4())}, headers=h)
    ).json()
    assert other["total"] == 0


def test_tick_schedules_the_closed_bar(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        alert_tasks.evaluate, "apply_async", lambda args, eta: calls.append((args, eta))
    )
    bar = alert_tasks.tick.run()
    [(args, eta)] = calls
    assert args == (bar,)
    bar_time = datetime.fromisoformat(bar)
    assert bar_time.second == 0 and eta == bar_time + timedelta(minutes=1, seconds=10)


async def test_evaluation_time_with_1000_alerts(
    session, session_factory, redis_client, make_user
) -> None:
    """1,000 active alerts on 3 instruments (10 fire): the per-minute run."""
    users = [await make_user(f"u{i}@example.com") for i in range(50)]
    instruments = [await make_instrument(session, s) for s in ("BTC/USDT", "ETH/USDT", "SOL/USDT")]
    for instrument in instruments:
        await _bars(session, instrument, BARS)
    conditions = ["above", "below", "crosses_above", "crosses_below", "change_pct"]
    rows = []
    for i in range(1000):
        condition = conditions[i % 5]
        value = {
            "above": 500.0,
            "below": 1.0,
            "crosses_above": 500.0,
            "crosses_below": 1.0,
            "change_pct": 50.0,
        }[condition]
        if i < 10:
            condition, value = "above", 102.0  # these fire
        rows.append(
            {
                "user_id": users[i % 50].id,
                "instrument_id": instruments[i % 3].id,
                "condition": condition,
                "value": value,
                "window_minutes": [1, 3, 15, 60][i % 4] if condition == "change_pct" else None,
                "created_at": T0 - timedelta(hours=1),
            }
        )
    await session.execute(insert(PriceAlert), rows)
    await session.commit()
    started = time.perf_counter()
    run = await _run(session_factory, redis_client)
    elapsed = (time.perf_counter() - started) * 1000
    assert (run.alerts, run.instruments, run.fired, run.notifications) == (1000, 3, 10, 10)
    print(f"\n[alerts] 1000 alerts / 3 instruments / 10 fired: {run.duration_ms} ms")
    await redis_client.delete(f"lock:alerts:{(B + timedelta(minutes=1)).isoformat()}")
    quiet = await _run(session_factory, redis_client, bar=B - timedelta(minutes=1))
    print(f"[alerts] 1000 alerts / 3 instruments / none fired: {quiet.duration_ms} ms")
    assert elapsed < 5000 and quiet.duration_ms < 5000
