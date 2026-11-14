"""The pooled model (app/discovery/pooled.py): counts, recent results, purge and choice, and no
feature reading at or after the entry bar."""

import numpy as np
import pandas as pd
import pytest

from app.discovery import pooled as pl
from app.research import gold_lab as gl
from tests.test_gold_levels_live import frames


def test_window_counts_exclude_the_bar_itself() -> None:
    e = np.array([3, 3, 10, 20])
    w = pl.window_counts(e, 40)
    assert (w[3], w[4], w[15], w[16], w[23], w[30], w[33]) == (0, 2, 3, 1, 1, 1, 0)


def test_open_counts() -> None:
    o = pl.open_counts(np.array([5]), np.array([9]), 15)
    assert o[5] == 0 and o[6] == 1 and o[9] == 1 and o[10] == 0


def test_recent_cell_reads_only_closed_trades() -> None:
    c = pd.DataFrame(
        {"cell": ["a"] * 4, "e": [1, 2, 10, 11], "j": [5, 12, 13, 20], "net": [1.0, -1.0, 3.0, 5.0]}
    )
    r = pl.recent_cell(c)
    assert np.isnan(r[0]) and np.isnan(r[1])  # nothing closed before bar 1 or 2
    assert r[2] == pytest.approx(1.0) and r[3] == pytest.approx(1.0)  # only the trade closed at 5


def test_purge_drops_trades_ending_near_the_year() -> None:
    tr = pd.DataFrame(
        {
            "exit_utc": pd.to_datetime(
                ["2019-12-30", "2019-12-31 12:00", "2020-01-02"], utc=True, format="mixed"
            )
        }
    )
    assert len(pl.purge(tr, 2020)) == 1


def test_choose_needs_one_trade_a_day() -> None:
    v = pd.DataFrame(
        {
            "ny_day": [1, 1, 2, 2],
            "net": [1.0, -1.0, 0.5, 0.2],
            "pred_ridge": [0.2, 0.0, 0.2, 0.2],
            "pred_lgbm": [0.3, -1, -1, -1],
        }
    )
    model, tau, g = pl.choose(v)
    assert model == "ridge" and tau == 0.0  # 1.5 a day, mean +0.567 at every tau: the lowest
    assert g["a_day"].max() == 1.5


def test_random_selection_takes_the_same_number_a_day() -> None:
    pool = pd.DataFrame({"ny_day": [1, 1, 1, 2, 2], "net": [1.0, 1.0, 1.0, 0.0, 0.0]})
    r = pl.random_selection(pool, pd.Series({1: 2, 2: 1}))
    assert r.shape == (pl.RAND,) and np.allclose(r, 2 / 3)


def test_features_do_not_read_at_or_after_the_entry() -> None:
    fr = frames()
    cx = gl.context(fr)
    rng = np.random.default_rng(0)
    n = len(cx.c)
    e = np.sort(rng.choice(np.arange(500, n - 300), 60, replace=False))
    c = pd.DataFrame(
        {
            "cell": rng.choice(["lab:A:M8", "levels:B:break", "six:LVL4H"], 60),
            "e": e,
            "j": e + rng.integers(1, 40, 60),
            "dir": rng.choice([1.0, -1.0], 60),
            "risk": 5.0,
            "gross": rng.normal(0, 1, 60),
        }
    )
    c["net"] = c["gross"] - 0.02
    c["group"] = c["cell"].str.split(":").str[0]
    c = pl.finish(c, cx)
    cells = sorted(c["cell"].unique())
    vol = pd.DataFrame({"ny_day": np.unique(cx.ny_day), "logF": -9.0, "vratio": 1.0, "p02": 2900.0})
    base = pl.features(c, cx, vol, cells)
    k = 30
    cut = int(base["e"].iloc[k])
    # change every bar from the entry on, and every outcome of trades closing at or after it
    fr2 = {tf: f.copy() for tf, f in fr.items()}
    fr2["5m"].loc[cut:, ["open", "high", "low", "close"]] *= 1.2
    cx2 = gl.context(fr2)
    c2 = c.copy()
    later = c2["j"] >= cut
    c2.loc[later, "net"] = 99.0
    alt = pl.features(c2, cx2, vol, cells)
    cols = [f for f in pl.FEATURES if f not in ("atr1h_4h", "atr4h_d")]
    pd.testing.assert_series_equal(base.loc[k, cols], alt.loc[k, cols], check_names=False)
