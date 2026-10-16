import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.candle import Timeframe


class BacktestStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


ACTIVE_STATUSES = (BacktestStatus.queued, BacktestStatus.running)


class Backtest(Base):
    """One backtest run of a global strategy on a market (engine: libs/backtest)."""

    __tablename__ = "backtests"
    __table_args__ = (
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_backtests_progress"),
        CheckConstraint("range_start < range_end", name="ck_backtests_range"),
        Index("ix_backtests_user_created", "user_id", text("created_at DESC")),
    )
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE")
    )
    timeframe: Mapped[Timeframe] = mapped_column(
        SAEnum(
            Timeframe,
            name="timeframe",
            native_enum=False,
            length=8,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    strategy_key: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)  # resolved
    params_hash: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)  # resolved BacktestConfig
    # requested range ("start"/"end" in the API; both inclusive) and the bars actually used
    range_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    range_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_bar_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_bar_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[BacktestStatus] = mapped_column(
        SAEnum(
            BacktestStatus,
            name="backtest_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=BacktestStatus.queued,
        server_default=BacktestStatus.queued.value,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # downsampled curves: {"time": [...], "equity": [...], "drawdown": [...]}
    equity_curve: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    bars: Mapped[int | None] = mapped_column(Integer)
    # clock_timestamp(): the real creation time even inside a longer transaction (ordering)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)  # task: start to finish
    engine_ms: Mapped[int | None] = mapped_column(Integer)  # signals + simulation + metrics


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    __table_args__ = (Index("uq_backtest_trades_number", "backtest_id", "number", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("backtests.id", ondelete="CASCADE")
    )
    number: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(5))  # long | short
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Double)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_price: Mapped[float] = mapped_column(Double)
    quantity: Mapped[float] = mapped_column(Double)
    gross_pnl: Mapped[float] = mapped_column(Double)
    fees: Mapped[float] = mapped_column(Double)
    net_pnl: Mapped[float] = mapped_column(Double)
    return_pct: Mapped[float] = mapped_column(Double)
    bars_held: Mapped[int] = mapped_column(Integer)
    entry_reason: Mapped[str | None] = mapped_column(String(64))
    exit_reason: Mapped[str] = mapped_column(String(16))
    # risk (Y13): initial stop, money at risk there, R = net_pnl / risk_amount, exit fills
    initial_stop: Mapped[float | None] = mapped_column(Double)
    risk_amount: Mapped[float | None] = mapped_column(Double)
    r_multiple: Mapped[float | None] = mapped_column(Double)
    fills: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
