"""Short series, constant prices, NaN inputs and invalid parameters."""

import warnings

import numpy as np
import pandas as pd
import pytest

import trading_indicators as ti
from tests.conftest import synthetic_ohlcv


def constant(n: int = 200, price: float = 100.0, volume: float = 5.0) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": price, "high": price, "low": price, "close": price, "volume": volume},
        index=index,
    )


@pytest.mark.parametrize("name", sorted(ti.INDICATORS))
def test_series_shorter_than_lookback_is_all_nan(name: str) -> None:
    spec = ti.get_indicator(name)
    lookback = spec.lookback()
    df = synthetic_ohlcv(max(lookback, 1), seed=3)  # one bar short of the first value
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = ti.compute(name, df)
    assert list(out.columns) == list(spec.outputs)
    assert len(out) == len(df)
    if lookback > 0:
        assert out.iloc[-1].isna().any()  # not every output is valid yet


@pytest.mark.parametrize("name", sorted(ti.INDICATORS))
def test_empty_and_single_bar(name: str) -> None:
    for n in (0, 1):
        out = ti.compute(name, synthetic_ohlcv(3, seed=1).iloc[:n])
        assert len(out) == n


@pytest.mark.parametrize("name", sorted(ti.INDICATORS))
def test_constant_prices_no_warnings(name: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no division-by-zero / invalid-value warnings
        out = ti.compute(name, constant())
    tail = out.iloc[-1]
    assert not tail.isna().any(), tail


def test_constant_prices_documented_values() -> None:
    df, close = constant(), constant()["close"]
    last = lambda x: x.iloc[-1]  # noqa: E731
    assert last(ti.rsi(close)) == 50
    assert last(ti.stoch(df)).tolist() == [50, 50]
    assert last(ti.stochrsi(close)).tolist() == [50, 50]
    assert last(ti.williams_r(df)) == -50
    assert last(ti.cci(df)) == 0
    assert last(ti.mfi(df)) == 50
    assert last(ti.roc(close)) == 0
    assert last(ti.atr(df)) == 0
    assert last(ti.adx(df)).tolist() == [0, 0, 0]
    assert last(ti.bollinger(close)).tolist() == [100, 100, 100]
    assert last(ti.macd(close)).tolist() == [0, 0, 0]
    assert last(ti.vwap(df)) == 100
    assert last(ti.obv(df)) == 5  # first bar's volume, never changed afterwards
    assert last(ti.supertrend(df)).tolist() == [100, -1]


def test_leading_nans_shift_the_warm_up() -> None:
    close = synthetic_ohlcv(100, seed=5)["close"]
    shifted = pd.concat([pd.Series([np.nan] * 10), close.reset_index(drop=True)])
    shifted.index = pd.RangeIndex(len(shifted))
    for fn, first in ((ti.sma, 19), (ti.ema, 19), (ti.rsi, 14)):
        plain = fn(close.reset_index(drop=True))
        delayed = fn(shifted)
        assert delayed.first_valid_index() == first + 10
        np.testing.assert_allclose(delayed.to_numpy()[10:], plain.to_numpy(), equal_nan=True)


def test_interior_nan_rolling_and_recursive() -> None:
    close = synthetic_ohlcv(120, seed=6)["close"].reset_index(drop=True)
    gap = close.copy()
    gap.iloc[60] = np.nan
    sma, ema = ti.sma(gap, 5), ti.ema(gap, 5)
    # rolling windows that contain the gap are NaN, then it recovers
    assert sma.iloc[60:65].isna().all() and not np.isnan(sma.iloc[65])
    # recursive: NaN only at the gap; the state carries over to the next valid value
    assert np.isnan(ema.iloc[60]) and not ema.iloc[61:].isna().any()
    expected = ema.iloc[59] + (2 / 6) * (gap.iloc[61] - ema.iloc[59])
    assert ema.iloc[61] == pytest.approx(expected)


def test_nan_inputs_never_warn() -> None:
    df = synthetic_ohlcv(300, seed=8)
    df.iloc[[0, 50, 51, 200], :] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for name in ti.INDICATORS:
            ti.compute(name, df)


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda c, df: ti.sma(c, 0), "length must be >= 1"),
        (lambda c, df: ti.ema(c, -3), "length must be >= 1"),
        (lambda c, df: ti.rsi(c, 2.5), "length must be an integer"),
        (lambda c, df: ti.rsi(c, True), "length must be an integer"),
        (lambda c, df: ti.wma(c, "10"), "length must be an integer"),
        (lambda c, df: ti.macd(c, 26, 12), "fast .* must be smaller than slow"),
        (lambda c, df: ti.bollinger(c, 20, 0), "std must be > 0"),
        (lambda c, df: ti.bollinger(c, 20, float("nan")), "std must be > 0"),
        (lambda c, df: ti.supertrend(df, 10, -1), "multiplier must be > 0"),
        (lambda c, df: ti.atr(df.drop(columns="high")), "missing column"),
        (lambda c, df: ti.rsi(df), "must be a pandas Series"),
        (lambda c, df: ti.adx(c), "expected a pandas DataFrame"),
        (lambda c, df: ti.sma(c.iloc[::-1]), "ascending"),
        (lambda c, df: ti.sma(c.astype(str) + "x"), "must be numeric"),
    ],
)
def test_invalid_input_raises_value_error(call, match: str) -> None:
    df = synthetic_ohlcv(50, seed=9)
    with pytest.raises(ValueError, match=match):
        call(df["close"], df)


def test_float_integral_lengths_are_accepted() -> None:
    close = synthetic_ohlcv(50, seed=9)["close"]
    pd.testing.assert_series_equal(ti.sma(close, 10.0), ti.sma(close, 10))
