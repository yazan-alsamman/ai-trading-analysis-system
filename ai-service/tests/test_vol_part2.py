"""Gold volatility forecast, part 2 (app/research/vol_part2.py): the helpers."""

import numpy as np
import pandas as pd
import pytest

from app.research import vol_part2 as vp


def test_ratio_is_the_volatility_ratio_clipped() -> None:
    f1 = np.array([0.0, 0.0, 0.0, 0.0])
    f3 = np.array([0.0, 2 * np.log(1.2), 2 * np.log(3.0), 2 * np.log(0.1)])
    assert vp.ratio(f1, f3) == pytest.approx([1.0, 1.2, 1.5, 0.67])


def test_bar_scale_maps_days_and_defaults_to_one() -> None:
    s = vp.bar_scale(np.array([20240102, 20240102, 20240103, 20240104]),
                     np.array([20240102, 20240104]), np.array([1.3, 0.8]))  # fmt: skip
    assert s.tolist() == [1.3, 1.3, 1.0, 0.8]


def test_day_sums_counts_only_the_five_and_fills_missing_days() -> None:
    base = pd.DataFrame({"strategy": ["LVL4H", "ASIA", "ROUND"], "ny_day": [1, 1, 2],
                         "net_slip": [0.5, -1.0, 3.0]})  # fmt: skip
    vol = pd.DataFrame({"strategy": ["LVL4H", "PIVOT"], "ny_day": [1, 3],
                        "net_slip": [0.2, 1.0]})  # fmt: skip
    d = vp.day_sums(base, vol)
    assert d.index.tolist() == [1, 3]
    assert d.loc[1].tolist() == pytest.approx([-0.5, 0.2, 0.7])
    assert d.loc[3].tolist() == pytest.approx([0.0, 1.0, 1.0])


def test_day_int() -> None:
    assert vp.day_int(pd.DatetimeIndex(["2026-01-09"])).tolist() == [20260109]
