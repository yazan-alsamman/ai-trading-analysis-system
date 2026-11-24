"""Gold pullback continuation (app/research/gold_pullback.py) on hand-built 5m bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_lab as gl
from app.research import gold_pullback as gp
from app.research import gold_retrace as gr


def bars() -> gl.Ctx:
    """Flat at 100, a rise to a high of 111.5 (bar 40, a leg of 12 = 2.4 x ATR(D1)), a pullback
    to 108.9 (bar 44, 22% of the leg), then a steady rise of 0.6 a bar."""
    c = list(np.r_[np.full(30, 100.0), 100 + np.arange(1, 12)])
    o = [100.0, *c[:-1]]
    h = [100.5] * 30 + [x + 0.5 for x in c[30:]]
    lo = [99.5] * 30 + [x - 0.5 for x in c[30:]]
    for row in ((111.0, 111.1, 110.3, 110.5), (110.5, 110.6, 109.8, 110.0),
                (110.0, 110.1, 109.3, 109.5), (109.5, 109.6, 108.9, 109.0),
                (109.0, 109.8, 109.0, 109.7), (109.7, 110.4, 109.6, 110.3)):  # fmt: skip
        o.append(row[0]), h.append(row[1]), lo.append(row[2]), c.append(row[3])
    for _ in range(20):
        o.append(c[-1]), c.append(c[-1] + 0.6), h.append(c[-1] + 0.1), lo.append(o[-1] - 0.1)
    o, h, lo, c = (np.array(x) for x in (o, h, lo, c))
    n = len(c)
    ts = pd.date_range("2024-03-05 14:00", periods=n, freq="5min", tz="UTC")
    m = pd.DataFrame({"ts_utc": ts, "close_utc": ts + pd.Timedelta("5min")})
    one, zero = np.ones(n), np.zeros(n, int)
    return gl.Ctx(m, o, h, lo, c, spread=np.zeros(n), atr5=one, atr1h=one, atr4h=one,
                  atrd=np.full(n, 5.0), ny_min=np.full(n, 600), ny_day=np.full(n, 20240305),
                  weekday=zero, deadline=np.full(n, n - 1), day_idx=zero,
                  d1=pd.DataFrame())  # fmt: skip


def test_bar_enters_at_the_first_close_above_the_previous_high() -> None:
    cx = bars()
    t = gp.run(cx, {}, "5m", 0.5, "BAR", "HIGH")
    assert t[["i", "dir", "j", "exit"]].to_numpy().tolist() == [[45, 1.0, 48, "tp"]]
    fr = gr.frame(cx, "5m")
    cand = gp.candidates(cx, fr, gr.legs(cx, fr), "BAR")
    assert cand[["i", "entry", "pb", "H"]].to_numpy().tolist() == [[45, 109.7, 108.9, 111.5]]
    assert cand["sl"].iloc[0] < 108.9


def test_swing_puts_a_stop_above_the_confirming_bars() -> None:
    cx = bars()
    fr = gr.frame(cx, "5m")
    cand = gp.candidates(cx, fr, gr.legs(cx, fr), "SWING")
    assert cand[["i", "entry", "pb", "touch"]].to_numpy().tolist() == [[47, 110.4, 108.9, True]]


def test_targets() -> None:
    cx = bars()
    fr = gr.frame(cx, "5m")
    cand = gp.candidates(cx, fr, gr.legs(cx, fr), "BAR")
    risk = 109.7 - cand["sl"].iloc[0]
    assert gp.signals(cx, cand, "5m", 0.5, "HIGH")["tp_r"].iloc[0] == pytest.approx(1.8 / risk)
    assert gp.signals(cx, cand, "5m", 0.5, "ABCD")["tp_r"].iloc[0] == pytest.approx(11.2 / risk)
    assert np.isinf(gp.signals(cx, cand, "5m", 0.5, "NONE")["tp_r"].iloc[0])
    assert gp.signals(cx, cand, "5m", 2.5, "HIGH").empty  # the leg is 2.4 x ATR(D1)
