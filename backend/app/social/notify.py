"""Notifications of posts and comments, through the Y15 path (``notifications.service``).

- ``new_post``: to every follower of the author, in batches (Celery task, so a popular author
  does not slow down publishing).
- ``comment_reply``: to the post author and to the author of the comment replied to (never to
  the commenter; one notification when both are the same person).
- ``post_liked``: in-app only and batched: one inbox row per post and UTC day whose count and
  title are updated by every like ("N people liked your post").
- ``content_hidden``: to the author when moderation hides a post or comment.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.instrument import Instrument
from app.models.notification import Notification, NotificationType, Severity
from app.models.social import Follow, Post, PostLike
from app.models.user import User
from app.notifications import preferences as prefs_mod
from app.notifications import service as notifications
from app.notifications import templates
from app.realtime import publisher
from app.realtime.topics import user_topic

logger = logging.getLogger(__name__)

FANOUT_BATCH = 500


def display_name(user: User) -> str:
    name = (user.full_name or "").strip()
    return name or f"user-{str(user.id)[:8]}"


# --- new posts -----------------------------------------------------------------------------------


def _enqueue_new_post(post_id: uuid.UUID) -> None:
    from app.tasks import celery_app  # noqa: PLC0415

    celery_app.send_task("notifications.new_post", args=[str(post_id)], queue=notifications.QUEUE)


enqueue_new_post: Callable[[uuid.UUID], None] = _enqueue_new_post  # replaced in tests


def schedule_new_post(post_id: uuid.UUID) -> None:
    try:
        enqueue_new_post(post_id)
    except Exception:  # noqa: BLE001 - the post is published anyway
        logger.exception("new_post fan-out for %s could not be enqueued", post_id)


async def fanout_new_post(
    factory: async_sessionmaker[AsyncSession], redis: Redis | None, post_id: uuid.UUID
) -> int:
    """One ``new_post`` notification per follower (dedup ``new_post:<id>``), in batches."""
    async with factory() as session:
        row = (
            await session.execute(
                select(Post, User, Instrument.symbol)
                .join(User, User.id == Post.author_id)
                .outerjoin(Instrument, Instrument.id == Post.instrument_id)
                .where(Post.id == post_id)
            )
        ).first()
    if row is None or row[0].status != "published":
        return 0
    post, author, symbol = row
    data = {
        "post_id": str(post.id),
        "title": post.title,
        "excerpt": templates.excerpt(post.body, 200),
        "author_id": str(author.id),
        "author_name": display_name(author),
        "instrument_symbol": symbol,
        "direction": post.direction.value if post.direction else None,
    }
    sent, last = 0, None
    while True:
        async with factory() as session:
            query = (
                select(Follow.follower_id)
                .join(User, User.id == Follow.follower_id)
                .where(Follow.followee_id == author.id, User.is_active.is_(True))
                .order_by(Follow.follower_id)
                .limit(FANOUT_BATCH)
            )
            if last is not None:
                query = query.where(Follow.follower_id > last)
            ids = list(await session.scalars(query))
            if not ids:
                return sent
            items = [
                notifications.NotifyItem(
                    user_id=uid,
                    type=NotificationType.new_post,
                    data=data,
                    dedup_key=f"new_post:{post.id}",
                )
                for uid in ids
            ]
            prepared = await notifications.prepare(session, redis, items)
            await session.commit()
        await notifications.after_commit(redis, prepared)
        sent += len(prepared.notifications)
        last = ids[-1]


# --- comments ------------------------------------------------------------------------------------


def comment_items(
    *,
    post: Post,
    post_author_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: str,
    commenter: User,
    replied_author_id: uuid.UUID | None,
) -> list[notifications.NotifyItem]:
    """Who hears about a new comment: the post author and the author of the comment replied
    to, never the commenter, at most once each."""
    base = {
        "post_id": str(post.id),
        "comment_id": str(comment_id),
        "post_title": post.title,
        "excerpt": templates.excerpt(body, 160),
        "author_name": display_name(commenter),
    }
    targets: dict[uuid.UUID, str] = {}
    if replied_author_id is not None and replied_author_id != commenter.id:
        targets[replied_author_id] = "comment"
    if post_author_id != commenter.id and post_author_id not in targets:
        targets[post_author_id] = "post"
    return [
        notifications.NotifyItem(
            user_id=uid,
            type=NotificationType.comment_reply,
            data={**base, "kind": kind},
            dedup_key=f"comment:{comment_id}",
        )
        for uid, kind in targets.items()
    ]


async def prepare_safely(session: AsyncSession, redis, items) -> notifications.Prepared:
    """``prepare`` in a savepoint: a notification failure never loses the content."""
    if not items:
        return notifications.Prepared()
    try:
        async with session.begin_nested():
            return await notifications.prepare(session, redis, items)
    except Exception:  # noqa: BLE001
        logger.exception("social notifications failed")
        return notifications.Prepared()


# --- likes ---------------------------------------------------------------------------------------


async def like_batch(
    session: AsyncSession, redis: Redis | None, post: Post, liker_id: uuid.UUID
) -> dict[str, Any] | None:
    """Create or update today's ``post_liked`` row of the post author (in-app only: no delivery
    rows). The count is the number of likes the post got today. Commits; returns the row."""
    if liker_id == post.author_id:
        return None
    now = datetime.now(UTC)
    day = datetime.combine(now.date(), time(), tzinfo=UTC)
    count = await session.scalar(
        select(func.count())
        .select_from(PostLike)
        .where(
            PostLike.post_id == post.id,
            PostLike.created_at >= day,
            PostLike.user_id != post.author_id,
        )
    )
    if not count:
        return None
    lang = (await prefs_mod.load(session, [post.author_id]))[post.author_id].language
    data = {"post_id": str(post.id), "post_title": post.title, "count": count}
    title, body = templates.inbox(NotificationType.post_liked, data, lang)
    table = Notification.__table__
    stmt = insert(table).values(
        id=uuid.uuid4(),
        user_id=post.author_id,
        type=NotificationType.post_liked,
        title=title[:200],
        body=body,
        data=data,
        severity=Severity.info,
        dedup_key=f"post_liked:{post.id}:{now:%Y%m%d}",
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_notifications_user_dedup",
        set_={
            "title": stmt.excluded.title,
            "body": stmt.excluded.body,
            "data": stmt.excluded.data,
            "read_at": None,  # unread again: there is news
        },
    ).returning(*table.c)
    row = dict((await session.execute(stmt)).one()._mapping)
    await session.commit()
    try:
        topic = user_topic(post.author_id)
        await publisher.publish(
            topic, {"type": "notification", "notification": notifications.wire(row)}, redis
        )
    except Exception:  # noqa: BLE001 - stored in the inbox anyway
        logger.exception("publishing a like notification failed")
    return row


# --- moderation ----------------------------------------------------------------------------------


def hidden_item(
    *,
    author_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    post_id: uuid.UUID,
    excerpt: str,
    reason: str | None,
) -> notifications.NotifyItem:
    return notifications.NotifyItem(
        user_id=author_id,
        type=NotificationType.content_hidden,
        data={
            "target_type": target_type,
            "target_id": str(target_id),
            "post_id": str(post_id),
            "comment_id": str(target_id) if target_type == "comment" else None,
            "excerpt": excerpt,
            "reason": reason,
        },
        dedup_key=f"hidden:{target_type}:{target_id}",
        severity=Severity.warning,
    )
