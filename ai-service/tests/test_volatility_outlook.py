"""The served volatility outlook (app/scoring/volatility.py): the same numbers as the research,
no look-ahead, its statuses, and that it changes nothing else in /v1/evaluate."""

import numpy as np
import pandas as pd
import pytest

from app.research import vol_forecast as vf
from app.scoring import volatility as vs
from tests.test_main import body, client
from tests.test_vol_forecast import four_h

NY = vs.NY


def bars15(start: str = "2024-01-01", n_days: int = 60, seed: int = 3) -> pd.DataFrame:
    t = pd.date_range(start, periods=n_days * 96, freq="15min", tz=NY).tz_convert("UTC")
    rng = np.random.default_rng(seed)
    vol = np.where(pd.DatetimeIndex(t).tz_convert(NY).hour.isin([8, 9, 10]), 0.002, 0.001)
    c = 2000 * np.exp(np.cumsum(rng.normal(0, vol)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame(
        {
            "ts_utc": t,
            "close_utc": t + pd.Timedelta(minutes=15),
            "open": o,
            "high": np.maximum(o, c) + 0.2,
            "low": np.minimum(o, c) - 0.2,
            "close": c,
        }
    )


def cal() -> pd.DataFrame:
    at = [
        pd.Timestamp(x, tz=NY).tz_convert("UTC")
        for x in ("2024-02-02 08:30", "2024-02-02 08:30", "2024-01-31 14:00", "2024-02-13 08:30")
    ]
    return pd.DataFrame(
        {
            "ts_utc": pd.DatetimeIndex(at),
            "currency": "USD",
            "importance": 3,
            "event": ["Nonfarm Payrolls", "Unemployment Rate", vs.FED, "CPI m/m"],
        }
    )


def params() -> dict:
    coef = {"const": -1.0, **{k: 0.1 * (i + 1) for i, k in enumerate(vs.M3)}}
    return {
        "model": "test",
        "m3": {"coef": coef, "s2": 0.2},
        "range_k": {"p20": 1.0, "p50": 1.5, "p80": 2.0},
    }


def test_the_served_features_equal_the_research_features() -> None:
    m, c = bars15(), cal()
    research = vf.features(m, four_h(m), c, step=15)
    days = [d for d in research.index if d >= pd.Timestamp("2024-02-05")][:8]
    assert len(days) == 8
    for day in days:
        x = vs.row(m, c, day)
        for k in vs.M3:
            assert x[k] == pytest.approx(research.loc[day, k]), (day, k)
        assert x["p02"] == pytest.approx(research.loc[day, "p02"])


def test_the_outlook_reads_nothing_after_0200() -> None:
    m, c, p = bars15(), cal(), params()
    as_of = pd.Timestamp("2024-02-02 10:00", tz=NY).tz_convert("UTC")
    a = vs.outlook(m, c, as_of, p)
    m2 = m.copy()
    late = m2["close_utc"] > pd.Timestamp("2024-02-02 02:00", tz=NY)
    m2.loc[late, ["open", "high", "low", "close"]] *= 1.3
    assert vs.outlook(m2, c, as_of, p) == a
    assert a.status == "ok" and a.day == "2024-02-02" and a.model == "test"
    assert [n.top3 for n in a.news] == [True, False]
    assert a.range_pct.p20 < a.range_pct.p50 < a.range_pct.p80
    assert a.range_usd.p50 == pytest.approx(
        a.range_pct.p50 / 100 * m2.loc[~late, "close"].iloc[-1], rel=1e-3
    )


def test_statuses() -> None:
    m, c, p = bars15(), cal(), params()

    def at(s: str):
        return vs.outlook(m, c, pd.Timestamp(s, tz=NY).tz_convert("UTC"), p).status

    assert at("2024-02-03 10:00") == "outside_window"  # Saturday
    assert at("2024-02-02 01:45") == "outside_window"
    assert at("2024-02-02 17:00") == "outside_window"
    assert at("2024-01-10 10:00") == "insufficient_history"
    assert at("2024-02-02 16:45") == "ok"


def test_titles() -> None:
    assert vs.canonical("Non-Farm Employment Change") == "Nonfarm Payrolls"
    assert vs.canonical("Nonfarm Payrolls") == "Nonfarm Payrolls"
    assert vs.canonical("CPI m/m") == "CPI m/m"
    assert vs.canonical("Core CPI m/m") == "Core CPI m/m"
    assert vs.canonical("Federal Funds Rate") == vs.FED
    assert vs.canonical("FOMC Statement") == vs.FED
    assert vs.canonical("Fed Interest Rate Decision") == vs.FED
    assert vs.canonical("FOMC Meeting Minutes") == "FOMC Meeting Minutes"


def test_the_frozen_parameters_load() -> None:
    p = vs.params()
    assert p["model"] == "vol-m3-15m-v1" and set(p["m3"]["coef"]) == {"const", *vs.M3}


def test_evaluate_carries_the_outlook_and_changes_nothing_else() -> None:
    b = body()
    r = client.post("/v1/evaluate", json=b).json()
    assert r["volatility"]["status"] == "insufficient_history"  # 12 days of bars only
    assert r["volatility"]["expected_move_pct"] is None
    b2 = dict(b, instrument_spec=b["instrument_spec"])
    r2 = client.post("/v1/evaluate", json=b2).json()
    assert {k: v for k, v in r.items() if k != "volatility"} == {
        k: v for k, v in r2.items() if k != "volatility"
    }
    assert r["new_setups"], "the setup of the hand-built pattern is still there"
