"""Trend indicators: SMA, EMA, WMA, MACD, ADX/DMI, Supertrend, Ichimoku."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_indicators import core


def sma(close: pd.Series, length: int = 20) -> pd.Series:
    """Simple moving average: ``mean(close[t-length+1 .. t])``. Warm-up: ``length - 1`` bars."""
    core.check_series(close, "close")
    length = core.check_int("length", length)
    return core.to_series(core.rolling_mean(core.values(close), length), close.index, "sma")


def ema(close: pd.Series, length: int = 20) -> pd.Series:
    """Exponential moving average, ``alpha = 2 / (length + 1)``.

    Seeded with the SMA of the first ``length`` values (TA-Lib convention), so the first value
    is at bar ``length - 1``.
    """
    core.check_series(close, "close")
    length = core.check_int("length", length)
    return core.to_series(core.ema(core.values(close), length), close.index, "ema")


def wma(close: pd.Series, length: int = 20) -> pd.Series:
    """Linearly weighted moving average, weights ``1..length`` (newest bar weighs most).

    ``WMA = sum(w_i * close_i) / sum(w_i)``. Warm-up: ``length - 1`` bars.
    """
    core.check_series(close, "close")
    length = core.check_int("length", length)
    x = core.values(close)
    out = np.full(len(x), np.nan)
    if len(x) >= length:
        weights = np.arange(1, length + 1, dtype=np.float64)
        windows = np.lib.stride_tricks.sliding_window_view(x, length)
        out[length - 1 :] = windows @ weights / weights.sum()  # NaN in a window -> NaN
    return core.to_series(out, close.index, "wma")


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Moving Average Convergence Divergence.

    ``macd = EMA(close, fast) - EMA(close, slow)``, ``signal = EMA(macd, signal)``,
    ``histogram = macd - signal``.

    Like TA-Lib, both EMAs start at bar ``slow - 1``: the fast EMA is seeded with the SMA of
    the ``fast`` bars ending there instead of starting earlier, so both lines see the same
    history. ``macd`` is valid from bar ``slow - 1``, ``signal``/``histogram`` from
    ``slow + signal - 2``.
    """
    core.check_series(close, "close")
    fast = core.check_int("fast", fast)
    slow = core.check_int("slow", slow)
    signal = core.check_int("signal", signal)
    if fast >= slow:
        raise ValueError(f"fast ({fast}) must be smaller than slow ({slow})")
    x = core.values(close)
    slow_line = core.ema(x, slow)
    fast_line = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) >= slow:
        # start the fast EMA so that its seed window ends where the slow EMA's does
        start = valid[slow - fast]
        fast_line[start:] = core.ema(x[start:], fast)
    macd_line = fast_line - slow_line
    signal_line = core.ema(macd_line, signal)
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "histogram": macd_line - signal_line},
        index=close.index,
    )


def adx(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Average Directional Index with the directional indicators (Wilder, TA-Lib convention).

    ``+DM = high - prev_high`` if it is positive and larger than ``prev_low - low``, else 0
    (``-DM`` symmetric). ``+DI = 100 * WilderSum(+DM) / WilderSum(TR)`` (0 when the TR sum is
    0), ``DX = 100 * |+DI - -DI| / (+DI + -DI)`` (0 when both are 0) and ``ADX = RMA(DX)``.
    ``plus_di``/``minus_di`` are valid from bar ``length``, ``adx`` from ``2 * length - 1``.
    """
    core.check_frame(df, ("high", "low", "close"))
    length = core.check_int("length", length)
    high, low, close = (core.values(df[c]) for c in ("high", "low", "close"))
    up = core.diff1(high)
    down = -core.diff1(low)
    with np.errstate(invalid="ignore"):
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    nan = np.isnan(up) | np.isnan(down)
    plus_dm[nan] = np.nan
    minus_dm[nan] = np.nan
    tr = core.true_range(high, low, close)
    tr_sum = core.wilder_sum(tr, length)
    plus_di = 100.0 * core.safe_div(core.wilder_sum(plus_dm, length), tr_sum, 0.0)
    minus_di = 100.0 * core.safe_div(core.wilder_sum(minus_dm, length), tr_sum, 0.0)
    dx = 100.0 * core.safe_div(np.abs(plus_di - minus_di), plus_di + minus_di, 0.0)
    return pd.DataFrame(
        {"adx": core.rma(dx, length), "plus_di": plus_di, "minus_di": minus_di},
        index=df.index,
    )


def supertrend(df: pd.DataFrame, length: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Supertrend (TradingView convention).

    ``basic = hl2 +/- multiplier * ATR(length)`` (Wilder ATR). The final upper band only moves
    down (and the lower band only up) unless the previous close crossed it. The trend flips up
    when the close rises above the final upper band and down when it falls below the final lower
    band. The first valid bar starts as a downtrend.

    Outputs: ``supertrend`` (the lower band in an uptrend, the upper band in a downtrend) and
    ``direction`` (+1 uptrend, -1 downtrend). Valid from bar ``length``.
    """
    core.check_frame(df, ("high", "low", "close"))
    length = core.check_int("length", length)
    multiplier = core.check_float("multiplier", multiplier)
    high, low, close = (core.values(df[c]) for c in ("high", "low", "close"))
    atr_ = core.rma(core.true_range(high, low, close), length)
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr_
    basic_lower = hl2 - multiplier * atr_

    n = len(close)
    line = np.full(n, np.nan)
    direction = np.full(n, np.nan)
    upper = lower = np.nan
    prev_close = np.nan
    trend = 0
    for t in range(n):
        bu, bl, c = basic_upper[t], basic_lower[t], close[t]
        if np.isnan(bu) or np.isnan(bl) or np.isnan(c):
            continue
        if trend == 0:  # first valid bar
            upper, lower, trend = bu, bl, -1
        else:
            upper = bu if (bu < upper or prev_close > upper) else upper
            lower = bl if (bl > lower or prev_close < lower) else lower
            if trend == -1 and c > upper:
                trend = 1
            elif trend == 1 and c < lower:
                trend = -1
        line[t] = lower if trend == 1 else upper
        direction[t] = trend
        prev_close = c
    return pd.DataFrame({"supertrend": line, "direction": direction}, index=df.index)


def ichimoku(
    df: pd.DataFrame, tenkan: int = 9, kijun: int = 26, senkou: int = 52, displacement: int = 26
) -> pd.DataFrame:
    """Ichimoku Kinko Hyo, aligned to the input bars without look-ahead.

    ``tenkan = (highest(high, tenkan) + lowest(low, tenkan)) / 2`` (``kijun`` likewise),
    ``senkou_a = (tenkan + kijun) / 2`` and ``senkou_b = midpoint over senkou`` are both
    projected ``displacement`` bars forward, so the value at bar ``t`` is the cloud that is
    drawn at ``t`` (computed at ``t - displacement``). The cloud beyond the last bar and the
    chikou span (close shifted *back*, i.e. future data at bar ``t``) are not returned.
    """
    core.check_frame(df, ("high", "low"))
    tenkan = core.check_int("tenkan", tenkan)
    kijun = core.check_int("kijun", kijun)
    senkou = core.check_int("senkou", senkou)
    displacement = core.check_int("displacement", displacement, minimum=0)
    high, low = core.values(df["high"]), core.values(df["low"])

    def midpoint(length: int) -> np.ndarray:
        return (core.rolling_max(high, length) + core.rolling_min(low, length)) / 2.0

    def shift(x: np.ndarray) -> np.ndarray:
        if displacement == 0:
            return x
        out = np.full(len(x), np.nan)
        out[displacement:] = x[: len(x) - displacement]
        return out

    tenkan_line, kijun_line = midpoint(tenkan), midpoint(kijun)
    return pd.DataFrame(
        {
            "tenkan": tenkan_line,
            "kijun": kijun_line,
            "senkou_a": shift((tenkan_line + kijun_line) / 2.0),
            "senkou_b": shift(midpoint(senkou)),
        },
        index=df.index,
    )
