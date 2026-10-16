"""Price alerts (Y18 part B): evaluated on every closed 1m candle, delivered as notifications."""

import uuid
from datetime import datetime
from enum import StrEnum

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
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlertCondition(StrEnum):
    above = "above"  # the bar's high >= value
    below = "below"  # the bar's low <= value
    crosses_above = "crosses_above"  # previous close < value <= this close
    crosses_below = "crosses_below"  # previous close > value >= this close
    change_pct = "change_pct"  # |close / close window_minutes ago - 1| >= value %


class AlertRepeat(StrEnum):
    once = "once"  # deactivated after firing
    every = "every"  # fires again after cooldown_minutes


def _enum(cls, name: str) -> SAEnum:
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class PriceAlert(Base):
    __tablename__ = "price_alerts"
    __table_args__ = (
        CheckConstraint("value > 0", name="ck_price_alerts_value_positive"),
        CheckConstraint(
            "(condition = 'change_pct') = (window_minutes IS NOT NULL)",
            name="ck_price_alerts_window",
        ),
        CheckConstraint(
            "(repeat = 'every') = (cooldown_minutes IS NOT NULL)", name="ck_price_alerts_cooldown"
        ),
        # the evaluator loads the active alerts of the instruments it checks
        Index(
            "ix_price_alerts_active_instrument",
            "instrument_id",
            postgresql_where=text("is_active"),
        ),
        Index("ix_price_alerts_user_created", "user_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE")
    )
    condition: Mapped[AlertCondition] = mapped_column(
        _enum(AlertCondition, "price_alert_condition")
    )
    value: Mapped[float] = mapped_column(Double)  # a price, or a percent for change_pct
    window_minutes: Mapped[int | None] = mapped_column(Integer)
    repeat: Mapped[AlertRepeat] = mapped_column(
        _enum(AlertRepeat, "price_alert_repeat"),
        default=AlertRepeat.once,
        server_default=AlertRepeat.once.value,
    )
    cooldown_minutes: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trigger_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )
