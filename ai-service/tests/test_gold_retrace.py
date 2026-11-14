"""Gold 50% correction (app/research/gold_retrace.py) on hand-built 5m bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_lab as gl
from app.research import gold_retrace as gr


def bars() -> gl.Ctx:
    """Flat at 100 (bars 0-29), a rise to a high of 111.5 (bar 40), two lower highs, then a
    steady fall of 0.5 a bar to bar 69. ATR(D1) is 5, so the rise (12) is 2.4 x ATR."""
    c = np.r_[
        np.full(30, 100.0), 100 + np.arange(1, 12), [110.5, 110.0], 110 - 0.5 * np.arange(1, 28)
    ]
    o = np.r_[100.0, c[:-1]]
    h = np.r_[np.full(30, 100.5), c[30:41] + 0.5, c[41:43] + 0.3, np.maximum(o[43:], c[43:]) + 0.1]
    lo = np.r_[np.full(30, 99.5), c[30:] - 0.5]
    n = len(c)
    ts = pd.date_range("2024-03-05 14:00", periods=n, freq="5min", tz="UTC")
    m = pd.DataFrame({"ts_utc": ts, "close_utc": ts + pd.Timedelta("5min")})
    one, zero = np.ones(n), np.zeros(n, int)
    return gl.Ctx(m, o, h, lo, c, spread=np.zeros(n), atr5=one, atr1h=one, atr4h=one,
                  atrd=np.full(n, 5.0), ny_min=np.full(n, 600), ny_day=np.full(n, 20240305),
                  weekday=zero, deadline=np.full(n, n - 1), day_idx=zero,
                  d1=pd.DataFrame())  # fmt: skip


def test_the_leg_is_found_at_its_confirmation() -> None:
    cx = bars()
    lg = gr.legs(cx, gr.frame(cx, "5m"))
    big = lg[lg["ratio"] >= 0.5]
    assert big[["dir", "H", "L", "j", "m"]].to_numpy().tolist() == [[1, 111.5, 99.5, 42, 42]]
    assert big["ratio"].iloc[0] == pytest.approx(12 / 5)


def test_corr_sells_the_confirmation_and_takes_the_half() -> None:
    cx = bars()
    fr = gr.frame(cx, "5m")
    s = gr.signals(cx, gr.legs(cx, fr), "CORR", "5m", 0.5)
    assert s[["i", "dir", "entry"]].to_numpy().tolist() == [[42, -1.0, 110.0]]
    assert s["risk"].iloc[0] == pytest.approx(111.5 + 1.2 - 110)  # SL at H + 0.1 x leg
    t = gr.simulate(s, cx, fr, "FIXED")
    assert t[["j", "exit"]].to_numpy().tolist() == [[50, "tp"]]  # 105.5 reached at bar 50
    assert t["gross"].iloc[0] == pytest.approx(4.5 / 2.7)


def test_fib50_buys_the_half_and_stops_at_78_6() -> None:
    cx = bars()
    fr = gr.frame(cx, "5m")
    s = gr.signals(cx, gr.legs(cx, fr), "FIB50", "5m", 0.5)
    assert s[["i", "dir", "entry"]].to_numpy().tolist() == [[50, 1.0, 105.5]]
    assert s["risk"].iloc[0] == pytest.approx(105.5 - (111.5 - 0.786 * 12))
    t = gr.simulate(s, cx, fr, "FIXED")
    assert t[["j", "exit", "gross"]].to_numpy().tolist() == [[57, "sl", -1.0]]


def test_no_look_ahead_in_the_legs() -> None:
    cx = bars()
    first = cx.m.iloc[:45].reset_index(drop=True)
    cut = gl.Ctx(first, *(x[:45] for x in (cx.o, cx.h, cx.lo, cx.c)),
                 spread=cx.spread[:45], atr5=cx.atr5[:45], atr1h=cx.atr1h[:45], atr4h=cx.atr4h[:45],
                 atrd=cx.atrd[:45], ny_min=cx.ny_min[:45], ny_day=cx.ny_day[:45],
                 weekday=cx.weekday[:45], deadline=cx.deadline[:45], day_idx=cx.day_idx[:45],
                 d1=cx.d1)  # fmt: skip
    a = gr.legs(cut, gr.frame(cut, "5m"))
    b = gr.legs(cx, gr.frame(cx, "5m"))
    pd.testing.assert_frame_equal(a, b[b["m"] < 45].reset_index(drop=True))
