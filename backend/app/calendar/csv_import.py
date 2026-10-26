"""History of the economic calendar from a CSV (a ForexFactory export such as the Kaggle
dataset, downloaded by hand: it is never committed). Shared by ``scripts/load_calendar_csv.py``
and ``POST /admin/calendar/import``.

The file is read row by row and stored in batches, so it is never held in memory. Times are
converted from ``tz`` with zoneinfo; a timed row without timezone information and no ``tz``
stops the import (the timezone is never guessed).

``fetched_at`` of history is an approximation (we do not know when each value was first
published): a row without ``actual`` is stored as known 7 days before the event; a row with
``actual`` becomes two versions, the same row without ``actual`` 7 days before, and the full row
at the event time. An "as of" read before the release sees the forecast, not the actual.
"""

from __future__ import annotations

import asyncio
import csv
import itertools
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.calendar.events import CALENDAR_TZ, EventIn
from app.calendar.service import upsert_versions
from app.models.economic_event import EventSource

FIELDS = ("date", "time", "currency", "impact", "title", "actual", "forecast", "previous")
REQUIRED = ("date", "currency", "impact", "title")
# header names of the common ForexFactory exports, compared case-insensitively
ALIASES = {
    "date": ("date", "datetime", "date_time", "date time", "timestamp", "start"),
    "time": ("time",),
    "currency": ("currency", "cur", "cur.", "country", "symbol"),
    "impact": ("impact", "importance", "volatility"),
    "title": ("event", "title", "name", "event name", "detail"),
    "actual": ("actual",),
    "forecast": ("forecast", "consensus"),
    "previous": ("previous", "prior"),
}
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%Y.%m.%d", "%b %d, %Y", "%a %b %d %Y")
TIME_FORMATS = ("%H:%M", "%H:%M:%S", "%I:%M%p", "%I:%M %p", "%I%p")
PRE_RELEASE = timedelta(days=7)
BATCH_SIZE = 5000
SAMPLE_ROWS = 5
SOURCES = (EventSource.forexfactory_kaggle.value, EventSource.manual.value)


class CsvFormatError(ValueError):
    """The file cannot be imported as a whole (columns, timezone): nothing more is read."""


class RowError(ValueError):
    """One row is skipped, with this reason."""


@dataclass
class ImportOptions:
    source: str = EventSource.forexfactory_kaggle.value
    tz: str | None = None
    since: date | None = date(2018, 1, 1)
    mapping: dict[str, str] = field(default_factory=dict)  # field -> header, overrides
    date_format: str | None = None
    dry_run: bool = False

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise CsvFormatError(f"source must be one of {', '.join(SOURCES)}")
        if self.tz:
            try:
                ZoneInfo(self.tz)
            except (ZoneInfoNotFoundError, ValueError):
                raise CsvFormatError(f"unknown timezone {self.tz!r}") from None
        unknown = set(self.mapping) - set(FIELDS)
        if unknown:
            raise CsvFormatError(f"unknown field(s) in the mapping: {', '.join(sorted(unknown))}")


@dataclass
class ImportSummary:
    columns: dict[str, str] = field(default_factory=dict)
    rows_read: int = 0
    skipped: Counter = field(default_factory=Counter)
    skipped_examples: list[str] = field(default_factory=list)
    versions: int = 0
    inserted: int = 0
    unchanged: int = 0
    first: date | None = None
    last: date | None = None
    impacts: Counter = field(default_factory=Counter)  # events (rows), not versions
    sample: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "columns": self.columns,
            "rows_read": self.rows_read,
            "skipped": dict(sorted(self.skipped.items())),
            "skipped_examples": self.skipped_examples,
            "versions": self.versions,
            "inserted": self.inserted,
            "unchanged": self.unchanged,
            "first_date": self.first.isoformat() if self.first else None,
            "last_date": self.last.isoformat() if self.last else None,
            "events_per_impact": dict(sorted(self.impacts.items())),
            "sample": self.sample,
        }


def parse_mapping(text: str | None) -> dict[str, str]:
    """``title=Event,date=Date`` -> {"title": "Event", "date": "Date"}."""
    out: dict[str, str] = {}
    for part in (text or "").split(","):
        if not part.strip():
            continue
        name, sep, column = part.partition("=")
        if not sep or not name.strip() or not column.strip():
            raise CsvFormatError(f"bad mapping {part.strip()!r}: use field=Column")
        out[name.strip().lower()] = column.strip()
    return out


def detect_columns(header: list[str], overrides: dict[str, str]) -> dict[str, int]:
    """Field -> column index, from the overrides first, then the known header names."""
    names = [h.strip() for h in header]
    lower = {n.lower(): i for i, n in enumerate(names)}
    found: dict[str, int] = {}
    for name in FIELDS:
        if name in overrides:
            column = overrides[name]
            if column.lower() not in lower:
                raise CsvFormatError(
                    f"column {column!r} (for {name}) is not in the header: {', '.join(names)}"
                )
            found[name] = lower[column.lower()]
            continue
        for alias in ALIASES[name]:
            if alias in lower and lower[alias] not in found.values():
                found[name] = lower[alias]
                break
    missing = [name for name in REQUIRED if name not in found]
    if missing:
        raise CsvFormatError(
            f"no column for {', '.join(missing)} in the header ({', '.join(names)}); "
            "name it with --map, e.g. --map title=Event,date=Date"
        )
    return found


def parse_impact(raw: str) -> str:
    text = raw.strip().lower()
    if "holiday" in text or "non-economic" in text or text.startswith(("gra", "grey")):
        return "holiday"
    if "high" in text or text.startswith("red") or text == "3":
        return "high"
    if "med" in text or "moderate" in text or text.startswith("ora") or text == "2":
        return "medium"
    if "low" in text or text.startswith("yel") or text == "1":
        return "low"
    raise RowError("bad impact")


def _parse_date(raw: str, fmt: str | None) -> datetime:
    raw = raw.strip()
    if fmt:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            raise RowError("bad date") from None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    for candidate in DATE_FORMATS:
        try:
            return datetime.strptime(raw, candidate)
        except ValueError:
            continue
    raise RowError("bad date")


def _parse_time(raw: str) -> time:
    for candidate in TIME_FORMATS:
        try:
            return datetime.strptime(
                raw.replace(" ", "").upper(), candidate.replace(" ", "")
            ).time()
        except ValueError:
            continue
    raise RowError("bad time")


def _has_clock(raw: str) -> bool:
    return ":" in raw


def parse_row(values: list[str], columns: dict[str, int], options: ImportOptions) -> EventIn:
    """One CSV row as a version (``fetched_at`` not set yet). Raises RowError to skip it and
    CsvFormatError when the file has no timezone information and ``tz`` is missing."""

    def get(name: str) -> str:
        index = columns.get(name)
        return values[index].strip() if index is not None else ""

    title, currency, raw_date = get("title"), get("currency"), get("date")
    if not title:
        raise RowError("missing title")
    if not currency:
        raise RowError("missing currency")
    if not raw_date:
        raise RowError("missing date")
    impact = parse_impact(get("impact"))
    raw_time = get("time")
    moment = _parse_date(raw_date, options.date_format)
    label = None
    if raw_time and not raw_time[0].isdigit():
        label = raw_time  # All Day, Tentative, Day 1, ...
    elif raw_time:
        moment = datetime.combine(moment.date(), _parse_time(raw_time), moment.tzinfo)
    elif not (options.date_format and "%H" in options.date_format) and not _has_clock(raw_date):
        label = "All Day"  # a day without a time
    if label is not None:
        scheduled_at, day = None, moment.date()
    else:
        if moment.tzinfo is None:
            if not options.tz:
                raise CsvFormatError(
                    "the CSV times have no timezone information: pass the timezone they are "
                    "in (--tz / tz=, e.g. America/New_York or UTC); it is never guessed"
                )
            moment = moment.replace(tzinfo=ZoneInfo(options.tz))
        scheduled_at, day = moment.astimezone(UTC), None
    try:
        return EventIn.build(
            source=options.source,
            currency=currency,
            title=title,
            impact=impact,
            scheduled_at=scheduled_at,
            scheduled_date=day,
            time_label=label,
            actual=get("actual"),
            forecast=get("forecast"),
            previous=get("previous"),
        )
    except ValueError as exc:
        raise RowError(str(exc)[:80]) from None


def versions(event: EventIn) -> list[EventIn]:
    """The approximated history of one row (see the module docstring)."""
    reference = event.scheduled_at or datetime.combine(
        event.scheduled_date, time(0), CALENDAR_TZ
    ).astimezone(UTC)
    before = reference - PRE_RELEASE
    if event.actual:
        return [event.without_actual(before), replace(event, fetched_at=reference)]
    return [replace(event, fetched_at=before)]


def _sample(event: EventIn) -> dict[str, Any]:
    return {
        "scheduled_at": event.scheduled_at.isoformat() if event.scheduled_at else None,
        "date": event.scheduled_date.isoformat(),
        "time_label": event.time_label,
        "currency": event.currency,
        "impact": event.impact,
        "title": event.title,
        "actual": event.actual,
        "forecast": event.forecast,
        "previous": event.previous,
    }


def iter_versions(
    rows: Iterator[list[str]], options: ImportOptions, summary: ImportSummary
) -> Iterator[EventIn]:
    """The versions of every importable row; the header is the first row."""
    header = next(rows, None)
    if not header:
        raise CsvFormatError("the file is empty")
    columns = detect_columns(header, options.mapping)
    summary.columns = {name: header[i].strip() for name, i in columns.items()}
    width = len(header)
    for line, values in enumerate(rows, start=2):
        if not values or not any(v.strip() for v in values):
            continue
        summary.rows_read += 1
        try:
            if len(values) != width:
                raise RowError("malformed row")
            event = parse_row(values, columns, options)
            if options.since and event.scheduled_date < options.since:
                raise RowError("before --from")
        except RowError as exc:
            summary.skipped[str(exc)] += 1
            if len(summary.skipped_examples) < 10 and str(exc) != "before --from":
                summary.skipped_examples.append(f"line {line}: {exc}")
            continue
        summary.impacts[event.impact] += 1
        summary.first = min(summary.first or event.scheduled_date, event.scheduled_date)
        summary.last = max(summary.last or event.scheduled_date, event.scheduled_date)
        if len(summary.sample) < SAMPLE_ROWS:
            summary.sample.append(_sample(event))
        yield from versions(event)


async def import_rows(
    session: AsyncSession | None,
    rows: Iterable[list[str]],
    options: ImportOptions,
    *,
    batch_size: int = BATCH_SIZE,
) -> ImportSummary:
    """Parse ``rows`` (a csv.reader) and store the versions in batches (one transaction each,
    idempotent). ``options.dry_run`` parses everything and stores nothing (no session needed)."""
    summary = ImportSummary(dry_run=options.dry_run)
    stream = iter_versions(iter(rows), options, summary)

    def take() -> list[EventIn]:
        return list(itertools.islice(stream, batch_size))

    while True:
        # reading and parsing is blocking file I/O and CPU: off the event loop
        batch = await asyncio.to_thread(take)
        if not batch:
            break
        summary.versions += len(batch)
        if options.dry_run:
            continue
        assert session is not None
        counts = await upsert_versions(session, batch)
        summary.inserted += counts["inserted"]
        summary.unchanged += counts["unchanged"]
    return summary


def reader(handle) -> Iterator[list[str]]:
    return csv.reader(handle)
