"""Discovery event detectors (app/discovery/events.py) on hand-built M1 bars."""

import numpy as np
import pandas as pd

from app.discovery import events as ev


def bars(close, start="2024-03-05 13:00", spread=0.2) -> pd.DataFrame:
    c = np.asarray(close, float)
    o = np.r_[c[0], c[:-1]]
    ts = pd.date_range(start, periods=len(c), freq="1min", tz="UTC")
    return pd.DataFrame({"ts_utc": ts, "open": o, "high": np.maximum(o, c) + 0.05,
                         "low": np.minimum(o, c) - 0.05, "close": c,
                         "spread": np.full(len(c), spread)})  # fmt: skip


def test_close_index_finds_the_bar_closing_at_a_time() -> None:
    m = bars(np.arange(10.0))
    when = pd.Series(pd.to_datetime(["2024-03-05 13:05", "2024-03-05 14:00"], utc=True))
    assert ev.close_index(m["ts_utc"], when).tolist() == [4, -1]


def test_f3_signs_by_the_move_after_the_release() -> None:
    # a release at 13:30 UTC; price rises after it
    c = np.r_[np.full(30, 4000.0), 4000 + np.arange(1, 31)]
    m = bars(c)
    cal = pd.DataFrame({"ts_utc": pd.to_datetime(["2024-03-05 13:30"], utc=True),
                        "currency": ["USD"], "event": ["Nonfarm Payrolls"],
                        "importance": [3]})  # fmt: skip
    e = ev.f3(m, cal)
    top = e[e["cell"].str.startswith("TOP3")].set_index("cell")
    assert top.loc["TOP3+1", "i"] == 30 and top.loc["TOP3+1", "sign"] == 1
    assert top.loc["TOP3+15", "i"] == 44
    assert set(e["cell"]) == {"TOP3+1", "TOP3+5", "TOP3+15", "HIGH+1", "HIGH+5", "HIGH+15"}


def test_window_times_follow_london_dst() -> None:
    days = pd.Series(["2024-01-10", "2024-07-10"])
    t = ev.window_times(days, "15:00", ev.LONDON)
    assert t.dt.strftime("%H:%M").tolist() == ["15:00", "14:00"]


def test_f5_break_counts_a_level_once_an_hour() -> None:
    # 3998 -> 4001 (crosses 4000), back to 3999, again 4001: one BREAK up at 4000 per grid
    m = bars([3998.0, 4001.0, 3999.0, 4001.0, 4002.0])
    e = ev.f5(m)
    up = e[(e["cell"] == "BREAK-25") & (e["sign"] == 1)]
    assert up["i"].tolist() == [1]
    assert e[e["cell"] == "BREAK-75"].empty  # 3975 and 4050 are not crossed


def test_f5_reject_is_signed_back_away() -> None:
    c = [3998.0, 3999.0]
    m = bars(c)
    m.loc[1, "high"] = 4000.5  # trades through 4000 and closes back below
    e = ev.f5(m)
    rej = e[e["cell"] == "REJECT-100"]
    assert rej[["i", "sign"]].values.tolist() == [[1, -1]]


def test_detectors_need_no_future_bars() -> None:
    rng = np.random.default_rng(3)
    c = 4000 + np.cumsum(rng.normal(0, 1.5, 600))
    full, cut = bars(c), bars(c[:400])
    a = ev.f5(full)
    b = ev.f5(cut)
    keep = ["family", "cell", "i", "sign"]
    pd.testing.assert_frame_equal(
        a[a["i"] < 400][keep].reset_index(drop=True), b[keep].reset_index(drop=True)
    )


def test_f1_unconfirmed_when_the_dollar_and_bond_stay_flat() -> None:
    rng = np.random.default_rng(5)
    n = 1600
    c = 4000 + np.cumsum(rng.normal(0, 0.05, n))
    c[1580:] += np.linspace(0, 30, 20)  # a fast rise of $30 at the end
    m = bars(c, start="2024-03-04 00:00")
    drv = pd.DataFrame({"ts_utc": m["ts_utc"], "close": np.full(n, 100.0)})  # flat
    e = ev.f1(m, drv, drv)
    un = e[e["cell"].str.startswith("UNCONF-k1-")]  # the noise alone can pass k = 0.5
    assert len(un) and (un["i"] >= 1580).all() and (un["sign"] == -1).all()
    assert e[e["cell"].str.startswith("CONF")].empty


def test_f1_ignores_the_drivers_before_their_clean_start() -> None:
    rng = np.random.default_rng(5)
    n = 1600
    c = 4000 + np.cumsum(rng.normal(0, 0.05, n))
    c[1580:] += np.linspace(0, 30, 20)
    m = bars(c, start="2019-06-03 00:00")  # the dollar is read, the bond is not yet (2020)
    drv = pd.DataFrame({"ts_utc": m["ts_utc"], "close": np.full(n, 100.0)})
    assert ev.f1(m, drv, drv).empty
