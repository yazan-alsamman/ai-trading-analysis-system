"""Small hand-built series where the signal bars are known exactly."""

import numpy as np
import pandas as pd
import pytest
import trading_indicators as ti

import trading_strategies as ts


def bars(close, high=None, low=None, volume=None) -> pd.DataFrame:
    close = np.asarray(close, dtype=float)
    high = close + 0.5 if high is None else np.asarray(high, dtype=float)
    low = close - 0.5 if low is None else np.asarray(low, dtype=float)
    volume = np.ones(len(close)) if volume is None else np.asarray(volume, dtype=float)
    index = pd.date_range("2026-01-01", periods=len(close), freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


def signal_bars(out: pd.DataFrame) -> dict[int, tuple[int, str]]:
    sig = out["signal"].to_numpy()
    return {int(t): (int(sig[t]), out["reason"].iloc[t]) for t in np.flatnonzero(sig)}


def assert_frame_contract(out: pd.DataFrame, df: pd.DataFrame) -> None:
    assert list(out.columns) == ["signal", "strength", "reason", "details"]
    assert out.index.equals(df.index)
    quiet = out["signal"] == 0
    assert (out.loc[quiet, "strength"] == 0).all()
    assert out.loc[quiet, "reason"].isna().all() and out.loc[quiet, "details"].isna().all()
    assert out["strength"].between(0, 1).all()


# --- ma_crossover ----------------------------------------------------------------------------


def test_ma_crossover_step_up_then_down() -> None:
    # flat 100 (EMAs equal: no cross), step to 110 at bar 10, step to 90 at bar 20
    df = bars([100] * 10 + [110] * 10 + [90] * 10)
    out = ts.run("ma_crossover", df, fast=2, slow=4)
    assert_frame_contract(out, df)
    assert signal_bars(out) == {10: (1, "ema_cross_up"), 20: (-1, "ema_cross_down")}
    d = out["details"].iloc[10]
    # fast EMA (alpha 2/3) jumps further than the slow one (alpha 0.4): 106.67 vs 104
    assert d["fast_prev"] == d["slow_prev"] == 100
    assert d["fast"] == pytest.approx(100 + 10 * 2 / 3, abs=1e-6)
    assert d["slow"] == pytest.approx(104.0, abs=1e-6)


def test_ma_crossover_adx_filter() -> None:
    df = bars([100] * 10 + [110] * 10 + [90] * 10)
    assert signal_bars(ts.run("ma_crossover", df, fast=2, slow=4, adx_min=100)) == {}
    adx = ti.adx(df, 14)["adx"]
    out = ts.run("ma_crossover", df, fast=2, slow=4, adx_min=1)
    # the ADX needs 27 bars, so only crossings after that can pass a non-zero filter
    assert all(t >= 27 and adx.iloc[t] >= 1 for t in signal_bars(out))


# --- rsi_reversal ----------------------------------------------------------------------------


def test_rsi_reversal_with_length_1() -> None:
    # RSI(1) is 100 on an up bar, 0 on a down bar and 50 on a flat one
    close = [10, 9, 8, 9, 9, 10, 11, 10]  # RSI: nan 0 0 100 50 100 100 0
    df = bars(close)
    out = ts.run("rsi_reversal", df, length=1, oversold=30, overbought=70)
    assert_frame_contract(out, df)
    assert signal_bars(out) == {
        3: (1, "rsi_cross_up_oversold"),  # 0 -> 100 crosses 30 up
        4: (-1, "rsi_cross_down_overbought"),  # 100 -> 50 crosses 70 down
        7: (-1, "rsi_cross_down_overbought"),  # 100 -> 0
    }
    assert out["details"].iloc[3] == {"rsi_prev": 0.0, "rsi": 100.0, "level": 30.0, "extreme": 0.0}
    assert out["strength"].iloc[3] == 1.0  # (30 - 0) / 30
    assert out["details"].iloc[7]["extreme"] == 100.0  # bars 5 and 6 were above 70


def test_rsi_reversal_strength_is_depth_of_excursion() -> None:
    # RSI(2) on a mild dip: one strategy signal with a strength strictly between 0 and 1
    df = bars([10, 10.4, 10.1, 9.9, 9.95, 10.3, 10.5])
    rsi = ti.rsi(df["close"], 2).to_numpy()
    out = ts.run("rsi_reversal", df, length=2, oversold=40, overbought=95)
    [(t, (side, _))] = signal_bars(out).items()
    assert side == 1 and rsi[t - 1] < 40 <= rsi[t]
    lowest = np.nanmin(rsi[:t])
    assert out["strength"].iloc[t] == pytest.approx((40 - lowest) / 40, abs=1e-6)
    assert 0 < out["strength"].iloc[t] < 1


# --- macd_cross ------------------------------------------------------------------------------


def test_macd_cross_on_steps() -> None:
    # flat (MACD = signal = 0), step up at bar 40: MACD jumps above its lagging signal line
    df = bars([100] * 40 + [110] * 30)
    out = ts.run("macd_cross", df, fast=3, slow=6, signal=4)
    assert_frame_contract(out, df)
    hits = signal_bars(out)
    assert hits[40] == (1, "macd_cross_up")
    assert min(hits) == 40
    # zero filter: that buy happens above zero, so it is dropped
    filtered = signal_bars(ts.run("macd_cross", df, fast=3, slow=6, signal=4, zero_filter=1))
    assert 40 not in filtered


def test_macd_cross_matches_line_crossings_on_random_data(ohlcv) -> None:
    out = ts.run("macd_cross", ohlcv)
    m = ti.macd(ohlcv["close"])
    diff = (m["macd"] - m["signal"]).to_numpy()
    up = np.flatnonzero((diff[:-1] <= 0) & (diff[1:] > 0)) + 1
    down = np.flatnonzero((diff[:-1] >= 0) & (diff[1:] < 0)) + 1
    assert set(np.flatnonzero(out["signal"] == 1)) == set(up)
    assert set(np.flatnonzero(out["signal"] == -1)) == set(down)
    zf = ts.run("macd_cross", ohlcv, zero_filter=1)
    line = m["macd"].to_numpy()
    assert all(line[t] < 0 for t in np.flatnonzero(zf["signal"] == 1))
    assert all(line[t] > 0 for t in np.flatnonzero(zf["signal"] == -1))


# --- bollinger_reversion ---------------------------------------------------------------------


def test_bollinger_reversion_buy_and_sell() -> None:
    # window [10, 10, 7]: mean 9, sigma sqrt(2) -> lower 7.586 > 7 (outside);
    # next window [10, 7, 10]: lower 7.586 <= 10 (back inside) -> buy at bar 4
    df = bars([10, 10, 10, 7, 10, 10, 10, 13, 10])
    out = ts.run("bollinger_reversion", df, length=3, std=1)
    assert_frame_contract(out, df)
    assert signal_bars(out) == {
        4: (1, "close_back_above_lower_band"),
        8: (-1, "close_back_below_upper_band"),
    }
    sigma = np.sqrt(2)
    assert out["strength"].iloc[4] == pytest.approx((9 - sigma - 7) / sigma, abs=1e-6)
    assert out["details"].iloc[4]["close_prev"] == 7.0


# --- supertrend_flip -------------------------------------------------------------------------


def test_supertrend_flip() -> None:
    # the hand example from the indicators tests: direction nan -1 -1 1 1 -1
    df = bars(
        close=[9, 10, 11.5, 13.5, 11.2, 9.5],
        high=[10, 11, 12, 14, 13, 11],
        low=[8, 9, 10, 12, 11, 9],
    )
    out = ts.run("supertrend_flip", df, length=1, multiplier=1)
    assert_frame_contract(out, df)
    assert signal_bars(out) == {3: (1, "supertrend_flip_up"), 5: (-1, "supertrend_flip_down")}
    assert out["details"].iloc[3] == {
        "close": 13.5,
        "supertrend": 10.5,
        "atr": 2.5,
        "direction": 1,
    }
    assert out["strength"].iloc[3] == 1.0  # |13.5 - 10.5| / (1 * 2.5) > 1, capped


# --- donchian_breakout -----------------------------------------------------------------------


def test_donchian_breakout_first_close_only() -> None:
    high = [10, 10, 10, 10, 12, 13, 11, 10, 9, 8]
    low = [8, 8, 8, 8, 10, 11, 9, 8, 7, 5]
    close = [9, 9, 9, 9, 11.5, 12.5, 10, 9, 7.5, 5.5]
    df = bars(close, high, low)
    out = ts.run("donchian_breakout", df, length=3)
    assert_frame_contract(out, df)
    # bar 4 closes 11.5 above the previous 3-bar high (10) -> buy. Bar 5 is still above (12.5 >
    # 12): same breakout, no new event. Bar 8 closes 7.5 below the previous 3-bar low
    # min(11, 9, 8) = 8 -> sell; bar 9 (5.5 < 7) is the same breakdown, no new event.
    assert signal_bars(out) == {
        4: (1, "close_above_channel_high"),
        8: (-1, "close_below_channel_low"),
    }
    assert out["details"].iloc[4]["channel_high"] == 10.0


def test_donchian_volume_filter() -> None:
    high = [10, 10, 10, 10, 12, 10, 10, 10, 13]
    low = [8] * 9
    close = [9, 9, 9, 9, 11, 9, 9, 9, 12]
    volume = [10, 10, 10, 10, 15, 10, 10, 10, 40]
    df = bars(close, high, low, volume)
    assert set(signal_bars(ts.run("donchian_breakout", df, length=3))) == {4, 8}
    # volume must exceed 2 x the average of the previous 3 bars: 15 > 20 no, 40 > 20 yes
    assert set(signal_bars(ts.run("donchian_breakout", df, length=3, volume_factor=2))) == {8}
