"""Gold volatility forecast (app/research/vol_forecast.py) on hand-built bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import vol_forecast as vf


def bars(start: str = "2024-01-01", n_days: int = 40, seed: int = 1, drop=()) -> pd.DataFrame:
    """Continuous 5m bars, every New York minute of ``n_days`` calendar days."""
    t = pd.date_range(start, periods=n_days * 288, freq="5min", tz=vf.NY).tz_convert("UTC")
    rng = np.random.default_rng(seed)
    c = 2000 * np.exp(np.cumsum(rng.normal(0, 0.0005, len(t))))
    o = np.r_[c[0], c[:-1]]
    m = pd.DataFrame({"ts_utc": t, "close_utc": t + pd.Timedelta(minutes=5), "open": o,
                      "high": np.maximum(o, c) + 0.1, "low": np.minimum(o, c) - 0.1,
                      "close": c})  # fmt: skip
    return m[~m["ts_utc"].isin(list(drop))].reset_index(drop=True)


def four_h(m: pd.DataFrame) -> pd.DataFrame:
    g = m.set_index("ts_utc").resample("4h")
    h = pd.DataFrame({"high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last()})
    h = h.dropna().reset_index()
    h["close_utc"] = h["ts_utc"] + pd.Timedelta(hours=4)
    return h


def empty_cal() -> pd.DataFrame:
    return pd.DataFrame({"ts_utc": pd.to_datetime([], utc=True), "currency": [], "importance": [],
                         "event": []})  # fmt: skip


def test_window_rv_is_the_sum_of_squared_returns_from_the_0155_close() -> None:
    m = bars(n_days=3)
    d, _ = vf.days(m)
    day = pd.Timestamp("2024-01-02")
    ny = m["ts_utc"].dt.tz_convert(vf.NY)
    mins = ny.dt.hour * 60 + ny.dt.minute
    on_day = ny.dt.tz_localize(None).dt.normalize() == day
    k = np.flatnonzero(on_day & (mins >= 120) & (mins <= 16 * 60 + 40))
    c = m["close"].to_numpy()
    expect = np.sum(np.log(c[k] / c[k - 1]) ** 2)
    assert len(k) == vf.W_BARS == 177
    assert d.loc[day, "rv"] == pytest.approx(expect)
    assert d.loc[day, "used"] and d.loc[day, "miss"] == 0
    assert d.loc[day, "p02"] == pytest.approx(c[k[0] - 1])


def test_a_long_gap_or_few_bars_drops_the_day() -> None:
    gap = pd.date_range("2024-01-02 09:00", "2024-01-02 09:30", freq="5min", tz=vf.NY)
    d, _ = vf.days(bars(n_days=3, drop=gap.tz_convert("UTC")))
    day = pd.Timestamp("2024-01-02")
    assert d.loc[day, "miss"] == 35 and not d.loc[day, "used"]
    short = pd.date_range("2024-01-03 02:00", "2024-01-03 02:25", freq="5min", tz=vf.NY)
    d2, _ = vf.days(bars(n_days=3, drop=short.tz_convert("UTC")))
    assert d2.loc[pd.Timestamp("2024-01-03"), "miss"] == 30
    assert d2.loc[pd.Timestamp("2024-01-03"), "used"]


def test_news_counts_only_the_window_and_flags_top3_and_early() -> None:
    def at(s: str) -> pd.Timestamp:
        return pd.Timestamp(s, tz=vf.NY).tz_convert("UTC")

    cal = pd.DataFrame({
        "ts_utc": [at("2024-01-05 08:30"), at("2024-01-05 08:30"), at("2024-01-05 10:00"),
                   at("2024-01-05 18:00"), at("2024-01-08 14:00"), at("2024-01-08 10:00")],
        "currency": ["USD", "USD", "USD", "USD", "USD", "EUR"],
        "importance": [3, 3, 3, 3, 3, 3],
        "event": ["Nonfarm Payrolls", "Unemployment Rate", "ISM Services PMI", "Late",
                  vf.FED, "Other"],
    })  # fmt: skip
    idx = pd.DatetimeIndex(["2024-01-05", "2024-01-08", "2024-01-09"])
    n = vf.news(cal, idx)
    assert n.loc["2024-01-05"].to_dict() == {"top3": 1, "fed": 0, "uh1": 0, "uh2": 1, "early": 1}
    assert n.loc["2024-01-08"].to_dict() == {"top3": 1, "fed": 1, "uh1": 0, "uh2": 0, "early": 0}
    assert n.loc["2024-01-09"].sum() == 0


def test_features_do_not_read_the_day_itself_or_later() -> None:
    m = bars(n_days=60)
    h4 = four_h(m)
    base = vf.features(m, h4, empty_cal())
    day = base.index[10]
    # change every bar from 02:00 New York of that day on
    t0 = vf.at_ny(pd.DatetimeIndex([day]), vf.W_FROM)[0]
    m2 = m.copy()
    late = m2["ts_utc"] >= t0
    m2.loc[late, ["open", "high", "low", "close"]] *= 1.5
    h42 = four_h(m2)
    alt = vf.features(m2, h42, empty_cal())
    cols = ["rv1", "rv5", "rv22", "on", "atr"]
    pd.testing.assert_series_equal(base.loc[day, cols], alt.loc[day, cols])
    assert base.loc[day, "y"] != alt.loc[day, "y"]


def test_qlike_is_zero_at_a_perfect_unbiased_forecast_and_holm() -> None:
    rv = np.array([1e-4, 4e-4])
    assert vf.qlike(rv, np.log(rv), 0.0) == pytest.approx([0.0, 0.0])
    assert (vf.qlike(rv, np.log(rv) + 0.3, 0.0) > 0).all()
    h = vf.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
