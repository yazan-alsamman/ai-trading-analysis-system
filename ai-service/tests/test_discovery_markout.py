"""Discovery markouts, controls and gates (app/discovery/markout.py, map.py) on hand-built data."""

import numpy as np
import pandas as pd
import pytest

from app.discovery import events as ev
from app.discovery import map as mp
from app.discovery import markout as mk
from tests.test_discovery_events import bars


def test_markout_uses_the_first_bar_closing_after_h_within_five_minutes() -> None:
    m = bars(np.arange(100.0), spread=0.2)
    m = m.drop(index=range(12, 14)).reset_index(drop=True)  # a two-minute gap
    bx = mk.bars(m)
    i, s = np.array([10]), np.array([1.0])
    # bar 10 closes 13:11; h = 2 targets 13:13, which falls in the gap -> the 13:15 close (bar 14)
    j = mk.markout_bar(bx, i, 2)
    assert m["ts_utc"].iloc[j[0]] == pd.Timestamp("2024-03-05 13:14", tz="UTC")
    z = mk.z_markout(bx, i, s, 2)
    assert z[0] == pytest.approx((14.0 - 10.0) / (0.2 + ev.COMMISSION))
    assert mk.z_markout(bx, i, -s, 2)[0] == pytest.approx(-z[0])
    # beyond the data: missing
    assert np.isnan(mk.z_markout(bx, np.array([95]), s, 60)[0])


def test_markout_reads_nothing_before_t0_plus_h() -> None:
    rng = np.random.default_rng(1)
    c = 100 + np.cumsum(rng.normal(0, 0.1, 400))
    a, b = mk.bars(bars(c)), mk.bars(bars(c[:300]))
    i, s = np.arange(50, 200), np.ones(150)
    np.testing.assert_allclose(mk.z_markout(a, i, s, 15), mk.z_markout(b, i, s, 15))


def test_e0_draws_stay_in_the_stratum_and_away_from_events() -> None:
    rng = np.random.default_rng(3)
    n = 1440 * 10
    c = 2000 + np.cumsum(rng.normal(0, 0.2, n))
    m = bars(c, start="2024-03-04 00:00")
    bx = mk.bars(m)
    i = np.array([1440 * 2 + 600, 1440 * 7 + 900])  # a Wednesday and the next Monday
    d = mk.e0_draws(bx, i, np.random.default_rng(mk.SEED_E0))
    assert d.shape == (2, mk.E0_DRAWS)
    for row, k in zip(d, i, strict=True):
        ok = row[row >= 0]
        assert len(ok) and (bx.key[ok] == bx.key[k]).all()
        for e in i:
            assert (np.abs(bx.mins[ok] - bx.mins[e]) > mk.E0_GAP).all()


def test_boot_t_and_multiplicity() -> None:
    blk = np.repeat(np.arange(20), 10)
    x = np.full(200, 1.0) + np.random.default_rng(4).normal(0, 0.1, 200)
    idx = mk.resamples(20, b=2000)
    obs, t = mk.boot_t(idx, blk, x)
    assert obs == pytest.approx(x.mean()) and t > 20
    obs2, t2 = mk.boot_t(idx, blk, x, blk, x)
    assert obs2 == pytest.approx(0.0) and abs(t2) < 1e-6 or np.isnan(t2)
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    assert mk.benjamini_hochberg(p, 0.05).tolist() == [True, True] + [False] * 8
    assert mk.holm(np.array([0.01, 0.04, 0.03]), 0.05).tolist() == [True, False, False]


def test_stability() -> None:
    y = np.array([2018] * 3 + [2019] * 3 + [2020] * 3)
    assert mk.stable(y, np.ones(9))
    assert not mk.stable(y, np.r_[np.full(3, 5.0), np.full(6, 0.1)])
    y2 = np.array([2020, 2020, 2021, 2021])
    assert mk.stable(y2, np.array([1.0, 1.0, 0.5, 0.5]), two_years=True)
    assert not mk.stable(y2, np.array([1.0, 1.0, -0.5, -0.5]), two_years=True)


def test_pbo_low_for_a_lasting_cell_and_middling_for_noise() -> None:
    rng = np.random.default_rng(5)
    noise = rng.normal(0, 1, (8, 30))
    assert 0.1 < mp.pbo(noise) < 0.9
    real = noise.copy()
    real[:, 0] += 5
    assert mp.pbo(real) < 0.05


def test_f2_placebo_moves_the_window_two_hours() -> None:
    n = 1440 * 3
    m = bars(np.linspace(2000, 2010, n), start="2024-03-04 00:00")
    p = mk.f2_placebo(m)
    pm = p[p["cell"] == "PM-30"]
    t = (m["ts_utc"].iloc[pm["i"]] + pd.Timedelta(minutes=1)).dt.tz_convert(ev.LONDON)
    assert set(t.dt.strftime("%H:%M")) == {"13:00", "17:00"}
    assert (pm["sign"] == -1).all()  # against a rising market
    cut = mk.f2_placebo(m.iloc[: 1440 * 2].reset_index(drop=True))
    early = p[p["i"] < 1440 * 2 - 10]
    assert len(cut[cut["i"] < 1440 * 2 - 10]) == len(early)


def test_f3_placebo_skips_days_with_a_release_nearby() -> None:
    n = 1440 * 12
    m = bars(np.linspace(2000, 2030, n), start="2024-03-04 00:00")
    rel = pd.to_datetime(["2024-03-08 13:30", "2024-03-07 13:45"], utc=True)
    cal = pd.DataFrame({"ts_utc": rel, "currency": ["USD", "USD"],
                        "event": ["Nonfarm Payrolls", "Other"], "importance": [3, 3]})  # fmt: skip
    p = mk.f3_placebo(m, cal)
    top = p[p["cell"] == "TOP3+1"]
    days = (m["ts_utc"].iloc[top["i"]]).dt.tz_convert(ev.NY).dt.date.astype(str).tolist()
    assert len(top) == mk.PLACEBO_DAYS
    assert "2024-03-08" not in days and "2024-03-07" not in days  # the release day, a near release
    # a release outside the data adds nothing
    far = pd.concat([cal, cal.assign(ts_utc=pd.to_datetime(["2023-01-06 13:30"] * 2, utc=True))])
    assert len(mk.f3_placebo(m, far)) == len(p)
