"""Higher timeframes from closed M1 bars.

Buckets follow the trading day, which runs 17:00-17:00 New York and is named after the day it
ends. 5m, 15m and 1h are the usual clock buckets; 4h bars open at 17:00, 21:00, 01:00, 05:00,
09:00 and 13:00 New York all year; D1 is the trading day. A bucket is emitted only once it has
closed: its ``close_utc`` must be at or before ``as_of``, the time up to which the input is known
(by default the close of the last input bar). Appending later bars never changes an emitted bucket.

Spread is kept as the minimum, mean and maximum of the input bars' spreads (price units): MT5
records the lowest spread inside each bar, and which statistic the cost model uses is decided in
the research protocol, not here."""

from __future__ import annotations

import pandas as pd

MARKET_TZ = "America/New_York"
# New York time shifted by 7 h puts every trading day boundary (17:00 New York) at midnight.
TRADING_DAY_SHIFT = pd.Timedelta(hours=7)

INTRADAY = {
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
}
TIMEFRAMES = [*INTRADAY, "D1"]

AGG_COLUMNS = [
    "ts_utc",
    "close_utc",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread_min",
    "spread_mean",
    "spread_max",
    "n_bars",
]


def _shifted(ts_utc: pd.Series) -> pd.Series:
    return ts_utc.dt.tz_convert(MARKET_TZ).dt.tz_localize(None) + TRADING_DAY_SHIFT


def trading_day(ts_utc: pd.Series) -> pd.Series:
    """The trading day (17:00-17:00 New York) of each bar, named after the day it ends."""
    return _shifted(ts_utc).dt.normalize()


def _day_bound(day: pd.Series) -> pd.Series:
    """UTC time of 17:00 New York on the evening before ``day`` (the start of that trading day)."""
    return (day - TRADING_DAY_SHIFT).dt.tz_localize(MARKET_TZ).dt.tz_convert("UTC")


def buckets(ts_utc: pd.Series, timeframe: str) -> tuple[pd.Series, pd.Series]:
    """Open and close time (UTC) of the ``timeframe`` bucket that contains each bar."""
    if timeframe == "D1":
        day = trading_day(ts_utc)
        return _day_bound(day), _day_bound(day + pd.Timedelta(days=1))
    freq = INTRADAY[timeframe]
    shifted = _shifted(ts_utc)
    start = ts_utc - (shifted - shifted.dt.floor(freq))
    return start, start + freq


def aggregate(
    bars: pd.DataFrame,
    timeframe: str,
    bar_length: pd.Timedelta,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """``timeframe`` bars from ``bars`` (``ts_utc`` open times, each ``bar_length`` long)."""
    if bars.empty:
        return pd.DataFrame({c: [] for c in AGG_COLUMNS})
    if as_of is None:
        as_of = bars["ts_utc"].iloc[-1] + bar_length
    bars = bars[bars["ts_utc"] + bar_length <= as_of]
    start, end = buckets(bars["ts_utc"], timeframe)
    g = bars.assign(_start=start, _end=end).groupby("_start", sort=True)
    out = g.agg(
        close_utc=("_end", "first"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        spread_min=("spread", "min"),
        spread_mean=("spread", "mean"),
        spread_max=("spread", "max"),
        n_bars=("open", "size"),
    )
    out["tick_volume"] = g["tick_volume"].sum(min_count=1).astype("Int64")
    out = out.rename_axis("ts_utc").reset_index()
    out = out[out["close_utc"] <= as_of]
    out["n_bars"] = out["n_bars"].astype("int64")
    for col in ("ts_utc", "close_utc"):
        out[col] = out[col].dt.as_unit("ns")
    return out[AGG_COLUMNS].reset_index(drop=True)
