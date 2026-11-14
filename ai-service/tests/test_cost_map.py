"""The cost-sensitivity map (app/discovery/cost_map.py): the cost split, the re-pricing and the
decision helpers."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.discovery import cost_map as cm


def test_priced_splits_trade_cost_and_stop_slip() -> None:
    cx = SimpleNamespace(spread=np.array([0.0, 0.33, 0.13]))
    c = pd.DataFrame(
        {
            "e": [1, 2],
            "risk": [10.0, 5.0],
            "exit": ["sl", "time"],
            "gross": [1.0, 0.5],
            "net": [1.0 - 0.04 - 0.01, 0.5 - 0.04],
        }
    )
    p = cm.priced(c, cx)
    assert p["c_trade"].tolist() == pytest.approx([0.04, 0.04])
    assert p["c_slip"].tolist() == pytest.approx([0.01, 0.0])
    assert p["resid"].abs().max() < 1e-12
    assert cm.net_at(p, 0.5).tolist() == pytest.approx([1.0 - 0.02 - 0.01, 0.5 - 0.02])


def test_holm_count() -> None:
    assert cm.holm_count({"a": 0.001, "b": 0.02, "c": 0.5}) == 2  # 0.02 <= 0.05 / 2
    assert cm.holm_count({"a": 0.001, "b": 0.01, "c": 0.02}) == 3


def test_boot_t_sign() -> None:
    days = pd.bdate_range("2022-01-03", periods=400)
    d = (days.year * 10000 + days.month * 100 + days.day).to_numpy()
    x = np.random.default_rng(1).normal(0.3, 1.0, 400)
    t, p = cm.boot_t(x, d)
    assert t > 3 and p < 0.01
