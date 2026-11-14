"""Gold night reversion (app/research/gold_night.py) on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_lab as gl
from app.research import gold_night as gn

# One night: 12 box bars 19:00-19:55 (range 99-101), then window bars from 20:00 to 01:55.
BOX_MIN = [19 * 60 + 5 * k for k in range(12)]


def night(window: list[tuple[float, float, float, float]]) -> gl.Ctx:
    """Box bars between 99 and 101, then ``window`` bars (open, high, low, close) from 20:00;
    the last one is the 01:55 bar."""
    box = [(100.0, 101.0 if k == 3 else 100.5, 99.0 if k == 7 else 99.5, 100.0) for k in range(12)]
    bars = box + window
    n = len(bars)
    mins = BOX_MIN + [20 * 60 + 5 * k for k in range(len(window) - 1)] + [115]
    o, h, lo, c = (np.array([b[q] for b in bars]) for q in range(4))
    ts = pd.date_range("2024-03-05 00:00", periods=n, freq="5min", tz="UTC")
    m = pd.DataFrame({"ts_utc": ts, "close_utc": ts + pd.Timedelta("5min")})
    one = np.ones(n)
    zero = np.zeros(n, int)
    return gl.Ctx(m, o, h, lo, c, spread=np.zeros(n), atr5=one, atr1h=one, atr4h=one, atrd=one,
                  ny_min=np.array(mins), ny_day=np.full(n, 20240304), weekday=zero,
                  deadline=np.full(n, n - 1), day_idx=zero, d1=pd.DataFrame())  # fmt: skip


def test_box_and_window() -> None:
    cx = night([(100, 100.5, 99.8, 100.2)] * 3)
    hi, lo, window, last = gn.night_parts(cx, "20:00")
    assert (hi[0], lo[0]) == (101.0, 99.0)
    assert window.tolist() == [False] * 12 + [True] * 3
    assert last.tolist() == [14] * 15


def test_touch_sells_the_upper_edge_and_takes_the_middle() -> None:
    # 20:00 touches 101 and stays below the SL (101 + 0.5 x 2 = 102); 20:05 reaches the middle
    cx = night([(100.5, 101.2, 100.4, 101.0), (101.0, 101.0, 99.9, 100.1), (100, 100, 100, 100)])
    s = gn.signals(cx, "20:00", "touch", 0.5, "mid")
    assert s[["i", "dir", "entry", "risk", "tp_r"]].to_numpy().tolist() == [
        [12, -1.0, 101.0, 1.0, 1.0]
    ]
    t = gn.simulate(s, cx)
    assert t[["j", "exit"]].to_numpy().tolist() == [[13, "tp"]]
    assert t["gross"].iloc[0] == pytest.approx(1.0)


def test_touch_bar_reaching_the_sl_is_a_full_loss() -> None:
    cx = night([(100.5, 102.5, 100.4, 100.2), (100, 100, 99.5, 99.6), (100, 100, 100, 100)])
    t = gn.simulate(gn.signals(cx, "20:00", "touch", 0.5, "mid"), cx)
    assert t[["j", "exit", "gross"]].to_numpy().tolist() == [[12, "sl", -1.0]]


def test_reclaim_enters_at_the_close_back_inside() -> None:
    # 20:00 trades to 98.5 and closes at 99.5: buy at 99.5, SL 98.5 - 0.1, target the far edge 101
    cx = night([(99.2, 99.6, 98.5, 99.5), (99.5, 100, 99.4, 99.9), (100, 100, 100, 100)])
    s = gn.signals(cx, "20:00", "reclaim", 0.0, "far")
    assert s[["i", "dir", "entry"]].to_numpy().tolist() == [[12, 1.0, 99.5]]
    assert s["risk"].iloc[0] == pytest.approx(1.1)
    assert s["tp_r"].iloc[0] == pytest.approx(1.5 / 1.1)
    t = gn.simulate(s, cx)  # the target is not reached: out at the 01:55 bar's close
    assert t[["j", "exit"]].to_numpy().tolist() == [[14, "time"]]


def test_no_look_ahead_in_the_box() -> None:
    a = night([(100, 100.5, 99.8, 100.2)] * 3)
    b = night([(100, 100.5, 99.8, 100.2)] * 2 + [(100, 120, 80, 100)])  # a wild last bar
    assert gn.night_parts(a, "20:00")[0][0] == gn.night_parts(b, "20:00")[0][0]


def test_portfolio_drawdown() -> None:
    t = pd.DataFrame({"i": [0, 1, 2, 3], "j": [1, 2, 3, 4], "net_slip": [1.0, -2.0, -1.0, 4.0]})
    p = gn.portfolio([t])
    assert (p["sum"], p["dd"]) == (2.0, 3.0)
