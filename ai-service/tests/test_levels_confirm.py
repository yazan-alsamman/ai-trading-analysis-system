"""The confirmation screen (app/levels/confirm.py) on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.levels import confirm as cf
from app.levels import families as fm
from tests.test_gold_pbk import ctx


def make(o, h, lo, c):
    return ctx(*(np.asarray(x, float) for x in (o, h, lo, c)))  # ATR(5m) = 1


def flat(n, p=100.0):
    a = np.full(n, p)
    return a.copy(), a + 0.1, a - 0.1, a.copy()


def test_lattice_break_and_rejection_events() -> None:
    o, h, lo, c = flat(60, 2005.0)
    c[55], h[55] = 2010.5, 2010.6  # a close above 2010 + 0.25: break up
    h[57], c[57] = 2010.0, 2005.0  # from 2005: up to 2010, close back below: rejected
    cx = make(o, h, lo, c)
    ev = cf.base_lattice(cx, fm.rnd(cx, 10.0))
    b = ev[(ev["kind"] == "break") & (ev["i"] == 55)].iloc[0]
    assert (b["d"], b["level"], b["target"], b["behind"]) == (1.0, 2010.0, 2020.0, 2000.0)
    r = ev[(ev["kind"] == "reject") & (ev["i"] == 57)].iloc[0]
    assert (r["d"], r["level"], r["target"]) == (-1.0, 2010.0, 2000.0)


def test_b1_b3_and_r4_from_a_break() -> None:
    o, h, lo, c = flat(60)
    # bar 52: a strong break of 101 (body 1.5 ATR, close at the top); bar 53 closes above 101
    o[52], c[52], h[52], lo[52] = 100.0, 101.5, 101.55, 99.95
    o[53], c[53], h[53], lo[53] = 101.5, 101.2, 101.6, 101.1
    o[54:57], c[54:57], h[54:57], lo[54:57] = 101.3, 101.3, 101.4, 101.2  # holds above
    cx = make(o, h, lo, c)
    ind = cf.Ind(cx, None)
    ev = pd.DataFrame(
        {
            "i": [52],
            "kind": ["break"],
            "d": [1.0],
            "level": [101.0],
            "target": [102.0],
            "behind": [100.0],
        }
    )
    s = cf.methods(cx, ind, ev).set_index("method")
    assert s.loc["B1", "i"] == 53 and s.loc["B1", "stop"] == pytest.approx(101.1 - 0.1)
    assert s.loc["B3", "i"] == 52
    assert "R4" not in s.index  # it did not fall back
    c2 = c.copy()
    c2[53] = 100.8  # back below 101 the next bar: a fakeout
    cx2 = make(o, h, lo, c2)
    s2 = cf.methods(cx2, cf.Ind(cx2, None), ev).set_index("method")
    assert s2.loc["R4", "d"] == -1.0 and s2.loc["R4", "target"] == 100.0


def test_r2_pin_bar() -> None:
    o, h, lo, c = flat(60)
    o[55], c[55], h[55], lo[55] = 100.0, 99.9, 101.2, 99.85  # a long upper wick through 101
    cx = make(o, h, lo, c)
    ev = pd.DataFrame(
        {
            "i": [55],
            "kind": ["reject"],
            "d": [-1.0],
            "level": [101.0],
            "target": [100.0],
            "behind": [102.0],
        }
    )
    s = cf.methods(cx, cf.Ind(cx, None), ev)
    r = s[s["method"] == "R2"].iloc[0]
    assert r["stop"] == pytest.approx(101.2 + 0.1)


def test_simulate_target_and_stop() -> None:
    o, h, lo, c = flat(20)
    h[5] = 102.5  # after an entry at 100 (bar 3's open), the target 102 is hit on bar 5
    cx = make(o, h, lo, c)
    sig = pd.DataFrame({"method": ["B1"], "i": [2], "d": [1.0], "stop": [99.0], "target": [102.0]})
    t = cf.simulate(cx, sig, "X").iloc[0]
    assert t["exit"] == "target" and t["gross"] == pytest.approx(2.0)
