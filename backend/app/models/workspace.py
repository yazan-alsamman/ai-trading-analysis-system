import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Workspace(Base):
    """A saved trading screen (layout, charts, indicators, drawings, watchlist) of one user.

    ``state`` is one validated JSON document (app/schemas/workspaces.py, ``schema_version``);
    ``version`` is the optimistic-concurrency counter, +1 on every state change.
    """

    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="ck_workspaces_name_length"),
        CheckConstraint("version >= 1", name="ck_workspaces_version_positive"),
        Index(
            "uq_workspaces_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
        Index("uq_workspaces_user_name", "user_id", text("lower(name)"), unique=True),
        Index("ix_workspaces_user_position", "user_id", "position"),
    )
    # updated_at is set by the server on UPDATE: fetch it back (RETURNING) instead of leaving
    # it expired, so responses can be built after a commit without lazy loads
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(60))
    position: Mapped[int] = mapped_column(Integer)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    share_slug: Mapped[str | None] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
