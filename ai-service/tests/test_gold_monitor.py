"""The live monitor (app/research/gold_monitor.py) on hand-built trades."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_monitor as gm


def demo(n: int = 40, start: str = "2026-11-10 10:00", net=None, slip=0.0) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    t = pd.date_range(start, periods=n, freq="7h")
    net = rng.normal(0.04, 1.2, n) if net is None else np.asarray(net, float)
    return pd.DataFrame({"strategy": [gm.STRATEGIES[k % 6] for k in range(n)], "opened": t,
                         "net": net, "gross": net + 0.01, "risk": 25.0, "slip": slip})  # fmt: skip


def test_cusum_closed_form_equals_the_recursion() -> None:
    x = np.random.default_rng(0).normal(-0.02, 1.2, 500)
    z = ((gm.BAD - gm.GOOD) * x - (gm.BAD**2 - gm.GOOD**2) / 2) / gm.SD**2
    s, out = 0.0, []
    for v in z:
        s = max(0.0, s + v)
        out.append(s)
    np.testing.assert_allclose(gm.cusum(x), out)


def test_first_cross_uses_the_cap_when_never() -> None:
    run_max = np.array([[0.0, 0.5, 1.2, 1.2], [0.0, 0.1, 0.2, 0.3]])
    assert gm.first_cross(run_max, 1.0).tolist() == [3, 4]


def test_edge_estimate_is_the_prior_without_trades_and_moves_with_them() -> None:
    b0 = gm.layer_b(demo(0))
    assert b0.loc["ALL6", "post"] == pytest.approx(0.5 * gm.REF["ALL6"][1])
    bad = gm.layer_b(demo(2000, net=np.full(2000, -0.3)))
    assert bad.loc["ALL6", "p"] < 0.01 and bad.loc["ALL6", "flag"] == "red"
    assert (bad.loc[list(gm.STRATEGIES), "flag"] == "review").all()
    good = gm.layer_b(demo(600, net=np.full(600, 0.1)))
    assert good.loc["ALL6", "flag"] == "ok" and good.loc["ALL6", "p"] > 0.9


def test_process_checks() -> None:
    a = gm.layer_a(demo(40, slip=2.0), (90, 5, 20))
    flags = {r["check"].split()[0]: r["flag"] for r in a}
    assert flags["A1"] == "red"  # Python 90 / 110 < 90%
    assert flags["A2"] == "amber"  # 2 / 25 = 0.08 R
    assert flags["A4"] == "ok"
    assert gm.layer_a(demo(40), None)[0]["value"] == "no export"


def test_week_check_counts_the_last_full_week() -> None:
    d = demo(30, start="2026-11-09 03:00")  # every 7 h from Monday 9 Nov: 24 in that week
    r = gm.week_check(d)
    assert r["value"].startswith("24 (week of 2026-11-09") and r["flag"] == "ok"
    assert gm.week_check(demo(5))["value"] == "no full week yet"


def test_drawdown_now_is_peak_minus_last() -> None:
    assert gm.drawdown_now(np.array([1.0, 2.0, -4.0, 1.0])) == pytest.approx(3.0)
    assert gm.drawdown_now(np.array([-1.0, -1.0])) == pytest.approx(2.0)


def test_verify_refuses_a_different_reference() -> None:
    t = pd.DataFrame({"strategy": ["LVL4H"] * 3, "net": [0.0, 0.1, 0.2]})
    with pytest.raises(SystemExit):
        gm.verify(t)


def test_health_without_a_reference(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(gm, "REF_FILE", tmp_path / "none.parquet")
    lines = gm.health(demo(10), None)
    assert any("reference is missing" in ln for ln in lines)
