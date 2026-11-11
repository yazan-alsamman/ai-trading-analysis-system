"""The planted-edge tool check (app/discovery/inject.py) on hand-built data."""

import dataclasses

import numpy as np
import pandas as pd
import pytest

from app.discovery import inject as ij
from app.discovery import markout as mk
from app.research import gold_lab as gl
from tests.test_discovery_events import bars
from tests.test_gold_pbk import ctx


def test_planted_ramps_then_stays() -> None:
    add = ij.planted(10, np.array([2]), np.array([3.0]), ramp=3)
    np.testing.assert_allclose(add, [0, 0, 0, 1, 2, 3, 3, 3, 3, 3])
    two = ij.planted(10, np.array([2, 4]), np.array([3.0, -3.0]), ramp=3)
    np.testing.assert_allclose(two[-1], 0.0)  # the steps add up
    end = ij.planted(5, np.array([3]), np.array([2.0]), ramp=3)  # near the end
    np.testing.assert_allclose(end, [0, 0, 0, 0, 2 / 3])


def test_a_planted_markout_lifts_z_by_delta() -> None:
    rng = np.random.default_rng(7)
    c = 2000 + np.cumsum(rng.normal(0, 0.1, 600))
    m = bars(c, spread=0.2)
    i, s = np.array([100, 300]), np.array([1.0, -1.0])
    bx = mk.bars(m)
    m2 = ij.plant_m1(m, i, s * 3.0 * bx.cost[i])
    z0 = mk.z_markout(bx, i, s, 30)
    z1 = mk.z_markout(mk.bars(m2), i, s, 30)
    np.testing.assert_allclose(z1 - z0, 3.0)


def test_b_planted_drift_shows_in_gross_r() -> None:
    n = 40
    flat = np.full(n, 100.0)
    cx = ctx(flat, flat + 0.01, flat - 0.01, flat)
    sig = pd.DataFrame({"strategy": "RAND", "i": [5], "dir": [1.0], "entry": [100.0],
                        "risk": [1.0], "tp_r": [np.nan], "end": [17]})  # fmt: skip
    add = ij.planted(n, np.array([5]), np.array([0.2]), ij.B_RAMP)
    cx2 = dataclasses.replace(cx, o=cx.o + add, h=cx.h + add, lo=cx.lo + add, c=cx.c + add)
    t = gl.simulate(sig, cx2, "M0").iloc[0]
    assert t["exit"] == "time" and t["gross"] == pytest.approx(0.2)
