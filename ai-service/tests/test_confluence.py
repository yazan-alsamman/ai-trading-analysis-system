"""Confluence (app/research/confluence.py): the helpers on hand-built trades."""

import numpy as np
import pandas as pd
import pytest

from app.research import confluence as cf


def market(seed: int, lift: float, n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = pd.date_range("2020-01-06", periods=n, freq="1D", tz="UTC")
    k = rng.integers(0, 3, n)
    return pd.DataFrame({"t": t, "k": k, "gross": rng.normal(0, 1, n) + lift * (k >= 1),
                         "net_slip": 0.0})  # fmt: skip


def test_diff_is_k1_minus_k0() -> None:
    t = pd.DataFrame({"k": [0, 0, 1, 2], "gross": [1.0, -1.0, 2.0, 0.0]})
    assert cf.diff(t) == pytest.approx(1.0)


def test_boot_centres_on_the_pooled_difference() -> None:
    mk = {"A": market(1, 0.5), "B": market(2, 0.5), "C": market(3, 0.0)}
    pooled, per = cf.boot(mk)
    assert pooled.shape == (cf.BOOT,) and set(per) == {"A", "B", "C"}
    d = np.mean([cf.diff(t) for t in mk.values()])
    assert np.median(pooled) == pytest.approx(d, abs=0.08)
    assert np.percentile(per["A"], 2.5) > 0
