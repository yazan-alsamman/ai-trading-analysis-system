"""Posts, comments, likes, follows, profiles and moderation.

Visibility of a post for a viewer: ``deleted`` posts exist for nobody (admins still get them by
id); ``hidden`` ones only for their author and admins; ``followers`` posts only for the author,
the author's followers and admins.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.backtest import Backtest
from app.models.custom_strategy import CustomStrategy, Visibility
from app.models.instrument import Instrument
from app.models.social import (
    Comment,
    ContentReport,
    ContentStatus,
    Follow,
    Post,
    PostLike,
    PostVisibility,
    ReportStatus,
    ReportTarget,
)
from app.models.strategy import Signal
from app.models.user import User, UserRole
from app.models.workspace import Workspace
from app.notifications import service as notifications
from app.notifications import templates
from app.schemas.posts import (
    AttachmentRef,
    CommentCreate,
    PostCreate,
    PostUpdate,
    ReportCreate,
    ReportResolve,
)
from app.social import notify
from app.social.notify import display_name

FOLLOWABLE = frozenset({UserRole.analyst, UserRole.expert})
REPLIES_INLINE = 20
PUBLISHED = ContentStatus.published
HIDDEN = ContentStatus.hidden
DELETED = ContentStatus.deleted


def _404(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def _is_admin(user: User) -> bool:
    return user.role == UserRole.admin


def author_of(user: User) -> dict[str, Any]:
    return {"id": user.id, "display_name": display_name(user), "role": user.role}


async def _quota(
    session: AsyncSession, column, owner, user_id, window: timedelta, limit: int, what
):
    """429 when ``limit`` items were created in the rolling ``window``; Retry-After tells when
    the oldest of them leaves it."""
    now = datetime.now(UTC)
    nth = await session.scalar(
        select(column)
        .where(owner == user_id, column > now - window)
        .order_by(column.desc())
        .offset(limit - 1)
        .limit(1)
    )
    if nth is not None:
        retry = max(1, int((nth + window - now).total_seconds()) + 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"At most {limit} {what}",
            headers={"Retry-After": str(retry)},
        )


# --- attachments ---------------------------------------------------------------------------------


def _invalid(index: int, message: str) -> dict[str, Any]:
    return {"loc": ["body", "attachments", index, "id"], "msg": message, "type": "value_error"}


async def validate_attachments(
    session: AsyncSession, author: User, refs: list[AttachmentRef]
) -> list[dict[str, str]]:
    """Only things readers may open: the author's own backtests, the author's own or public
    custom strategies, shared workspaces and signals. 422 otherwise (one error per item)."""
    errors = []
    seen = set()
    for i, ref in enumerate(refs):
        if (ref.type, ref.id) in seen:
            errors.append(_invalid(i, "attached twice"))
            continue
        seen.add((ref.type, ref.id))
        if ref.type == "backtest":
            row = await session.get(Backtest, ref.id)
            ok = row is not None and row.user_id == author.id
            message = "backtest not found among your backtests"
        elif ref.type == "custom_strategy":
            row = await session.get(CustomStrategy, ref.id)
            ok = row is not None and (
                row.user_id == author.id or row.visibility == Visibility.public
            )
            message = "custom strategy not found (yours or public)"
        elif ref.type == "shared_workspace":
            row = await session.get(Workspace, ref.id)
            ok = row is not None and row.is_shared and row.share_slug is not None
            message = "workspace not found or not shared (share it first)"
        else:
            ok = await session.get(Signal, ref.id) is not None
            message = "signal not found"
        if not ok:
            errors.append(_invalid(i, message))
    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, errors)
    return [{"type": r.type, "id": str(r.id)} for r in refs]


async def resolve_attachments(
    session: AsyncSession, viewer: User, posts: list[Post]
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Summaries of every attachment of these posts, one query per attachment type."""
    wanted: dict[str, set[uuid.UUID]] = defaultdict(set)
    for post in posts:
        for ref in post.attachments or []:
            wanted[ref["type"]].add(uuid.UUID(ref["id"]))
    found: dict[tuple[str, str], dict[str, Any]] = {}
    if wanted.get("backtest"):
        rows = await session.execute(
            select(Backtest, Instrument.symbol)
            .join(Instrument, Instrument.id == Backtest.instrument_id)
            .where(Backtest.id.in_(wanted["backtest"]))
        )
        for bt, symbol in rows.all():
            m = bt.metrics or {}
            found[("backtest", str(bt.id))] = {
                "owner_id": bt.user_id,
                "strategy_key": bt.strategy_key,
                "symbol": symbol,
                "timeframe": bt.timeframe.value,
                "status": bt.status.value,
                "range_start": bt.range_start,
                "range_end": bt.range_end,
                "metrics": {
                    k: m.get(k)
                    for k in (
                        "total_return_pct",
                        "max_drawdown_pct",
                        "sharpe",
                        "trades",
                        "win_rate_pct",
                    )
                }
                if m
                else None,
            }
    if wanted.get("custom_strategy"):
        for cs in await session.scalars(
            select(CustomStrategy).where(CustomStrategy.id.in_(wanted["custom_strategy"]))
        ):
            found[("custom_strategy", str(cs.id))] = {
                "owner_id": cs.user_id,
                "public": cs.visibility == Visibility.public,
                "name": cs.name,
                "kind": cs.kind.value,
                "description": cs.description,
                "key": f"custom:{cs.id}",
            }
    if wanted.get("shared_workspace"):
        for ws in await session.scalars(
            select(Workspace).where(Workspace.id.in_(wanted["shared_workspace"]))
        ):
            found[("shared_workspace", str(ws.id))] = {
                "shared": ws.is_shared and ws.share_slug is not None,
                "name": ws.name,
                "share_slug": ws.share_slug,
            }
    if wanted.get("signal"):
        rows = await session.execute(
            select(Signal, Instrument.symbol)
            .join(Instrument, Instrument.id == Signal.instrument_id)
            .where(Signal.id.in_(wanted["signal"]))
        )
        for sig, symbol in rows.all():
            found[("signal", str(sig.id))] = {
                "instrument_id": sig.instrument_id,
                "symbol": symbol,
                "timeframe": sig.timeframe.value,
                "strategy_key": sig.strategy_key,
                "side": sig.side.value,
                "price": sig.price,
                "strength": sig.strength,
                "bar_time": sig.bar_time,
            }
    out: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for post in posts:
        items = []
        for ref in post.attachments or []:
            summary = dict(found.get((ref["type"], ref["id"])) or {})
            available = bool(summary)
            if ref["type"] == "custom_strategy" and summary:
                # a strategy made private again is only shown to its owner
                available = summary.pop("public") or summary["owner_id"] == viewer.id
            if ref["type"] == "shared_workspace" and summary:
                available = summary.pop("shared")
            summary.pop("owner_id", None)
            items.append(
                {"type": ref["type"], "id": ref["id"], "available": available}
                | (summary if available else {})
            )
        out[post.id] = items
    return out


# --- posts ---------------------------------------------------------------------------------------


def can_post(user: User) -> bool:
    return user.role.value in get_settings().post_role_set


def _edit_allowed(viewer: User, post: Post, now: datetime | None = None) -> bool:
    if post.status == DELETED:
        return False
    if _is_admin(viewer):
        return True
    window = timedelta(hours=get_settings().post_edit_window_hours)
    return (
        post.author_id == viewer.id
        and post.status == PUBLISHED
        and (now or datetime.now(UTC)) - post.created_at <= window
    )


def _followees(viewer_id: uuid.UUID):
    return select(Follow.followee_id).where(Follow.follower_id == viewer_id)


def _visible_clause(viewer: User):
    shown = or_(Post.status == PUBLISHED, and_(Post.author_id == viewer.id, Post.status == HIDDEN))
    if _is_admin(viewer):
        return shown
    audience = or_(
        Post.visibility == PostVisibility.public,
        Post.author_id == viewer.id,
        Post.author_id.in_(_followees(viewer.id)),
    )
    return and_(shown, audience)


async def _is_follower(session: AsyncSession, follower_id, followee_id) -> bool:
    return (
        await session.get(Follow, {"follower_id": follower_id, "followee_id": followee_id})
    ) is not None


async def visible_post(session: AsyncSession, viewer: User, post_id: uuid.UUID) -> Post:
    post = await session.get(Post, post_id)
    if post is None:
        raise _404("Post")
    if _is_admin(viewer):
        return post
    if post.status == DELETED or (post.status == HIDDEN and post.author_id != viewer.id):
        raise _404("Post")
    if (
        post.visibility == PostVisibility.followers
        and post.author_id != viewer.id
        and not await _is_follower(session, viewer.id, post.author_id)
    ):
        raise _404("Post")
    return post


async def create_post(session: AsyncSession, user: User, data: PostCreate) -> Post:
    if not can_post(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot publish posts")
    settings = get_settings()
    await _quota(
        session,
        Post.created_at,
        Post.author_id,
        user.id,
        timedelta(days=1),
        settings.posts_per_day,
        "posts per day",
    )
    if data.instrument_id is not None and await session.get(Instrument, data.instrument_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown instrument_id")
    attachments = await validate_attachments(session, user, data.attachments)
    post = Post(
        author_id=user.id,
        title=data.title,
        body=data.body,
        instrument_id=data.instrument_id,
        timeframe=data.timeframe,
        direction=data.direction,
        attachments=attachments,
        visibility=data.visibility,
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)
    notify.schedule_new_post(post.id)
    return post


async def update_post(session: AsyncSession, user: User, post: Post, data: PostUpdate) -> Post:
    if post.author_id != user.id and not _is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can edit this post")
    if not _edit_allowed(user, post):
        hours = get_settings().post_edit_window_hours
        if post.status == HIDDEN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This post was hidden by moderation")
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Posts can be edited within {hours} hours")
    fields = data.model_dump(exclude_unset=True)
    if "instrument_id" in fields and data.instrument_id is not None:
        if await session.get(Instrument, data.instrument_id) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown instrument_id")
    if "attachments" in fields:
        author = await session.get(User, post.author_id)
        fields["attachments"] = await validate_attachments(session, author, data.attachments)
    for name, value in fields.items():
        setattr(post, name, value)
    if fields:
        post.edited_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(post)
    return post


async def delete_post(session: AsyncSession, user: User, post: Post) -> None:
    if post.author_id != user.id and not _is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can delete this post")
    post.status = DELETED
    await session.commit()


async def feed(
    session: AsyncSession,
    viewer: User,
    *,
    scope: str = "all",
    instrument_id: uuid.UUID | None = None,
    author_id: uuid.UUID | None = None,
    direction=None,
    limit: int,
    offset: int,
) -> tuple[list[Post], int]:
    conditions = [_visible_clause(viewer)]
    if scope == "following":
        conditions.append(Post.author_id.in_(_followees(viewer.id)))
    if instrument_id is not None:
        conditions.append(Post.instrument_id == instrument_id)
    if author_id is not None:
        conditions.append(Post.author_id == author_id)
    if direction is not None:
        conditions.append(Post.direction == direction)
    total = await session.scalar(select(func.count()).select_from(Post).where(*conditions))
    rows = await session.scalars(
        select(Post)
        .where(*conditions)
        .order_by(Post.created_at.desc(), Post.id)
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all()), total or 0


async def serialize_posts(
    session: AsyncSession, viewer: User, posts: list[Post]
) -> list[dict[str, Any]]:
    if not posts:
        return []
    ids = [p.id for p in posts]
    authors = {
        u.id: u
        for u in await session.scalars(
            select(User).where(User.id.in_({p.author_id for p in posts}))
        )
    }
    instrument_ids = {p.instrument_id for p in posts if p.instrument_id}
    symbols = (
        dict(
            (
                await session.execute(
                    select(Instrument.id, Instrument.symbol).where(
                        Instrument.id.in_(instrument_ids)
                    )
                )
            ).all()
        )
        if instrument_ids
        else {}
    )
    liked = set(
        await session.scalars(
            select(PostLike.post_id).where(PostLike.user_id == viewer.id, PostLike.post_id.in_(ids))
        )
    )
    attachments = await resolve_attachments(session, viewer, posts)
    now = datetime.now(UTC)
    return [
        {
            "id": p.id,
            "author": author_of(authors[p.author_id]),
            "title": p.title,
            "body": p.body,
            "instrument": (
                {"id": p.instrument_id, "symbol": symbols.get(p.instrument_id, "?")}
                if p.instrument_id
                else None
            ),
            "timeframe": p.timeframe,
            "direction": p.direction,
            "attachments": attachments.get(p.id, []),
            "visibility": p.visibility,
            "status": p.status,
            "comments_count": p.comments_count,
            "likes_count": p.likes_count,
            "liked_by_me": p.id in liked,
            "can_edit": _edit_allowed(viewer, p, now)
            and (p.author_id == viewer.id or _is_admin(viewer)),
            "edited_at": p.edited_at,
            "created_at": p.created_at,
        }
        for p in posts
    ]


# --- likes ---------------------------------------------------------------------------------------


async def like(session: AsyncSession, redis: Redis | None, user: User, post: Post) -> dict:
    """Idempotent. The counter moves in the same transaction as the like row, atomically
    (``likes_count = likes_count + 1``), so concurrent likes never lose an update."""
    if post.status != PUBLISHED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This post cannot be liked")
    inserted = await session.scalar(
        insert(PostLike)
        .values(post_id=post.id, user_id=user.id)
        .on_conflict_do_nothing()
        .returning(PostLike.post_id)
    )
    if inserted is not None:
        count = await session.scalar(
            update(Post)
            .where(Post.id == post.id)
            .values(likes_count=Post.likes_count + 1)
            .returning(Post.likes_count)
        )
    else:
        count = await session.scalar(select(Post.likes_count).where(Post.id == post.id))
    await session.commit()
    if inserted is not None:
        await notify.like_batch(session, redis, post, user.id)
    return {"liked": True, "likes_count": count}


async def unlike(session: AsyncSession, user: User, post: Post) -> dict:
    removed = await session.scalar(
        delete(PostLike)
        .where(PostLike.post_id == post.id, PostLike.user_id == user.id)
        .returning(PostLike.post_id)
    )
    if removed is not None:
        count = await session.scalar(
            update(Post)
            .where(Post.id == post.id)
            .values(likes_count=func.greatest(Post.likes_count - 1, 0))
            .returning(Post.likes_count)
        )
    else:
        count = await session.scalar(select(Post.likes_count).where(Post.id == post.id))
    await session.commit()
    return {"liked": False, "likes_count": count}


# --- comments ------------------------------------------------------------------------------------


async def create_comment(
    session: AsyncSession, redis: Redis | None, user: User, post: Post, data: CommentCreate
) -> Comment:
    if post.status != PUBLISHED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Comments are closed on this post")
    settings = get_settings()
    await _quota(
        session,
        Comment.created_at,
        Comment.author_id,
        user.id,
        timedelta(hours=1),
        settings.comments_per_hour,
        "comments per hour",
    )
    parent_id, replied_author = None, None
    if data.parent_id is not None:
        parent = await session.get(Comment, data.parent_id)
        if (
            parent is None
            or parent.post_id != post.id
            or (parent.status == HIDDEN and parent.author_id != user.id and not _is_admin(user))
        ):
            raise _404("Comment")
        if parent.status == DELETED:
            raise HTTPException(status.HTTP_409_CONFLICT, "That comment was deleted")
        replied_author = parent.author_id
        parent_id = parent.parent_id or parent.id  # two levels at most
    comment = Comment(post_id=post.id, author_id=user.id, parent_id=parent_id, body=data.body)
    session.add(comment)
    await session.flush()
    await session.execute(
        update(Post).where(Post.id == post.id).values(comments_count=Post.comments_count + 1)
    )
    items = notify.comment_items(
        post=post,
        post_author_id=post.author_id,
        comment_id=comment.id,
        body=comment.body,
        commenter=user,
        replied_author_id=replied_author,
    )
    prepared = await notify.prepare_safely(session, redis, items)
    await session.commit()
    await session.refresh(comment)
    await notifications.after_commit(redis, prepared)
    return comment


def serialize_comment(
    viewer: User, comment: Comment, authors: dict[uuid.UUID, User]
) -> dict[str, Any]:
    own = comment.author_id == viewer.id
    deleted = comment.status == DELETED
    hidden_from_viewer = comment.status == HIDDEN and not (own or _is_admin(viewer))
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "parent_id": comment.parent_id,
        "author": None if deleted else author_of(authors[comment.author_id]),
        "body": None if deleted or hidden_from_viewer else comment.body,
        "status": comment.status,
        "created_at": comment.created_at,
        "edited_at": comment.edited_at,
        "can_edit": own and comment.status == PUBLISHED,
    }


async def _authors(session: AsyncSession, comments) -> dict[uuid.UUID, User]:
    ids = {c.author_id for c in comments}
    if not ids:
        return {}
    return {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))}


async def threads(
    session: AsyncSession, viewer: User, post: Post, *, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    """Top-level comments oldest first (paginated), each with its first 20 replies inline."""
    top_filter = and_(Comment.post_id == post.id, Comment.parent_id.is_(None))
    total = await session.scalar(select(func.count()).select_from(Comment).where(top_filter))
    tops = list(
        await session.scalars(
            select(Comment)
            .where(top_filter)
            .order_by(Comment.created_at, Comment.id)
            .limit(limit)
            .offset(offset)
        )
    )
    top_ids = [c.id for c in tops]
    replies: dict[uuid.UUID, list[Comment]] = defaultdict(list)
    counts: dict[uuid.UUID, int] = {}
    if top_ids:
        counts = dict(
            (
                await session.execute(
                    select(Comment.parent_id, func.count())
                    .where(Comment.parent_id.in_(top_ids))
                    .group_by(Comment.parent_id)
                )
            ).all()
        )
        ranked = (
            select(
                Comment.id,
                func.row_number()
                .over(partition_by=Comment.parent_id, order_by=(Comment.created_at, Comment.id))
                .label("n"),
            )
            .where(Comment.parent_id.in_(top_ids))
            .subquery()
        )
        for reply in await session.scalars(
            select(Comment)
            .join(ranked, ranked.c.id == Comment.id)
            .where(ranked.c.n <= REPLIES_INLINE)
            .order_by(Comment.created_at, Comment.id)
        ):
            replies[reply.parent_id].append(reply)
    authors = await _authors(session, [*tops, *(r for rs in replies.values() for r in rs)])
    out = []
    for top in tops:
        count = counts.get(top.id, 0)
        out.append(
            {
                **serialize_comment(viewer, top, authors),
                "replies": [serialize_comment(viewer, r, authors) for r in replies[top.id]],
                "replies_count": count,
                "more_replies": count > REPLIES_INLINE,
            }
        )
    return out, total or 0


async def replies_page(
    session: AsyncSession, viewer: User, post: Post, parent_id: uuid.UUID, *, limit, offset
) -> tuple[list[dict[str, Any]], int]:
    parent = await session.get(Comment, parent_id)
    if parent is None or parent.post_id != post.id or parent.parent_id is not None:
        raise _404("Comment")
    where = Comment.parent_id == parent_id
    total = await session.scalar(select(func.count()).select_from(Comment).where(where))
    rows = list(
        await session.scalars(
            select(Comment)
            .where(where)
            .order_by(Comment.created_at, Comment.id)
            .limit(limit)
            .offset(offset)
        )
    )
    authors = await _authors(session, rows)
    return [serialize_comment(viewer, c, authors) for c in rows], total or 0


async def own_comment(session: AsyncSession, viewer: User, comment_id: uuid.UUID) -> Comment:
    comment = await session.get(Comment, comment_id)
    if comment is None:
        raise _404("Comment")
    await visible_post(session, viewer, comment.post_id)
    return comment


async def update_comment(session: AsyncSession, user: User, comment: Comment, body: str):
    if comment.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can edit this comment")
    if comment.status != PUBLISHED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This comment is {comment.status.value}")
    comment.body = body
    comment.edited_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(comment)
    return comment


async def delete_comment(session: AsyncSession, user: User, comment: Comment) -> None:
    """Soft delete: the body is erased and the comment stays as a placeholder in its thread."""
    if comment.author_id != user.id and not _is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can delete this comment")
    if comment.status == DELETED:
        return
    was_published = comment.status == PUBLISHED
    comment.status, comment.body = DELETED, ""
    if was_published:
        await _decrement_comments(session, comment.post_id)
    await session.commit()


async def _decrement_comments(session: AsyncSession, post_id: uuid.UUID) -> None:
    await session.execute(
        update(Post)
        .where(Post.id == post_id)
        .values(comments_count=func.greatest(Post.comments_count - 1, 0))
    )


# --- follows and profiles ------------------------------------------------------------------------


async def _followable(session: AsyncSession, viewer: User, user_id: uuid.UUID) -> User:
    target = await session.get(User, user_id)
    if target is None or not target.is_active:
        raise _404("User")
    if target.id == viewer.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot follow yourself")
    if target.role not in FOLLOWABLE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only analysts and experts can be followed"
        )
    return target


async def followers_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(Follow).where(Follow.followee_id == user_id)
        )
        or 0
    )


async def follow(session: AsyncSession, viewer: User, user_id: uuid.UUID) -> dict:
    target = await _followable(session, viewer, user_id)
    await session.execute(
        insert(Follow).values(follower_id=viewer.id, followee_id=target.id).on_conflict_do_nothing()
    )
    await session.commit()
    return {"following": True, "followers_count": await followers_count(session, target.id)}


async def unfollow(session: AsyncSession, viewer: User, user_id: uuid.UUID) -> dict:
    target = await session.get(User, user_id)
    if target is None:
        raise _404("User")
    await session.execute(
        delete(Follow).where(Follow.follower_id == viewer.id, Follow.followee_id == user_id)
    )
    await session.commit()
    return {"following": False, "followers_count": await followers_count(session, user_id)}


async def follow_list(
    session: AsyncSession, viewer: User, *, followers: bool, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    """``followers``: who follows me; else whom I follow. Newest first."""
    mine, other = (
        (Follow.followee_id, Follow.follower_id)
        if followers
        else (Follow.follower_id, Follow.followee_id)
    )
    total = await session.scalar(select(func.count()).select_from(Follow).where(mine == viewer.id))
    rows = await session.execute(
        select(User, Follow.created_at)
        .join(Follow, other == User.id)
        .where(mine == viewer.id)
        .order_by(Follow.created_at.desc(), User.id)
        .limit(limit)
        .offset(offset)
    )
    return [{"user": author_of(u), "since": since} for u, since in rows.all()], total or 0


async def profile(session: AsyncSession, viewer: User, user_id: uuid.UUID) -> dict[str, Any]:
    """Public profile: no email, no ids of other users."""
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _404("User")
    posts_count = await session.scalar(
        select(func.count())
        .select_from(Post)
        .where(Post.author_id == user.id, Post.status == PUBLISHED)
    )
    following_count = await session.scalar(
        select(func.count()).select_from(Follow).where(Follow.follower_id == user.id)
    )
    recent, _ = await feed(session, viewer, author_id=user.id, limit=5, offset=0)
    strategies = await session.scalars(
        select(CustomStrategy)
        .where(CustomStrategy.user_id == user.id, CustomStrategy.visibility == Visibility.public)
        .order_by(CustomStrategy.updated_at.desc())
        .limit(20)
    )
    return {
        "id": user.id,
        "display_name": display_name(user),
        "role": user.role,
        "member_since": user.created_at,
        "posts_count": posts_count or 0,
        "followers_count": await followers_count(session, user.id),
        "following_count": following_count or 0,
        "followable": user.role in FOLLOWABLE and user.id != viewer.id,
        "is_following": await _is_follower(session, viewer.id, user.id),
        "recent_posts": await serialize_posts(session, viewer, recent),
        "public_strategies": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "kind": s.kind.value,
                "updated_at": s.updated_at,
            }
            for s in strategies
        ],
    }


# --- reports and moderation ----------------------------------------------------------------------


async def _target(session: AsyncSession, target_type: ReportTarget, target_id: uuid.UUID):
    """(author id, post id, row) of a post or comment, or None."""
    if target_type == ReportTarget.post:
        post = await session.get(Post, target_id)
        return None if post is None else (post.author_id, post.id, post)
    comment = await session.get(Comment, target_id)
    return None if comment is None else (comment.author_id, comment.post_id, comment)


async def report(
    session: AsyncSession, user: User, data: ReportCreate
) -> tuple[ContentReport, bool]:
    """(report, created). Reporting the same content twice returns the first report."""
    found = await _target(session, data.target_type, data.target_id)
    if found is None:
        raise _404(data.target_type.value.capitalize())
    author_id, post_id, row = found
    await visible_post(session, user, post_id)
    if row.status != PUBLISHED:
        raise _404(data.target_type.value.capitalize())
    if author_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot report your own content")
    existing = await session.scalar(
        select(ContentReport).where(
            ContentReport.reporter_id == user.id,
            ContentReport.target_type == data.target_type,
            ContentReport.target_id == data.target_id,
        )
    )
    if existing is not None:
        return existing, False
    await _quota(
        session,
        ContentReport.created_at,
        ContentReport.reporter_id,
        user.id,
        timedelta(days=1),
        get_settings().reports_per_day,
        "reports per day",
    )
    row = ContentReport(
        reporter_id=user.id,
        target_type=data.target_type,
        target_id=data.target_id,
        reason=data.reason.strip(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row, True


async def list_reports(
    session: AsyncSession, *, report_status: ReportStatus | None, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    where = [] if report_status is None else [ContentReport.status == report_status]
    total = await session.scalar(select(func.count()).select_from(ContentReport).where(*where))
    reports = list(
        await session.scalars(
            select(ContentReport)
            .where(*where)
            .order_by(ContentReport.created_at.desc(), ContentReport.id)
            .limit(limit)
            .offset(offset)
        )
    )
    open_counts = dict(
        (
            await session.execute(
                select(ContentReport.target_id, func.count())
                .where(
                    ContentReport.status == ReportStatus.open,
                    ContentReport.target_id.in_({r.target_id for r in reports} or {uuid.uuid4()}),
                )
                .group_by(ContentReport.target_id)
            )
        ).all()
    )
    out = []
    for r in reports:
        reporter = await session.get(User, r.reporter_id)
        found = await _target(session, r.target_type, r.target_id)
        target = None
        if found is not None:
            author_id, post_id, row = found
            author = await session.get(User, author_id)
            target = {
                "status": row.status.value,
                "post_id": str(post_id),
                "author": {"id": str(author.id), "display_name": display_name(author)},
                "title": getattr(row, "title", None),
                "excerpt": templates.excerpt(row.body, 300),
            }
        out.append(
            {
                "id": r.id,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "reason": r.reason,
                "status": r.status,
                "resolution": r.resolution,
                "created_at": r.created_at,
                "resolved_at": r.resolved_at,
                "reporter": author_of(reporter) if reporter else None,
                "target": target,
                "open_reports_on_target": open_counts.get(r.target_id, 0),
            }
        )
    return out, total or 0


async def resolve(
    session: AsyncSession,
    redis: Redis | None,
    admin: User,
    report_id: uuid.UUID,
    data: ReportResolve,
) -> ContentReport:
    """``hide``: the content is hidden and its author notified; ``dismiss``: nothing changes.
    Either way every open report on the same content is resolved with this decision."""
    row = await session.get(ContentReport, report_id)
    if row is None:
        raise _404("Report")
    if row.status == ReportStatus.resolved:
        raise HTTPException(status.HTTP_409_CONFLICT, "Report already resolved")
    prepared = notifications.Prepared()
    if data.action == "hide":
        found = await _target(session, row.target_type, row.target_id)
        if found is not None:
            author_id, post_id, target = found
            if target.status == PUBLISHED:
                target.status = HIDDEN
                if row.target_type == ReportTarget.comment:
                    await _decrement_comments(session, post_id)
                item = notify.hidden_item(
                    author_id=author_id,
                    target_type=row.target_type.value,
                    target_id=row.target_id,
                    post_id=post_id,
                    excerpt=getattr(target, "title", None) or templates.excerpt(target.body, 80),
                    reason=data.note or row.reason,
                )
                prepared = await notify.prepare_safely(session, redis, [item])
    now = datetime.now(UTC)
    await session.execute(
        update(ContentReport)
        .where(
            ContentReport.target_type == row.target_type,
            ContentReport.target_id == row.target_id,
            ContentReport.status == ReportStatus.open,
        )
        .values(
            status=ReportStatus.resolved,
            resolution=data.action,
            resolved_by=admin.id,
            resolved_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    await session.refresh(row)
    await notifications.after_commit(redis, prepared)
    return row
