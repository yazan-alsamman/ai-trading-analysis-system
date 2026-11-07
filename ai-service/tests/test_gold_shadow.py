"""Gold shadow candidates (app/research/gold_shadow.py) on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_lab as gl
from app.research import gold_shadow as gs


def ctx(o, h, lo, c, ny_min, d1=None) -> gl.Ctx:
    """Five-minute bars from 2024-03-04 14:00 UTC; New York minutes as given, a Monday."""
    n = len(c)
    ts = pd.date_range("2024-03-04 14:00", periods=n, freq="5min", tz="UTC")
    m = pd.DataFrame({"ts_utc": ts, "close_utc": ts + pd.Timedelta("5min")})
    arr = [np.asarray(x, float) for x in (o, h, lo, c)]
    one = np.ones(n)
    return gl.Ctx(m, *arr, spread=np.zeros(n), atr5=one, atr1h=one, atr4h=one, atrd=one,
                  ny_min=np.asarray(ny_min), ny_day=np.full(n, 20240304), weekday=np.zeros(n, int),
                  deadline=np.full(n, n - 1), day_idx=np.zeros(n, int),
                  d1=d1 if d1 is not None else pd.DataFrame())  # fmt: skip


def test_open_signal_side_entry_and_stop() -> None:
    # bar 2 is the 09:30 candle: it closes up, above the EMA of the bars before it
    o = [98.0, 98.2, 99.0, 99.6, 100]
    h = [98.3, 98.6, 99.8, 100, 100]
    lo = [97.9, 98.1, 98.5, 99.4, 100]
    c = [98.2, 98.5, 99.6, 99.9, 100]
    cx = ctx(o, h, lo, c, [9 * 60 + 20, 9 * 60 + 25, 9 * 60 + 30, 9 * 60 + 35, 9 * 60 + 40])
    for side in ("EMA", "COLOR"):
        s = gs.open_signals(cx, "09:30", side, 0.0)
        assert s[["i", "dir", "entry", "risk"]].to_numpy().tolist() == [[2, 1.0, 99.6, 99.6 - 98.5]]
    assert gs.open_signals(cx, "09:30", "EMA", 2.0).empty  # range 1.3 < 2 x ATR(5m) = 2
    # no look-ahead: later bars (a crash) do not change the signal
    more = ctx(o + [90, 80], h + [100, 90], lo + [89, 79], c + [90, 80],
               [9 * 60 + m for m in (20, 25, 30, 35, 40, 45, 50)])  # fmt: skip
    a = gs.open_signals(cx, "09:30", "EMA", 0.0).drop(columns="end")
    b = gs.open_signals(more, "09:30", "EMA", 0.0).drop(columns="end")
    pd.testing.assert_frame_equal(a, b)


def test_bar_trail_follows_each_closed_low_and_exits_at_a_gap() -> None:
    # entry at 100 (bar 1's open), SL 99; lows rise to 100.5, then bar 4 trades down to 100.2
    o = [99.5, 100, 100.6, 101, 100.8]
    h = [100, 100.8, 101.2, 101.4, 100.9]
    lo = [99, 99.5, 100.5, 100.9, 100.2]
    c = [99.9, 100.6, 101, 101.2, 100.4]
    cx = ctx(o, h, lo, c, [570, 575, 580, 585, 590])
    sig = pd.DataFrame({"strategy": "OPEN", "i": [0], "dir": [1.0], "entry": [100.0],
                        "risk": [1.0], "tp_r": [np.nan], "end": [4]})  # fmt: skip
    t = gs.simulate_bar(sig, cx)
    # after bar 3 the SL is 100.9; bar 4 opens below it (100.8): the exit is the open
    assert t[["j", "exit"]].to_numpy().tolist() == [[4, "sl"]]
    assert t["gross"].iloc[0] == pytest.approx(0.8)
    assert t["cost"].iloc[0] == pytest.approx(gl.COMMISSION)


def test_nfp_rule_gives_the_known_release_days() -> None:
    days = gs.nfp_days(2023, 2024)
    assert {20230804, 20240105, 20240202, 20240308} <= days
    assert len(gs.nfp_days(2024, 2024)) == 12


def test_week_levels_are_the_previous_weeks_range() -> None:
    # trading days Mon 2024-03-04 to Fri 03-08, then Mon 03-11 and Tue 03-12 (closes 17:00 NY)
    dates = ["2024-03-04", "2024-03-05", "2024-03-06", "2024-03-07", "2024-03-08", "2024-03-11",
             "2024-03-12"]  # fmt: skip
    days = pd.to_datetime(dates).tz_localize(gl.NY) + pd.Timedelta("17h")
    d1 = pd.DataFrame({"close_utc": days.tz_convert("UTC"), "high": [5, 6, 9, 7, 8, 20, 21],
                       "low": [3, 2, 4, 1, 5, 15, 16]})  # fmt: skip
    cx = ctx([1], [1], [1], [1], [600], d1=d1)
    lv = gs.week_levels(cx)
    assert np.isnan(lv["PWH"][:5]).all()
    assert lv["PWH"][5:].tolist() == [9, 9] and lv["PWL"][5:].tolist() == [1, 1]


def test_asia_range_is_known_at_two_new_york() -> None:
    # day 0: bars at 19:00, 01:00 and 03:00 New York (the last is outside the range)
    cx = ctx([1, 1, 1], [5, 7, 9], [3, 2, 1], [4, 4, 4], [19 * 60, 60, 180],
             d1=pd.DataFrame({"high": [0.0]}))  # fmt: skip
    lv = gs.asia_levels(cx)
    assert (lv["ASH"].tolist(), lv["ASL"].tolist()) == ([7.0], [2.0])
