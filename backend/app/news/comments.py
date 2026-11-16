"""Readers' comments on news articles (docs/news-comments.md).

- Everyone signed in may comment (JWT only; API keys cannot). The rolling hourly cap is
  ``COMMENTS_PER_HOUR`` (shared with post comments by setting, counted separately).
- Two levels: a reply to a reply is stored under the top-level comment.
- Deleting is soft (``status = deleted``, body erased) so replies keep their place; deleted
  comments are left out of the list. The author or an admin may delete; only the author edits.
- ``news_articles.comments_count`` counts the published comments; it is kept in the same
  transaction as every change.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.news import NewsArticle, NewsComment
from app.models.user import User, UserRole
from app.social.notify import display_name

PUBLISHED, HIDDEN, DELETED = "published", "hidden", "deleted"


def _404(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def _is_admin(user: User) -> bool:
    return user.role == UserRole.admin


def require_enabled() -> None:
    if not get_settings().news_comments_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "News comments are turned off")


async def article_or_404(session: AsyncSession, article_id: uuid.UUID) -> NewsArticle:
    article = await session.get(NewsArticle, article_id)
    if article is None:
        raise _404("Article")
    return article


def serialize(viewer: User, comment: NewsComment, authors: dict[uuid.UUID, User]) -> dict:
    own = comment.author_id == viewer.id
    author = authors.get(comment.author_id)
    return {
        "id": comment.id,
        "article_id": comment.article_id,
        "parent_id": comment.parent_id,
        "author": (
            {"id": author.id, "display_name": display_name(author), "role": author.role}
            if author is not None
            else None
        ),
        "body": comment.body,
        "status": comment.status,
        "created_at": comment.created_at,
        "edited_at": comment.edited_at,
        "is_own": own,
        "can_edit": own and comment.status == PUBLISHED,
        "can_delete": (own or _is_admin(viewer)) and comment.status != DELETED,
    }


async def _authors(session: AsyncSession, comments: list[NewsComment]) -> dict[uuid.UUID, User]:
    ids = {c.author_id for c in comments}
    if not ids:
        return {}
    return {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))}


async def list_comments(
    session: AsyncSession,
    viewer: User,
    article: NewsArticle,
    *,
    limit: int,
    offset: int,
    parent_id: uuid.UUID | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Newest first. Every comment (top-level and replies) unless ``parent_id`` is given (the
    replies of one comment, oldest first). Hidden comments only for their author and admins."""
    visible = NewsComment.status == PUBLISHED
    if _is_admin(viewer):
        visible = NewsComment.status != DELETED
    else:
        visible = or_(
            visible, (NewsComment.status == HIDDEN) & (NewsComment.author_id == viewer.id)
        )
    conditions = [NewsComment.article_id == article.id, visible]
    order = [NewsComment.created_at.desc(), NewsComment.id]
    if parent_id is not None:
        conditions.append(NewsComment.parent_id == parent_id)
        order = [NewsComment.created_at, NewsComment.id]
    total = await session.scalar(select(func.count()).select_from(NewsComment).where(*conditions))
    rows = list(
        await session.scalars(
            select(NewsComment).where(*conditions).order_by(*order).limit(limit).offset(offset)
        )
    )
    authors = await _authors(session, rows)
    return [serialize(viewer, c, authors) for c in rows], total or 0


async def _hourly_cap(session: AsyncSession, user: User) -> None:
    limit = get_settings().comments_per_hour
    now = datetime.now(UTC)
    window = timedelta(hours=1)
    nth = await session.scalar(
        select(NewsComment.created_at)
        .where(NewsComment.author_id == user.id, NewsComment.created_at > now - window)
        .order_by(NewsComment.created_at.desc())
        .offset(limit - 1)
        .limit(1)
    )
    if nth is not None:
        retry = max(1, int((nth + window - now).total_seconds()) + 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"At most {limit} comments per hour",
            headers={"Retry-After": str(retry)},
        )


async def _recount(session: AsyncSession, article_id: uuid.UUID) -> None:
    count = (
        select(func.count())
        .select_from(NewsComment)
        .where(NewsComment.article_id == article_id, NewsComment.status == PUBLISHED)
        .scalar_subquery()
    )
    await session.execute(
        update(NewsArticle).where(NewsArticle.id == article_id).values(comments_count=count)
    )


async def create(
    session: AsyncSession,
    user: User,
    article: NewsArticle,
    body: str,
    parent_id: uuid.UUID | None,
) -> dict[str, Any]:
    await _hourly_cap(session, user)
    top_id = None
    if parent_id is not None:
        parent = await session.get(NewsComment, parent_id)
        if parent is None or parent.article_id != article.id:
            raise _404("Comment")
        if parent.status != PUBLISHED:
            raise HTTPException(status.HTTP_409_CONFLICT, "That comment cannot be replied to")
        top_id = parent.parent_id or parent.id  # two levels at most
    comment = NewsComment(article_id=article.id, author_id=user.id, parent_id=top_id, body=body)
    session.add(comment)
    await session.flush()
    await _recount(session, article.id)
    await session.commit()
    await session.refresh(comment)
    return serialize(user, comment, {user.id: user})


async def own_or_404(session: AsyncSession, comment_id: uuid.UUID) -> NewsComment:
    comment = await session.get(NewsComment, comment_id)
    if comment is None or comment.status == DELETED:
        raise _404("Comment")
    return comment


async def edit(session: AsyncSession, user: User, comment: NewsComment, body: str) -> dict:
    if comment.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can edit this comment")
    if comment.status != PUBLISHED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This comment is {comment.status}")
    comment.body = body
    comment.edited_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(comment)
    return serialize(user, comment, {user.id: user})


async def delete(session: AsyncSession, user: User, comment: NewsComment) -> None:
    if comment.author_id != user.id and not _is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the author can delete this comment")
    comment.status, comment.body = DELETED, ""
    await session.flush()
    await _recount(session, comment.article_id)
    await session.commit()


async def hide(session: AsyncSession, comment: NewsComment, hidden: bool) -> None:
    """Admin moderation: hide (only its author still sees it) or publish again."""
    comment.status = HIDDEN if hidden else PUBLISHED
    await session.flush()
    await _recount(session, comment.article_id)
    await session.commit()
