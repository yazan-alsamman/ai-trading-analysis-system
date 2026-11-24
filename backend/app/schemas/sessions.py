"""The trading-session calendar stored on an instrument (``instruments.session_calendar``).

All times are wall-clock times in ``tz`` (an IANA zone such as ``America/New_York``), so DST is
handled by the zone, never by a fixed offset. See docs/instruments.md for the format.
"""

import datetime as dt
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Day = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _hhmm(value: str) -> str:
    try:
        parsed = dt.time.fromisoformat(value)
    except ValueError:
        raise ValueError("time must be HH:MM (00:00-23:59)") from None
    if len(value) != 5 or parsed.second or parsed.microsecond:
        raise ValueError("time must be HH:MM (00:00-23:59)")
    return value


HHMM = Annotated[str, AfterValidator(_hhmm)]


def _zone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"unknown time zone {value!r} (use an IANA name)") from None
    return value


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WeekPoint(_M):
    day: Day
    time: HHMM


class DailyBreak(_M):
    """Closed every day from ``start`` to ``end`` (``end`` < ``start`` crosses midnight)."""

    start: HHMM
    end: HHMM

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if self.start == self.end:
            raise ValueError("a daily break needs start != end")
        return self


class Holiday(_M):
    """Closed for the whole local ``date``, or from ``start`` to ``end`` (local date-times
    without an offset, e.g. ``2026-12-24T16:55``)."""

    name: str | None = Field(default=None, max_length=64)
    date: dt.date | None = None
    start: dt.datetime | None = None
    end: dt.datetime | None = None

    @model_validator(mode="after")
    def _one_form(self) -> Self:
        if self.date is not None:
            if self.start is not None or self.end is not None:
                raise ValueError("give either date or start/end, not both")
            return self
        if self.start is None or self.end is None:
            raise ValueError("a holiday needs date, or both start and end")
        if self.start.tzinfo is not None or self.end.tzinfo is not None:
            raise ValueError("holiday start/end are local times in tz, without an offset")
        if self.end <= self.start:
            raise ValueError("holiday end must be after start")
        return self


class SessionCalendar(_M):
    """When the market is open. Without ``week_open``/``week_close`` it trades all week."""

    tz: Annotated[str, AfterValidator(_zone)]
    week_open: WeekPoint | None = None
    week_close: WeekPoint | None = None
    daily_breaks: list[DailyBreak] = Field(default_factory=list, max_length=8)
    holidays: list[Holiday] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def _week(self) -> Self:
        if (self.week_open is None) != (self.week_close is None):
            raise ValueError("give both week_open and week_close, or neither")
        if self.week_open is not None and self.week_open == self.week_close:
            raise ValueError("week_open and week_close must differ")
        return self
