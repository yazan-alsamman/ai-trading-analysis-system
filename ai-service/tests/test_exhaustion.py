"""Range exhaustion (app/research/exhaustion.py): the helpers on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import exhaustion as ex
from tests.test_gold_pbk import ctx


def day_ctx():
    # 6 bars of one New York day: 01:50, 01:55 (before the window), then 02:00-02:15
    h = np.array([110.0, 120.0, 101.0, 103.0, 102.0, 108.0])
    lo = np.array([90.0, 80.0, 99.0, 100.0, 97.0, 101.0])
    c = (h + lo) / 2
    cx = ctx(c, h, lo, c)
    cx.ny_min = np.array([110, 115, 120, 125, 130, 135])
    cx.ny_day = np.full(6, 20240102)
    return cx


def test_range_before_reads_only_window_bars_before_the_entry() -> None:
    cx = day_ctx()
    r = ex.range_before(cx, np.array([2, 3, 4, 5]))
    assert r.tolist() == pytest.approx([0.0, 2.0, 4.0, 6.0])  # 101-99, 103-99, 103-97


def test_u_divides_by_the_forecast_scale() -> None:
    cx = day_ctx()
    t = pd.DataFrame({"i": [5], "strategy": ["LVL4H"], "net_slip": [0.1]})
    out = ex.with_u(t, cx, np.array([20240102]), np.array([0.0004]), np.array([100.0]))
    assert out["u"].iloc[0] == pytest.approx(6.0 / (100.0 * 0.02))
    none = ex.with_u(t, cx, np.array([20240103]), np.array([0.0004]), np.array([100.0]))
    assert np.isnan(none["u"].iloc[0])


def test_split_and_boot_sign() -> None:
    rng = np.random.default_rng(0)
    n = 3000
    days = pd.bdate_range("2022-01-03", periods=n // 3).repeat(3)[:n]
    u = rng.uniform(0, 3, n)
    t = pd.DataFrame(
        {
            "ny_day": (days.year * 10000 + days.month * 100 + days.day).to_numpy(),
            "u": u,
            "net_slip": rng.normal(0, 1, n) - 0.3 * (u > 2),
        }
    )
    b = ex.boot(t, 2.0)
    assert b["d"] == pytest.approx(ex.split(t, 2.0)) and b["d"] < 0 and b["p"] < 0.05
