"""Research frames for the signal strategies: the store's 5m, 15m, 1h, 4h and D1 bars of one
instrument that opened on or after ``start`` and closed by ``end``. Later rows are filtered out
while the file is read, so they are never loaded; ``end`` past the lockbox start is refused (the
store holds nothing later, and no code path may ask for it)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import splits
from app.data.importer import DEFAULT_OUT as STORE

FRAMES = ("5m", "15m", "1h", "4h", "D1")


def load(
    symbol: str, start: pd.Timestamp, end: pd.Timestamp, store: Path = STORE
) -> dict[str, pd.DataFrame]:
    lockbox = pd.Timestamp(splits().lockbox_start, tz="UTC")
    if end > lockbox:
        raise ValueError(f"end {end} is past the lockbox start {lockbox}")
    out = {}
    for tf in FRAMES:
        df = pd.read_parquet(
            store / symbol / f"{tf}.parquet",
            filters=[("close_utc", "<=", end), ("ts_utc", ">=", start)],
        )
        out[tf] = df.reset_index(drop=True)
    return out
