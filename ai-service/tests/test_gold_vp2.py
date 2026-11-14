"""Value-area re-entry and accepted break (app/research/gold_vp2.py) on hand-built data."""

from types import SimpleNamespace

import numpy as np
import pytest

from app.research import gold_vp2 as g


def test_profile_poc_and_value_area() -> None:
    # most time spent around 100-101, a thin tail to 110
    h = np.array([101.0] * 20 + [110.0])
    lo = np.array([100.0] * 20 + [101.0])
    vah, val, poc = g.profile(h, lo, np.ones(21))
    assert 100.0 <= poc <= 101.1  # the middle of the heaviest 0.1 bin
    assert 100.0 <= val < poc < vah <= 101.2  # 70% of the time: inside the 100-101 block


def view(c, h=None, lo=None):
    c = np.asarray(c, float)
    n = len(c)
    return SimpleNamespace(
        c=c,
        h=c + 0.1 if h is None else np.asarray(h, float),
        lo=c - 0.1 if lo is None else np.asarray(lo, float),
        day=np.zeros(n, int),
        omin=np.full(n, 600),
        deadline=np.full(n, n - 1),
        atr=np.ones(n),
    )


def test_reentry_after_a_close_above_targets_the_poc() -> None:
    # value area 95-105, POC 100: closes 104, 106 (outside), 107, 104, 103 (inside twice)
    v = view(
        [104, 106, 107, 104, 103, 102, 101], h=[104.1, 106.1, 108.0, 104.1, 103.1, 102.1, 101.1]
    )
    s = g.signals(v, np.array([105.0]), np.array([95.0]), np.array([100.0]))
    r = s[s["setup"] == "REENTRY"].iloc[0]
    assert r["i"] == 4 and r["dir"] == -1.0 and r["target"] == 100.0
    assert r["stop"] == pytest.approx(108.0 + 0.1)  # the high since leaving + 0.1 ATR


def test_accepted_break_needs_two_closes_outside_from_inside() -> None:
    v = view([104, 104, 106, 107, 108, 109])  # bar 0 only seeds the previous close
    s = g.signals(v, np.array([105.0]), np.array([95.0]), np.array([100.0]))
    a = s[s["setup"] == "ACCEPTED"].iloc[0]
    assert a["i"] == 3 and a["dir"] == 1.0 and a["stop"] == pytest.approx(105.0 - 0.25)
    # a day that opens already outside has no fresh break
    v2 = view([106, 106, 107, 108, 109])
    s2 = g.signals(v2, np.array([105.0]), np.array([95.0]), np.array([100.0]))
    assert (s2["setup"] == "ACCEPTED").sum() == 0
