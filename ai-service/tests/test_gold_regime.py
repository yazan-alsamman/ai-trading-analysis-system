"""Gold regime detectors (app/research/gold_regime.py)."""

import numpy as np
import pandas as pd

from app.research import gold_regime as rg


def test_perf_uses_only_trades_closed_before_the_entry() -> None:
    ts = pd.date_range("2024-01-01", periods=6, freq="h", tz="UTC")
    t = pd.DataFrame({
        "kind": ["BREAK"] * 5 + ["RECLAIM"],
        "t_in": ts[[0, 1, 2, 3, 4, 4]],
        "t_out": ts[[1, 2, 3, 5, 5, 5]] - pd.Timedelta("1min"),
        "net_slip": [-1.0, -1.0, 1.0, -1.0, 0.5, 0.2],
    })  # fmt: skip
    bad = rg.perf_bad(t, 2)
    # at t_in 2: two closed (-1, -1): BAD; at 3: last two (-1, +1) mean 0: GOOD;
    # at 4: trade 3 still open, so the same: GOOD
    assert bad.tolist() == [False, False, True, False, False, False]
    assert np.isclose(rg._t(pd.Series([1.0, 2.0, 3.0])), 2.0 / (1.0 / np.sqrt(3)))
