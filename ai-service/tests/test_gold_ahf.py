"""Gold AH filters (app/research/gold_ahf.py) on hand-built and synthetic bars; no market data."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_ah as ah
from app.research import gold_ahf as ahf


def _bars(days: int = 30, seed: int = 7) -> pd.DataFrame:
    """A random walk on a Monday-to-Friday M1 grid (UTC), with spread and tick volume."""
    ts = pd.date_range("2016-03-07", periods=days * 1440, freq="1min", tz="UTC")
    ts = ts[ts.day_of_week < 5]
    rng = np.random.default_rng(seed)
    n = len(ts)
    c = 1200 + np.cumsum(rng.normal(0, 0.25, n))
    o = np.r_[c[0], c[:-1]]
    w = np.abs(rng.normal(0, 0.15, n))
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "open": o,
            "high": np.maximum(o, c) + w,
            "low": np.minimum(o, c) - w,
            "close": c,
            "tick_volume": rng.integers(10, 200, n),
            "spread": rng.uniform(0.2, 0.4, n),
        }
    )


def test_leg_levels_are_the_leg_index_prices() -> None:
    cx = ah.context(_bars(5))
    sig = ah.raw_signals(cx)
    seen = 0
    for i, d in zip(sig.i.to_numpy()[:200], sig.d.to_numpy()[:200], strict=True):
        r = ah.leg_index(cx, int(i), int(d))
        lv = ah.leg_levels(cx, int(i), int(d))
        assert (r is None) == (lv is None)
        if r is not None:
            lo_src, hi_src = (cx.lo, cx.h) if d == 1 else (cx.h, cx.lo)
            assert lv == (lo_src[r[0]], hi_src[r[1]])
            assert r[0] < r[1] <= i and 1 <= r[2] <= ah.LEG_TRIES
            seen += 1
    assert seen > 10


def test_features_do_not_look_ahead() -> None:
    full = _bars(30)
    cut = len(full) - 3 * 1440
    a = ahf.build_set(full)
    b = ahf.build_set(full.iloc[:cut].reset_index(drop=True))
    a = a[a.i < cut - 1].set_index(["i", "d"])
    b = b[b.i < cut - 1].set_index(["i", "d"])
    assert len(b) > 100
    assert a.index.equals(b.index)
    pd.testing.assert_frame_equal(a[ahf.FEATURES], b[ahf.FEATURES], check_dtype=False)


def test_every_feature_is_computed_somewhere() -> None:
    t = ahf.build_set(_bars(30))
    late = t[t.ts >= t.ts.min() + pd.Timedelta(days=25)]
    # needs 20 days of M1 (vol_1d_20d) or 250 days (atr_d_pct): not in 30 synthetic days
    long_ones = {"vol_1d_20d", "atr_d_pct"}
    for k in ahf.FEATURES:
        if k not in long_ones:
            assert late[k].notna().any(), k
    assert set(late.session.unique()) <= {0, 1, 2, 3}
    assert (late.k5.dropna().between(0, 1)).all()
    assert (late.rw_p.between(0, 1)).all()


def test_cluster_t_matches_a_hand_computation() -> None:
    y = np.array([1.0, -1.0, 2.0, 0.0, 3.0, 1.0])
    week = np.array([0, 0, 1, 1, 2, 2])
    wk, nw = ahf._week_index(week)
    m, t = ahf.cluster_t(y, wk, nw, np.ones(6, bool))
    s = np.array([0.0, 2.0, 4.0])
    var = ((s - 1.0 * 2) ** 2).sum() / 36 * 3 / 2
    assert m == pytest.approx(1.0)
    assert t == pytest.approx(1.0 / np.sqrt(var))


def test_skip_mask_skips_while_the_same_side_is_open() -> None:
    t = pd.DataFrame({"i": [10, 12, 13, 30], "d": [1, 1, -1, 1], "exit_i": [20, 25, 14, 40]})
    keep = np.ones(4, bool)
    assert ahf.skip_mask(t, keep).tolist() == [True, False, True, True]
    keep[0] = False  # the first one filtered out: the second now trades
    assert ahf.skip_mask(t, keep).tolist() == [False, True, True, True]


def test_recent_uses_only_trades_closed_before_the_bar() -> None:
    t = pd.DataFrame(
        {"i": [1, 2, 3, 10], "exit_i": [5, 4, 12, 20], "gross": [1.0, 3.0, 100.0, 7.0]}
    )
    r = ahf._recent(t, np.ones(4, bool), n=2)
    # at bar 10, closed before it: exits 4 (3.0) and 5 (1.0); exit 12 is not
    assert np.isnan(r[:3]).all()
    assert r[3] == pytest.approx(2.0)


def _trades(n: int = 6000, seed: int = 3, signal: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.Series(
        pd.to_datetime(
            np.sort(
                rng.integers(pd.Timestamp("2012-01-02").value, pd.Timestamp("2021-12-30").value, n)
            ),
            utc=True,
        )
    )
    f = pd.DataFrame({k: rng.normal(size=n) for k in ahf.NUMERIC})
    f["hour"], f["weekday"], f["session"] = (
        rng.integers(0, 24, n),
        rng.integers(0, 5, n),
        rng.integers(0, 4, n),
    )
    gross = rng.normal(0, 1, n) + signal * (f["ret60"].to_numpy() > 0.84)
    t = pd.DataFrame(
        {
            "i": np.arange(n) * 10,
            "d": rng.choice([1, -1], n),
            "ts": ts,
            "exit_ts": ts + pd.Timedelta(hours=2),
            "exit_i": np.arange(n) * 10 + 5,
            "gross": gross,
            "cost": 0.05,
            "net": gross - 0.05,
            "net_slip": gross - 0.06,
            "net_2x": gross - 0.1,
            "hit_tp": gross > 0,
            "p0": 0.5,
        }
    )
    t["year"] = t.ts.dt.year
    t["week"] = ((t.ts.dt.tz_localize(None) - pd.Timestamp("1970-01-05")).dt.days // 7).astype(int)
    return pd.concat([t, f[ahf.FEATURES]], axis=1)


def test_greedy_finds_a_planted_condition() -> None:
    t = _trades(signal=1.0)
    q = ahf.edges(t)
    conds, tv = ahf.greedy(t, t.gross.to_numpy(), t.week.to_numpy(), q)
    assert conds[0].feature == "ret60" and conds[0].op == ">="
    assert tv > 5


def test_screen_and_meta_run_end_to_end_on_synthetic_trades() -> None:
    t = _trades(signal=1.0)
    text, state = ahf.screen(t)
    assert "Stage 2" in text and isinstance(state["stage2"], bool)
    assert state["conds"][0][0] == "ret60"
    text, state = ahf.meta_stage(t, dict(state, stage2=True))
    assert "| lr |" in text and "| lgbm |" in text
    assert set(state["stage3"]) == {"lr", "lgbm"}


def test_meta_runs_on_every_trade_under_the_amendment() -> None:
    t = _trades(n=4000, signal=1.0)
    state = {"stage2": False, "conds": [], "amendment": 1}
    text, state = ahf.meta_stage(t, state)
    assert "every X1 trade" in text and "## By window" in text
    assert state["v_net_slip"] is not None
