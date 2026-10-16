"""Volume indicators: OBV, VWAP (anchored to each UTC day), volume SMA."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_indicators import core


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume: starts at the first bar's volume (TA-Lib convention), then adds the
    volume when the close rises, subtracts it when it falls, and keeps it when unchanged.

    OBV is cumulative, so its level depends on where the input starts; only its shape matters.
    A bar with a missing close or volume is NaN and contributes nothing.
    """
    core.check_frame(df, ("close", "volume"))
    close, volume = core.values(df["close"]), core.values(df["volume"])
    missing = np.isnan(close) | np.isnan(volume)
    out = np.full(len(close), np.nan)
    if missing.all():
        return core.to_series(out, df.index, "obv")
    # compare with the last *valid* close, so a gap does not swallow the next bar's volume
    last_valid = pd.Series(np.where(missing, np.nan, close)).ffill().to_numpy()
    direction = np.sign(close - core.shift1(last_valid))
    signed = np.where(np.isnan(direction) | missing, 0.0, direction * volume)
    first = int(np.argmax(~missing))
    signed[first] = volume[first]  # OBV starts at the first valid bar's volume
    out = np.cumsum(signed)
    out[:first] = np.nan
    out[missing] = np.nan
    return core.to_series(out, df.index, "obv")
    change = np.nan_to_num(core.diff1(close), nan=0.0)
    change[1:][np.isnan(core.diff1(close)[1:])] = np.nan
    signed = np.sign(change) * volume
    missing = np.isnan(change) | np.isnan(volume)
    signed[missing] = 0.0
    signed[0] = 0.0 if np.isnan(volume[0]) else volume[0]
    out = np.cumsum(signed)
    out[missing | np.isnan(close)] = np.nan
    return core.to_series(out, df.index, "obv")


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume-Weighted Average Price anchored to each UTC calendar day.

    ``tp = (high + low + close) / 3`` and ``VWAP = cumsum(tp * volume) / cumsum(volume)``, both
    sums restarting at 00:00 UTC. While the day's cumulative volume is still 0 the VWAP is the
    typical price. Needs a ``DatetimeIndex`` (naive timestamps are taken as UTC).
    """
    core.check_frame(df, ("high", "low", "close", "volume"))
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("vwap needs a DatetimeIndex (UTC)")
    index = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
    day = index.floor("D").asi8
    tp = (core.values(df["high"]) + core.values(df["low"]) + core.values(df["close"])) / 3.0
    volume = core.values(df["volume"])
    missing = np.isnan(tp) | np.isnan(volume)
    flow = np.where(missing, 0.0, tp * np.where(missing, 0.0, volume))
    vol = np.where(missing, 0.0, volume)
    frame = pd.DataFrame({"day": day, "flow": flow, "vol": vol})
    cum = frame.groupby("day", sort=False)[["flow", "vol"]].cumsum()
    out = core.safe_div(cum["flow"].to_numpy(), cum["vol"].to_numpy(), np.nan)
    no_volume_yet = cum["vol"].to_numpy() == 0
    out[no_volume_yet] = tp[no_volume_yet]
    out[missing] = np.nan
    return core.to_series(out, df.index, "vwap")


def volume_sma(df: pd.DataFrame, length: int = 20) -> pd.Series:
    """Simple moving average of volume. Valid from bar ``length - 1``."""
    core.check_frame(df, ("volume",))
    length = core.check_int("length", length)
    out = core.rolling_mean(core.values(df["volume"]), length)
    return core.to_series(out, df.index, "volume_sma")
