"""Gold winners past 16:45 (app/research/gold_hold.py) on two hand-built trading days."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_hold as gh
from tests.test_gold_pbk import ctx


def two_days(rise_after: bool = True):
    """Day 0 is bars 0-19 (16:45 at bar 15), day 1 bars 20-39 (16:45 at bar 35). A buy at 100
    (bar 1, D 1) rises 0.25 a bar to bar 15, waits, then rises (or falls) 0.1 a bar on day 1."""
    c = np.r_[100.0, 100.0, 100 + 0.25 * np.arange(1, 15), np.full(4, 103.5)]
    step = 0.1 if rise_after else -0.3
    c = np.r_[c, 103.5 + step * np.arange(1, 21)]
    o = np.r_[c[0], c[:-1]]
    cx = ctx(o, np.maximum(o, c), np.minimum(o, c), c)
    cx.day_idx = np.r_[np.zeros(20, int), np.ones(20, int)]
    cx.deadline = np.r_[np.full(20, 15), np.full(20, 35)]
    cx.d1 = pd.DataFrame({"close_utc": pd.to_datetime(["2024-03-04 22:00", "2024-03-05 22:00"],
                                                      utc=True)})  # fmt: skip
    sig = pd.DataFrame({"strategy": ["LVL4H"], "i": [1], "dir": [1.0], "entry": [100.0],
                        "risk": [1.0], "end": [15]})  # fmt: skip
    return cx, sig


def test_base_closes_at_16_45_and_win1_runs_on() -> None:
    cx, sig = two_days()
    base = gh.simulate(sig, cx, "BASE").iloc[0]
    assert (base["j"], base["exit"]) == (15, "time")
    assert base["gross"] == pytest.approx(3.5)
    win = gh.simulate(sig, cx, "WIN1").iloc[0]
    assert win["j"] == 35 and bool(win["overnight"])
    assert win["gross"] == pytest.approx(3.5 + 1.6)  # day 1 to bar 35: 16 bars of 0.1
    assert win["swap"] == pytest.approx(100 * 0.03 / 360)  # one night, a buy


def test_a_held_winner_can_still_stop_out() -> None:
    cx, sig = two_days(rise_after=False)
    win = gh.simulate(sig, cx, "WIN1").iloc[0]
    assert win["exit"] == "sl" and win["j"] > 15
    assert win["gross"] < 3.5
