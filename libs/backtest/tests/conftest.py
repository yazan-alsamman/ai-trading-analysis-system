import numpy as np
import pandas as pd
import pytest


def bars(rows: list[tuple[float, float, float, float]], start: str = "2025-01-01") -> pd.DataFrame:
    """Hourly OHLCV frame from (open, high, low, close) rows."""
    o, h, low, c = (list(col) for col in zip(*rows, strict=True))
    index = pd.date_range(start, periods=len(rows), freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": o, "high": h, "low": low, "close": c, "volume": 1.0}, index=index, dtype=float
    )


def flat(prices: list[float]) -> pd.DataFrame:
    """Bars with open = high = low = close = price."""
    return bars([(p, p, p, p) for p in prices])


def signals(df: pd.DataFrame, events: dict[int, int]) -> pd.DataFrame:
    sig = np.zeros(len(df), dtype=np.int8)
    reason = np.full(len(df), None, dtype=object)
    for i, s in events.items():
        sig[i] = s
        reason[i] = "test_buy" if s == 1 else "test_sell"
    return pd.DataFrame({"signal": sig, "reason": reason}, index=df.index)


def synthetic_ohlcv(n: int = 3000, seed: int = 42, freq: str = "h") -> pd.DataFrame:
    """Fixed-seed random walk (like libs/strategies/tests)."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    open_ = np.concatenate(([100.0], close[:-1])) * np.exp(rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    volume = rng.lognormal(3, 0.6, n)
    index = pd.date_range("2025-01-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return synthetic_ohlcv()


NO_COSTS = {"fee_bps": 0, "slippage_bps": 0}
