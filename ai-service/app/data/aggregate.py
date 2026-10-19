"""Build higher-timeframe bars from closed 5m bars.

Buckets are aligned to the trading day (17:00 New York), so 4h bars open at 17:00, 21:00, 01:00,
05:00, 09:00 and 13:00 New York time all year (the same as FxPro's chart outside the DST mismatch
weeks). 15m and 1h buckets are the usual clock buckets. A bucket is emitted only once it has closed:
its end must be at or before ``as_of``, the time up to which the input is known to be complete."""

from __future__ import annotations

import pandas as pd

from app.data.schema import BASE_TIMEFRAME, SessionSpec
from app.data.sessions import MARKET_TZ, TRADING_DAY_SHIFT, open_slots

TIMEFRAMES = {
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
}

AGG_COLUMNS = [
    "ts_utc",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "spread_max",
    "n_bars",
    "n_expected",
    "source",
]


def bucket_start(ts_utc: pd.Series, freq: pd.Timedelta) -> pd.Series:
    """Open time (UTC) of the ``freq`` bucket that contains each bar."""
    shifted = ts_utc.dt.tz_convert(MARKET_TZ).dt.tz_localize(None) + TRADING_DAY_SHIFT
    return ts_utc - (shifted - shifted.dt.floor(freq))


def _empty() -> pd.DataFrame:
    dtypes = {
        "ts_utc": "datetime64[ns, UTC]",
        "tick_volume": "Int64",
        "n_bars": "int64",
        "n_expected": "int64",
    }
    dtypes.update({c: "float64" for c in ("open", "high", "low", "close", "spread", "spread_max")})
    dtypes["source"] = str
    return pd.DataFrame({c: pd.Series([], dtype=dtypes[c]) for c in AGG_COLUMNS})


def aggregate(
    m5: pd.DataFrame,
    freq: pd.Timedelta,
    session: SessionSpec,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Aggregate closed 5m bars into ``freq`` bars, keeping only buckets that closed by ``as_of``.

    ``as_of`` defaults to the close of the last 5m bar. ``spread`` stays the in-bar minimum (the
    minimum of the 5m minimums); ``spread_max`` is the largest 5m minimum in the bucket. ``n_bars``
    counts the 5m bars present and ``n_expected`` the 5m slots inside trading hours, so partial
    buckets are visible."""
    if m5.empty:
        return _empty()
    if as_of is None:
        as_of = m5["ts_utc"].iloc[-1] + BASE_TIMEFRAME
    m5 = m5[m5["ts_utc"] + BASE_TIMEFRAME <= as_of]
    if m5.empty:
        return _empty()

    start = bucket_start(m5["ts_utc"], freq)
    g = m5.groupby(start.rename("ts_utc"), sort=True)
    out = g.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        spread=("spread", "min"),
        spread_max=("spread", "max"),
        n_bars=("open", "size"),
        source=("source", "first"),
    )
    out["tick_volume"] = g["tick_volume"].sum(min_count=1).astype("Int64")
    out = out.reset_index()
    out = out[out["ts_utc"] + freq <= as_of]
    if out.empty:
        return _empty()

    slots = pd.Series(open_slots(out["ts_utc"].iloc[0], out["ts_utc"].iloc[-1] + freq, session))
    expected = slots.groupby(bucket_start(slots, freq)).size()
    out["n_expected"] = out["ts_utc"].map(expected).fillna(0).astype("int64")
    out["n_bars"] = out["n_bars"].astype("int64")
    out["ts_utc"] = out["ts_utc"].dt.as_unit("ns")
    return out[AGG_COLUMNS].reset_index(drop=True)
