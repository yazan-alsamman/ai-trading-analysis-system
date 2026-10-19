"""Broker server time, UTC conversion and the trading-session calendar.

FxPro's MT5 server clock follows EU daylight-saving rules: UTC+2 in winter and UTC+3 from the last
Sunday of March to the last Sunday of October (the zone ``Europe/Athens``). The market itself runs
on New York time (week open Sunday 18:00, daily break 17:00-18:00), so for most of the year server
time equals New York time + 7 h. In the few weeks when US and EU daylight saving disagree (from the
second Sunday of March to the last Sunday of March, and from the last Sunday of October to the first
Sunday of November) the two differ by an hour; the export shows the daily break and the weekly open
shifting by one hour in server time in those weeks, and NFP (08:30 New York) bars sit at 14:30
server time, i.e. UTC+2. See the data-quality report for the evidence."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.schema import BASE_TIMEFRAME, SessionSpec

SERVER_TZ = "Europe/Athens"
MARKET_TZ = "America/New_York"
# Shifting New York time by this offset makes every trading day start at midnight (17:00 NY ->
# 00:00).
TRADING_DAY_SHIFT = pd.Timedelta(hours=7)


def server_to_utc(server_ts: pd.Series, server_tz: str = SERVER_TZ) -> pd.Series:
    """Convert naive broker server timestamps to UTC.

    Times that do not exist or are ambiguous on the server clock (the hour skipped or repeated at a
    DST change, always on a Sunday morning when the market is closed) come back as NaT so the caller
    can reject them as malformed."""
    local = server_ts.dt.tz_localize(server_tz, ambiguous="NaT", nonexistent="NaT")
    return local.dt.tz_convert("UTC")


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_open(ts_utc: pd.Series | pd.DatetimeIndex, session: SessionSpec) -> np.ndarray:
    """True where a bar opening at ``ts_utc`` lies inside expected trading hours."""
    idx = pd.DatetimeIndex(ts_utc).tz_convert(MARKET_TZ)
    dow = idx.dayofweek.to_numpy()  # Monday = 0
    mins = (idx.hour * 60 + idx.minute).to_numpy()
    week_open, week_close = _minutes(session.week_open), _minutes(session.week_close)
    closed = (dow == 5) | ((dow == 4) & (mins >= week_close)) | ((dow == 6) & (mins < week_open))
    if session.daily_break is not None:
        b0, b1 = (_minutes(t) for t in session.daily_break)
        closed |= (mins >= b0) & (mins < b1)
    return ~closed


def open_slots(start: pd.Timestamp, end: pd.Timestamp, session: SessionSpec) -> pd.DatetimeIndex:
    """Every 5-minute bar open time in [start, end] (UTC) that lies inside trading hours."""
    grid = pd.date_range(start.floor(BASE_TIMEFRAME), end, freq=BASE_TIMEFRAME, tz="UTC")
    return grid[is_open(grid, session)]


def trading_day(ts_utc: pd.Series) -> pd.Series:
    """The trading day of each bar: days run 17:00-17:00 New York and are named after the day they
    end."""
    ny = ts_utc.dt.tz_convert(MARKET_TZ).dt.tz_localize(None)
    return (ny + TRADING_DAY_SHIFT).dt.normalize()


def dst_mismatch(ts_utc: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    """True where server time is not New York time + 7 h (the US/EU DST mismatch weeks)."""
    idx = pd.DatetimeIndex(ts_utc)
    server = idx.tz_convert(SERVER_TZ).tz_localize(None)
    ny = idx.tz_convert(MARKET_TZ).tz_localize(None)
    return np.asarray((server - ny) != TRADING_DAY_SHIFT)


def market_holidays(years: range) -> set[pd.Timestamp]:
    """Dates (New York) on which thin or missing gold/FX trading is expected: US market holidays and
    the Christmas / New Year eves."""
    from pandas.tseries.holiday import (
        GoodFriday,
        USLaborDay,
        USMartinLutherKingJr,
        USMemorialDay,
        USPresidentsDay,
        USThanksgivingDay,
    )

    start, end = f"{years.start}-01-01", f"{years.stop - 1}-12-31"
    days: set[pd.Timestamp] = set()
    for rule in (
        GoodFriday,
        USLaborDay,
        USMartinLutherKingJr,
        USMemorialDay,
        USPresidentsDay,
        USThanksgivingDay,
    ):
        days.update(pd.Timestamp(d) for d in rule.dates(start, end))
    days.update(pd.Timestamp(d) + pd.Timedelta(days=1) for d in USThanksgivingDay.dates(start, end))
    for y in years:
        for m, d in ((1, 1), (1, 2), (6, 19), (7, 3), (7, 4), (7, 5), (12, 24), (12, 25), (12, 26)):
            days.add(pd.Timestamp(y, m, d))
        days.add(pd.Timestamp(y, 12, 31))
    return days
