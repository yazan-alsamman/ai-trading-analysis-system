"""Gold New York opening range (app/research/gold_orb.py) on hand-built bars."""

import numpy as np
import pandas as pd

from app.research import gold_lab as gl
from app.research import gold_orb as go


def ctx(mins: list[int], h: list[float], lo: list[float], day: list[int]) -> gl.Ctx:
    n = len(mins)
    ts = pd.date_range("2024-03-05 12:00", periods=n, freq="5min", tz="UTC")
    m = pd.DataFrame({"ts_utc": ts, "close_utc": ts + pd.Timedelta("5min")})
    one, zero = np.ones(n), np.zeros(n, int)
    c = (np.array(h) + np.array(lo)) / 2
    return gl.Ctx(m, c, np.array(h, float), np.array(lo, float), c, spread=np.zeros(n),
                  atr5=one, atr1h=one, atr4h=one, atrd=one, ny_min=np.array(mins),
                  ny_day=np.full(n, 20240305), weekday=zero, deadline=np.full(n, n - 1),
                  day_idx=np.array(day), d1=pd.DataFrame({"high": [0.0, 0.0]}))  # fmt: skip


def test_range_of_the_six_bars_from_0820() -> None:
    mins = [8 * 60 + 15 + 5 * k for k in range(9)]  # 08:15 to 08:55
    h = [200, 101, 102, 101, 103, 101, 101, 300, 300]
    lo = [50, 99, 98, 99, 99, 97, 99, 10, 10]
    lv = go.orb_levels(ctx(mins, h, lo, [0] * 9))
    assert (lv["ORH"][0], lv["ORL"][0]) == (103.0, 97.0)  # 08:15 and 08:50 on are outside


def test_a_short_range_has_no_levels() -> None:
    mins = [8 * 60 + 20 + 5 * k for k in range(4)]  # only four bars
    lv = go.orb_levels(ctx(mins, [101] * 4, [99] * 4, [1] * 4))
    assert np.isnan(lv["ORH"]).all() and np.isnan(lv["ORL"]).all()
