"""Gold time-of-day strategies (app/research/gold_time.py) on one hand-built trading day."""

import numpy as np
import pandas as pd

from app.research import gold_lab as gl
from app.research import gold_time as gt


def day() -> gl.Ctx:
    """One trading day of 5m bars, 18:00 to 17:00 New York: price rises 0.1 a bar until 10:00,
    then falls 0.1 a bar."""
    n = 23 * 12
    ny_min = (18 * 60 + 5 * np.arange(n)) % 1440
    up = int(np.flatnonzero(ny_min == 9 * 60 + 55)[0])  # the bar closing at 10:00
    c = np.r_[100 + 0.1 * np.arange(1, up + 2), 100 + 0.1 * (up + 1) - 0.1 * np.arange(1, n - up)]
    o = np.r_[100.0, c[:-1]]
    ts = pd.date_range("2024-03-04 23:00", periods=n, freq="5min", tz="UTC")
    m = pd.DataFrame({"ts_utc": ts, "close_utc": ts + pd.Timedelta("5min")})
    last = int(np.flatnonzero(ny_min == 16 * 60 + 40)[0])
    one = np.ones(n)
    return gl.Ctx(m, o, np.maximum(o, c) + 0.05, np.minimum(o, c) - 0.05, c, spread=np.zeros(n),
                  atr5=one, atr1h=one, atr4h=np.full(n, 10.0), atrd=np.full(n, 30.0),
                  ny_min=ny_min, ny_day=np.full(n, 20240305), weekday=np.ones(n, int),
                  deadline=np.full(n, last), day_idx=np.zeros(n, int),
                  d1=pd.DataFrame())  # fmt: skip


def test_the_clock_finds_the_bar_closing_at_a_time() -> None:
    cx = day()
    ck = gt.Clock(cx)
    assert ck.first[0] == 0
    assert cx.ny_min[ck.at(gt.hm(10))[0]] == 9 * 60 + 55
    assert cx.ny_min[ck.at(gt.hm(2))[0]] == 1 * 60 + 55


def test_a_follows_the_morning_move() -> None:
    cx = day()
    s = gt.signals(cx, gt.Clock(cx), "A", {"signal": "S1", "entry": gt.hm(14, 30), "mgmt": "TIME"})
    assert s["dir"].tolist() == [1.0]  # up from 18:00 to 10:00
    assert cx.ny_min[s["i"].iloc[0]] == 14 * 60 + 25
    assert cx.ny_min[s["end"].iloc[0]] == 16 * 60 + 40
    assert s["risk"].iloc[0] == 7.5


def test_b_with_and_against_london() -> None:
    cx = day()
    ck = gt.Clock(cx)
    st = {"mode": "CONT", "exit": gt.hm(12), "mgmt": "TIME"}
    cont = gt.signals(cx, ck, "B", st)
    rev = gt.signals(cx, ck, "B", {**st, "mode": "REV"})
    assert cont["dir"].tolist() == [1.0] and rev["dir"].tolist() == [-1.0]
    assert cx.ny_min[cont["end"].iloc[0]] == 11 * 60 + 55


def test_c_holds_the_night() -> None:
    cx = day()
    s = gt.signals(cx, gt.Clock(cx), "C", {"side": "SHORT", "entry": gt.hm(20), "mgmt": "TIME"})
    assert s["dir"].tolist() == [-1.0]
    assert cx.ny_min[s["i"].iloc[0]] == 19 * 60 + 55
    assert cx.ny_min[s["end"].iloc[0]] == 1 * 60 + 55
