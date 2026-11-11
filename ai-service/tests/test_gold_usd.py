"""Gold on the dollar's breaks (app/research/gold_usd.py) on hand-built 5m bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_usd as gu
from tests.test_gold_pbk import ctx


def gold():
    """Flat at 100 for 15 bars, then up 0.5 a bar."""
    c = np.r_[np.full(15, 100.0), 100 + 0.5 * np.arange(1, 16)]
    o = np.r_[c[0], c[:-1]]
    cx = ctx(o, np.maximum(o, c) + 0.1, np.minimum(o, c) - 0.1, c)
    cx.atr4h[:] = 10.0  # D = 7.5
    return cx


def breaks(cx, bars, dirs):
    ts = pd.to_datetime(cx.m["ts_utc"].to_numpy()[bars], utc=True)
    return pd.DataFrame({"ts": ts, "dir": np.asarray(dirs, float)})


def test_gold_follows_the_break_at_the_same_bars_close() -> None:
    cx = gold()
    s = gu.signals(cx, breaks(cx, [14, 20], [1, -1]), "NONE")
    assert s[["i", "dir"]].to_numpy().tolist() == [[14, 1.0], [20, -1.0]]
    assert s["entry"].tolist() == [cx.c[14], cx.c[20]]
    assert s["risk"].iloc[0] == pytest.approx(7.5)


def test_lag_skips_a_move_gold_already_made() -> None:
    cx = gold()
    # at bar 27 gold is up 6.0 over 12 bars, more than D / 4: a buy is late, a sell is not
    s = gu.signals(cx, breaks(cx, [27, 27], [1, -1]), "LAG")
    assert s["dir"].tolist() == [-1.0]
    assert len(gu.signals(cx, breaks(cx, [27], [1]), "NONE")) == 1


def test_a_break_without_a_gold_bar_is_dropped() -> None:
    cx = gold()
    br = breaks(cx, [14], [1])
    br["ts"] = br["ts"] + pd.Timedelta(minutes=2)
    assert gu.signals(cx, br, "NONE").empty
