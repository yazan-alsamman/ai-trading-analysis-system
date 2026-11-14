"""Gold daily swing (app/research/gold_swing.py) on hand-built daily bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_swing as sw


def d1(close: list[float]) -> pd.DataFrame:
    c = np.array(close, float)
    o = np.r_[c[0], c[:-1]]
    days = pd.bdate_range("2024-01-01", periods=len(c)).tz_localize("America/New_York")
    return pd.DataFrame({"close_utc": (days + pd.Timedelta("17h")).tz_convert("UTC"), "open": o,
                         "high": np.maximum(o, c) + 0.5, "low": np.minimum(o, c) - 0.5, "close": c,
                         "spread_mean": 0.0})  # fmt: skip


def test_breakout_entry_next_open_and_channel_exit() -> None:
    # 25 flat days, a rise (day 25 closes above the 20-day high), then a fall through the 10-day low
    close = [100.0] * 25 + [103, 105, 107, 109, 111] + [108, 104, 100, 96, 92]
    t, mt = sw.simulate(d1(close), 20, 10, shorts=False)
    first = t.iloc[0]
    assert (first["i"], first["dir"], first["entry"]) == (26, 1, 103.0)  # day 26 opens at 103
    assert first["why"] in ("sl", "channel") and first["j"] > 26
    # the daily marked-to-market R adds up to the closed trades' net R with swap
    assert mt["net"].sum() == pytest.approx(t["net"].sum(), abs=1e-9)
    assert t["swap"].iloc[0] > 0  # a long pays the swap scenario


def test_no_shorts_when_off() -> None:
    close = [100.0] * 25 + [97, 95, 93, 91, 89, 87, 92, 97, 102, 106]  # then a rebound closes it
    t, _ = sw.simulate(d1(close), 20, 10, shorts=False)
    assert t.empty
    t, _ = sw.simulate(d1(close), 20, 10, shorts=True)
    assert t["dir"].iloc[0] == -1
