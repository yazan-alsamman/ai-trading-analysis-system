"""No look-ahead: future bars never change signals that already exist."""

import zlib

import numpy as np
import pandas as pd
import pytest

import trading_strategies as ts
from tests.conftest import synthetic_ohlcv

LOOSE = {  # parameters that fire often, so the comparison covers many signal rows
    "ma_crossover": {"fast": 3, "slow": 8},
    "rsi_reversal": {"oversold": 45, "overbought": 55},
    "macd_cross": {},
    "bollinger_reversion": {"std": 1.0},
    "supertrend_flip": {"multiplier": 1.0},
    "donchian_breakout": {"length": 5},
}


def _future(last: pd.DataFrame, k: int, rng: np.random.Generator) -> pd.DataFrame:
    prev = last["close"].iloc[-1]
    close = prev * np.exp(np.cumsum(rng.normal(0, rng.uniform(0.002, 0.05), k)))
    open_ = np.concatenate(([prev], close[:-1]))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, k)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, k)))
    index = pd.date_range(last.index[-1] + pd.Timedelta(hours=1), periods=k, freq="h")
    volume = rng.lognormal(3, 1.5, k)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


@pytest.mark.parametrize("key", sorted(ts.STRATEGIES))
def test_appending_future_bars_changes_nothing(key: str) -> None:
    rng = np.random.default_rng(zlib.crc32(key.encode()))
    history = synthetic_ohlcv(800, seed=21)
    params = LOOSE[key]
    full = ts.run(key, history, **params)
    assert (full["signal"] != 0).sum() >= 5  # the property is checked on real signal rows
    for _ in range(12):
        n = int(rng.integers(0, len(history)))
        past = history.iloc[: n + 1]
        extended = pd.concat([past, _future(past, int(rng.integers(1, 150)), rng)])
        before = ts.run(key, past, **params)
        after = ts.run(key, extended, **params).iloc[: n + 1]
        pd.testing.assert_frame_equal(before, after, check_exact=True)


@pytest.mark.parametrize("key", sorted(ts.STRATEGIES))
def test_changing_a_future_bar_changes_nothing_before_it(key: str) -> None:
    df = synthetic_ohlcv(600, seed=22)
    base = ts.run(key, df, **LOOSE[key])
    shocked = df.copy()
    shocked.iloc[500, :] = shocked.iloc[500, :] * [1.0, 1.3, 0.7, 1.25, 40.0]
    after = ts.run(key, shocked, **LOOSE[key])
    pd.testing.assert_frame_equal(base.iloc[:500], after.iloc[:500], check_exact=True)
