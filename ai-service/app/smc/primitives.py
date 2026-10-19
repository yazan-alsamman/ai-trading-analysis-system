"""SMC primitives: ATR, confirmed swing pivots and liquidity levels.

Bars are frames with ``ts_utc`` (bar open time), ``open``, ``high``, ``low``, ``close`` and
``spread``, sorted by time, as written by ``app.data``. A value is *available* from the moment the
bar that confirms it has closed, never earlier."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.data.sessions import MARKET_TZ, trading_day


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Wilder's ATR. ``out[j]`` uses bars up to ``j`` only; NaN until ``period`` true ranges
    exist."""
    n = len(close)
    out = np.full(n, np.nan)
    if n == 0:
        return out
    prev_close = np.concatenate(([close[0]], close[:-1]))
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    tr[0] = high[0] - low[0]
    if n < period:
        return out
    value = tr[:period].mean()
    out[period - 1] = value
    for j in range(period, n):
        value = (value * (period - 1) + tr[j]) / period
        out[j] = value
    return out


def swing_lows(low: np.ndarray, k: int) -> np.ndarray:
    """Boolean mask: bar ``i`` is a swing low if its low is strictly below the lows of the ``k``
    bars on each side. Bars without ``k`` bars after them are never marked, and a swing low at
    ``i`` may only be used once bar ``i + k`` has closed."""
    n = len(low)
    mask = np.zeros(n, dtype=bool)
    if n < 2 * k + 1:
        return mask
    mask[k : n - k] = True
    for off in range(1, k + 1):
        mask[k : n - k] &= low[k : n - k] < low[k - off : n - k - off]
        mask[k : n - k] &= low[k : n - k] < low[k + off : n - k + off]
    return mask


def swing_highs(high: np.ndarray, k: int) -> np.ndarray:
    return swing_lows(-high, k)


@dataclass(frozen=True)
class Level:
    """A liquidity level: ``kind`` is ``"low"`` (sell-side liquidity under the price) or ``"high"``.
    It can be used by bars that open at or after ``available_at``."""

    price: float
    kind: str
    source: str  # "1h", "4h" or "pd" (previous trading day)
    origin_ts: pd.Timestamp
    available_at: pd.Timestamp
    origin_day: np.datetime64  # trading day of origin, for the age limit

    @property
    def key(self) -> str:
        return f"{self.source}:{self.kind}:{self.origin_ts.isoformat()}:{self.price:.5f}"


def htf_swing_levels(
    bars: pd.DataFrame, timeframe: pd.Timedelta, k: int, source: str
) -> list[Level]:
    """Confirmed swing highs and lows of a higher-timeframe frame as levels. A pivot at bar ``i``
    becomes available when bar ``i + k`` closes."""
    hi = bars["high"].to_numpy()
    lo = bars["low"].to_numpy()
    ts = bars["ts_utc"]
    days = trading_day(ts).to_numpy().astype("datetime64[D]")
    levels: list[Level] = []
    for kind, mask, prices in (
        ("high", swing_highs(hi, k), hi),
        ("low", swing_lows(lo, k), lo),
    ):
        for i in np.flatnonzero(mask):
            levels.append(
                Level(
                    price=float(prices[i]),
                    kind=kind,
                    source=source,
                    origin_ts=ts.iloc[i],
                    available_at=ts.iloc[i + k] + timeframe,
                    origin_day=days[i],
                )
            )
    return levels


def previous_day_levels(bars: pd.DataFrame, timeframe: pd.Timedelta) -> list[Level]:
    """The high and low of each trading day (17:00-17:00 New York), available once the day's last
    bar has closed."""
    day = trading_day(bars["ts_utc"])
    g = bars.assign(_day=day.to_numpy()).groupby("_day", sort=True)
    agg = g.agg(high=("high", "max"), low=("low", "min"), last=("ts_utc", "max"))
    levels: list[Level] = []
    for day_ts, row in agg.iterrows():
        origin = pd.Timestamp(day_ts).tz_localize("UTC")
        available = row["last"] + timeframe
        d = np.datetime64(pd.Timestamp(day_ts).date(), "D")
        levels.append(Level(float(row["high"]), "high", "pd", origin, available, d))
        levels.append(Level(float(row["low"]), "low", "pd", origin, available, d))
    return levels


# ICT-style session windows in New York time: [start, end) in minutes after midnight.
SESSIONS = {"asia": (20 * 60, 24 * 60), "london": (2 * 60, 5 * 60)}


def session_levels(bars: pd.DataFrame, timeframe: pd.Timedelta) -> list[Level]:
    """The high and low of each Asian (20:00-00:00 New York) and London (02:00-05:00 New York)
    session, available once the session has ended."""
    ny = bars["ts_utc"].dt.tz_convert(MARKET_TZ)
    mins = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
    date = ny.dt.tz_localize(None).dt.normalize().to_numpy()
    days = trading_day(bars["ts_utc"]).to_numpy().astype("datetime64[D]")
    levels: list[Level] = []
    for name, (start, end) in SESSIONS.items():
        mask = (mins >= start) & (mins < end)
        if not mask.any():
            continue
        sub = pd.DataFrame(
            {
                "date": date[mask],
                "high": bars["high"].to_numpy()[mask],
                "low": bars["low"].to_numpy()[mask],
                "day": days[mask],
                "first": bars["ts_utc"].to_numpy()[mask],
            }
        )
        g = sub.groupby("date", sort=True).agg(
            high=("high", "max"), low=("low", "min"), day=("day", "first"), first=("first", "min")
        )
        for d, row in g.iterrows():
            end_ts = (pd.Timestamp(d) + pd.Timedelta(minutes=end)).tz_localize(MARKET_TZ)
            available = end_ts.tz_convert("UTC")
            origin = pd.Timestamp(row["first"]).tz_convert("UTC")
            od = np.datetime64(row["day"], "D")
            levels.append(Level(float(row["high"]), "high", name, origin, available, od))
            levels.append(Level(float(row["low"]), "low", name, origin, available, od))
    return levels


def mirror(bars: pd.DataFrame) -> pd.DataFrame:
    """Negate prices so that a sell-side rule can be run as its buy-side mirror: highs become lows
    and the other way round. Spread is unchanged."""
    out = bars.copy()
    out["open"] = -bars["open"]
    out["close"] = -bars["close"]
    out["high"] = -bars["low"]
    out["low"] = -bars["high"]
    return out
