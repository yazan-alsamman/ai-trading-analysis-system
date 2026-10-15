"""Shared building blocks: input validation, moving averages, Wilder smoothing, true range.

Conventions used by every indicator in this package:

* Inputs are pandas Series/DataFrames (columns ``open, high, low, close, volume``) ordered by
  time. Outputs are aligned to the input index and are ``NaN`` during the warm-up period.
* No look-ahead: the value at bar ``t`` only uses bars ``<= t``.
* Missing data: leading ``NaN`` values are skipped (the warm-up starts at the first valid value).
  A ``NaN`` later on makes the output ``NaN`` at that bar. Rolling-window indicators stay ``NaN``
  while the gap is inside their window; recursive ones (EMA, Wilder) keep their state and
  continue with the next valid value.
* Divisions that would be 0/0 have a documented, finite result (e.g. RSI = 50 when there is no
  movement) and never emit numpy warnings.
"""

from __future__ import annotations

import numbers
from collections.abc import Iterable

import numpy as np
import pandas as pd

OHLCV = ("open", "high", "low", "close", "volume")


# --- validation ------------------------------------------------------------------------------


def check_int(name: str, value: object, minimum: int = 1, maximum: int | None = None) -> int:
    """An integer parameter (bools and non-integral floats are rejected)."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer, got {value!r}")
    value = int(value)
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
        raise ValueError(f"{name} must be {bounds}, got {value}")
    return value


def check_float(
    name: str, value: object, minimum: float = 0.0, maximum: float | None = None
) -> float:
    """A finite float parameter with ``minimum < value <= maximum``."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be a number, got {value!r}")
    value = float(value)
    if not np.isfinite(value) or value <= minimum or (maximum is not None and value > maximum):
        bounds = f"> {minimum}" if maximum is None else f"> {minimum} and <= {maximum}"
        raise ValueError(f"{name} must be {bounds}, got {value}")
    return value


def check_series(series: object, name: str = "series") -> pd.Series:
    if not isinstance(series, pd.Series):
        raise ValueError(f"{name} must be a pandas Series, got {type(series).__name__}")
    _check_index(series.index)
    return series


def check_frame(df: object, columns: Iterable[str]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"expected a pandas DataFrame, got {type(df).__name__}")
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"missing column(s): {', '.join(missing)}")
    _check_index(df.index)
    return df


def _check_index(index: pd.Index) -> None:
    if not index.is_monotonic_increasing:
        raise ValueError("the index must be sorted in ascending (time) order")


def values(series: pd.Series) -> np.ndarray:
    """Float64 numpy copy of a Series (non-numeric values raise ValueError)."""
    try:
        return series.to_numpy(dtype=np.float64, na_value=np.nan, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{series.name or 'series'} must be numeric") from exc


def to_series(data: np.ndarray, index: pd.Index, name: str) -> pd.Series:
    return pd.Series(data, index=index, name=name, dtype=np.float64)


def safe_div(num: np.ndarray, den: np.ndarray, fill: float) -> np.ndarray:
    """num / den, with ``fill`` where den == 0, NaN where an input is NaN, no warnings."""
    num, den = np.broadcast_arrays(np.asarray(num, np.float64), np.asarray(den, np.float64))
    out = np.full(num.shape, np.nan)
    ok = ~(np.isnan(num) | np.isnan(den))
    zero = ok & (den == 0)
    nonzero = ok & ~zero
    out[nonzero] = num[nonzero] / den[nonzero]
    out[zero] = fill
    return out


# --- moving averages ------------------------------------------------------------------------


def rolling_mean(x: np.ndarray, length: int) -> np.ndarray:
    """Simple moving average; NaN until ``length`` valid values are in the window."""
    return pd.Series(x).rolling(length, min_periods=length).mean().to_numpy(copy=True)


def rolling_max(x: np.ndarray, length: int) -> np.ndarray:
    return pd.Series(x).rolling(length, min_periods=length).max().to_numpy(copy=True)


def rolling_min(x: np.ndarray, length: int) -> np.ndarray:
    return pd.Series(x).rolling(length, min_periods=length).min().to_numpy(copy=True)


def rolling_sum(x: np.ndarray, length: int) -> np.ndarray:
    return pd.Series(x).rolling(length, min_periods=length).sum().to_numpy(copy=True)


def seeded_ema(x: np.ndarray, length: int, alpha: float) -> np.ndarray:
    """Recursive exponential smoothing ``y[t] = y[t-1] + alpha * (x[t] - y[t-1])``.

    Seeded like TA-Lib: the first output is the simple mean of the first ``length`` valid
    values, placed at the ``length``-th valid value. Later NaN inputs give NaN outputs and leave
    the state unchanged.
    """
    out = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < length:
        return out
    seed_at = valid[length - 1]
    tail = x[seed_at:].copy()
    tail[0] = x[valid[:length]].mean()
    ewm = pd.Series(tail).ewm(alpha=alpha, adjust=False, ignore_na=True)
    smoothed = ewm.mean().to_numpy(copy=True)  # writable (pandas 3 returns read-only views)
    smoothed[1:][np.isnan(tail[1:])] = np.nan
    out[seed_at:] = smoothed
    return out


def ema(x: np.ndarray, length: int) -> np.ndarray:
    """EMA with ``alpha = 2 / (length + 1)``, seeded with the SMA of the first ``length`` values."""
    return seeded_ema(x, length, 2.0 / (length + 1))


def rma(x: np.ndarray, length: int) -> np.ndarray:
    """Wilder's smoothing (RMA/SMMA): ``alpha = 1 / length``, seeded with an SMA."""
    return seeded_ema(x, length, 1.0 / length)


def wilder_sum(x: np.ndarray, length: int) -> np.ndarray:
    """Wilder's running *sum* as used by TA-Lib's DMI/ADX family.

    ``S[t] = S[t-1] - S[t-1] / length + x[t]``, started from the plain sum of the first
    ``length - 1`` valid values, so the first output is at the ``length``-th valid value.
    """
    out = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < length:
        return out
    start = valid[length - 2] if length > 1 else valid[0] - 1
    initial = x[valid[: length - 1]].sum()
    # S[t] = (1 - a) S[t-1] + a * (length * x[t]) with a = 1/length: an EMA over length * x.
    scaled = np.empty(len(x) - start)
    scaled[0] = initial
    scaled[1:] = x[start + 1 :] * length
    smoothed = pd.Series(scaled).ewm(alpha=1.0 / length, adjust=False, ignore_na=True).mean()
    smoothed = smoothed.to_numpy(copy=True)
    smoothed[1:][np.isnan(scaled[1:])] = np.nan
    out[start + 1 :] = smoothed[1:]
    return out


def shift1(x: np.ndarray) -> np.ndarray:
    """The previous bar's value (NaN at the first bar); same length as ``x``."""
    out = np.full(len(x), np.nan)
    out[1:] = x[:-1]
    return out


def diff1(x: np.ndarray) -> np.ndarray:
    """``x[t] - x[t-1]`` (NaN at the first bar); same length as ``x``."""
    return x - shift1(x)


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """``max(high - low, |high - prev_close|, |low - prev_close|)``; NaN at the first bar
    (no previous close), like TA-Lib's TRANGE."""
    prev_close = shift1(close)
    ranges = np.vstack([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    out = np.full(len(close), np.nan)
    ok = ~np.isnan(ranges).any(axis=0)
    out[ok] = ranges[:, ok].max(axis=0)
    return out
