"""Gold fixed target and early lock (app/research/gold_exit.py) on hand-built 5m bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_exit as gx
from tests.test_gold_pbk import ctx


def path(closes: list[float]):
    """Bars whose open is the last close and whose high / low are the two ends."""
    c = np.array(closes, float)
    o = np.r_[c[0], c[:-1]]
    return o, np.maximum(o, c), np.minimum(o, c), c


def buy(cx) -> pd.DataFrame:
    n = len(cx.c)
    return pd.DataFrame({"strategy": ["LVL4H"], "i": [1], "dir": [1.0], "entry": [100.0],
                         "end": [n - 1]})  # fmt: skip


def run(closes, k=0.4, lock="BE", trail=False):
    cx = ctx(*path(closes))
    cx.atrd[:] = 10.0  # S = k x 10
    return gx.simulate(buy(cx), cx, k, lock, trail).iloc[0]


def test_the_target_is_k_atr_d1() -> None:
    t = run([100, 100, 101, 102.5, 104.1, 104.0])
    assert (t["exit"], t["gross"]) == ("tp", pytest.approx(1.0))
    assert t["risk"] == pytest.approx(4.0)


def test_half_the_target_locks_break_even() -> None:
    t = run([100, 100, 101, 102.1, 101, 99.9, 99])
    assert t["exit"] == "sl" and bool(t["locked"])
    assert t["gross"] == pytest.approx(0.07 / 4)  # entry + cost (spread 0 + $0.07)


def test_q_locks_a_quarter() -> None:
    t = run([100, 100, 102.1, 101.5, 100.5, 99], lock="Q")
    assert t["gross"] == pytest.approx(0.25)


def test_no_lock_before_half_the_target() -> None:
    t = run([100, 100, 101.9, 99, 95.9, 95])
    assert t["exit"] == "sl" and not bool(t["locked"])
    assert t["gross"] == pytest.approx(-1.0)
