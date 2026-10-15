"""No look-ahead: appending future bars must never change values that already exist."""

import zlib

import numpy as np
import pandas as pd
import pytest

import trading_indicators as ti
from tests.conftest import synthetic_ohlcv


def _future_bars(last: pd.DataFrame, k: int, rng: np.random.Generator) -> pd.DataFrame:
    """k random but consistent bars that continue after ``last``."""
    prev = last["close"].iloc[-1]
    close = prev * np.exp(np.cumsum(rng.normal(0, rng.uniform(0.002, 0.05), k)))
    open_ = np.concatenate(([prev], close[:-1]))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, k)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, k)))
    index = pd.date_range(last.index[-1] + pd.Timedelta(hours=1), periods=k, freq="h")
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.lognormal(3, 1.5, k),
        },
        index=index,
    )


@pytest.mark.parametrize("name", sorted(ti.INDICATORS))
def test_appending_future_bars_changes_nothing(name: str) -> None:
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    history = synthetic_ohlcv(600, seed=7)
    for _ in range(15):
        n = int(rng.integers(0, len(history)))
        past = history.iloc[: n + 1]
        k = int(rng.integers(1, 200))
        extended = pd.concat([past, _future_bars(past, k, rng)])
        before = ti.compute(name, past)
        after = ti.compute(name, extended).iloc[: n + 1]
        # bit-for-bit identical, NaNs included
        pd.testing.assert_frame_equal(before, after, check_exact=True)


@pytest.mark.parametrize("name", sorted(ti.INDICATORS))
def test_changing_a_future_bar_changes_nothing_before_it(name: str) -> None:
    df = synthetic_ohlcv(400, seed=11)
    base = ti.compute(name, df)
    shocked = df.copy()
    t = 300
    shocked.iloc[t, :] = shocked.iloc[t, :] * [1.0, 1.5, 0.5, 1.4, 50.0]  # o, h, l, c, v
    after = ti.compute(name, shocked)
    pd.testing.assert_frame_equal(base.iloc[:t], after.iloc[:t], check_exact=True)
