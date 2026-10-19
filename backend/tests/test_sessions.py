"""Session calendar (app.services.sessions): the FxPro XAU/USD calendar in New York time, checked
against concrete UTC times in winter (EST, UTC-5), summer (EDT, UTC-4) and on both 2026 DST
transition weekends (US: Sunday 8 March and Sunday 1 November)."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.sessions import SessionCalendar
from app.services import sessions

FXPRO = {
    "tz": "America/New_York",
    "week_open": {"day": "sun", "time": "18:00"},
    "week_close": {"day": "fri", "time": "16:55"},
    "daily_breaks": [{"start": "16:55", "end": "18:00"}],
    "holidays": [],
}
# Sunday 18:00 -> Friday 16:55 is 4 days 22:55 = 7,135 minutes, less four 65-minute breaks
# (Monday to Thursday; Friday's 16:55 is the weekly close).
BARS_PER_WEEK = 7135 - 4 * 65


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def cal(**changes) -> SessionCalendar:
    return SessionCalendar.model_validate({**FXPRO, **changes})


# --- is_open / next_open -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ts", "expected"),
    [
        # winter (EST): the week opens Sunday 23:00 UTC
        ("2026-01-11 22:59", False),
        ("2026-01-11 23:00", True),
        # winter daily break 16:55-18:00 EST = 21:55-23:00 UTC
        ("2026-01-13 21:54", True),
        ("2026-01-13 21:55", False),
        ("2026-01-13 22:59", False),
        ("2026-01-13 23:00", True),
        # winter Friday close 16:55 EST = 21:55 UTC, closed on Saturday
        ("2026-01-16 21:54", True),
        ("2026-01-16 21:55", False),
        ("2026-01-17 12:00", False),
        # summer (EDT): the week opens Sunday 22:00 UTC
        ("2026-07-12 21:59", False),
        ("2026-07-12 22:00", True),
        # summer daily break 16:55-18:00 EDT = 20:55-22:00 UTC
        ("2026-07-14 20:54", True),
        ("2026-07-14 20:55", False),
        ("2026-07-14 21:59", False),
        ("2026-07-14 22:00", True),
        # summer Friday close 16:55 EDT = 20:55 UTC
        ("2026-07-17 20:54", True),
        ("2026-07-17 20:55", False),
    ],
)
def test_is_open(ts: str, expected: bool) -> None:
    assert sessions.is_open(FXPRO, utc(ts)) is expected


def test_march_transition_weekend() -> None:
    """Friday 6 March still closes on EST, Sunday 8 March (DST began at 02:00) opens on EDT."""
    assert sessions.is_open(FXPRO, utc("2026-03-06 21:54"))
    assert not sessions.is_open(FXPRO, utc("2026-03-06 21:55"))  # 16:55 EST
    assert sessions.next_open(FXPRO, utc("2026-03-06 21:55")) == utc("2026-03-08 22:00")
    assert not sessions.is_open(FXPRO, utc("2026-03-08 21:59"))
    assert sessions.is_open(FXPRO, utc("2026-03-08 22:00"))  # 18:00 EDT, not 23:00 UTC
    # the first break after the change is already on EDT
    assert not sessions.is_open(FXPRO, utc("2026-03-09 20:55"))
    assert sessions.next_open(FXPRO, utc("2026-03-09 20:55")) == utc("2026-03-09 22:00")


def test_november_transition_weekend() -> None:
    """Friday 30 October closes on EDT, Sunday 1 November (DST ended at 02:00) opens on EST."""
    assert not sessions.is_open(FXPRO, utc("2026-10-30 20:55"))  # 16:55 EDT
    assert sessions.next_open(FXPRO, utc("2026-10-30 20:55")) == utc("2026-11-01 23:00")
    assert not sessions.is_open(FXPRO, utc("2026-11-01 22:00"))  # 17:00 EST
    assert sessions.is_open(FXPRO, utc("2026-11-01 23:00"))  # 18:00 EST
    assert not sessions.is_open(FXPRO, utc("2026-11-02 21:55"))
    assert sessions.next_open(FXPRO, utc("2026-11-02 21:55")) == utc("2026-11-02 23:00")


def test_next_open() -> None:
    open_ts = utc("2026-01-13 10:00")
    assert sessions.next_open(FXPRO, open_ts) == open_ts  # already open
    assert sessions.next_open(FXPRO, utc("2026-01-13 22:10")) == utc("2026-01-13 23:00")
    # Friday after the close and all of Saturday -> Sunday 18:00 EST
    assert sessions.next_open(FXPRO, utc("2026-01-16 21:55")) == utc("2026-01-18 23:00")
    assert sessions.next_open(FXPRO, utc("2026-01-17 03:00")) == utc("2026-01-18 23:00")
    # Sunday during the day (the daily break rule alone would say 18:00 too)
    assert sessions.next_open(FXPRO, utc("2026-07-12 15:00")) == utc("2026-07-12 22:00")


def test_holidays() -> None:
    calendar = cal(
        holidays=[
            {"name": "Thanksgiving", "date": "2026-11-26"},
            {"name": "Early close", "start": "2026-12-24T13:00", "end": "2026-12-24T18:00"},
        ]
    )
    # a whole local day: Thursday 26 November 00:00-24:00 EST = 05:00 UTC to 05:00 UTC
    assert sessions.is_open(calendar, utc("2026-11-26 04:59"))
    assert not sessions.is_open(calendar, utc("2026-11-26 05:00"))
    assert not sessions.is_open(calendar, utc("2026-11-26 15:00"))
    assert sessions.next_open(calendar, utc("2026-11-26 15:00")) == utc("2026-11-27 05:00")
    assert sessions.is_open(FXPRO, utc("2026-11-26 15:00"))  # the plain calendar is open
    # a local window: 13:00-18:00 EST on 24 December, overlapping the daily break
    assert sessions.is_open(calendar, utc("2026-12-24 17:59"))
    assert not sessions.is_open(calendar, utc("2026-12-24 18:00"))
    assert sessions.next_open(calendar, utc("2026-12-24 18:00")) == utc("2026-12-24 23:00")
    bars = list(
        sessions.expected_bar_starts(calendar, utc("2026-11-26 00:00"), utc("2026-11-27 06:00"))
    )
    assert bars[-1] == utc("2026-11-27 05:59")
    assert utc("2026-11-26 04:59") in bars and utc("2026-11-26 05:00") not in bars
    assert len(bars) == 5 * 60 + 60  # 00:00-04:59 and 05:00-05:59 on the 27th


def test_all_week_calendar() -> None:
    crypto = {"tz": "UTC"}
    assert sessions.is_open(crypto, utc("2026-01-17 12:00"))
    assert len(
        list(sessions.expected_bar_starts(crypto, utc("2026-01-17"), utc("2026-01-18")))
    ) == (1440)


# --- expected_bar_starts -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("week_start", "first", "last"),
    [
        ("2026-01-11", "2026-01-11 23:00", "2026-01-16 21:54"),  # winter
        ("2026-07-12", "2026-07-12 22:00", "2026-07-17 20:54"),  # summer
        ("2026-03-08", "2026-03-08 22:00", "2026-03-13 20:54"),  # DST began that Sunday
        ("2026-11-01", "2026-11-01 23:00", "2026-11-06 21:54"),  # DST ended that Sunday
    ],
)
def test_one_minute_bars_of_a_week(week_start: str, first: str, last: str) -> None:
    start = utc(week_start)
    bars = list(sessions.expected_bar_starts(FXPRO, start, start + timedelta(days=7)))
    assert bars[0] == utc(first)
    assert bars[-1] == utc(last)
    assert len(bars) == BARS_PER_WEEK
    assert all(b.second == 0 and b.tzinfo is not None for b in bars)
    assert bars == sorted(set(bars))


def test_week_spanning_the_march_change() -> None:
    """Monday 2 to Sunday 8 March: opens on EST and closes on EST; the next week opens on EDT."""
    bars = list(sessions.expected_bar_starts(FXPRO, utc("2026-03-02"), utc("2026-03-09")))
    assert bars[0] == utc("2026-03-02 00:00")
    assert utc("2026-03-06 21:54") in bars and utc("2026-03-06 21:55") not in bars
    assert utc("2026-03-08 21:59") not in bars and utc("2026-03-08 22:00") in bars


def test_daily_break_bars() -> None:
    bars = list(
        sessions.expected_bar_starts(FXPRO, utc("2026-07-14 20:50"), utc("2026-07-14 22:05"))
    )
    assert bars == [utc(f"2026-07-14 20:{m}") for m in range(50, 55)] + [
        utc(f"2026-07-14 22:0{m}") for m in range(5)
    ]


def test_higher_timeframes() -> None:
    hourly = list(
        sessions.expected_bar_starts(FXPRO, utc("2026-01-13 19:00"), utc("2026-01-14 01:00"), "1h")
    )
    # 21:00-21:54 is open, 22:00-22:59 is all break, 23:00 reopens
    assert hourly == [utc(f"2026-01-13 {h}:00") for h in (19, 20, 21, 23)] + [
        utc("2026-01-14 00:00")
    ]
    daily = list(sessions.expected_bar_starts(FXPRO, utc("2026-01-10"), utc("2026-01-18"), "1d"))
    # Saturday 10 closed, Sunday 11 opens at 23:00 UTC, Friday 16 closes at 21:55
    assert daily == [utc(f"2026-01-{d}") for d in range(11, 17)]
    # an unaligned start is rounded up to the next bucket
    five = list(
        sessions.expected_bar_starts(FXPRO, utc("2026-01-13 10:02"), utc("2026-01-13 10:20"), "5m")
    )
    assert five == [utc("2026-01-13 10:05"), utc("2026-01-13 10:10"), utc("2026-01-13 10:15")]


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        sessions.is_open(FXPRO, datetime(2026, 1, 13, 10, 0))


# --- validation ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"tz": "Mars/Olympus"},
        {"tz": "UTC+2"},
        {"week_open": {"day": "sunday", "time": "18:00"}},
        {"week_open": {"day": "sun", "time": "18:00:00"}},
        {"week_open": {"day": "sun", "time": "24:00"}},
        {"week_open": None},
        {"week_close": {"day": "sun", "time": "18:00"}},
        {"daily_breaks": [{"start": "16:55", "end": "16:55"}]},
        {"holidays": [{"date": "2026-12-25", "start": "2026-12-25T00:00"}]},
        {"holidays": [{"start": "2026-12-25T10:00"}]},
        {"holidays": [{"start": "2026-12-25T10:00", "end": "2026-12-25T09:00"}]},
        {"holidays": [{"start": "2026-12-25T10:00+00:00", "end": "2026-12-25T11:00+00:00"}]},
        {"extra": 1},
    ],
)
def test_invalid_calendars(changes: dict) -> None:
    with pytest.raises(ValidationError):
        cal(**changes)


def test_fxpro_calendar_round_trips() -> None:
    assert cal().model_dump(mode="json", exclude_none=True) == FXPRO
