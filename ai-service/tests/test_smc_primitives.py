import numpy as np
import pandas as pd

from app.smc.primitives import (
    atr,
    htf_swing_levels,
    mirror,
    previous_day_levels,
    swing_highs,
    swing_lows,
)


def _bars(ts, o, h, lo, c):
    return pd.DataFrame(
        {
            "ts_utc": pd.DatetimeIndex(ts, tz="UTC"),
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "spread": 0.0,
        }
    )


def test_atr_constant_range_and_no_values_before_period():
    n = 20
    high = np.full(n, 101.0)
    low = np.full(n, 100.0)
    close = np.full(n, 100.5)
    out = atr(high, low, close, 14)
    assert np.isnan(out[:13]).all()
    assert np.allclose(out[13:], 1.0)


def test_atr_uses_only_past_bars():
    rng = np.random.default_rng(1)
    c = 100 + rng.normal(0, 1, 200).cumsum()
    h, lo = c + rng.uniform(0.1, 1, 200), c - rng.uniform(0.1, 1, 200)
    full = atr(h, lo, c, 14)
    part = atr(h[:120], lo[:120], c[:120], 14)
    assert np.allclose(full[:120], part, equal_nan=True)


def test_swing_lows_strict_and_never_at_the_edges():
    low = np.array([5, 4, 3, 2, 3, 4, 5, 1, 1, 2, 3], dtype=float)
    mask = swing_lows(low, 2)
    assert np.flatnonzero(mask).tolist() == [3]  # the tie at 7-8 is not a pivot
    assert not mask[-2:].any()


def test_swing_highs_mirror_swing_lows():
    high = np.array([1, 2, 5, 2, 1, 3, 1], dtype=float)
    assert np.flatnonzero(swing_highs(high, 2)).tolist() == [2]


def test_htf_level_available_after_confirming_bar_closes():
    ts = pd.date_range("2024-01-02 00:00", periods=7, freq="1h")
    lows = [5, 4, 3, 2, 3, 4, 5]
    bars = _bars(ts, lows, [x + 1 for x in lows], lows, lows)
    levels = [
        lv for lv in htf_swing_levels(bars, pd.Timedelta(hours=1), 2, "1h") if lv.kind == "low"
    ]
    assert len(levels) == 1
    lv = levels[0]
    assert lv.price == 2
    assert lv.origin_ts == pd.Timestamp("2024-01-02 03:00", tz="UTC")
    # bar 5 (03:00 + 2 bars) closes at 06:00
    assert lv.available_at == pd.Timestamp("2024-01-02 06:00", tz="UTC")


def test_previous_day_levels_available_when_the_day_ends():
    # 21:30-22:30 UTC on a winter day spans the 17:00 New York day boundary (22:00 UTC).
    ts = pd.date_range("2024-01-09 21:30", periods=4, freq="15min")
    bars = _bars(
        ts, [10, 11, 12, 13], [10.5, 11.5, 20, 13.5], [9.5, 8, 11.5, 12.5], [10, 11, 12, 13]
    )
    levels = previous_day_levels(bars, pd.Timedelta(minutes=15))
    first = [lv for lv in levels if lv.available_at == pd.Timestamp("2024-01-09 22:00", tz="UTC")]
    assert {(lv.kind, lv.price) for lv in first} == {("high", 11.5), ("low", 8.0)}


def test_mirror_swaps_high_and_low():
    bars = _bars(["2024-01-02"], [10.0], [12.0], [9.0], [11.0])
    m = mirror(bars)
    assert (m["high"].iloc[0], m["low"].iloc[0]) == (-9.0, -12.0)
    pd.testing.assert_frame_equal(mirror(m), bars)


def test_session_levels_available_when_the_session_ends():
    from app.smc.primitives import session_levels

    # London 02:00-05:00 New York = 07:00-10:00 UTC in January.
    ts = pd.date_range("2024-01-10 06:45", periods=14, freq="15min")
    highs = [1.0] + [2.0] * 12 + [9.0]
    bars = _bars(ts, highs, highs, [h - 0.5 for h in highs], highs)
    london = [lv for lv in session_levels(bars, pd.Timedelta(minutes=15)) if lv.source == "london"]
    assert {(lv.kind, lv.price) for lv in london} == {("high", 2.0), ("low", 1.5)}
    assert all(lv.available_at == pd.Timestamp("2024-01-10 10:00", tz="UTC") for lv in london)
