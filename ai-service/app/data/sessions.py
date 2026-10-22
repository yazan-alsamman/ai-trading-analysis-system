"""Trading hours from the instrument config, in New York wall-clock time."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import Instrument

MARKET_TZ = "America/New_York"


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_open(ts_utc: pd.DatetimeIndex | pd.Series, instrument: Instrument) -> np.ndarray:
    """True where a bar opening at ``ts_utc`` lies inside the configured trading hours."""
    ny = pd.DatetimeIndex(ts_utc).tz_convert(MARKET_TZ)
    dow = ny.dayofweek.to_numpy()  # Monday = 0
    mins = (ny.hour * 60 + ny.minute).to_numpy()
    week_open, week_close = _minutes(instrument.week_open), _minutes(instrument.week_close)
    closed = (dow == 5) | ((dow == 4) & (mins >= week_close)) | ((dow == 6) & (mins < week_open))
    if instrument.daily_break is not None:
        b0, b1 = (_minutes(t) for t in instrument.daily_break)
        closed |= (mins >= b0) & (mins < b1)
    return ~closed


def market_holidays(first_year: int, last_year: int) -> set[pd.Timestamp]:
    """New York dates with thin or no trading: US market holidays, the day after Thanksgiving,
    and the Christmas and New Year days."""
    from pandas.tseries.holiday import (
        GoodFriday,
        USLaborDay,
        USMartinLutherKingJr,
        USMemorialDay,
        USPresidentsDay,
        USThanksgivingDay,
    )

    start, end = f"{first_year}-01-01", f"{last_year}-12-31"
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
    for y in range(first_year, last_year + 1):
        for m, d in ((1, 1), (1, 2), (6, 19), (7, 3), (7, 4), (7, 5), (12, 24), (12, 25), (12, 26)):
            days.add(pd.Timestamp(y, m, d))
        days.add(pd.Timestamp(y, 12, 31))
    return days
