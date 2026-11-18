"""Gold magnet (app/research/gold_magnet.py): the helpers on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_magnet as g
from tests.test_gold_pbk import ctx


def bars(c: list[float], h: list[float], lo: list[float]):
    c = np.array(c, float)
    o = np.r_[c[0], c[:-1]]
    return ctx(o, np.array(h, float), np.array(lo, float), c)


def sig(entry=100.0, risk=1.0, target=102.0, s=1):
    return pd.DataFrame({"i": [0], "dir": [float(s)], "entry": [entry], "risk": [risk],
                         "target": [target], "family": ["DAY"]})  # fmt: skip


def test_first_touch() -> None:
    x = np.array([1.0, 2.0, 3.0, 2.0])
    assert g._first_touch(x, 2.5, 1, 0, 3) == 2
    assert g._first_touch(x, 5.0, 1, 0, 3) == 4  # none: b + 1
    assert g._first_touch(x, 1.5, -1, 1, 3) == 4


def test_be_moves_the_stop_after_plus_one_r() -> None:
    # bar 1 reaches +1.2 R, bar 2 falls back to the entry, bar 3 to the old SL
    cx = bars([100, 101, 100.2, 99.5, 99], [100, 101.2, 101, 100.3, 99.5],
              [100, 100.4, 99.9, 98.9, 98.8])  # fmt: skip
    m0 = g.simulate(cx, sig(), "M0").iloc[0]
    be = g.simulate(cx, sig(), "BE").iloc[0]
    assert m0["exit"] == "sl" and m0["j"] == 3 and m0["gross"] == pytest.approx(-1.0)
    cost = gl.COMMISSION  # spread 0 in the test context
    assert be["exit"] == "sl" and be["j"] == 2 and be["gross"] == pytest.approx(cost)


def test_target_and_same_bar_rule() -> None:
    cx = bars([100, 101, 102.5], [100, 101.5, 102.6], [100, 100.5, 101.8])
    assert g.simulate(cx, sig(), "M0").iloc[0]["exit"] == "tp"
    # a bar reaching both the target and the SL counts as the SL
    cx = bars([100, 100], [100, 102.5], [100, 98.5])
    t = g.simulate(cx, sig(), "M0").iloc[0]
    assert t["exit"] == "sl" and t["gross"] == pytest.approx(-1.0)


def test_mfe_stops_before_the_sl_bar() -> None:
    cx = bars([100, 101, 100, 99], [100, 101.5, 103, 100], [100, 100.5, 98.9, 98])
    tr = pd.DataFrame({"i": [0], "dir": [1.0], "entry": [100.0], "sl": [99.0], "risk": [1.0]})
    # bar 2 reaches 103 but also the SL: only bar 1's +1.5 R counts
    assert g.mfe_before_sl(cx, tr)[0] == pytest.approx(1.5)


def test_fx_lines_drop_summary_bars(tmp_path) -> None:
    lines = [b"<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n",
             b"2016.01.18\t01:00:00\t1.0\t1.0\t1.0\t1.0\t161\t0\t0\n",
             b"2018.01.29\t00:00:00\t1348.68\t1352.30\t1337.51\t1340.27\t196790\t0\t0\n",
             b"2018.01.29\t01:00:00\t1348.68\t1350.09\t1348.68\t1350.03\t161\t24150\t37\n",
             b"2018.03.01\t01:00:00\t1.0\t1.0\t1.0\t1.0\t161\t0\t0\n"]  # fmt: skip
    p = tmp_path / "GOLD_M1.csv"
    p.write_bytes(b"".join(lines))
    out = list(gv.fx_lines(p))
    assert out == [lines[0], lines[3], lines[4]]  # before the first day: out; zero volume alone: in


def test_magnet_excess_against_q() -> None:
    tr = pd.DataFrame({"mfe": [0.0, 1.0, 2.0, 3.0, 2.5, 0.5],
                       "m": [np.nan, np.nan, np.nan, np.nan, 2.0, 2.0],
                       "family": ["", "", "", "", "DAY", "DAY"],
                       "tday": [0, 1, 2, 3, 4, 5]})  # fmt: skip
    a = g.magnet(tr)
    q2 = 3 / 6  # MFE >= 2 in three of the six triggers
    assert a["level"] == 2 and a["hit"] == pytest.approx(0.5)
    assert a["q"] == pytest.approx(q2) and a["excess"] == pytest.approx(0.0)
    assert a["rw"] == pytest.approx(1 / 3)
