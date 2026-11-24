import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Double, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Timeframe(StrEnum):
    m1 = "1m"
    m5 = "5m"
    m15 = "15m"
    h1 = "1h"
    h4 = "4h"
    d1 = "1d"

    @property
    def relation(self) -> str:
        """Table/view holding this timeframe. Never build relation names from user input."""
        return TIMEFRAME_SPECS[self].relation

    @property
    def interval(self) -> timedelta:
        return TIMEFRAME_SPECS[self].interval

    @property
    def policy_end_offset(self) -> timedelta | None:
        return TIMEFRAME_SPECS[self].policy_end_offset


@dataclass(frozen=True)
class TimeframeSpec:
    relation: str
    interval: timedelta
    # end_offset of the cagg refresh policy (migration 0003): buckets newer than this are left to
    # real-time aggregation and must not be materialized by manual refreshes either.
    policy_end_offset: timedelta | None = None


# 1m is the source of truth (hypertable); every other timeframe is a hierarchical continuous
# aggregate: 5m <- 1m, 15m <- 5m, 1h <- 15m, 4h <- 1h, 1d <- 1h (see migration 0003).
TIMEFRAME_SPECS: dict[Timeframe, TimeframeSpec] = {
    Timeframe.m1: TimeframeSpec("candles_1m", timedelta(minutes=1)),
    Timeframe.m5: TimeframeSpec("candles_5m", timedelta(minutes=5), timedelta(minutes=5)),
    Timeframe.m15: TimeframeSpec("candles_15m", timedelta(minutes=15), timedelta(minutes=15)),
    Timeframe.h1: TimeframeSpec("candles_1h", timedelta(hours=1), timedelta(hours=1)),
    Timeframe.h4: TimeframeSpec("candles_4h", timedelta(hours=4), timedelta(hours=4)),
    Timeframe.d1: TimeframeSpec("candles_1d", timedelta(days=1), timedelta(days=1)),
}

# Continuous aggregates in refresh order (each one reads the previous level).
AGGREGATE_TIMEFRAMES: tuple[Timeframe, ...] = (
    Timeframe.m5,
    Timeframe.m15,
    Timeframe.h1,
    Timeframe.h4,
    Timeframe.d1,
)


class Candle(Base):
    """A 1-minute candle (TimescaleDB hypertable). ``ts`` is the UTC start of the minute.

    ``spread`` (price units), ``source`` and ``received_at`` exist on 1m only; the continuous
    aggregates do not carry them. ``spread >= 0`` is enforced by the API schema: TimescaleDB
    refuses new constraints on a hypertable with compression enabled (migration 0013).
    """

    __tablename__ = "candles_1m"
    __table_args__ = (
        CheckConstraint("high >= low", name="ck_candles_1m_high_low"),
        CheckConstraint("high >= greatest(open, close)", name="ck_candles_1m_high"),
        CheckConstraint("low <= least(open, close)", name="ck_candles_1m_low"),
        CheckConstraint("volume >= 0", name="ck_candles_1m_volume"),
        CheckConstraint("ts = date_trunc('minute', ts)", name="ck_candles_1m_ts_minute"),
    )

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Double)
    high: Mapped[float] = mapped_column(Double)
    low: Mapped[float] = mapped_column(Double)
    close: Mapped[float] = mapped_column(Double)
    volume: Mapped[float] = mapped_column(Double)
    trades: Mapped[int | None] = mapped_column(Integer)
    spread: Mapped[float | None] = mapped_column(Double)
    source: Mapped[str | None] = mapped_column(String(32))  # fxpro_ctrader, binance, seed, ...
    # when the backend first received the bar (kept on re-sends, for the feed lag)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
