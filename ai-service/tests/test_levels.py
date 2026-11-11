"""Level families (app/levels): signals, entries and trades on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.levels import events as ev
from app.levels import families as fm
from app.levels import trades as tr
from tests.test_gold_pbk import ctx


def make(c, h=None, lo=None):
    c = np.asarray(c, float)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.01 if h is None else np.asarray(h, float)
    lo = np.minimum(o, c) - 0.01 if lo is None else np.asarray(lo, float)
    return ctx(o, h, lo, c)  # ATR(5m) = 1: b = 0.25, tau = 0.05


def test_lattice_break_and_rejection() -> None:
    cx = make([2005.0, 2010.4])
    s = ev.lattice_signals(cx, fm.rnd(cx, 10.0))
    b = s[s["behaviour"] == "break"].iloc[0]
    assert (b["i"], b["dir"], b["level"], b["target"], b["stop"]) == (1, 1.0, 2010, 2020, 2005)
    cx = make([2008.0, 2010.03], h=[2008.01, 2010.5], lo=[2007.99, 2008.0])
    r = ev.lattice_signals(cx, fm.rnd(cx, 10.0))
    r = r[r["behaviour"] == "rejection"].iloc[0]
    assert (r["dir"], r["level"], r["target"], r["stop"]) == (-1.0, 2010, 2000, 2015)


def test_percent_lattice_levels() -> None:
    cx = make([1000 * 1.01**50 - 3, 1000 * 1.01**50 + 1])
    s = ev.lattice_signals(cx, fm.pct(cx, 0.01))
    b = s[s["behaviour"] == "break"].iloc[0]
    assert b["level"] == pytest.approx(1000 * 1.01**50)
    assert b["target"] == pytest.approx(1000 * 1.01**51)
    assert b["stop"] == pytest.approx((1000 * 1.01**50 + 1000 * 1.01**49) / 2)


def test_discrete_break_uses_the_farthest_level_and_its_neighbours() -> None:
    cx = make([99.0, 106.0, 106.0])
    recs = pd.DataFrame({"level": [100.0, 105.0, 110.0], "start": 0, "end": 3})
    s = ev.discrete_signals(cx, fm.Discrete("X", recs))
    b = s[s["behaviour"] == "break"].iloc[0]
    assert (b["i"], b["level"], b["target"], b["stop"]) == (1, 105.0, 110.0, 102.5)


def test_discrete_dead_levels_are_not_neighbours() -> None:
    cx = make([104.0, 105.4, 105.4])
    recs = pd.DataFrame({"level": [100.0, 105.0, 110.0, 108.0], "start": 0, "end": [3, 3, 3, 1]})
    b = ev.discrete_signals(cx, fm.Discrete("X", recs)).iloc[0]
    assert b["target"] == 110.0  # 108 died before bar 1


def test_signals_do_not_change_when_bars_are_added() -> None:
    rng = np.random.default_rng(3)
    c = 2000 + np.cumsum(rng.normal(0, 2, 400))
    full, cut = make(c), make(c[:250])
    for f in (fm.rnd, fm.pct):
        step = 10.0 if f is fm.rnd else 0.005
        a = ev.lattice_signals(full, f(full, step))
        b = ev.lattice_signals(cut, f(cut, step))
        pd.testing.assert_frame_equal(
            a[a["i"] < 250].reset_index(drop=True), b.reset_index(drop=True)
        )
    recs = pd.DataFrame({"level": [1990.0, 2000.0, 2010.0], "start": 0, "end": 400})
    a = ev.discrete_signals(full, fm.Discrete("X", recs))
    b = ev.discrete_signals(cut, fm.Discrete("X", recs.assign(end=250)))
    pd.testing.assert_frame_equal(a[a["i"] < 250].reset_index(drop=True), b.reset_index(drop=True))


def test_one_trade_target_stop_and_the_five_hour_rule() -> None:
    n = 200
    flat = np.full(n, 100.0)
    cx = make(flat)
    up = flat.copy()
    up[5:] = 102.5
    cx_up = make(up)
    assert tr.one_trade(cx_up, 1, n - 1, 1.0, 100.0, 99.0, 102.0)[2] == "target"
    # at 5 hours +1.2 R: the stop goes to +1 R; then price falls back
    path = flat.copy()
    path[30:65] = 101.2
    path[65:] = 100.5
    j, px, why = tr.one_trade(make(path), 1, n - 1, 1.0, 100.0, 99.0, 105.0)
    assert why == "stop" and px == pytest.approx(101.0) and j == 65
    # below +1 R at 5 hours: closed then
    j, px, why = tr.one_trade(cx, 1, n - 1, 1.0, 100.0, 99.0, 105.0)
    assert why == "5h" and j == 1 + tr.HOLD - 1
    # the day ends first
    assert tr.one_trade(cx, 1, 20, 1.0, 100.0, 99.0, 105.0)[2] == "eod"


def test_entries_apply_the_cost_filter() -> None:
    cx = make(np.full(10, 100.0))
    sig = pd.DataFrame(
        {
            "family": "X",
            "kind": "real",
            "behaviour": "break",
            "i": [2, 3],
            "dir": [1.0, 1.0],
            "level": 100.0,
            "target": [100.15, 101.0],
            "stop": [99.0, 99.0],
        }
    )
    e = tr.entries(cx, sig, dl=np.full(10, 9))
    assert e["i"].tolist() == [3]  # the first target is under 3 x $0.07
    assert e["m"].iloc[0] == pytest.approx(1.0)


def test_swing_points_are_known_three_bars_later() -> None:
    h = np.array([1, 2, 3, 9, 3, 2, 1, 1.0])
    ts = pd.date_range("2024-03-05", periods=len(h), freq="15min", tz="UTC")
    f = pd.DataFrame({"high": h, "low": h - 0.5, "close_utc": ts + pd.Timedelta("15min")})
    p = fm.swing_points(f)
    top = p[p["side"] == 1].iloc[0]
    assert top["level"] == 9 and top["j"] == 3
    assert pd.Timestamp(top["known"], tz="UTC") == f["close_utc"].iloc[6]


def test_shift_moves_levels_and_keeps_life() -> None:
    from app.levels import discover as dc

    cx = make(np.full(5, 100.0))
    lat = dc.shift(fm.rnd(cx, 10.0), 0.3, 0.0)
    assert np.allclose(lat.origin, 3.0) and np.allclose(lat.step, 10.0)
    recs = pd.DataFrame({"level": [100.0, 110.0], "start": [0, 1], "end": [5, 4]})
    d = dc.shift(fm.Discrete("X", recs), 0.75, 8.0)
    assert d.recs["level"].tolist() == [102.0, 112.0]
    assert d.recs["end"].tolist() == [5, 4]


def test_boot_t_of_a_real_minus_placebo_difference() -> None:
    from app.discovery import markout as mk
    from app.levels import discover as dc

    rng = np.random.default_rng(9)
    real = pd.DataFrame({"blk": np.repeat(np.arange(20), 30), "net": rng.normal(0.3, 1, 600)})
    plc = pd.DataFrame({"blk": np.arange(20), "s": np.zeros(20), "n": np.full(20, 300)})
    mr, mp_, t = dc.boot_t(mk.resamples(20, b=2000), real, plc)
    assert mr == pytest.approx(real["net"].mean()) and mp_ == 0.0 and t > 3


def test_range_projections() -> None:
    p = fm.projected(np.array([110.0]), np.array([100.0]), H=np.array([110.0]))
    assert {k: float(v[0]) for k, v in p.items()} == {
        "H": 110.0,
        "H+1": 120.0,
        "H+2": 130.0,
        "L-1": 90.0,
        "L-2": 80.0,
    }
