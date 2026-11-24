import numpy as np
import pandas as pd
import pytest

from app.smc.primitives import (
    LevelBook,
    atr,
    previous_day_levels,
    swing_highs,
    swing_levels,
    swing_lows,
)


def frame(highs, lows, start="2024-01-15 14:00", freq="15min", closes=None) -> pd.DataFrame:
    """Bars from explicit highs and lows (opens and closes at the middle unless given)."""
    ts = pd.date_range(start, periods=len(highs), freq=freq, tz="UTC")
    high, low = np.asarray(highs, float), np.asarray(lows, float)
    mid = (high + low) / 2
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "close_utc": ts + pd.Timedelta(freq),
            "open": mid,
            "high": high,
            "low": low,
            "close": mid if closes is None else np.asarray(closes, float),
        }
    )


def random_walk(n: int, seed: int, freq: str = "15min") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0, 1, n)
    low = np.minimum(open_, close) - rng.uniform(0, 1, n)
    f = frame(high, low, freq=freq, closes=close)
    f["open"] = open_
    return f


# ---- ATR ---------------------------------------------------------------------------------------


def test_atr_is_wilder_and_nan_until_the_period() -> None:
    f = frame([12, 13, 11, 14, 12], [10, 10, 9, 11, 10], closes=[11, 12, 10, 13, 11])
    out = atr(f["high"].to_numpy(), f["low"].to_numpy(), f["close"].to_numpy(), 3)
    # true ranges: 2, max(3, 2, 1)=3, max(2, 1, 3)=3, max(3, 4, 1)=4, max(2, 1, 3)=3
    assert np.isnan(out[:2]).all()
    assert out[2] == pytest.approx((2 + 3 + 3) / 3)
    assert out[3] == pytest.approx((out[2] * 2 + 4) / 3)
    assert out[4] == pytest.approx((out[3] * 2 + 3) / 3)


# ---- swings ------------------------------------------------------------------------------------


def test_swing_high_needs_strictly_lower_highs_on_both_sides() -> None:
    high = np.array([1, 2, 5, 3, 4, 4, 2, 1], float)
    assert np.flatnonzero(swing_highs(high, 2)).tolist() == [2]  # 4, 4 is a tie: not a swing
    assert np.flatnonzero(swing_highs(high, 1)).tolist() == [2]
    assert not swing_highs(high, 2)[-2:].any()  # never marked without k bars after


def test_swing_lows_mirror_swing_highs() -> None:
    low = np.array([5, 4, 1, 3, 2, 4, 5], float)
    assert np.flatnonzero(swing_lows(low, 2)).tolist() == [2]


# ---- liquidity levels -------------------------------------------------------------------------


def test_swing_level_is_available_when_the_confirming_bar_closes() -> None:
    h1 = frame([1, 2, 3, 9, 3, 2, 1, 2], [0, 1, 2, 8, 2, 1, 0, 1], freq="1h")
    levels = [lv for lv in swing_levels(h1, 3, "1h") if lv.side == "high"]
    assert len(levels) == 1
    lv = levels[0]
    assert lv.price == 9 and lv.origin_utc == h1["ts_utc"][3]
    assert lv.available_utc == h1["close_utc"][6]  # bar 3 + k = 6


def test_previous_day_levels_are_available_when_the_day_closes() -> None:
    d1 = frame([2010, 2020], [1990, 1995], start="2024-01-14 22:00", freq="1D")
    levels = previous_day_levels(d1)
    assert [(lv.side, lv.price) for lv in levels[:2]] == [("high", 2010), ("low", 1990)]
    assert levels[0].available_utc == pd.Timestamp("2024-01-15 22:00", tz="UTC")


def test_level_book_adds_spends_and_expires_levels() -> None:
    entry = frame([101, 101, 101, 101, 104], [99, 99, 99, 95, 99])
    t = entry["ts_utc"]
    pd_low = previous_day_levels(frame([110], [96], start="2024-01-11 22:00", freq="1D"))
    future = previous_day_levels(frame([103], [98], start="2024-01-15 10:00", freq="1h"))
    late = [lv for lv in future if lv.side == "high"]
    late = [type(lv)(lv.price, "high", "1h", lv.origin_utc, t[2], lv.day) for lv in late]
    book = LevelBook(entry, [lv for lv in pd_low if lv.side == "low"] + late, max_age_days=5)
    assert book.step(0) == {"high": [], "low": []}
    assert [lv.price for lv in book.active["low"]] == [96]
    assert book.active["high"] == []  # the 103 level is not available before bar 2
    book.step(1)
    book.step(2)
    assert [lv.price for lv in book.active["high"]] == [103]
    traded = book.step(3)  # low 95 trades through 96
    assert [lv.price for lv in traded["low"]] == [96] and book.active["low"] == []
    traded = book.step(4)  # high 104 trades through 103
    assert [lv.price for lv in traded["high"]] == [103]


def test_levels_older_than_the_age_limit_are_dropped() -> None:
    d1 = frame([2010], [1990], start="2024-01-08 22:00", freq="1D")  # trading day Tue 2024-01-09
    entry = frame([2000] * 2, [1995] * 2, start="2024-01-16 15:00")  # Tue 01-16: 5 trading days on
    book = LevelBook(entry, previous_day_levels(d1), max_age_days=5)
    book.step(0)
    assert len(book.active["low"]) == 1
    entry_later = frame([2000], [1995], start="2024-01-17 15:00")  # 6 trading days on
    book = LevelBook(entry_later, previous_day_levels(d1), max_age_days=5)
    book.step(0)
    assert book.active == {"high": [], "low": []}


# ---- no look-ahead ----------------------------------------------------------------------------


@pytest.mark.parametrize("n", [50, 333, 777])
def test_atr_and_swings_never_change_when_bars_are_appended(n: int) -> None:
    full = random_walk(1000, seed=1)
    part = full.iloc[:n]
    for k in (2, 3):
        a, b = swing_highs(full["high"].to_numpy(), k), swing_highs(part["high"].to_numpy(), k)
        assert (a[: n - k] == b[: n - k]).all()  # usable part of the prefix
    x = atr(*(full[c].to_numpy() for c in ("high", "low", "close")), 14)
    y = atr(*(part[c].to_numpy() for c in ("high", "low", "close")), 14)
    np.testing.assert_array_equal(x[:n], y)


@pytest.mark.parametrize("n", [80, 400])
def test_levels_and_the_book_never_change_when_bars_are_appended(n: int) -> None:
    h1 = random_walk(600, seed=2, freq="1h")
    m15 = random_walk(4 * 600, seed=3)
    m15["ts_utc"] = pd.date_range(h1["ts_utc"][0], periods=len(m15), freq="15min", tz="UTC")
    m15["close_utc"] = m15["ts_utc"] + pd.Timedelta("15min")
    cut = h1["close_utc"].iloc[n - 1]
    full_levels = swing_levels(h1, 3, "1h")
    part_levels = swing_levels(h1.iloc[:n], 3, "1h")
    assert part_levels == [lv for lv in full_levels if lv.available_utc <= cut]

    entries = m15[m15["close_utc"] <= cut]
    a = LevelBook(m15, full_levels, 5)
    b = LevelBook(entries, part_levels, 5)
    for j in range(len(entries)):
        assert a.step(j) == b.step(j)
