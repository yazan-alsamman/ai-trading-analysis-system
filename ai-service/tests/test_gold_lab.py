"""Gold lab (app/research/gold_lab.py): the trade simulator on hand-built bars (M0 and M8), the
swing series, and every signal rule on a synthetic market. Nothing here reads the store."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.research import gold_lab as gl
from tests.strategy_data import market


def ctx(path: list[tuple[float, float, float]], n: int = 60, spread: float = 0.2):
    """Bars (high, low, close) after a flat start at 100, then flat bars at the last close."""
    h, lo, c = np.full(n, 100.0), np.full(n, 100.0), np.full(n, 100.0)
    for k, (hh, ll, cc) in enumerate(path, start=1):
        h[k], lo[k], c[k] = hh, ll, cc
    last = len(path)
    h[last + 1 :], lo[last + 1 :], c[last + 1 :] = c[last], c[last], c[last]
    return SimpleNamespace(h=h, lo=lo, c=c, spread=np.full(n, spread), atr5=np.full(n, 1.0))


def sig(tp_r=1.5, end=30, d=1.0):
    return pd.DataFrame(
        {
            "strategy": ["X"],
            "i": [0],
            "dir": [d],
            "entry": [100.0],
            "risk": [2.0],
            "tp_r": [tp_r],
            "end": [end],
        }
    )


def test_m0_takes_the_first_of_sl_and_tp() -> None:
    t = gl.simulate(sig(), ctx([(101.0, 99.5, 100.5), (103.1, 100.5, 103.0)]), "M0").iloc[0]
    assert t["exit"] == "tp" and t["gross"] == pytest.approx(1.5)
    t = gl.simulate(sig(), ctx([(100.5, 97.9, 98.0)]), "M0").iloc[0]
    assert t["exit"] == "sl" and t["gross"] == pytest.approx(-1.0)
    # a bar reaching both counts as the SL
    t = gl.simulate(sig(), ctx([(103.5, 97.5, 100.0)]), "M0").iloc[0]
    assert t["exit"] == "sl"
    # neither by the end: the close of the last bar
    t = gl.simulate(sig(end=3), ctx([(100.5, 99.5, 100.4), (100.6, 99.8, 100.6)]), "M0").iloc[0]
    assert t["exit"] == "time" and t["gross"] == pytest.approx(0.3)
    # a sell mirrors it; the cost is in R
    t = gl.simulate(sig(d=-1.0), ctx([(100.5, 96.9, 97.0)]), "M0").iloc[0]
    assert t["exit"] == "tp" and t["cost"] == pytest.approx((0.2 + gl.COMMISSION) / 2.0)


def test_m8_moves_the_sl_to_break_even_after_one_r() -> None:
    # +1 R (102) reached, then back through the entry: out at entry + cost, a little above 0
    path = [(102.2, 100.0, 102.0), (102.1, 99.0, 99.5)]
    t = gl.simulate(sig(), ctx(path), "M8").iloc[0]
    assert t["exit"] == "sl" and t["gross"] == pytest.approx((0.2 + gl.COMMISSION) / 2.0)
    # M8 has no TP: a move past 1.5 R keeps the trade open
    t = gl.simulate(sig(end=4), ctx([(104.0, 100.0, 103.9), (104.5, 103.5, 104.4)]), "M8").iloc[0]
    assert t["exit"] != "tp"


def test_one_active_trade_per_strategy() -> None:
    s = pd.concat([sig(end=10), sig(end=12).assign(i=5)], ignore_index=True)
    t = gl.simulate(s, ctx([(100.5, 99.5, 100.2)] * 20), "M0")
    assert len(t) == 1


def test_swing_lows_are_confirmed_k_bars_later() -> None:
    lo = np.array([5.0, 4.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    s = gl.swing_lows(lo)
    assert np.isnan(s[3]) and s[4] == 3.0 and s[6] == 3.0


@pytest.fixture(scope="module")
def synthetic():
    fr = market("XAUUSD", start="2023-09-25", end="2023-11-18")
    other = {s: market(s, start="2023-09-25", end="2023-11-18") for s in ("EURUSD", "USDJPY")}
    cx = gl.context(fr)
    return cx, gl.all_signals(fr, cx, other)


def test_signals_are_valid_on_a_synthetic_market(synthetic) -> None:
    cx, s = synthetic
    assert {"S1", "S4", "S6", "S6R", "S7", "EMAX", "EMAX_R", "RSI2", "LVL4H", "PIVOT"} <= set(
        s.strategy
    )
    assert (s["risk"] > 0).all() and (s["end"] > s["i"]).all()
    assert set(np.unique(s["dir"])) <= {-1.0, 1.0}
    rev = s[s.strategy == "S6R"].set_index("i")["dir"]
    fwd = s[s.strategy == "S6"].set_index("i")["dir"]
    assert (rev == -fwd.reindex(rev.index)).all()


def test_the_session_end_is_16_45_new_york_the_same_day(synthetic) -> None:
    cx, _ = synthetic
    ny_close = pd.to_datetime(cx.m["close_utc"].to_numpy()[cx.deadline], utc=True).tz_convert(gl.NY)
    ny_open = pd.to_datetime(cx.m["ts_utc"].to_numpy(), utc=True).tz_convert(gl.NY)
    ok = cx.deadline >= 0
    assert (ny_close[ok].hour * 60 + ny_close[ok].minute <= 16 * 60 + 45).all()
    assert (ny_close[ok].normalize() == ny_open[ok].normalize()).all()
