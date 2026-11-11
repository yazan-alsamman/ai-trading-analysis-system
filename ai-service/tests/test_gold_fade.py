"""Gold fades of the five's trades (app/research/gold_fade.py) on hand-built 5m bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_fade as gf
from tests.test_gold_pbk import ctx


def test_the_fade_is_the_other_side_with_the_same_d() -> None:
    """A buy at 100 with D 2; price falls 0.5 a bar: the original loses, the fade (a sell) wins
    its 1 D target at 98."""
    c = np.r_[100.0, 100.0, 100 - 0.5 * np.arange(1, 9)]
    o = np.r_[c[0], c[:-1]]
    cx = ctx(o, np.maximum(o, c), np.minimum(o, c), c)
    t = pd.DataFrame({"strategy": ["LVL4H"], "i": [1], "dir": [1.0], "entry": [100.0],
                      "risk": [2.0], "end": [len(c) - 1]})  # fmt: skip
    f = gf.fades(cx, t, "TP1").iloc[0]
    assert f["dir"] == -1.0 and f["exit"] == "tp"
    assert f["gross"] == pytest.approx(1.0)
    m8 = gf.fades(cx, t, "M8").iloc[0]
    assert m8["dir"] == -1.0 and m8["gross"] > 1.0  # no target: it runs to the end


def test_accept_uses_the_ev_rule() -> None:
    s = {"m1": 1.0, "m0": -0.5}
    assert gf.accept(np.array([0.2, 0.34, 0.5]), s).tolist() == [False, True, True]
