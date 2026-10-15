from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def synthetic_ohlcv(n: int = 3000, seed: int = 42, start: str = "2025-01-01") -> pd.DataFrame:
    """Fixed-seed random-walk OHLCV with consistent bars and an hourly UTC index."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    open_ = np.concatenate(([100.0], close[:-1])) * np.exp(rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    volume = rng.lognormal(3, 0.6, n)
    index = pd.date_range(start, periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


def binance_btcusdt() -> pd.DataFrame:
    """1,000 real BTCUSDT 1h candles (Binance public klines, Sep-Oct 2026)."""
    df = pd.read_csv(FIXTURES / "btcusdt_1h_binance.csv")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("time"), utc=True))
    return df.astype(float)


DATASETS = {"synthetic": synthetic_ohlcv, "btcusdt": binance_btcusdt}


@pytest.fixture(params=sorted(DATASETS))
def dataset(request) -> pd.DataFrame:
    return DATASETS[request.param]()


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return synthetic_ohlcv()
