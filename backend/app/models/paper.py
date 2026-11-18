"""Paper trading (migration 0026, docs/paper-trading.md): a simulated account per user, orders
and positions filled on the platform's live 1m candles. No real money, no broker."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaperSide(StrEnum):
    buy = "buy"
    sell = "sell"


class PaperOrderType(StrEnum):
    market = "market"
    limit = "limit"
    stop = "stop"


class PaperOrderStatus(StrEnum):
    pending = "pending"
    filled = "filled"
    cancelled = "cancelled"
    rejected = "rejected"


class PaperPositionStatus(StrEnum):
    open = "open"
    closed = "closed"


class PaperCloseReason(StrEnum):
    manual = "manual"
    stop_loss = "stop_loss"
    take_profit = "take_profit"
    reset = "reset"


class PaperAccount(Base):
    """``balance`` is the cash: the initial balance plus every realized P/L (costs included)."""

    __tablename__ = "paper_accounts"
    __table_args__ = (
        CheckConstraint("leverage BETWEEN 1 AND 1000", name="ck_paper_accounts_leverage"),
        CheckConstraint("initial_balance > 0", name="ck_paper_accounts_initial"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    currency: Mapped[str] = mapped_column(String(8), default="USD", server_default="USD")
    initial_balance: Mapped[float] = mapped_column(Double)
    balance: Mapped[float] = mapped_column(Double)
    leverage: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_paper_positions_side"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_paper_positions_status"),
        CheckConstraint("lots > 0", name="ck_paper_positions_lots"),
        Index("ix_paper_positions_user_status", "user_id", "status", text("opened_at DESC")),
        Index(
            "ix_paper_positions_open_instrument",
            "instrument_id",
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE")
    )
    side: Mapped[str] = mapped_column(String(4))
    lots: Mapped[float] = mapped_column(Double)
    contract_size: Mapped[float] = mapped_column(Double)  # copied at open: P/L stays stable
    entry_price: Mapped[float] = mapped_column(Double)
    stop_loss: Mapped[float | None] = mapped_column(Double)
    take_profit: Mapped[float | None] = mapped_column(Double)
    margin: Mapped[float] = mapped_column(Double)
    cost: Mapped[float] = mapped_column(Double, default=0.0, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(8), default="open", server_default="open")
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    # the engine has checked SL/TP on every closed 1m bar that starts before this
    checked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_price: Mapped[float | None] = mapped_column(Double)
    close_reason: Mapped[str | None] = mapped_column(String(16))
    pnl: Mapped[float | None] = mapped_column(Double)  # realized, net of cost


class PaperOrder(Base):
    __tablename__ = "paper_orders"
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_paper_orders_side"),
        CheckConstraint("type IN ('market', 'limit', 'stop')", name="ck_paper_orders_type"),
        CheckConstraint(
            "status IN ('pending', 'filled', 'cancelled', 'rejected')",
            name="ck_paper_orders_status",
        ),
        CheckConstraint("lots > 0", name="ck_paper_orders_lots"),
        Index("ix_paper_orders_user_created", "user_id", text("created_at DESC")),
        Index(
            "ix_paper_orders_pending_instrument",
            "instrument_id",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE")
    )
    side: Mapped[str] = mapped_column(String(4))
    type: Mapped[str] = mapped_column(String(8))
    lots: Mapped[float] = mapped_column(Double)
    price: Mapped[float | None] = mapped_column(Double)  # limit / stop trigger
    stop_loss: Mapped[float | None] = mapped_column(Double)
    take_profit: Mapped[float | None] = mapped_column(Double)
    status: Mapped[str] = mapped_column(String(12))
    reject_reason: Mapped[str | None] = mapped_column(String(64))
    fill_price: Mapped[float | None] = mapped_column(Double)
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("paper_positions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    checked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
