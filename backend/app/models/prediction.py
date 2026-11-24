"""Prediction tracking (Y16, docs/predictions.md): the outcome of each strategy signal after a
fixed horizon. AI setups need no table of their own: their outcome is derived from
``ai_setups`` and ``ai_setup_events``."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SignalOutcome(Base):
    """A buy/sell signal resolved ``horizon_bars`` closed bars after its bar by the
    ``predictions.resolve_signals`` task (one row per signal, never rewritten).

    ``return_pct``, ``mfe_pct`` and ``mae_pct`` are signed in the signal's direction (positive =
    in its favour) from the signal's price. ``correct``: the move in the signal's direction is
    larger than ``cost_per_unit`` (the instrument's fixed cost, 0 without one). A horizon with
    missing bars is resolved with ``correct`` null, null prices and the reason in ``note``."""

    __tablename__ = "signal_outcomes"
    __table_args__ = (
        CheckConstraint("horizon_bars > 0", name="ck_signal_outcomes_horizon"),
        CheckConstraint("cost_per_unit >= 0", name="ck_signal_outcomes_cost"),
        Index("ix_signal_outcomes_resolved_at", "resolved_at"),
    )

    signal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True
    )
    horizon_bars: Mapped[int] = mapped_column(Integer)
    exit_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_price: Mapped[float | None] = mapped_column(Double)
    return_pct: Mapped[float | None] = mapped_column(Double)
    mfe_pct: Mapped[float | None] = mapped_column(Double)
    mae_pct: Mapped[float | None] = mapped_column(Double)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    cost_per_unit: Mapped[float] = mapped_column(Double)
    note: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
