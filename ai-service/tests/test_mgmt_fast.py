"""Path-based management (app/research/mgmt_fast.py) on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_lab as gl
from app.research import mgmt_fast as mf
from tests.test_gold_pbk import ctx


def make(c):
    c = np.asarray(c, float)
    o = np.r_[c[0], c[:-1]]
    return ctx(o, np.maximum(o, c) + 0.05, np.minimum(o, c) - 0.05, c)


def sig(n):
    return pd.DataFrame(
        {
            "strategy": ["X"],
            "i": [0],
            "dir": [1.0],
            "entry": [100.0],
            "risk": [1.0],
            "tp_r": [np.nan],
            "end": [n - 1],
        }
    )


def no15(n):
    nan = np.full(n, np.nan)
    return nan, nan, nan


def test_base_equals_gold_lab_m8() -> None:
    rng = np.random.default_rng(4)
    c = 100 + np.cumsum(rng.normal(0.05, 0.4, 300))
    cx = make(c)
    s = sig(300)
    a = gl.simulate(s, cx, "M8")
    b = mf.simulate(s, cx, "BASE", no15(300))
    assert a["gross"].iloc[0] == pytest.approx(b["gross"].iloc[0])
    assert a["j"].iloc[0] == b["j"].iloc[0] and a["exit"].iloc[0] == b["exit"].iloc[0]


def test_f1_keeps_the_original_stop_until_two_r_on_a_fast_trade() -> None:
    # +1.2 R on the first bar (fast), back to +0.02 (BE would stop it), then up to +3 R
    c = [100, 101.2, 100.02, 101.5, 102.5, 103.0]
    cx = make(c)
    base = mf.simulate(sig(6), cx, "BASE", no15(6)).iloc[0]
    f1 = mf.simulate(sig(6), cx, "F1", no15(6)).iloc[0]
    assert base["exit"] == "sl" and base["fast"]
    assert f1["exit"] == "time" and f1["gross"] == pytest.approx(3.0)
