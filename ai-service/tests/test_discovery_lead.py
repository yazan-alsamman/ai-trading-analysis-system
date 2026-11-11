"""The round-number lead test (app/discovery/lead.py) on hand-built data."""

import numpy as np
import pandas as pd

from app.discovery import events as ev
from app.discovery import lead as ld
from tests.test_discovery_events import bars


def test_grid_breaks_match_gold_f5_break() -> None:
    rng = np.random.default_rng(11)
    c = 2000 + np.cumsum(rng.normal(0, 1.5, 3000))
    m = bars(c)
    gold = ev.f5(m)
    for g in (50.0, 100.0):
        a = gold[gold["cell"] == f"BREAK-{g:g}"][["i", "sign"]].reset_index(drop=True)
        b = ld.grid_breaks(m, (g,))[["i", "sign"]].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_grid_breaks_on_fx_steps_and_no_look_ahead() -> None:
    rng = np.random.default_rng(12)
    c = 1.10 + np.cumsum(rng.normal(0, 0.0004, 4000))
    m = bars(c, spread=0.00002)
    e = ld.grid_breaks(m, (0.005,))
    assert len(e) > 0
    lvl = np.where(e["sign"] > 0, np.floor(c[e["i"] - 1] / 0.005) * 0.005 + 0.005,
                   np.ceil(c[e["i"] - 1] / 0.005) * 0.005 - 0.005)  # fmt: skip
    assert (np.sign(c[e["i"]] - lvl) * e["sign"] >= 0).all()  # the close reached the level
    cut = ld.grid_breaks(m.iloc[:2500].reset_index(drop=True), (0.005,))
    pd.testing.assert_frame_equal(cut, e[e["i"] < 2500].reset_index(drop=True))


def test_bars_cost_uses_the_market_commission() -> None:
    m = bars(np.full(100, 150.0), spread=0.01)
    bx = ld.bars_with(m, ld.FX_COMMISSION * m["close"].to_numpy())
    np.testing.assert_allclose(bx.cost, 0.01 + 7e-5 * 150.0)


def test_decide_needs_both_controls_positive() -> None:
    r = pd.DataFrame({"market": ["A", "B", "C"], "grid": [1, 1, 1], "h": [120] * 3,
                      "ex_e0": [0.2, 0.2, -0.2], "t_e0": [5.0, 5.0, -5.0],
                      "ex_pl": [0.2, -0.1, 0.2], "t_pl": [5.0, -1.0, 5.0],
                      "mean_z": [3.0, 1.0, 1.0]})  # fmt: skip
    d = ld.decide(r)
    assert d["continues"].tolist() == [True, False, False]
    assert d["tradable"].tolist() == [True, False, False]
