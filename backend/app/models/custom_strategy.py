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
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

KEY_PREFIX = "custom:"


class CustomStrategyKind(StrEnum):
    builder = "builder"
    composite = "composite"


class Visibility(StrEnum):
    private = "private"
    public = "public"


class CustomStrategy(Base):
    """A user's own strategy: rules (Builder) or several strategies voting (Composite).

    ``definition`` is the validated, normalised JSON document (``trading_strategies.custom``);
    ``version`` is the optimistic-concurrency counter, +1 on every definition change.
    ``definition_hash`` identifies the setup like a global strategy's ``params_hash``: the hash
    of the definition's snapshot, which for a composite includes its custom members'
    definitions (so editing a member changes the composite's hash too).
    """

    __tablename__ = "custom_strategies"
    __table_args__ = (
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 60", name="ck_custom_strategies_name_length"
        ),
        CheckConstraint(
            "char_length(description) <= 500", name="ck_custom_strategies_description_length"
        ),
        CheckConstraint("version >= 1", name="ck_custom_strategies_version_positive"),
        Index("uq_custom_strategies_user_name", "user_id", text("lower(name)"), unique=True),
        Index("ix_custom_strategies_visibility_updated", "visibility", text("updated_at DESC")),
        Index("ix_custom_strategies_user_created", "user_id", "created_at"),
    )
    # updated_at is set by the server on UPDATE: fetch it back instead of leaving it expired
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(500), default="", server_default="")
    kind: Mapped[CustomStrategyKind] = mapped_column(
        SAEnum(
            CustomStrategyKind,
            name="custom_strategy_kind",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    definition_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    visibility: Mapped[Visibility] = mapped_column(
        SAEnum(
            Visibility,
            name="custom_strategy_visibility",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=Visibility.private,
        server_default=Visibility.private.value,
    )
    cloned_from: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("custom_strategies.id", ondelete="SET NULL")
    )
    # clock_timestamp(): the real time even inside a longer transaction (list ordering)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )

    @property
    def key(self) -> str:
        """The strategy key used everywhere a global key is (``custom:<uuid>``)."""
        return f"{KEY_PREFIX}{self.id}"
