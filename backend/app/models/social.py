"""Posts, comments, likes, follows and content reports (Y18)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.candle import Timeframe
from app.models.strategy import _timeframe

TITLE_MAX = 140
POST_BODY_MAX = 20_000
COMMENT_BODY_MAX = 2_000


class PostDirection(StrEnum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class PostVisibility(StrEnum):
    public = "public"
    followers = "followers"
    subscribers = "subscribers"  # Y19: an expert's subscribers (others see a teaser)


class ContentStatus(StrEnum):
    published = "published"
    hidden = "hidden"  # by moderation
    deleted = "deleted"  # by the author or an admin (soft)


class ReportTarget(StrEnum):
    post = "post"
    comment = "comment"
    message = "message"  # Y19: a chat message


class ReportStatus(StrEnum):
    open = "open"
    resolved = "resolved"


def _enum(cls, name: str) -> SAEnum:
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Post(Base):
    """An analysis. ``body`` is Markdown as written (never rendered by the API);
    ``attachments`` holds references only (``[{type, id}]``), resolved on read."""

    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("comments_count >= 0 AND likes_count >= 0", name="ck_posts_counters"),
        Index(
            "ix_posts_published",
            text("created_at DESC"),
            postgresql_where=text("status = 'published'"),
        ),
        Index("ix_posts_author_created", "author_id", text("created_at DESC")),
        Index("ix_posts_instrument_created", "instrument_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(TITLE_MAX))
    body: Mapped[str] = mapped_column(Text)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="SET NULL")
    )
    timeframe: Mapped[Timeframe | None] = mapped_column(_timeframe)
    direction: Mapped[PostDirection | None] = mapped_column(_enum(PostDirection, "post_direction"))
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    visibility: Mapped[PostVisibility] = mapped_column(
        _enum(PostVisibility, "post_visibility"),
        default=PostVisibility.public,
        server_default=PostVisibility.public.value,
    )
    status: Mapped[ContentStatus] = mapped_column(
        _enum(ContentStatus, "content_status"),
        default=ContentStatus.published,
        server_default=ContentStatus.published.value,
    )
    comments_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    likes_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class Comment(Base):
    """Two levels: a reply to a reply is stored under the top-level comment."""

    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_post_created", "post_id", "created_at"),
        Index("ix_comments_parent_created", "parent_id", "created_at"),
        Index("ix_comments_author_created", "author_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    post_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("comments.id", ondelete="CASCADE")
    )
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[ContentStatus] = mapped_column(
        _enum(ContentStatus, "content_status"),
        default=ContentStatus.published,
        server_default=ContentStatus.published.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PostLike(Base):
    """A user's like of a post (``posts.likes_count`` moves in the same transaction)."""

    __tablename__ = "post_likes"
    __table_args__ = (Index("ix_post_likes_post_created", "post_id", "created_at"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class Follow(Base):
    """A user following an analyst or expert (the following feed and new_post notifications)."""

    __tablename__ = "follows"
    __table_args__ = (
        CheckConstraint("follower_id <> followee_id", name="ck_follows_not_self"),
        Index("ix_follows_followee", "followee_id", "created_at"),
    )

    follower_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    followee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class ContentReport(Base):
    """A user's report of a post, comment or chat message; an admin hides the content or
    dismisses it."""

    __tablename__ = "content_reports"
    __table_args__ = (
        UniqueConstraint(
            "reporter_id", "target_type", "target_id", name="uq_content_reports_reporter_target"
        ),
        Index("ix_content_reports_status_created", "status", "created_at"),
        Index("ix_content_reports_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    target_type: Mapped[ReportTarget] = mapped_column(_enum(ReportTarget, "report_target"))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[ReportStatus] = mapped_column(
        _enum(ReportStatus, "report_status"),
        default=ReportStatus.open,
        server_default=ReportStatus.open.value,
    )
    resolution: Mapped[str | None] = mapped_column(String(16))  # hide | dismiss
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
