"""Heikin-Ashi flips (app/research/gold_ha.py) on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_ha as g


def frame(c, start="2024-03-05 14:00"):  # 09:00 New York, a Tuesday
    c = np.asarray(c, float)
    o = np.r_[c[0], c[:-1]]
    ts = pd.date_range(start, periods=len(c), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "close_utc": ts + pd.Timedelta("15min"),
            "open": o,
            "high": np.maximum(o, c) + 0.5,
            "low": np.minimum(o, c) - 0.5,
            "close": c,
            "spread_mean": np.full(len(c), 0.2),
        }
    )


def test_heikin_ashi_formula() -> None:
    o, h, lo, c = (np.array(x, float) for x in ([10, 12], [13, 14], [9, 11], [12, 13]))
    ho, hc = g.heikin_ashi(o, h, lo, c)
    assert hc.tolist() == [11.0, 12.5]
    assert ho[0] == 11.0 and ho[1] == pytest.approx((11.0 + 11.0) / 2)


def test_flips_carry_colour_over_dojis() -> None:
    col, flip = g.flips(np.array([1, 2, 2, 3.0]), np.array([2, 1, 2, 3.0]))
    assert col.tolist() == [1, -1, -1, -1] and flip.tolist() == [False, True, False, False]


def test_trades_enter_and_exit_at_the_real_next_open() -> None:
    up = list(np.linspace(100, 110, 20))
    down = list(np.linspace(109, 95, 20))
    f = frame(up + down + list(np.linspace(96, 105, 10)))
    t = g.trades(f, "H24")
    first = t.iloc[0]
    assert first["dir"] in (1.0, -1.0)
    assert first["entry"] == pytest.approx(f["open"].iloc[first["k"]])  # a real price
    assert first["k"] == first["i"] + 1
    assert first["exit_px"] == pytest.approx(f["open"].iloc[first["x"]])
    ha = g.trades(f, "H24", fill="ha")
    assert not np.allclose(ha["entry"], t["entry"])  # HA prices are not the real ones


def test_day_cell_closes_at_16_45_new_york() -> None:
    f = frame(
        list(np.linspace(100, 120, 40)) + list(np.linspace(119, 100, 20)), start="2024-03-05 18:00"
    )  # 13:00 New York; 16:45 is bar 15's close
    cut, blocked = g.cut_bars(f, "DAY")
    k = int(np.flatnonzero(cut)[0])
    close_ny = f["close_utc"].dt.tz_convert("America/New_York").iloc[k]
    assert (close_ny.hour, close_ny.minute) == (16, 45)
    assert blocked[k + 1] and not blocked[k]
