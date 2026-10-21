"""AI engine storage (B8, docs/ai-contract.md): setups decided by ai-service, their state
events, the model registry, per-user sizes and explanations. The backend never creates a
setup: rows come from ai-service responses (``app/ai/store.py``)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

STATES = "'DEVELOPING', 'ARMED', 'ACTIVE', 'CLOSED', 'EXPIRED', 'INVALIDATED'"


class AISetup(Base):
    """A setup as ai-service last described it. ``last_payload`` is the setup exactly as last
    returned (with ``state`` kept in step with transitions): the next evaluate request echoes it
    in ``open_setups``."""

    __tablename__ = "ai_setups"
    __table_args__ = (
        CheckConstraint(f"state IN ({STATES})", name="ck_ai_setups_state"),
        CheckConstraint("direction IN ('buy', 'sell')", name="ck_ai_setups_direction"),
        CheckConstraint(
            "probability IS NULL OR probability BETWEEN 0 AND 1", name="ck_ai_setups_probability"
        ),
        Index("ix_ai_setups_open", "instrument_id", "profile", "state"),
        Index("ix_ai_setups_created", text("created_at DESC")),
    )

    setup_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE")
    )
    profile: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(4))
    state: Mapped[str] = mapped_column(String(16))
    entry: Mapped[float | None] = mapped_column(Double)
    sl: Mapped[float | None] = mapped_column(Double)
    tp: Mapped[float | None] = mapped_column(Double)
    r_multiple: Mapped[float | None] = mapped_column(Double)
    probability: Mapped[float | None] = mapped_column(Double)
    ev_r: Mapped[float | None] = mapped_column(Double)
    ev_r_lower: Mapped[float | None] = mapped_column(Double)
    grade: Mapped[str | None] = mapped_column(String(4))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    horizon_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    realized_r: Mapped[float | None] = mapped_column(Double)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    last_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    strategy_version: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(128))
    features_version: Mapped[str | None] = mapped_column(String(64))
    first_request_id: Mapped[str] = mapped_column(String(160))
    last_request_id: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class AISetupEvent(Base):
    """Append-only history of a setup's states. ``from_state`` is null for its first
    appearance. Unique ``(setup_id, to_state, at)``: re-applying a response adds nothing."""

    __tablename__ = "ai_setup_events"
    __table_args__ = (
        UniqueConstraint("setup_id", "to_state", "at", name="uq_ai_setup_events_setup_state_at"),
        CheckConstraint(
            f"from_state IS NULL OR from_state IN ({STATES})", name="ck_ai_setup_events_from"
        ),
        CheckConstraint(f"to_state IN ({STATES})", name="ck_ai_setup_events_to"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    setup_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ai_setups.setup_id", ondelete="CASCADE")
    )
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))
    realized_r: Mapped[float | None] = mapped_column(Double)
    request_id: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class AIModelVersion(Base):
    """The model registry. At most one row is active (partial unique index). Versions that
    ai-service reports and nobody registered are added inactive, with a note."""

    __tablename__ = "ai_model_versions"
    __table_args__ = (
        Index(
            "uq_ai_model_versions_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    model_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    training_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_hash: Mapped[str | None] = mapped_column(String(128))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text)


class AISetupSize(Base):
    """A setup sized for one user (B10, ``app/ai/sizing.py``): by ai-service ``/v1/size`` or,
    when it is unavailable, by the backend's B4 lot sizing (``source``). ``inputs`` is what the
    size depends on (account, risk, spec and setup hashes, guard): the same inputs reuse it."""

    __tablename__ = "ai_setup_sizes"
    __table_args__ = (
        CheckConstraint("source IN ('ai-service', 'local')", name="ck_ai_setup_sizes_source"),
    )

    setup_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ai_setups.setup_id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    lots: Mapped[float] = mapped_column(Double)
    risk_usd: Mapped[float] = mapped_column(Double)  # in the account currency (contract name)
    margin_required: Mapped[float | None] = mapped_column(Double)
    feasible: Mapped[bool] = mapped_column(Boolean)
    warnings: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(16), server_default="local")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class AISetupTake(Base):
    """A user says they took a setup (B10). ``lots`` / ``risk_amount`` default to their stored
    size; when the setup ends, ``apply_evaluation`` fills ``closed_at``, ``realized_r``,
    ``pnl = realized_r * risk_amount`` and ``close_reason`` (EXPIRED / INVALIDATED: 0)."""

    __tablename__ = "ai_setup_takes"
    __table_args__ = (Index("ix_ai_setup_takes_user", "user_id", text("taken_at DESC")),)

    setup_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ai_setups.setup_id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    lots: Mapped[float | None] = mapped_column(Double)
    risk_amount: Mapped[float | None] = mapped_column(Double)
    entry_price: Mapped[float | None] = mapped_column(Double)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    realized_r: Mapped[float | None] = mapped_column(Double)
    pnl: Mapped[float | None] = mapped_column(Double)
    close_reason: Mapped[str | None] = mapped_column(String(64))


class AISetupExplanation(Base):
    """A setup explained by ai-service ``/v1/explain`` in one language (filled by B9/B11)."""

    __tablename__ = "ai_setup_explanations"
    __table_args__ = (
        CheckConstraint("lang IN ('ar', 'en')", name="ck_ai_setup_explanations_lang"),
    )

    setup_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("ai_setups.setup_id", ondelete="CASCADE"), primary_key=True
    )
    lang: Mapped[str] = mapped_column(String(8), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean)
    template_used: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
