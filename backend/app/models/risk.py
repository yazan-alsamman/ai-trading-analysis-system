import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RiskProfile(Base):
    """A user's risk rules and declared account size (one per user, created on first read).

    ``config`` is a validated, normalised risk config (``trading_backtest.validate_risk_config``:
    stop, trailing, take_profit, sizing, guards, fee_bps). ``account_size`` is what the user
    declares; we never connect to an exchange.
    """

    __tablename__ = "risk_profiles"
    __table_args__ = (
        CheckConstraint("account_size > 0", name="ck_risk_profiles_account_size_positive"),
        CheckConstraint("leverage > 0 AND leverage <= 10000", name="ck_risk_profiles_leverage"),
    )
    __mapper_args__ = {"eager_defaults": True}

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    account_size: Mapped[float] = mapped_column(
        Double, default=10_000.0, server_default=text("10000")
    )
    quote_currency: Mapped[str] = mapped_column(String(10), default="USDT", server_default="USDT")
    # B10: the account's leverage (AI setup margin), and when account_size last changed (the
    # drawdown guard counts the taken trades closed since then; null: all of them)
    leverage: Mapped[float] = mapped_column(Double, default=100.0, server_default=text("100"))
    balance_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    template: Mapped[str | None] = mapped_column(String(20))  # set when made from a template
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )


class SignalPlan(Base):
    """The trade plan of one signal for one user (and activation): entry, stop, targets, size,
    risk. ``signals`` rows stay user-independent; plans depend on each user's risk rules."""

    __tablename__ = "signal_plans"
    __table_args__ = (
        UniqueConstraint(
            "signal_id",
            "user_id",
            "user_strategy_id",
            name="uq_signal_plans_signal_user_setup",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_signal_plans_user_created", "user_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("signals.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    user_strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_strategies.id", ondelete="SET NULL")
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
