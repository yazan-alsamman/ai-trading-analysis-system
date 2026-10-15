"""Volatility indicators: Bollinger Bands, ATR, Keltner Channels, Donchian Channels."""

from __future__ import annotations

import pandas as pd

from trading_indicators import core


def bollinger(close: pd.Series, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands: ``middle = SMA(close, length)``, ``upper/lower = middle +/- std * sigma``
    with the *population* standard deviation (ddof = 0, like TA-Lib and TradingView).
    Valid from bar ``length - 1``."""
    core.check_series(close, "close")
    length = core.check_int("length", length)
    std = core.check_float("std", std)
    x = core.values(close)
    middle = core.rolling_mean(x, length)
    sigma = pd.Series(x).rolling(length, min_periods=length).std(ddof=0).to_numpy(copy=True)
    return pd.DataFrame(
        {"upper": middle + std * sigma, "middle": middle, "lower": middle - std * sigma},
        index=close.index,
    )


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range: Wilder's RMA of the true range, seeded with the mean of the first
    ``length`` true ranges (TA-Lib convention). The first bar has no true range, so ATR is valid
    from bar ``length``."""
    core.check_frame(df, ("high", "low", "close"))
    length = core.check_int("length", length)
    high, low, close = (core.values(df[c]) for c in ("high", "low", "close"))
    return core.to_series(core.rma(core.true_range(high, low, close), length), df.index, "atr")


def keltner(
    df: pd.DataFrame, length: int = 20, multiplier: float = 2.0, atr_length: int = 10
) -> pd.DataFrame:
    """Keltner Channels (TradingView convention): ``middle = EMA(close, length)``,
    ``upper/lower = middle +/- multiplier * ATR(atr_length)``.
    Valid from bar ``max(length - 1, atr_length)``."""
    core.check_frame(df, ("high", "low", "close"))
    length = core.check_int("length", length)
    multiplier = core.check_float("multiplier", multiplier)
    atr_length = core.check_int("atr_length", atr_length)
    high, low, close = (core.values(df[c]) for c in ("high", "low", "close"))
    middle = core.ema(close, length)
    band = multiplier * core.rma(core.true_range(high, low, close), atr_length)
    return pd.DataFrame(
        {"upper": middle + band, "middle": middle, "lower": middle - band}, index=df.index
    )


def donchian(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """Donchian Channels: ``upper = highest(high, length)``, ``lower = lowest(low, length)``,
    ``middle = (upper + lower) / 2``. The current bar is included. Valid from ``length - 1``."""
    core.check_frame(df, ("high", "low"))
    length = core.check_int("length", length)
    upper = core.rolling_max(core.values(df["high"]), length)
    lower = core.rolling_min(core.values(df["low"]), length)
    return pd.DataFrame(
        {"upper": upper, "middle": (upper + lower) / 2.0, "lower": lower}, index=df.index
    )
