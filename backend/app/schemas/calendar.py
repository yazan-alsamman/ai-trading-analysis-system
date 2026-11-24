from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.economic_event import EventImpact


class EventRead(BaseModel):
    """One version of an event (the newest known at ``as_of`` in a list)."""

    model_config = ConfigDict(from_attributes=True)

    event_key: str = Field(description="stable identity of the event across its versions")
    scheduled_at: datetime | None = Field(description="UTC; null for All Day / Tentative")
    scheduled_date: date = Field(description="the event's day in New York (ForexFactory's day)")
    time_label: str | None = Field(examples=["All Day", "Tentative"])
    currency: str = Field(examples=["USD"])
    impact: EventImpact
    title: str = Field(examples=["CPI m/m"])
    actual: str | None = Field(description="as published", examples=["0.3%"])
    forecast: str | None = Field(examples=["0.2%"])
    previous: str | None = Field(examples=["0.4%"])
    actual_value: float | None = Field(description="parsed: % stripped, K/M/B multiplied")
    forecast_value: float | None
    previous_value: float | None
    fetched_at: datetime = Field(description="when this version became known")
    source: str = Field(examples=["forexfactory_live"])


class EventList(BaseModel):
    as_of: datetime = Field(description="the versions known at this time are shown")
    start: datetime
    end: datetime
    currencies: list[str] | None = Field(description="null: every currency")
    min_impact: EventImpact
    events: list[EventRead]


class EventHistory(BaseModel):
    event_key: str
    versions: list[EventRead] = Field(description="oldest first")


class ImportResult(BaseModel):
    dry_run: bool
    columns: dict[str, str] = Field(description="field -> CSV column used")
    rows_read: int
    skipped: dict[str, int] = Field(description="skipped rows by reason")
    skipped_examples: list[str]
    versions: int = Field(description="versions built (a row with actual gives two)")
    inserted: int
    unchanged: int = Field(description="versions already stored")
    first_date: date | None
    last_date: date | None
    events_per_impact: dict[str, int]
    sample: list[dict[str, Any]] = Field(description="the first parsed rows")


class RefreshResult(BaseModel):
    status: str = Field(
        description="ok | not_modified | blocked (429/403: back-off) | backoff | error | "
        "locked (another fetch runs) | disabled"
    )
    inserted: int | None = None
    unchanged: int | None = None
    items: int | None = None
    skipped: int | None = None
    http_status: int | None = None
    until: datetime | None = None
    error: str | None = None
