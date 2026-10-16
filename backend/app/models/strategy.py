import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    Index,
    String,
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

# Timeframe stored as its value ("1m", "1h", ...) in a plain string column
_timeframe = SAEnum(
    Timeframe,
    name="timeframe",
    native_enum=False,
    length=8,
    values_callable=lambda e: [m.value for m in e],
    validate_strings=True,
)


class SignalSide(StrEnum):
    buy = "buy"
    sell = "sell"


class UserStrategy(Base):
    """A user activating a global strategy (code, not a table) on one market."""

    __tablename__ = "user_strategies"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "strategy_key",
            "params_hash",
            "instrument_id",
            "timeframe",
            name="uq_user_strategies_setup",
        ),
        # the signal engine looks up active setups by market
        Index("ix_user_strategies_market", "instrument_id", "timeframe", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    strategy_key: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    params_hash: Mapped[str] = mapped_column(String(64))
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE")
    )
    timeframe: Mapped[Timeframe] = mapped_column(_timeframe)
    name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    notify: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # risk rules of this activation's trade plans (null: the user's risk profile)
    risk_override: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Signal(Base):
    """A signal produced by the live engine for one strategy setup on one closed bar."""

    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "timeframe",
            "strategy_key",
            "params_hash",
            "bar_time",
            name="uq_signals_bar",
        ),
        Index("ix_signals_market_time", "instrument_id", "timeframe", text("bar_time DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE")
    )
    timeframe: Mapped[Timeframe] = mapped_column(_timeframe)
    strategy_key: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    params_hash: Mapped[str] = mapped_column(String(64))
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    side: Mapped[SignalSide] = mapped_column(
        SAEnum(SignalSide, name="signal_side", values_callable=lambda e: [m.value for m in e])
    )
    strength: Mapped[float] = mapped_column(Double)
    price: Mapped[float] = mapped_column(Double)
    reason: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
