"""The five as a portfolio (app/research/risk_split.py): the helpers on hand-built trades."""

import numpy as np
import pandas as pd
import pytest

from app.research import risk_split as rs


def trades() -> pd.DataFrame:
    # one day: LVL4H buy 10-20, PIVOT buy 12-15, ASIA sell 13-30, PIVW buy 15-25 (PIVOT exits at
    # 15: still open), PWHL buy 21-22 (LVL4H closed at 20), and LVL4H + PIVOT both buy at bar 40
    return pd.DataFrame({
        "strategy": ["LVL4H", "PIVOT", "ASIA", "PIVW", "PWHL", "PIVOT", "LVL4H", "ROUND"],
        "i": [10, 12, 13, 15, 21, 40, 40, 16],
        "j": [20, 15, 30, 25, 22, 50, 50, 18],
        "dir": [1.0, 1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "ny_day": 20240102,
        "net_slip": [1.0, 0.5, -1.0, 0.8, 0.2, -1.0, -1.0, 2.0],
    })  # fmt: skip


def test_k_counts_open_same_direction_trades_in_the_registered_order() -> None:
    t = trades()
    o = rs.open_same(t, rs.FIVE)
    assert o.loc[0, "k"] == 0  # LVL4H first
    assert o.loc[1, "k"] == 1 and o.loc[1, "partners"] == [0]
    assert o.loc[2, "k"] == 0  # the sell
    assert o.loc[3, "k"] == 2 and sorted(o.loc[3, "partners"]) == [0, 1]  # PIVOT exits at 15
    assert o.loc[4, "k"] == 1 and o.loc[4, "partners"] == [3]  # LVL4H closed at 20
    assert o.loc[6, "k"] == 0 and o.loc[5, "k"] == 1  # same bar: LVL4H before PIVOT
    assert 7 not in o.index  # ROUND is not one of the five
    o6 = rs.open_same(t, rs.SIX)
    assert o6.loc[7, "k"] == 2 and sorted(o6.loc[7, "partners"]) == [0, 3]  # PIVOT left at 15


def test_weights() -> None:
    o = pd.DataFrame({"k": [0, 1, 2]}, index=[0, 1, 2])
    w = rs.weights(o, 0.5)
    assert w["BASE"].tolist() == [1, 1, 1]
    assert w["SPLIT"].tolist() == pytest.approx([1, 1 / 2, 1 / 3])
    assert w["LEARNED"].tolist() == pytest.approx([1, 1 / 1.5, 1 / 2])


def test_drawdown_and_equal_return_scaling() -> None:
    x = np.array([1.0, -2.0, -1.0, 3.0, -0.5])
    assert rs.max_dd(x) == pytest.approx(3.0)
    d = pd.DataFrame({"BASE": x, "SPLIT": x / 2, "LEARNED": -np.abs(x)})
    assert rs.dd_equal(d, "SPLIT") == pytest.approx(rs.dd_equal(d, "BASE"))
    assert np.isnan(rs.dd_equal(d, "LEARNED"))


def test_rho_pools_new_and_open_pairs() -> None:
    t = trades()
    o = rs.open_same(t, rs.FIVE)
    rho, n, _ = rs.rho_of(t, o)
    assert n == int(o["k"].sum())
    a = [n_ for n_, ps in o["partners"].items() for _ in ps]
    b = [m for ps in o["partners"] for m in ps]
    assert rho == pytest.approx(np.corrcoef(t.loc[a, "net_slip"], t.loc[b, "net_slip"])[0, 1])


def test_day_table_and_boot_are_paired() -> None:
    days = pd.bdate_range("2022-01-03", periods=200)
    di = (days.year * 10000 + days.month * 100 + days.day).to_numpy()
    rng = np.random.default_rng(0)
    base = rng.normal(0.05, 1, len(di))
    d = pd.DataFrame({"BASE": base, "SPLIT": base, "LEARNED": base}, index=di)
    b = rs.boot(d)
    assert b["SPLIT"]["diff"] == 0 and b["SPLIT"]["lo"] == 0 and b["SPLIT"]["hi"] == 0
    assert b["SPLIT"]["holm"] >= b["SPLIT"]["p"]


def test_episodes_do_not_overlap() -> None:
    d = pd.DataFrame({"BASE": [1.0, -3.0, 4.0, -1.0, -1.0, 5.0, -0.5]},
                     index=[1, 2, 3, 4, 5, 6, 7])  # fmt: skip
    assert rs.episodes(d) == [(1, 2, 3.0), (3, 5, 2.0), (6, 7, 0.5)]
