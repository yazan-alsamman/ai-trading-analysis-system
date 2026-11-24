"""Synthetic markets for the strategy and management tests: an M1 random walk with volatility
clusters, inside the instrument's trading hours, aggregated to the store frames with the
importer's own code (``app.data.aggregate``), so every frame is consistent as in the store.
Nothing here touches the research store."""

from __future__ import annotations

from functools import cache

import numpy as np
import pandas as pd

from app.config import instruments
from app.data.aggregate import aggregate
from app.data.sessions import is_open

M1 = pd.Timedelta(minutes=1)
# Covers both daylight-saving changes of autumn 2024 (EU 27 October, US 3 November): the week
# between them has the rollover at 18:00 New York.
START, END = "2024-09-23", "2024-11-16"
# The same weeks of 2023 (EU 29 October, US 5 November), inside the primary period, for code that
# refuses bars after 2024-07-01.
PRIMARY = ("2023-09-25", "2023-11-18")


def m1_walk(symbol: str, start: str, end: str, seed: int, sigma: float, price: float):
    ts = pd.date_range(start, end, freq="1min", tz="UTC", inclusive="left")
    ts = ts[is_open(ts, instruments()[symbol])]
    rng = np.random.default_rng(seed)
    n = len(ts)
    vol = sigma * np.exp(np.convolve(rng.normal(0, 0.35, n), np.ones(240) / 15.5, "same"))
    ret = rng.standard_t(5, n) * vol / np.sqrt(5 / 3)
    close = price + np.cumsum(ret)
    open_ = np.r_[price, close[:-1]]
    wick = np.abs(rng.normal(0, 0.5, (2, n))) * vol
    high = np.maximum(open_, close) + wick[0]
    low = np.minimum(open_, close) - wick[1]
    return pd.DataFrame(
        {
            "ts_utc": ts.as_unit("ns"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": rng.integers(1, 60, n),
            "spread": np.round(rng.uniform(0.02, 0.06, n) * price / 2000, 6),
        }
    )


@cache
def market(
    symbol: str = "XAUUSD", seed: int = 7, start: str = START, end: str = END
) -> dict[str, pd.DataFrame]:
    """The frames 5m, 15m, 1h, 4h, D1 of a synthetic instrument (gold-like scale)."""
    price, sigma = (2000.0, 0.45) if symbol == "XAUUSD" else (1.1, 0.00025)
    bars = m1_walk(symbol, start, end, seed, sigma, price)
    return {tf: aggregate(bars, tf, M1) for tf in ("5m", "15m", "1h", "4h", "D1")}


def cut(frames: dict[str, pd.DataFrame], t: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Every bar closed by ``t``: the frames as they stood at that time."""
    return {k: v[v["close_utc"] <= t].reset_index(drop=True) for k, v in frames.items()}
