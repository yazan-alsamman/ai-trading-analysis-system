"""The trade-path map (app/research/trade_path.py) on hand-built bars."""

import numpy as np
import pytest

from app.research import trade_path as tp
from tests.test_gold_pbk import ctx


def make(c, h=None, lo=None):
    c = np.asarray(c, float)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) if h is None else np.asarray(h, float)
    lo = np.minimum(o, c) if lo is None else np.asarray(lo, float)
    return ctx(o, h, lo, c)


def test_path_stops_at_minus_one_r_and_ignores_that_bar() -> None:
    # buy at 100, R 1: up to 101.5, then a bar that reaches both 102 and 98.9
    cx = make([100, 101, 101.5, 100.5], h=[100, 101, 101.5, 102], lo=[100, 100.5, 101, 98.9])
    p = tp.path(cx, 0, 1.0, 100.0, 1.0)
    assert p["best"].tolist() == [1.0, 1.5] and p["final"] == -1.0


def test_measures_give_back_and_move_from_one_r() -> None:
    # up to +2 R, back to +1.3 R (past 30% of 2), then ends at +1.2 R
    c = [100, 101, 102, 101.3, 101.2]
    cx = make(c)
    m = tp.measures(tp.path(cx, 0, 1.0, 100.0, 1.0))
    assert m["mfe"] == pytest.approx(2.0)
    assert m["move_from_1"] == pytest.approx(0.2)
    assert m["give_2_0.3"] == pytest.approx(1.2 - 1.3)
    assert np.isnan(m["give_2_0.5"])


def test_mirror_is_the_same_path_reversed() -> None:
    cx = make([100, 100.5, 99.5, 100.2])
    a, b = tp.path(cx, 0, 1.0, 100.0, 1.0), tp.mirror(cx, 0, 1.0, 100.0, 1.0)
    np.testing.assert_allclose(a["close"], -b["close"])
