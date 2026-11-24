"""Chart image analyses (Y14, docs/chart-analysis.md): one row per analysis a user asked for.

The image itself is **never stored**: only its SHA-256 (duplicates within 24 h reuse the row),
size, dimensions and type. ``result`` is the checked ``ChartAnalysis`` (status ``ok`` or
``not_chart``), or ``{"code", "message"}`` for ``refused`` and ``error``."""

import uuid
from datetime import datetime
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

STATUSES = ("ok", "not_chart", "refused", "error")


class ChartAnalysisRecord(Base):
    __tablename__ = "chart_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ok', 'not_chart', 'refused', 'error')", name="ck_chart_analyses_status"
        ),
        CheckConstraint("language IN ('ar', 'en')", name="ck_chart_analyses_language"),
        Index("ix_chart_analyses_user_created", "user_id", text("created_at DESC")),
        Index("ix_chart_analyses_user_sha", "user_id", "image_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    image_sha256: Mapped[str] = mapped_column(String(64))
    image_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    mime: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(2))
    symbol_hint: Mapped[str | None] = mapped_column(String(32))
    timeframe_hint: Mapped[str | None] = mapped_column(String(8))
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
