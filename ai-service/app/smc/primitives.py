"""SMC primitives on closed bars: ATR, confirmed swings and liquidity levels.

Bars are store frames (``ts_utc`` open, ``close_utc`` close, ``open``, ``high``, ``low``,
``close``), sorted by time. A value is *available* from the close of the bar that settles it,
never earlier: an ATR at bar ``j`` uses bars up to ``j``; a swing at bar ``i`` is known when bar
``i + k`` closes; a liquidity level can be used by a bar that opens at or after its
``available_utc``. Appending later bars never changes anything already available."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from app.data.aggregate import trading_day


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Wilder's average true range. ``out[j]`` uses bars up to ``j``; NaN for the first
    ``period - 1`` bars."""
    n = len(close)
    out = np.full(n, np.nan)
    if n < period:
        return out
    prev = np.r_[close[0], close[:-1]]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = high[0] - low[0]
    value = tr[:period].mean()
    out[period - 1] = value
    for j in range(period, n):
        value = (value * (period - 1) + tr[j]) / period
        out[j] = value
    return out


def swing_highs(high: np.ndarray, k: int) -> np.ndarray:
    """Bar ``i`` is a swing high when its high is strictly above the highs of the ``k`` bars on
    each side. Usable only once bar ``i + k`` has closed; the last ``k`` bars are never marked."""
    n = len(high)
    out = np.zeros(n, dtype=bool)
    if n < 2 * k + 1:
        return out
    mid = high[k : n - k]
    ok = np.ones(n - 2 * k, dtype=bool)
    for d in range(1, k + 1):
        ok &= (mid > high[k - d : n - k - d]) & (mid > high[k + d : n - k + d])
    out[k : n - k] = ok
    return out


def swing_lows(low: np.ndarray, k: int) -> np.ndarray:
    """Mirror of ``swing_highs``."""
    return swing_highs(-low, k)


@dataclass(frozen=True)
class Level:
    """A liquidity level. ``side`` is ``"high"`` (buy-side liquidity, resting above price) or
    ``"low"`` (sell-side, below). Usable by bars opening at or after ``available_utc``."""

    price: float
    side: str
    source: str  # "1h", "4h" (confirmed swings) or "pd" (previous trading day high / low)
    origin_utc: pd.Timestamp  # open of the bar that made the extreme
    available_utc: pd.Timestamp
    day: date  # trading day of the extreme, for the age limit

    @property
    def key(self) -> str:
        return f"{self.source}:{self.side}:{self.origin_utc.isoformat()}:{self.price!r}"


def _days(ts: pd.Series) -> list[date]:
    return [d.date() for d in trading_day(ts)]


def swing_levels(frame: pd.DataFrame, k: int, source: str) -> list[Level]:
    """Confirmed swing highs and lows of a context frame as levels, available when bar ``i + k``
    closes."""
    high, low = frame["high"].to_numpy(float), frame["low"].to_numpy(float)
    days = _days(frame["ts_utc"])
    out = []
    for side, mask, price in (
        ("high", swing_highs(high, k), high),
        ("low", swing_lows(low, k), low),
    ):
        for i in np.flatnonzero(mask):
            out.append(
                Level(
                    float(price[i]),
                    side,
                    source,
                    frame["ts_utc"].iloc[i],
                    frame["close_utc"].iloc[i + k],
                    days[i],
                )
            )
    return sorted(out, key=lambda lv: (lv.available_utc, lv.key))


def previous_day_levels(d1: pd.DataFrame) -> list[Level]:
    """Each trading day's high and low, available once the day (its D1 bar) has closed."""
    days = _days(d1["ts_utc"])
    out = []
    for i in range(len(d1)):
        for side, col in (("high", "high"), ("low", "low")):
            out.append(
                Level(
                    float(d1[col].iloc[i]),
                    side,
                    "pd",
                    d1["ts_utc"].iloc[i],
                    d1["close_utc"].iloc[i],
                    days[i],
                )
            )
    return sorted(out, key=lambda lv: (lv.available_utc, lv.key))


class LevelBook:
    """The active liquidity levels as the entry bars go by.

    ``step(j)`` must be called for every entry bar in order. It first adds the levels available
    by the bar's open, drops those older than ``max_age_days`` trading days, then removes and
    returns the levels the bar traded through (its low below a ``low`` level, its high above a
    ``high`` level): a level is spent the first time price trades beyond it, whether that turns
    out to be a sweep or a breakout."""

    def __init__(self, entry: pd.DataFrame, levels: list[Level], max_age_days: int):
        self.open_utc = entry["ts_utc"].to_numpy()
        self.high = entry["high"].to_numpy(float)
        self.low = entry["low"].to_numpy(float)
        self.days = _days(entry["ts_utc"])
        self.pending = sorted(levels, key=lambda lv: (lv.available_utc, lv.key))
        self.next = 0
        self.max_age = max_age_days
        self.active: dict[str, list[Level]] = {"high": [], "low": []}

    def _fresh(self, lv: Level, today: date) -> bool:
        return int(np.busday_count(lv.day, today)) <= self.max_age

    def step(self, j: int) -> dict[str, list[Level]]:
        t = pd.Timestamp(self.open_utc[j])
        while self.next < len(self.pending) and self.pending[self.next].available_utc <= t:
            lv = self.pending[self.next]
            self.active[lv.side].append(lv)
            self.next += 1
        today = self.days[j]
        traded = {"high": [], "low": []}
        for side, beyond in (
            ("high", lambda p: self.high[j] > p),
            ("low", lambda p: self.low[j] < p),
        ):
            keep = []
            for lv in self.active[side]:
                if not self._fresh(lv, today):
                    continue
                (traded[side] if beyond(lv.price) else keep).append(lv)
            self.active[side] = keep
        return traded
