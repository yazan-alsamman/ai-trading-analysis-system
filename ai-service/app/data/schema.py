"""Canonical bar schema and instrument specs shared by every data source."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Bars are keyed by their open time (``ts_utc``); a 5m bar stamped 10:00 covers [10:00, 10:05).
CANONICAL_COLUMNS = [
    "ts_utc",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "source",
]

BASE_TIMEFRAME = pd.Timedelta(minutes=5)


@dataclass(frozen=True)
class SessionSpec:
    """Trading hours in New York wall-clock time.

    The week opens on Sunday at ``week_open`` and closes on Friday at ``week_close``. If
    ``daily_break`` is set, the market is also closed every day between those two times.
    """

    week_open: str = "18:00"
    week_close: str = "17:00"
    daily_break: tuple[str, str] | None = ("17:00", "18:00")


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    point: float  # price value of one MT5 point
    price_decimals: int
    session: SessionSpec


INSTRUMENTS: dict[str, InstrumentSpec] = {
    "XAUUSD": InstrumentSpec("XAUUSD", point=0.01, price_decimals=2, session=SessionSpec()),
    # FX has no daily break, only the 17:00 New York rollover.
    "EURUSD": InstrumentSpec(
        "EURUSD", point=0.00001, price_decimals=5, session=SessionSpec(daily_break=None)
    ),
}


def content_hash(df: pd.DataFrame) -> str:
    """SHA-256 of a frame's columns, dtypes and values; independent of the file format and library
    version."""
    h = hashlib.sha256()
    for col in df.columns:
        s = df[col]
        h.update(f"{col}:{s.dtype}\n".encode())
        if isinstance(s.dtype, pd.DatetimeTZDtype) or pd.api.types.is_datetime64_dtype(s):
            values = s.dt.as_unit("ns").astype("int64").to_numpy()
            h.update(values.tobytes())
        elif pd.api.types.is_numeric_dtype(s):
            mask = s.isna().to_numpy()
            values = s.astype("float64").to_numpy(na_value=np.nan)
            h.update(np.where(mask, 0.0, values).astype("<f8").tobytes())
            h.update(np.packbits(mask).tobytes())
        else:
            h.update("\x1f".join(s.astype(str).tolist()).encode())
    return h.hexdigest()


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
