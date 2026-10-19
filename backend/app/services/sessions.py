"""Trading sessions: is a market open at an instant, when does it open next, and which bars
should exist in a range (so a data-quality check can tell real gaps from weekends and breaks).

Pure functions over a :class:`~app.schemas.sessions.SessionCalendar` (or its JSON). Every rule
is evaluated in the calendar's wall-clock time via ``zoneinfo``; there is no fixed offset, so
DST transitions move the UTC times by themselves.
"""

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.models.candle import Timeframe
from app.schemas.sessions import DAYS, DailyBreak, SessionCalendar

_WEEK = 7 * 24 * 3600
_DAY = 24 * 3600
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# Safety net for next_open: each step jumps to the end of one closure, so a real calendar needs
# only a few steps; a calendar that never opens stops here.
MAX_JUMPS = 1000


def calendar_of(calendar: SessionCalendar | Mapping[str, Any]) -> SessionCalendar:
    if isinstance(calendar, SessionCalendar):
        return calendar
    return SessionCalendar.model_validate(calendar)


def _seconds(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 3600 + int(minutes) * 60


def _week_seconds(day: str, hhmm: str) -> int:
    """Seconds since Monday 00:00 local."""
    return DAYS.index(day) * _DAY + _seconds(hhmm)


def _local(calendar: SessionCalendar, ts_utc: datetime) -> datetime:
    if ts_utc.tzinfo is None:
        raise ValueError("ts_utc must be timezone-aware")
    return ts_utc.astimezone(ZoneInfo(calendar.tz))


def _to_utc(calendar: SessionCalendar, local_naive: datetime) -> datetime:
    return local_naive.replace(tzinfo=ZoneInfo(calendar.tz)).astimezone(UTC)


def _in_break(brk: DailyBreak, second_of_day: int) -> bool:
    start, end = _seconds(brk.start), _seconds(brk.end)
    if start < end:
        return start <= second_of_day < end
    return second_of_day >= start or second_of_day < end  # crosses midnight


def _closure_end(calendar: SessionCalendar, local: datetime) -> datetime | None:
    """The local (naive) wall time at which the closure containing ``local`` ends, or None if
    the market is open. When several closures overlap, the first one found is returned; the
    caller checks again from there."""
    naive = local.replace(tzinfo=None)
    for holiday in calendar.holidays:
        if holiday.date is not None:
            if naive.date() == holiday.date:
                return datetime.combine(holiday.date, datetime.min.time()) + timedelta(days=1)
        elif holiday.start <= naive < holiday.end:
            return holiday.end

    if calendar.week_open is not None:
        pos = naive.weekday() * _DAY + naive.hour * 3600 + naive.minute * 60 + naive.second
        opens = _week_seconds(calendar.week_open.day, calendar.week_open.time)
        closes = _week_seconds(calendar.week_close.day, calendar.week_close.time)
        if opens < closes:
            is_open = opens <= pos < closes
        else:  # the trading week wraps over Monday 00:00 (e.g. Sunday open, Friday close)
            is_open = pos >= opens or pos < closes
        if not is_open:
            wait = (opens - pos) % _WEEK
            return naive.replace(microsecond=0) + timedelta(seconds=wait)

    second_of_day = naive.hour * 3600 + naive.minute * 60 + naive.second
    for brk in calendar.daily_breaks:
        if _in_break(brk, second_of_day):
            wait = (_seconds(brk.end) - second_of_day) % _DAY
            return naive.replace(microsecond=0) + timedelta(seconds=wait)
    return None


def is_open(calendar: SessionCalendar | Mapping[str, Any], ts_utc: datetime) -> bool:
    """Whether the market trades at ``ts_utc`` (open times are inclusive, close times
    exclusive: with a 16:55 close, 16:54:59 is open and 16:55 is closed)."""
    cal = calendar_of(calendar)
    return _closure_end(cal, _local(cal, ts_utc)) is None


def next_open(calendar: SessionCalendar | Mapping[str, Any], ts_utc: datetime) -> datetime:
    """``ts_utc`` itself if the market is open then, otherwise the UTC instant it next opens."""
    cal = calendar_of(calendar)
    current = ts_utc.astimezone(UTC)
    for _ in range(MAX_JUMPS):
        end = _closure_end(cal, _local(cal, current))
        if end is None:
            return current
        following = _to_utc(cal, end)
        if following <= current:  # a wall time that does not exist (DST gap): step past it
            following = current + timedelta(minutes=1)
        current = following
    raise ValueError("the session calendar never opens")


def _floor_bucket(value: datetime, interval: timedelta) -> datetime:
    return value - (value - _EPOCH) % interval


def _ceil_bucket(value: datetime, interval: timedelta) -> datetime:
    floor = _floor_bucket(value, interval)
    return floor if floor == value else floor + interval


def expected_bar_starts(
    calendar: SessionCalendar | Mapping[str, Any],
    start_utc: datetime,
    end_utc: datetime,
    timeframe: Timeframe | str = "1m",
) -> Iterator[datetime]:
    """UTC starts of the bars that should exist in ``[start_utc, end_utc)``.

    Buckets are aligned to the epoch like ``time_bucket`` (so 1d bars start at 00:00 UTC). A
    bar should exist when the market is open at any moment inside it; for 1m that means open at
    the bar's start minute. Closed stretches are skipped in one jump, not minute by minute.
    """
    cal = calendar_of(calendar)
    interval = Timeframe(timeframe).interval
    current = _ceil_bucket(start_utc.astimezone(UTC), interval)
    end_utc = end_utc.astimezone(UTC)
    while current < end_utc:
        bucket_end = current + interval
        opening = next_open(cal, current)
        if opening < bucket_end:
            yield current
            current = bucket_end
        else:  # closed for the whole bucket: go to the bucket in which it reopens
            current = _floor_bucket(opening, interval)
