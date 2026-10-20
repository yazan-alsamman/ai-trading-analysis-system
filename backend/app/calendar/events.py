"""Economic-calendar events, pure: the normalised input row, number parsing, the event key and
the version hash (docs/economic-calendar.md)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.economic_event import EventImpact, EventSource

# ForexFactory's calendar runs on New York time: the event's day, and its week (Sunday to
# Saturday), are taken there.
CALENDAR_TZ = ZoneInfo("America/New_York")
IMPACT_RANK = {
    EventImpact.holiday: 0,
    EventImpact.low: 1,
    EventImpact.medium: 2,
    EventImpact.high: 3,
}
TEXT_MAX = 32  # actual / forecast / previous / time_label
TITLE_MAX = 255
_MULTIPLIERS = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
_NUMBER = re.compile(r"^([+-]?\d+(?:\.\d+)?)([KMBT])?$", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


def source_family(source: str) -> str:
    """Both ForexFactory sources share one family, so live rows and history merge."""
    return "forexfactory" if source.startswith("forexfactory") else source


def impacts_at_least(minimum: str) -> list[str]:
    floor = IMPACT_RANK[EventImpact(minimum)]
    return [i.value for i, rank in IMPACT_RANK.items() if rank >= floor]


def parse_number(raw: str | None) -> float | None:
    """``0.3%`` -> 0.3, ``-12K`` -> -12000, ``1.25M`` -> 1250000, ``1,234`` -> 1234; null when
    empty or not a plain number (``<0.1%``, ``3.5|3.6``)."""
    if raw is None:
        return None
    text = raw.strip().replace(",", "").replace(" ", "").removesuffix("%")
    match = _NUMBER.match(text)
    if not match:
        return None
    value = float(match.group(1))
    suffix = match.group(2)
    return value * _MULTIPLIERS[suffix.upper()] if suffix else value


def clean(raw: str | None, limit: int = TEXT_MAX) -> str | None:
    """Empty strings are null; text is kept as published (trimmed and clipped)."""
    if raw is None:
        return None
    text = _SPACES.sub(" ", str(raw)).strip()
    return text[:limit] or None


def normalise_title(title: str) -> str:
    return _SPACES.sub(" ", title).strip().casefold()


def calendar_date(moment: datetime) -> date:
    return moment.astimezone(CALENDAR_TZ).date()


def week_start(day: date) -> date:
    """The Sunday that starts ForexFactory's week of ``day``."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def event_key(source: str, currency: str, title: str, day: date) -> str:
    """sha256 of (source family, currency, normalised title, the day in New York) as first
    observed: a later revision keeps the key it was first stored with."""
    raw = "|".join((source_family(source), currency.upper(), normalise_title(title), str(day)))
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class EventIn:
    """One version of an event, normalised (what a source says at one moment)."""

    source: str
    currency: str
    title: str
    impact: str
    scheduled_date: date  # the day in New York
    scheduled_at: datetime | None = None  # UTC; None: All Day / Tentative (time_label)
    time_label: str | None = None
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None
    fetched_at: datetime | None = None  # None: the time passed to upsert_versions

    @classmethod
    def build(
        cls,
        *,
        source: str | EventSource,
        currency: str,
        title: str,
        impact: str | EventImpact,
        scheduled_at: datetime | None,
        scheduled_date: date | None = None,
        time_label: str | None = None,
        actual: str | None = None,
        forecast: str | None = None,
        previous: str | None = None,
        fetched_at: datetime | None = None,
    ) -> EventIn:
        if scheduled_at is not None:
            scheduled_at = scheduled_at.astimezone(UTC)
            scheduled_date = calendar_date(scheduled_at)
        if scheduled_date is None:
            raise ValueError("an event needs a time or a day")
        title = clean(title, TITLE_MAX)
        if not title:
            raise ValueError("an event needs a title")
        currency = (currency or "").strip().upper()
        if not currency or len(currency) > 8:
            raise ValueError(f"bad currency {currency!r}")
        return cls(
            source=EventSource(source).value,
            currency=currency,
            title=title,
            impact=EventImpact(impact).value,
            scheduled_date=scheduled_date,
            scheduled_at=scheduled_at,
            time_label=clean(time_label) if scheduled_at is None else None,
            actual=clean(actual),
            forecast=clean(forecast),
            previous=clean(previous),
            fetched_at=fetched_at,
        )

    @property
    def natural_key(self) -> str:
        return event_key(self.source, self.currency, self.title, self.scheduled_date)

    @property
    def content_hash(self) -> str:
        """The fields that define a version: a change in any of them is a new row."""
        fields = [
            self.scheduled_at.isoformat() if self.scheduled_at else None,
            self.time_label,
            self.impact,
            self.actual,
            self.forecast,
            self.previous,
            self.title,
        ]
        return hashlib.sha256(json.dumps(fields).encode()).hexdigest()

    def without_actual(self, fetched_at: datetime | None) -> EventIn:
        return replace(self, actual=None, fetched_at=fetched_at)

    def row(self, key: str, fetched_at: datetime) -> dict:
        return {
            "event_key": key,
            "source": self.source,
            "currency": self.currency,
            "title": self.title,
            "impact": self.impact,
            "scheduled_at": self.scheduled_at,
            "scheduled_date": self.scheduled_date,
            "time_label": self.time_label,
            "actual": self.actual,
            "forecast": self.forecast,
            "previous": self.previous,
            "actual_value": parse_number(self.actual),
            "forecast_value": parse_number(self.forecast),
            "previous_value": parse_number(self.previous),
            "fetched_at": self.fetched_at or fetched_at,
            "content_hash": self.content_hash,
        }
