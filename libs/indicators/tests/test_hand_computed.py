"""Indicators TA-Lib does not have, checked on small hand-computed examples."""

import numpy as np
import pandas as pd
import pytest

import trading_indicators as ti

nan = np.nan


def frame(high, low, close=None, volume=None, index=None) -> pd.DataFrame:
    n = len(high)
    close = close if close is not None else [(h + lo) / 2 for h, lo in zip(high, low, strict=True)]
    volume = volume if volume is not None else [1.0] * n
    index = index if index is not None else pd.date_range("2026-01-01", periods=n, freq="h")
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
        dtype=float,
    )


def test_supertrend_hand_example() -> None:
    # length 1 => ATR = true range; multiplier 1 => bands = hl2 +/- TR
    df = frame(
        high=[10, 11, 12, 14, 13, 11],
        low=[8, 9, 10, 12, 11, 9],
        close=[9, 10, 11.5, 13.5, 11.2, 9.5],
    )
    out = ti.supertrend(df, length=1, multiplier=1.0)
    # bar 1: TR 2, hl2 10 -> bands 12/8, starts down -> 12
    # bar 2: TR 2, hl2 11 -> upper stays 12 (13 > 12), lower rises to 9; close 11.5 < 12 -> down
    # bar 3: TR 2.5, hl2 13 -> upper 12, lower 10.5; close 13.5 > 12 -> up -> 10.5
    # bar 4: TR 2.5, hl2 12 -> lower stays 10.5; close 11.2 >= 10.5 -> still up
    # bar 5: TR 2.2, hl2 10 -> upper 12.2 (< 14.5); close 9.5 < 10.5 -> down -> 12.2
    np.testing.assert_allclose(out["supertrend"], [nan, 12, 12, 10.5, 10.5, 12.2])
    np.testing.assert_array_equal(out["direction"], [nan, -1, -1, 1, 1, -1])


def test_ichimoku_hand_example() -> None:
    df = frame(high=[5, 7, 6, 9, 8, 10], low=[3, 4, 2, 5, 6, 7])
    out = ti.ichimoku(df, tenkan=2, kijun=3, senkou=4, displacement=2)
    np.testing.assert_allclose(out["tenkan"], [nan, 5, 4.5, 5.5, 7, 8])
    np.testing.assert_allclose(out["kijun"], [nan, nan, 4.5, 5.5, 5.5, 7.5])
    # (tenkan + kijun) / 2 = [., ., 4.5, 5.5, 6.25, 7.75], drawn 2 bars later
    np.testing.assert_allclose(out["senkou_a"], [nan, nan, nan, nan, 4.5, 5.5])
    # 4-bar midpoint = [., ., ., 5.5, 5.5, 6], drawn 2 bars later
    np.testing.assert_allclose(out["senkou_b"], [nan, nan, nan, nan, nan, 5.5])
    assert ti.lookback("ichimoku", tenkan=2, kijun=3, senkou=4, displacement=2) == 5


def test_donchian_hand_example() -> None:
    df = frame(high=[5, 7, 6, 9, 8, 10], low=[3, 4, 2, 5, 6, 7])
    out = ti.donchian(df, length=3)
    np.testing.assert_allclose(out["upper"], [nan, nan, 7, 9, 9, 10])
    np.testing.assert_allclose(out["lower"], [nan, nan, 2, 2, 2, 5])
    np.testing.assert_allclose(out["middle"], [nan, nan, 4.5, 5.5, 5.5, 7.5])


def test_vwap_resets_each_utc_day() -> None:
    index = pd.DatetimeIndex(
        [
            "2026-01-01 00:00",
            "2026-01-01 12:00",
            "2026-01-02 00:00",
            "2026-01-02 01:00",
            "2026-01-03 00:00",
            "2026-01-03 01:00",
        ],
        tz="UTC",
    )
    df = frame(
        high=[10, 12, 20, 21, 31, 33],
        low=[8, 10, 18, 19, 29, 31],
        close=[9, 11, 19, 20, 30, 32],  # typical prices 9, 11, 19, 20, 30, 32
        volume=[1, 3, 2, 0, 0, 1],
        index=index,
    )
    np.testing.assert_allclose(
        ti.vwap(df),
        [
            9,  # 9*1 / 1
            10.5,  # (9*1 + 11*3) / 4
            19,  # new day
            19,  # zero volume adds nothing
            30,  # no volume yet today -> typical price
            32,  # 32*1 / 1
        ],
    )


def test_vwap_day_boundary_is_utc_even_for_other_timezones() -> None:
    # 23:30 UTC is already the next day in Berlin (UTC+1), but VWAP resets at 00:00 UTC
    utc = pd.DatetimeIndex(["2026-01-01 22:30", "2026-01-01 23:30", "2026-01-02 00:30"])
    df = frame(high=[10, 20, 30], low=[10, 20, 30], close=[10, 20, 30], index=utc)
    berlin = df.tz_localize("UTC").tz_convert("Europe/Berlin")
    assert berlin.index[1].day == 2  # local midnight already passed
    np.testing.assert_allclose(ti.vwap(berlin), [10, 15, 30])
    np.testing.assert_allclose(ti.vwap(df), [10, 15, 30])  # naive index taken as UTC


def test_vwap_needs_datetime_index() -> None:
    df = frame(high=[1, 2], low=[1, 2], index=pd.RangeIndex(2))
    with pytest.raises(ValueError, match="DatetimeIndex"):
        ti.vwap(df)


def test_volume_sma_hand_example() -> None:
    df = frame(high=[1] * 4, low=[1] * 4, volume=[1, 2, 3, 6])
    np.testing.assert_allclose(ti.volume_sma(df, length=2), [nan, 1.5, 2.5, 4.5])


def test_obv_hand_example() -> None:
    df = frame(high=[1] * 5, low=[1] * 5, close=[10, 11, 11, 9, 12], volume=[5, 2, 3, 4, 1])
    np.testing.assert_allclose(ti.obv(df), [5, 7, 7, 3, 4])


def test_obv_skips_missing_bars() -> None:
    df = frame(
        high=[1] * 6, low=[1] * 6, close=[nan, 10, 11, nan, 9, 12], volume=[7, 5, 2, 3, 4, 1]
    )
    # starts at the first valid bar; bar 4 compares with the last valid close (11)
    np.testing.assert_allclose(ti.obv(df), [nan, 5, 7, nan, 3, 4])
