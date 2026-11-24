"""Session VWAP with volume-weighted standard-deviation bands (S6; PREREG section 5).

``libs/indicators`` ``vwap`` is anchored at 00:00 UTC and has no bands, so this is new code. A
session starts with the first bar opening at or after ``anchor`` New York and runs until the next
one (a bar opening before the anchor belongs to the previous day's session). With the typical
price ``tp = (high + low + close) / 3`` and the tick volume ``v`` of the bars of the session so
far (current bar included):

    vwap = sum(v * tp) / sum(v)
    sd   = sqrt(max(sum(v * tp^2) / sum(v) - vwap^2, 0))
    upper, lower = vwap +/- band_std * sd

While the session's volume is still 0 the VWAP is the typical price and the bands are on it. A
bar with missing volume counts as volume 0. The value at a bar uses that bar and earlier bars of
its session only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.sessions import MARKET_TZ, hhmm_minutes


def session_ids(ts_utc: pd.Series, anchor: str) -> np.ndarray:
    """The session of each bar: the New York date of (open time - anchor), as int days."""
    shifted = ts_utc.dt.tz_convert(MARKET_TZ).dt.tz_localize(None) - pd.Timedelta(
        minutes=hhmm_minutes(anchor)
    )
    return shifted.dt.normalize().to_numpy().astype("datetime64[D]").astype("int64")


def session_vwap(frame: pd.DataFrame, anchor: str, band_std: float) -> pd.DataFrame:
    h, lo, c = (frame[k].to_numpy(float) for k in ("high", "low", "close"))
    tp = (h + lo + c) / 3.0
    v = pd.to_numeric(frame["tick_volume"], errors="coerce").fillna(0).to_numpy(float)
    g = pd.DataFrame(
        {"s": session_ids(frame["ts_utc"], anchor), "v": v, "pv": v * tp, "pv2": v * tp * tp}
    )
    cum = g.groupby("s", sort=False)[["v", "pv", "pv2"]].cumsum()
    sv, spv, spv2 = (cum[k].to_numpy() for k in ("v", "pv", "pv2"))
    with np.errstate(invalid="ignore", divide="ignore"):
        vwap = np.where(sv > 0, spv / sv, tp)
        var = np.where(sv > 0, spv2 / sv - vwap * vwap, 0.0)
    sd = np.sqrt(np.maximum(var, 0.0))
    return pd.DataFrame(
        {
            "vwap": vwap,
            "upper": vwap + band_std * sd,
            "lower": vwap - band_std * sd,
            "session": g["s"].to_numpy(),
        },
        index=frame.index,
    )
