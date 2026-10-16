"""The one way to produce notifications, and the delivery machinery behind it.

Producing (in the producer's transaction):

1. :func:`prepare` stores one inbox row per item (idempotent on ``(user_id, dedup_key)``) and
   one delivery row per external channel and target the user wants. Preferences are applied
   in order: event enabled for the channel -> signal filters -> quiet hours -> hourly cap. Held
   deliveries (quiet hours, cap) wait for a digest; ``critical`` events skip both.
2. After the producer commits, :func:`after_commit` publishes ``{"type": "notification"}`` on
   each user's ``user:{id}`` topic and enqueues the sends on the ``notifications`` queue (in
   chunks, so 500 users cost a handful of tasks, not 1,000).

Sending (Celery, :func:`send_deliveries`): every delivery is claimed with ``FOR UPDATE SKIP
LOCKED`` and only while ``pending``, so a duplicated task never sends twice. Retries use
exponential backoff with jitter (max ``notification_max_attempts``), provider ``retry_after``
is honoured, and a per-channel circuit breaker holds deliveries while a provider is down.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.notification import (
    Channel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationType,
    Severity,
    TelegramLink,
    UserDevice,
)
from app.models.user import User, UserRole
from app.notifications import breaker, templates
from app.notifications import preferences as prefs_mod
from app.notifications.channels import (
    PermanentError,
    RateLimited,
    TransientError,
    enabled_channels,
)
from app.notifications.channels import email as email_channel
from app.notifications.channels.push import FcmClient
from app.notifications.channels.telegram import TelegramClient
from app.notifications.preferences import EXTERNAL, Prefs
from app.realtime import publisher
from app.realtime.topics import channel_for, user_topic

logger = logging.getLogger(__name__)

QUEUE = "notifications"
SEND_CHUNK = 50  # deliveries per send task
SEND_CONCURRENCY = 8  # deliveries in flight inside one task
HOLD_DIGEST = ("quiet_hours", "hourly_cap")
HOLD_CIRCUIT = "circuit_open"
DISABLED = "channel disabled on server"
DIGEST_RETRY = timedelta(minutes=5)
READ_RETENTION = timedelta(days=90)
UNREAD_RETENTION = timedelta(days=180)
BROADCAST_BATCH = 500


@dataclass
class NotifyItem:
    user_id: uuid.UUID
    type: NotificationType
    data: dict[str, Any]
    dedup_key: str
    severity: Severity = Severity.info
    # explicit channels (test messages): skip the preference matrix, filters, quiet hours, cap
    channels: tuple[str, ...] | None = None


@dataclass
class Prepared:
    notifications: list[dict[str, Any]] = field(default_factory=list)  # newly stored rows
    send_ids: list[uuid.UUID] = field(default_factory=list)  # deliveries to send now
    deliveries: list[dict[str, Any]] = field(default_factory=list)  # every delivery row made

    def extend(self, other: Prepared) -> None:
        self.notifications += other.notifications
        self.send_ids += other.send_ids
        self.deliveries += other.deliveries


# --- enqueueing (replaced in tests) --------------------------------------------------------------


def send_chunks(ids: Sequence[uuid.UUID | str], countdown: float | None = None) -> int:
    """One ``notifications.send`` task per chunk of deliveries."""
    from app.tasks import celery_app  # the API process only needs Celery to send

    for i in range(0, len(ids), SEND_CHUNK):
        chunk = [str(x) for x in ids[i : i + SEND_CHUNK]]
        celery_app.send_task("notifications.send", args=[chunk], queue=QUEUE, countdown=countdown)
    return -(-len(ids) // SEND_CHUNK)


def _enqueue_celery(ids: Sequence[uuid.UUID], countdown: float | None = None) -> None:
    """A big batch (a signal for hundreds of users) is one ``notifications.fanout`` task that a
    worker splits into chunks, so the producer (the signal engine) pays for one enqueue."""
    if len(ids) <= SEND_CHUNK:
        send_chunks(ids, countdown)
        return
    from app.tasks import celery_app

    celery_app.send_task(
        "notifications.fanout", args=[[str(x) for x in ids]], queue=QUEUE, countdown=countdown
    )


enqueue: Callable[..., None] = _enqueue_celery


def _enqueue_broadcast(broadcast_id, title, body, severity, roles) -> None:
    from app.tasks import celery_app

    celery_app.send_task(
        "notifications.broadcast",
        args=[str(broadcast_id), title, body, str(severity), [str(r) for r in roles or []]],
        queue=QUEUE,
    )


enqueue_broadcast: Callable[..., None] = _enqueue_broadcast  # replaced in tests


def _schedule(ids: Sequence[uuid.UUID], countdown: float | None = None) -> None:
    if not ids:
        return
    try:
        enqueue(list(ids), countdown) if countdown else enqueue(list(ids))
    except Exception:  # noqa: BLE001 - the rows stay pending; the pump re-dispatches them
        logger.exception("notifications: could not enqueue %d deliveries", len(ids))


# --- producing -----------------------------------------------------------------------------------


def wire(row: dict[str, Any] | Notification) -> dict[str, Any]:
    """The JSON of a notification (API and WebSocket)."""
    get = row.get if isinstance(row, dict) else (lambda k: getattr(row, k))
    created, read = get("created_at"), get("read_at")
    return {
        "id": str(get("id")),
        "type": str(get("type").value if hasattr(get("type"), "value") else get("type")),
        "title": get("title"),
        "body": get("body"),
        "data": get("data"),
        "severity": str(
            get("severity").value if hasattr(get("severity"), "value") else get("severity")
        ),
        "created_at": created.isoformat() if created else None,
        "read_at": read.isoformat() if read else None,
    }


async def _targets(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str], dict[uuid.UUID, list[str]]]:
    """(emails, telegram chat ids, device ids) of many users in three queries."""
    emails = dict(
        (await session.execute(select(User.id, User.email).where(User.id.in_(user_ids)))).all()
    )
    chats = {
        uid: str(chat)
        for uid, chat in (
            await session.execute(
                select(TelegramLink.user_id, TelegramLink.chat_id).where(
                    TelegramLink.user_id.in_(user_ids)
                )
            )
        ).all()
    }
    devices: dict[uuid.UUID, list[str]] = defaultdict(list)
    for uid, did in (
        await session.execute(
            select(UserDevice.user_id, UserDevice.id)
            .where(UserDevice.user_id.in_(user_ids))
            .order_by(UserDevice.created_at)
        )
    ).all():
        devices[uid].append(str(did))
    return emails, chats, devices


async def prepare(
    session: AsyncSession,
    redis: Redis | None,
    items: Sequence[NotifyItem],
    now: datetime | None = None,
) -> Prepared:
    """Store inbox rows and decide deliveries for many items at once (the caller commits, then
    calls :func:`after_commit`). Items whose ``dedup_key`` already exists are skipped."""
    out = Prepared()
    if not items:
        return out
    now = now or datetime.now(UTC)
    redis = redis or get_redis()
    user_ids = sorted({i.user_id for i in items})
    prefs = await prefs_mod.load(session, user_ids)
    rows, by_key = [], {}
    for item in items:
        title, body = templates.inbox(item.type, item.data, prefs[item.user_id].language)
        rows.append(
            {
                "id": uuid.uuid4(),
                "user_id": item.user_id,
                "type": item.type,
                "title": title[:200],
                "body": body,
                "data": item.data,
                "severity": item.severity,
                "dedup_key": item.dedup_key[:200],
            }
        )
        by_key[(item.user_id, item.dedup_key[:200])] = item
    # Core executemany (batched "insertmanyvalues"), not one huge multi-row VALUES: 500 rows in
    # ~0.1 s instead of ~1 s; only the keys come back, the rest is known here
    table = Notification.__table__
    stmt = (
        insert(table)
        .on_conflict_do_nothing(constraint="uq_notifications_user_dedup")
        .returning(table.c.id, table.c.created_at)
    )
    created = dict((await session.execute(stmt, rows)).all())
    stored = [
        {**r, "created_at": created[r["id"]], "read_at": None} for r in rows if r["id"] in created
    ]
    if not stored:
        return out
    out.notifications = stored
    emails, chats, devices = await _targets(session, sorted({r["user_id"] for r in stored}))
    server = enabled_channels()

    # 1. what each channel would get; 2. hourly caps in one Redis round trip
    planned: list[tuple[dict[str, Any], str, list[str], str | None, datetime | None]] = []
    cap_checks: list[tuple[int, uuid.UUID, str]] = []
    for row in stored:
        item = by_key[(row["user_id"], row["dedup_key"])]
        p: Prefs = prefs[item.user_id]
        explicit = item.channels is not None
        wanted = item.channels if explicit else tuple(str(c) for c in EXTERNAL)
        for channel in wanted:
            if not explicit and (
                not p.wants(item.type, channel) or not p.passes_filters(item.type, item.data)
            ):
                continue
            if channel == "telegram":
                targets = [chats[item.user_id]] if item.user_id in chats else []
            elif channel == "email":
                targets = [emails[item.user_id]] if emails.get(item.user_id) else []
            else:
                targets = devices.get(item.user_id, [])
            if not targets:
                continue
            hold, release = None, None
            if server.get(channel) and not explicit and item.severity != Severity.critical:
                until = p.quiet_until(now)
                if until is not None:
                    hold, release = "quiet_hours", until
                else:
                    cap_checks.append((len(planned), item.user_id, channel))
            planned.append((row, channel, targets, hold, release))
    if cap_checks:
        hour = now.strftime("%Y%m%d%H")
        pipe = redis.pipeline(transaction=False)
        for _, uid, channel in cap_checks:
            key = f"notif:cap:{uid}:{channel}:{hour}"
            pipe.incr(key)
            pipe.expire(key, 7200)
        counts = (await pipe.execute())[0::2]
        for (index, uid, channel), count in zip(cap_checks, counts, strict=True):
            if count > prefs[uid].cap(channel):
                row, ch, targets, _, _ = planned[index]
                planned[index] = (row, ch, targets, "hourly_cap", prefs_mod.next_hour(now))

    delivery_rows = []
    for row, channel, targets, hold, release in planned:
        for target in targets:
            disabled = not server.get(channel)
            delivery_rows.append(
                {
                    "id": uuid.uuid4(),
                    "notification_id": row["id"],
                    "channel": channel,
                    "target": target,
                    "status": DeliveryStatus.skipped if disabled else DeliveryStatus.pending,
                    "last_error": DISABLED if disabled else None,
                    "hold": None if disabled else hold,
                    "release_at": None if disabled else release,
                }
            )
    if delivery_rows:
        table = NotificationDelivery.__table__
        stmt = (
            insert(table)
            .on_conflict_do_nothing(constraint="uq_notification_deliveries_target")
            .returning(table.c.id)
        )
        inserted = set((await session.execute(stmt, delivery_rows)).scalars())
        for d in delivery_rows:
            if d["id"] not in inserted:
                continue
            out.deliveries.append(d)
            if d["status"] == DeliveryStatus.pending and d["hold"] is None:
                out.send_ids.append(d["id"])
    return out


async def after_commit(redis: Redis | None, prepared: Prepared) -> None:
    """Publish the WebSocket messages and enqueue the sends (never raises)."""
    redis = redis or get_redis()
    if prepared.notifications:
        # one round trip for all users (500 users: one pipeline, not 500 PUBLISH calls)
        try:
            pipe = redis.pipeline(transaction=False)
            for row in prepared.notifications:
                topic = user_topic(row["user_id"])
                message = {"type": "notification", "notification": wire(row)}
                pipe.publish(channel_for(topic), publisher.encode(topic, message))
            await pipe.execute()
        except Exception:  # noqa: BLE001 - stored in the inbox anyway
            logger.exception(
                "notifications: publishing %d messages failed", len(prepared.notifications)
            )
    _schedule(prepared.send_ids)


async def notify(session: AsyncSession, item: NotifyItem, redis: Redis | None = None) -> Prepared:
    """Store one notification and commit, then publish and enqueue. Never raises: a failing
    notification must not break the action that produced it."""
    try:
        prepared = await prepare(session, redis, [item])
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("notifications: could not store %s for %s", item.type, item.user_id)
        await session.rollback()
        return Prepared()
    await after_commit(redis, prepared)
    return prepared


async def notify_with(
    factory: async_sessionmaker[AsyncSession], item: NotifyItem, redis: Redis | None = None
) -> Prepared:
    """:func:`notify` in a session of its own (Celery tasks)."""
    async with factory() as session:
        return await notify(session, item, redis)


# --- sending -------------------------------------------------------------------------------------

# replaced in tests (they inject fake transports)
telegram_client: Callable[[], TelegramClient] = TelegramClient
fcm_client: Callable[[Redis], FcmClient] = FcmClient
send_email: Callable[..., Any] = email_channel.send


def backoff(attempt: int) -> float:
    """2, 4, 8, 16 s ... (cap 300 s) plus up to 50 % jitter."""
    base = min(300.0, 2.0 ** max(1, attempt))
    return base + random.uniform(0, base / 2)


async def _render_and_send(
    session: AsyncSession, redis: Redis, delivery: NotificationDelivery, note: Notification, lang
) -> str:
    title, body = templates.inbox(note.type, note.data, lang)
    channel = Channel(delivery.channel)
    if channel == Channel.telegram:
        return await telegram_client().send_message(
            int(delivery.target), templates.telegram(title, body)
        )
    if channel == Channel.email:
        subject, text, html = templates.email(title, body, lang)
        return await send_email(delivery.target, subject, text, html)
    device = await session.get(UserDevice, uuid.UUID(delivery.target))
    if device is None:
        raise PermanentError("push: device removed")
    short_title, short_body = templates.push(title, body)
    data = templates.deep_link(str(note.type), note.data, str(note.id))
    return await fcm_client(redis).send(device.token, short_title, short_body, data)


async def _cleanup(session: AsyncSession, channel: Channel, target: str, action: str | None):
    """Side effects of permanent errors: a blocked bot unlinks, an invalid token is deleted."""
    if action == "unlink" and channel == Channel.telegram:
        await session.execute(delete(TelegramLink).where(TelegramLink.chat_id == int(target)))
        logger.info("notifications: telegram chat unlinked after a permanent error")
    elif action == "delete_device" and channel == Channel.push:
        await session.execute(delete(UserDevice).where(UserDevice.id == uuid.UUID(target)))
        logger.info("notifications: invalid FCM token, device %s deleted", target)


async def _send_one(
    factory: async_sessionmaker[AsyncSession], redis: Redis, delivery_id: uuid.UUID
) -> tuple[str, float | None]:
    """(outcome, retry countdown or None)."""
    settings = get_settings()
    async with factory() as session:
        delivery = await session.scalar(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.id == delivery_id,
                NotificationDelivery.status == DeliveryStatus.pending,
                NotificationDelivery.hold.is_(None),
            )
            .with_for_update(skip_locked=True)
        )
        if delivery is None:
            return "noop", None  # already handled, held, or being sent by another worker
        channel = str(delivery.channel)
        if not enabled_channels().get(channel):
            delivery.status, delivery.last_error = DeliveryStatus.skipped, DISABLED
            await session.commit()
            return "skipped", None
        wait = await breaker.open_for(redis, channel)
        if wait:
            delivery.hold = HOLD_CIRCUIT
            delivery.release_at = datetime.now(UTC) + timedelta(seconds=wait)
            await session.commit()
            return "held", None
        note = await session.get(Notification, delivery.notification_id)
        lang = Prefs.of(await session.get(NotificationPreference, note.user_id)).language
        delivery.attempts += 1
        retry: float | None = None
        try:
            provider_id = await _render_and_send(session, redis, delivery, note, lang)
        except RateLimited as exc:
            delivery.last_error = exc.message
            if delivery.attempts >= settings.notification_max_attempts:
                delivery.status = DeliveryStatus.failed
            else:
                retry = exc.retry_after
        except PermanentError as exc:
            delivery.status, delivery.last_error = DeliveryStatus.failed, exc.message
            await _cleanup(session, Channel(channel), delivery.target, exc.action)
        except TransientError as exc:
            delivery.last_error = exc.message
            await breaker.failure(redis, channel)
            if delivery.attempts >= settings.notification_max_attempts:
                delivery.status = DeliveryStatus.failed
            else:
                retry = backoff(delivery.attempts)
        else:
            delivery.status = DeliveryStatus.sent
            delivery.sent_at = datetime.now(UTC)
            delivery.provider_message_id = (provider_id or "")[:255] or None
            delivery.last_error = None
            await breaker.success(redis, channel)
        outcome = str(delivery.status) if retry is None else "retry"
        await session.commit()
    return outcome, retry


async def send_deliveries(
    factory: async_sessionmaker[AsyncSession], redis: Redis, ids: Iterable[uuid.UUID]
) -> dict[str, int]:
    """Send a batch (a Celery task's body); retries are scheduled after the commit."""
    semaphore = asyncio.Semaphore(SEND_CONCURRENCY)
    counts: dict[str, int] = defaultdict(int)

    async def one(delivery_id: uuid.UUID) -> None:
        async with semaphore:
            try:
                outcome, retry = await _send_one(factory, redis, delivery_id)
            except Exception:  # noqa: BLE001 - one bad delivery must not stop the batch
                logger.exception("notifications: delivery %s crashed", delivery_id)
                outcome, retry = "error", None
        counts[outcome] += 1
        if retry is not None:
            _schedule([delivery_id], retry)

    await asyncio.gather(*(one(i) for i in ids))
    return dict(counts)


# --- digests and held deliveries -----------------------------------------------------------------


async def release_circuit_holds(
    factory: async_sessionmaker[AsyncSession], now: datetime | None = None, limit: int = 1000
) -> int:
    """Deliveries held while a circuit was open go back to the queue once it may close."""
    now = now or datetime.now(UTC)
    async with factory() as session:
        due = select(NotificationDelivery.id).where(
            NotificationDelivery.status == DeliveryStatus.pending,
            NotificationDelivery.hold == HOLD_CIRCUIT,
            NotificationDelivery.release_at <= now,
        )
        ids = list(
            await session.scalars(
                update(NotificationDelivery)
                .where(NotificationDelivery.id.in_(due.limit(limit).scalar_subquery()))
                .values(hold=None, release_at=None)
                .returning(NotificationDelivery.id)
            )
        )
        await session.commit()
    _schedule(ids)
    return len(ids)


async def send_digests(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    now: datetime | None = None,
    limit: int = 2000,
) -> dict[str, int]:
    """Held deliveries (quiet hours, hourly cap) whose time has come: one digest message per
    (user, channel, target), or the original message when only one is waiting."""
    now = now or datetime.now(UTC)
    settings = get_settings()
    counts: dict[str, int] = defaultdict(int)
    async with factory() as session:
        rows = (
            await session.execute(
                select(NotificationDelivery, Notification)
                .join(Notification, Notification.id == NotificationDelivery.notification_id)
                .where(
                    NotificationDelivery.status == DeliveryStatus.pending,
                    NotificationDelivery.hold.in_(HOLD_DIGEST),
                    NotificationDelivery.release_at <= now,
                )
                .order_by(Notification.created_at)
                .limit(limit)
                .with_for_update(of=NotificationDelivery, skip_locked=True)
            )
        ).all()
        groups: dict[tuple, list[tuple[NotificationDelivery, Notification]]] = defaultdict(list)
        for d, n in rows:
            groups[(n.user_id, str(d.channel), d.target)].append((d, n))
        server = enabled_channels()
        for (user_id, channel, target), members in groups.items():
            deliveries = [d for d, _ in members]
            if not server.get(channel):
                for d in deliveries:
                    d.status, d.last_error, d.hold = DeliveryStatus.skipped, DISABLED, None
                counts["skipped"] += len(deliveries)
                continue
            wait = await breaker.open_for(redis, channel)
            if wait:
                for d in deliveries:
                    d.release_at = now + timedelta(seconds=wait)
                counts["held"] += len(deliveries)
                continue
            lang = Prefs.of(await session.get(NotificationPreference, user_id)).language
            try:
                if len(members) == 1:
                    d, n = members[0]
                    provider_id = await _render_and_send(session, redis, d, n, lang)
                else:
                    provider_id = await _send_digest(session, redis, channel, target, members, lang)
            except RateLimited as exc:
                _retry_later(deliveries, exc.message, now + timedelta(seconds=exc.retry_after))
                counts["retry"] += 1
            except PermanentError as exc:
                for d in deliveries:
                    d.status, d.last_error, d.hold = DeliveryStatus.failed, exc.message, None
                    d.attempts += 1
                await _cleanup(session, Channel(channel), target, exc.action)
                counts["failed"] += 1
            except TransientError as exc:
                await breaker.failure(redis, channel)
                _retry_later(deliveries, exc.message, now + DIGEST_RETRY)
                for d in deliveries:
                    if d.attempts >= settings.notification_max_attempts:
                        d.status, d.hold = DeliveryStatus.failed, None
                counts["retry"] += 1
            else:
                for d in deliveries:
                    d.status, d.hold, d.release_at = DeliveryStatus.sent, None, None
                    d.sent_at, d.attempts = now, d.attempts + 1
                    d.provider_message_id = (provider_id or "")[:255] or None
                await breaker.success(redis, channel)
                counts["digests" if len(members) > 1 else "sent"] += 1
                counts["items"] += len(members)
        await session.commit()
    return dict(counts)


def _retry_later(deliveries, message: str, when: datetime) -> None:
    for d in deliveries:
        d.attempts += 1
        d.last_error = message
        d.release_at = when


async def _send_digest(session, redis, channel: str, target: str, members, lang: str) -> str:
    titles = [templates.inbox(n.type, n.data, lang)[0] for _, n in members]
    title, body = templates.digest(titles, lang)
    if channel == "telegram":
        return await telegram_client().send_message(int(target), templates.telegram(title, body))
    if channel == "email":
        subject, text, html = templates.email(title, body, lang)
        return await send_email(target, subject, text, html)
    device = await session.get(UserDevice, uuid.UUID(target))
    if device is None:
        raise PermanentError("push: device removed")
    short_title, short_body = templates.push(title, body)
    data = {"screen": "notifications", "type": "digest", "count": str(len(members))}
    return await fcm_client(redis).send(device.token, short_title, short_body, data)


# --- housekeeping, broadcast, stats --------------------------------------------------------------


async def cleanup(
    factory: async_sessionmaker[AsyncSession], now: datetime | None = None, batch: int = 5000
) -> int:
    """Retention: read notifications older than 90 days, unread older than 180 days (with their
    deliveries). Deleted in batches so no statement holds locks for long."""
    now = now or datetime.now(UTC)
    old = (
        (Notification.read_at.is_not(None)) & (Notification.created_at < now - READ_RETENTION)
    ) | ((Notification.read_at.is_(None)) & (Notification.created_at < now - UNREAD_RETENTION))
    total = 0
    while True:
        async with factory() as session:
            ids = select(Notification.id).where(old).limit(batch).scalar_subquery()
            result = await session.execute(delete(Notification).where(Notification.id.in_(ids)))
            await session.commit()
        total += result.rowcount or 0
        if (result.rowcount or 0) < batch:
            return total


async def broadcast(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis | None,
    broadcast_id: uuid.UUID,
    title: str,
    body: str,
    severity: Severity,
    roles: list[UserRole] | None,
) -> int:
    """A ``system`` notification for every active user (optionally of some roles), in batches;
    idempotent per broadcast id (``dedup_key = broadcast:<id>``)."""
    sent, last = 0, None
    while True:
        async with factory() as session:
            query = select(User.id).where(User.is_active.is_(True)).order_by(User.id)
            if roles:
                query = query.where(User.role.in_(roles))
            if last is not None:
                query = query.where(User.id > last)
            ids = list(await session.scalars(query.limit(BROADCAST_BATCH)))
            if not ids:
                return sent
            items = [
                NotifyItem(
                    user_id=uid,
                    type=NotificationType.system,
                    data={"title": title, "body": body, "broadcast_id": str(broadcast_id)},
                    dedup_key=f"broadcast:{broadcast_id}",
                    severity=severity,
                )
                for uid in ids
            ]
            prepared = await prepare(session, redis, items)
            await session.commit()
        await after_commit(redis, prepared)
        sent += len(prepared.notifications)
        last = ids[-1]


async def stats(session: AsyncSession, redis: Redis) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(hours=24)
    rows = await session.execute(
        select(NotificationDelivery.channel, NotificationDelivery.status, func.count())
        .where(NotificationDelivery.created_at >= since)
        .group_by(NotificationDelivery.channel, NotificationDelivery.status)
    )
    per: dict[str, dict[str, int]] = {str(c): {str(s): 0 for s in DeliveryStatus} for c in Channel}
    for channel, status_, count in rows.all():
        per[str(channel)][str(status_)] = count
    held = dict(
        (
            await session.execute(
                select(NotificationDelivery.hold, func.count())
                .where(
                    NotificationDelivery.status == DeliveryStatus.pending,
                    NotificationDelivery.hold.is_not(None),
                )
                .group_by(NotificationDelivery.hold)
            )
        ).all()
    )
    notifications = await session.scalar(
        select(func.count()).select_from(Notification).where(Notification.created_at >= since)
    )
    server = enabled_channels()
    channels = {
        name: {
            "enabled_on_server": server[name],
            **per[name],
            "circuit": await breaker.state(redis, name),
        }
        for name in per
    }
    return {
        "since": since,
        "notifications": notifications or 0,
        "channels": channels,
        "held": held,
        "queue_length": int(await redis.llen(QUEUE)),
    }


# --- inbox ---------------------------------------------------------------------------------------


async def list_inbox(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
    offset: int,
    type_: NotificationType | None = None,
    unread: bool | None = None,
) -> tuple[list[Notification], int]:
    conditions = [Notification.user_id == user.id]
    if type_ is not None:
        conditions.append(Notification.type == type_)
    if unread is True:
        conditions.append(Notification.read_at.is_(None))
    elif unread is False:
        conditions.append(Notification.read_at.is_not(None))
    total = await session.scalar(
        select(func.count()).select_from(Notification).where(and_(*conditions))
    )
    rows = await session.scalars(
        select(Notification)
        .where(and_(*conditions))
        .order_by(Notification.created_at.desc(), Notification.id)
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all()), total or 0


async def unread_count(session: AsyncSession, user: User) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        )
        or 0
    )
