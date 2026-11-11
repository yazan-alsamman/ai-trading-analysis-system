"""Gold trade paths (app/research/gold_path.py) on hand-built 5m bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_exit as gx
from app.research import gold_path as gp
from tests.test_gold_pbk import ctx


def test_the_path_of_one_buy(monkeypatch) -> None:
    """Entry 100 at bar 1: up 0.5 a bar to 103 (bar 7), then down 0.5 a bar."""
    c = np.r_[100.0, 100.0, 100 + 0.5 * np.arange(1, 7), 103 - 0.5 * np.arange(1, 9)]
    o = np.r_[c[0], c[:-1]]
    cx = ctx(o, np.maximum(o, c), np.minimum(o, c), c)
    n = len(c)
    sig = pd.DataFrame({"strategy": ["LVL4H"], "i": [1], "dir": [1.0], "entry": [100.0],
                        "risk": [2.0], "tp_r": [np.nan], "end": [n - 1], "kind": ["PDH"],
                        "level": [100.0]})  # fmt: skip
    monkeypatch.setattr(gx, "signals", lambda _cx: sig)
    p = gp.paths(cx).iloc[0]
    assert p["m5"] == pytest.approx(0.5)  # one bar later
    assert p["m30"] == pytest.approx(3.0)  # six bars later, the top
    assert p["mfe"] == pytest.approx(3.0) and p["t_mfe"] == 30
    assert p["mae"] == pytest.approx(1.0)  # the last bar's low, 99
    assert p["mfe_pre_sl"] == pytest.approx(3.0)  # -1 D (98) is never reached
