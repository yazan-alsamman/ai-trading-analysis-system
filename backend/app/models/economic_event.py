"""Economic calendar (B6, docs/economic-calendar.md): one row per observed version of an event."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Double,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventImpact(StrEnum):
    holiday = "holiday"
    low = "low"
    medium = "medium"
    high = "high"


class EventSource(StrEnum):
    forexfactory_live = "forexfactory_live"  # the weekly JSON, fetched by calendar.refresh
    forexfactory_kaggle = "forexfactory_kaggle"  # history, loaded from a CSV by an admin
    manual = "manual"


class EconomicEvent(Base):
    """A version of an economic-calendar event as it was known at ``fetched_at``. Revisions
    (time moved, actual released, impact changed) are new rows with the same ``event_key``;
    the newest row with ``fetched_at <= T`` is what was known at T (point in time)."""

    __tablename__ = "economic_events"
    __table_args__ = (
        UniqueConstraint("event_key", "content_hash", name="uq_economic_events_key_hash"),
        CheckConstraint(
            "impact IN ('high', 'medium', 'low', 'holiday')", name="ck_economic_events_impact"
        ),
        CheckConstraint(
            "source IN ('forexfactory_live', 'forexfactory_kaggle', 'manual')",
            name="ck_economic_events_source",
        ),
        CheckConstraint("currency = upper(currency)", name="ck_economic_events_currency"),
        Index("ix_economic_events_key_fetched", "event_key", text("fetched_at DESC")),
        Index("ix_economic_events_scheduled", "scheduled_at"),
        Index("ix_economic_events_currency_impact", "currency", "impact", "scheduled_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    event_key: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(255))
    impact: Mapped[str] = mapped_column(String(8))
    # UTC; null when the source gives no time ("All Day", "Tentative": kept in time_label)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # the event's day in America/New_York (ForexFactory's calendar day), always set: it keeps
    # the events without a time in date-range queries
    scheduled_date: Mapped[date] = mapped_column(Date)
    time_label: Mapped[str | None] = mapped_column(String(32))
    actual: Mapped[str | None] = mapped_column(String(32))
    forecast: Mapped[str | None] = mapped_column(String(32))
    previous: Mapped[str | None] = mapped_column(String(32))
    actual_value: Mapped[float | None] = mapped_column(Double)
    forecast_value: Mapped[float | None] = mapped_column(Double)
    previous_value: Mapped[float | None] = mapped_column(Double)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
