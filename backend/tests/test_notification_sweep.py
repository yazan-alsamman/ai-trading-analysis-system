"""B11 part D: the stuck-delivery sweeper. A crash between the producer's commit and the
enqueue (or a lost retry task) leaves pending deliveries nobody sends; ``notifications.sweep``
enqueues them again, and the send claim (``FOR UPDATE SKIP LOCKED``, pending only) keeps a
duplicate task from sending twice."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.notification import DeliveryStatus, NotificationDelivery, TelegramLink
from app.models.user import User, UserRole
from app.notifications import service
from app.tasks import notifications as notification_tasks
from tests.notification_utils import TOKEN, FakeTelegram, item


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> FakeTelegram:
    fake = FakeTelegram()
    monkeypatch.setattr(get_settings(), "telegram_bot_token", TOKEN)
    monkeypatch.setattr(service, "telegram_client", fake.client)
    return fake


async def _user(session: AsyncSession, email: str, chat: int) -> User:
    user = User(email=email, hashed_password="x", role=UserRole.trader)
    session.add(user)
    await session.commit()
    session.add(TelegramLink(user_id=user.id, chat_id=chat, username="u"))
    await session.commit()
    return user


async def _deliveries(session: AsyncSession, user: User) -> list[NotificationDelivery]:
    from app.models.notification import Notification

    rows = await session.scalars(
        select(NotificationDelivery)
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
        .where(Notification.user_id == user.id)
        .order_by(NotificationDelivery.created_at)
        .execution_options(populate_existing=True)
    )
    return list(rows.all())


async def test_stuck_deliveries_are_sent_exactly_once(
    committed_session_factory, redis_client: Redis, telegram: FakeTelegram, notification_queue
) -> None:
    """Real row locks (a pool of its own): the swept task and the original send run at once."""
    factory = committed_session_factory
    async with factory() as session:
        user = await _user(session, "sweep@example.com", 5001)
        # the producer commits, then "crashes" before after_commit: nothing is enqueued
        prepared = await service.prepare(session, redis_client, [item(user.id) for _ in range(3)])
        await session.commit()
        assert len(prepared.send_ids) == 3 and notification_queue == []
        ids = prepared.send_ids
        assert (await service.sweep_stuck(factory)).requeued == []  # too young: its task may come
        await session.execute(
            update(NotificationDelivery)
            .where(NotificationDelivery.id.in_(ids))
            .values(created_at=datetime.now(UTC) - timedelta(seconds=121))
        )
        await session.commit()

    swept = (await service.sweep_stuck(factory)).requeued
    assert sorted(swept) == sorted(ids)
    assert sorted(notification_queue[-1][0]) == sorted(ids)  # enqueued with the normal path
    # the swept task and a late original task, at the same time
    await asyncio.gather(
        service.send_deliveries(factory, redis_client, swept),
        service.send_deliveries(factory, redis_client, ids),
    )
    assert len(telegram.sent()) == 3  # each delivery exactly once
    async with factory() as session:
        assert {d.status for d in await _deliveries(session, user)} == {DeliveryStatus.sent}
    assert (await service.sweep_stuck(factory)).requeued == []


async def test_what_the_sweeper_leaves_alone(
    session: AsyncSession, session_factory, make_user, redis_client: Redis, telegram
) -> None:
    user = await make_user("leave@example.com")
    session.add(TelegramLink(user_id=user.id, chat_id=5002, username="u"))
    await session.commit()
    prepared = await service.prepare(session, redis_client, [item(user.id) for _ in range(5)])
    await session.commit()
    old = datetime.now(UTC) - timedelta(minutes=10)
    held, retry_later, retry_lost, sent, fresh = prepared.send_ids
    await session.execute(
        update(NotificationDelivery)
        .where(NotificationDelivery.id.in_([held, retry_later, retry_lost, sent]))
        .values(created_at=old)
    )
    await session.execute(  # quiet hours: waits for its digest
        update(NotificationDelivery)
        .where(NotificationDelivery.id == held)
        .values(hold="quiet_hours", release_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.execute(  # a retry whose task is due in a minute
        update(NotificationDelivery)
        .where(NotificationDelivery.id == retry_later)
        .values(attempts=1, next_attempt_at=datetime.now(UTC) + timedelta(minutes=1))
    )
    await session.execute(  # a retry whose task never came
        update(NotificationDelivery)
        .where(NotificationDelivery.id == retry_lost)
        .values(attempts=2, next_attempt_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    await session.execute(
        update(NotificationDelivery)
        .where(NotificationDelivery.id == sent)
        .values(status=DeliveryStatus.sent)
    )
    await session.commit()
    swept = await service.sweep_stuck(session_factory)
    assert (swept.requeued, swept.expired) == ([retry_lost], 0)


async def test_a_retry_records_when_it_is_due(
    session: AsyncSession, session_factory, make_user, redis_client: Redis, telegram
) -> None:
    user = await make_user("retry@example.com")
    session.add(TelegramLink(user_id=user.id, chat_id=5003, username="u"))
    await session.commit()
    prepared = await service.prepare(session, redis_client, [item(user.id)])
    await session.commit()
    telegram.responses["sendMessage"] = [(502, {"ok": False, "description": "Bad Gateway"})]
    before = datetime.now(UTC)
    await service.send_deliveries(session_factory, redis_client, prepared.send_ids)
    [delivery] = await _deliveries(session, user)
    assert (delivery.status, delivery.attempts) == (DeliveryStatus.pending, 1)
    assert delivery.next_attempt_at >= before + timedelta(seconds=2)


async def _age(session: AsyncSession, delivery_id, **delta) -> None:
    await session.execute(
        update(NotificationDelivery)
        .where(NotificationDelivery.id == delivery_id)
        .values(created_at=datetime.now(UTC) - timedelta(**delta))
    )


async def test_too_old_deliveries_expire_instead_of_being_sent(
    session: AsyncSession, session_factory, make_user, redis_client: Redis, telegram,
    notification_queue,
) -> None:  # fmt: skip
    user = await make_user("old@example.com")
    session.add(TelegramLink(user_id=user.id, chat_id=5004, username="u"))
    await session.commit()
    prepared = await service.prepare(session, redis_client, [item(user.id) for _ in range(3)])
    await session.commit()
    stale, recent, held = prepared.send_ids
    await _age(session, stale, days=2)  # stuck since before the deploy
    await _age(session, recent, minutes=5)
    await _age(session, held, days=2)
    await session.execute(  # quiet hours: the digest path handles it
        update(NotificationDelivery)
        .where(NotificationDelivery.id == held)
        .values(hold="quiet_hours", release_at=datetime.now(UTC) + timedelta(hours=1))
    )
    await session.commit()

    swept = await service.sweep_stuck(session_factory)
    assert (swept.requeued, swept.expired) == ([recent], 1)
    assert notification_queue[-1][0] == [recent]
    await service.send_deliveries(session_factory, redis_client, [stale, recent, held])
    by_id = {d.id: d for d in await _deliveries(session, user)}
    assert (by_id[stale].status, by_id[stale].last_error) == (
        DeliveryStatus.skipped,
        "expired: not sent within NOTIFICATION_SWEEP_MAX_AGE_SECONDS",
    )
    assert by_id[stale].attempts == 0  # never sent
    assert by_id[recent].status == DeliveryStatus.sent
    assert (by_id[held].status, by_id[held].hold) == (DeliveryStatus.pending, "quiet_hours")
    assert len(telegram.sent()) == 1  # only the recent one, once
    swept = await service.sweep_stuck(session_factory)
    assert (swept.requeued, swept.expired) == ([], 0)


async def test_a_delivery_being_sent_is_not_expired(
    committed_session_factory, redis_client: Redis, telegram
) -> None:
    """Real row locks: a send holds the row (FOR UPDATE) while the sweeper runs."""
    factory = committed_session_factory
    async with factory() as session:
        user = await _user(session, "busy@example.com", 5005)
        prepared = await service.prepare(session, redis_client, [item(user.id)])
        await session.commit()
        [delivery_id] = prepared.send_ids
        await _age(session, delivery_id, days=2)
        await session.commit()
    async with factory() as sender:  # a send in progress holds the row lock
        await sender.scalar(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .with_for_update()
        )
        swept = await service.sweep_stuck(factory)
        assert (swept.expired, swept.requeued) == (0, [])  # left alone, and never re-sent
        await sender.rollback()
    async with factory() as session:
        [delivery] = await _deliveries(session, user)
        assert (delivery.status, delivery.last_error) == (DeliveryStatus.pending, None)
    swept = await service.sweep_stuck(factory)  # once the send let go, it expires
    assert swept.expired == 1


def test_the_task_logs_the_counts(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.tasks.notifications")
    # nothing stuck in the committed test database
    assert notification_tasks.sweep() == {"requeued": 0, "expired": 0}
    assert "notifications.sweep requeued=0 expired=0" in caplog.text
