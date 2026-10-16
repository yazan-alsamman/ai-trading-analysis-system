"""Momentum oscillators: RSI, Stochastic, StochRSI, CCI, Williams %R, ROC, MFI."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_indicators import core

_CCI_CHUNK = 65_536  # rows per block when computing rolling mean deviations


def _rsi(x: np.ndarray, length: int) -> np.ndarray:
    delta = core.diff1(x)
    with np.errstate(invalid="ignore"):
        gains = np.where(delta > 0, delta, 0.0)
        losses = np.where(delta < 0, -delta, 0.0)
    gains[np.isnan(delta)] = np.nan
    losses[np.isnan(delta)] = np.nan
    avg_gain, avg_loss = core.rma(gains, length), core.rma(losses, length)
    return 100.0 * core.safe_div(avg_gain, avg_gain + avg_loss, 0.5)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index with Wilder's smoothing (TA-Lib/TradingView convention).

    ``RSI = 100 * RMA(gain) / (RMA(gain) + RMA(loss))`` over close-to-close changes; the
    averages are seeded with the simple mean of the first ``length`` changes, so the first value
    is at bar ``length``. When there is no movement at all (both averages 0) RSI is 50.
    """
    core.check_series(close, "close")
    length = core.check_int("length", length)
    return core.to_series(_rsi(core.values(close), length), close.index, "rsi")


def _stoch_k(close: np.ndarray, high: np.ndarray, low: np.ndarray, length: int) -> np.ndarray:
    highest, lowest = core.rolling_max(high, length), core.rolling_min(low, length)
    return 100.0 * core.safe_div(close - lowest, highest - lowest, 0.5)


def stoch(
    df: pd.DataFrame, k_length: int = 14, k_smooth: int = 3, d_smooth: int = 3
) -> pd.DataFrame:
    """Stochastic oscillator (slow %K / %D).

    ``raw = 100 * (close - lowest(low, k_length)) / (highest(high, k_length) -
    lowest(low, k_length))`` (50 when the range is 0), ``k = SMA(raw, k_smooth)``,
    ``d = SMA(k, d_smooth)``. Valid from ``k_length + k_smooth + d_smooth - 3``.
    """
    core.check_frame(df, ("high", "low", "close"))
    k_length = core.check_int("k_length", k_length)
    k_smooth = core.check_int("k_smooth", k_smooth)
    d_smooth = core.check_int("d_smooth", d_smooth)
    raw = _stoch_k(*(core.values(df[c]) for c in ("close", "high", "low")), k_length)
    k = core.rolling_mean(raw, k_smooth) if k_smooth > 1 else raw
    d = core.rolling_mean(k, d_smooth) if d_smooth > 1 else k
    return pd.DataFrame({"k": k, "d": d}, index=df.index)


def stochrsi(
    close: pd.Series,
    rsi_length: int = 14,
    stoch_length: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> pd.DataFrame:
    """Stochastic RSI: the stochastic formula applied to RSI(rsi_length) instead of prices.

    ``raw = 100 * (rsi - lowest(rsi)) / (highest(rsi) - lowest(rsi))`` over ``stoch_length``
    (50 when RSI was flat), ``k = SMA(raw, k_smooth)``, ``d = SMA(k, d_smooth)``.
    Valid from ``rsi_length + stoch_length + k_smooth + d_smooth - 3``.
    """
    core.check_series(close, "close")
    rsi_length = core.check_int("rsi_length", rsi_length)
    stoch_length = core.check_int("stoch_length", stoch_length)
    k_smooth = core.check_int("k_smooth", k_smooth)
    d_smooth = core.check_int("d_smooth", d_smooth)
    r = _rsi(core.values(close), rsi_length)
    raw = _stoch_k(r, r, r, stoch_length)
    k = core.rolling_mean(raw, k_smooth) if k_smooth > 1 else raw
    d = core.rolling_mean(k, d_smooth) if d_smooth > 1 else k
    return pd.DataFrame({"k": k, "d": d}, index=close.index)


def cci(df: pd.DataFrame, length: int = 20, constant: float = 0.015) -> pd.Series:
    """Commodity Channel Index.

    ``tp = (high + low + close) / 3``, ``CCI = (tp - SMA(tp)) / (constant * MD)`` where ``MD``
    is the mean absolute deviation of ``tp`` from that SMA over the same window (0 when MD is 0).
    Valid from bar ``length - 1``.
    """
    core.check_frame(df, ("high", "low", "close"))
    length = core.check_int("length", length)
    constant = core.check_float("constant", constant)
    tp = (core.values(df["high"]) + core.values(df["low"]) + core.values(df["close"])) / 3.0
    mean = core.rolling_mean(tp, length)
    mean_dev = np.full(len(tp), np.nan)
    if len(tp) >= length:
        windows = np.lib.stride_tricks.sliding_window_view(tp, length)
        for start in range(0, len(windows), _CCI_CHUNK):
            block = windows[start : start + _CCI_CHUNK]
            centre = mean[length - 1 + start : length - 1 + start + len(block)]
            mean_dev[length - 1 + start : length - 1 + start + len(block)] = np.abs(
                block - centre[:, None]
            ).mean(axis=1)
    out = core.safe_div(tp - mean, constant * mean_dev, 0.0)
    return core.to_series(out, df.index, "cci")


def williams_r(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Williams %R: ``-100 * (highest(high) - close) / (highest(high) - lowest(low))`` over
    ``length`` bars, in [-100, 0] (-50 when the range is 0). Valid from bar ``length - 1``."""
    core.check_frame(df, ("high", "low", "close"))
    length = core.check_int("length", length)
    high, low, close = (core.values(df[c]) for c in ("high", "low", "close"))
    highest, lowest = core.rolling_max(high, length), core.rolling_min(low, length)
    out = -100.0 * core.safe_div(highest - close, highest - lowest, 0.5)
    return core.to_series(out, df.index, "williams_r")


def roc(close: pd.Series, length: int = 10) -> pd.Series:
    """Rate of change in percent: ``100 * (close / close[t - length] - 1)``.

    NaN when the reference close is 0. Valid from bar ``length``.
    """
    core.check_series(close, "close")
    length = core.check_int("length", length)
    x = core.values(close)
    prev = np.full(len(x), np.nan)
    prev[length:] = x[: len(x) - length] if len(x) > length else []
    out = 100.0 * (core.safe_div(x, prev, np.nan) - 1.0)
    return core.to_series(out, close.index, "roc")


def mfi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Money Flow Index (a volume-weighted RSI).

    ``tp = (high + low + close) / 3`` and ``raw = tp * volume``. A bar's flow is positive when
    ``tp`` rose versus the previous bar, negative when it fell, and ignored when unchanged.
    ``MFI = 100 * sum(positive) / (sum(positive) + sum(negative))`` over ``length`` bars
    (50 when there was no flow). Valid from bar ``length``.
    """
    core.check_frame(df, ("high", "low", "close", "volume"))
    length = core.check_int("length", length)
    tp = (core.values(df["high"]) + core.values(df["low"]) + core.values(df["close"])) / 3.0
    flow = tp * core.values(df["volume"])
    change = core.diff1(tp)
    with np.errstate(invalid="ignore"):
        positive = np.where(change > 0, flow, 0.0)
        negative = np.where(change < 0, flow, 0.0)
    missing = np.isnan(change) | np.isnan(flow)
    positive[missing] = np.nan
    negative[missing] = np.nan
    pos_sum, neg_sum = core.rolling_sum(positive, length), core.rolling_sum(negative, length)
    out = 100.0 * core.safe_div(pos_sum, pos_sum + neg_sum, 0.5)
    return core.to_series(out, df.index, "mfi")
