"""Gold PBK / RTB (app/research/gold_pbk.py) on hand-built 5m bars."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_lab as gl
from app.research import gold_pbk as gp
from app.research import gold_retrace as gr
from tests.test_gold_retrace import bars as leg_bars


def ctx(o, h, lo, c, deadline: int | None = None) -> gl.Ctx:
    n = len(c)
    ts = pd.date_range("2024-03-05 14:00", periods=n, freq="5min", tz="UTC")
    m = pd.DataFrame({"ts_utc": ts, "close_utc": ts + pd.Timedelta("5min")})
    one, zero = np.ones(n), np.zeros(n, int)
    dl = np.full(n, n - 1 if deadline is None else deadline)
    return gl.Ctx(m, np.asarray(o, float), np.asarray(h, float), np.asarray(lo, float),
                  np.asarray(c, float), spread=np.zeros(n), atr5=one, atr1h=one, atr4h=one,
                  atrd=np.full(n, 5.0), ny_min=np.full(n, 600), ny_day=np.full(n, 20240305),
                  weekday=zero, deadline=dl, day_idx=zero, d1=pd.DataFrame())  # fmt: skip


def touch_bars():
    """A swing high of 105 at bar 10, a fall to 101.5, a return that touches 105 at bar 25
    (close 104.6), a pullback to 104.0 (bar 26), an up close at 104.5 (bar 27), then a rise."""
    c = list(100 + 0.45 * np.arange(11))  # 100 .. 104.5
    c += list(104.5 - 0.3 * np.arange(1, 11))  # bars 11-20: down to 101.5
    c += [102.3, 103.1, 103.8, 104.2, 104.6, 104.2, 104.5]  # bars 21-27
    c += list(104.5 + 0.5 * np.arange(1, 9))  # bars 28-35: up to 108.5
    c = np.array(c)
    o = np.r_[100.0, c[:-1]]
    h = np.maximum(o, c) + 0.2
    lo = np.minimum(o, c) - 0.2
    h[10] = 105.0
    h[25], lo[25] = 105.0, 104.1
    h[26], lo[26] = 104.7, 104.0
    h[27], lo[27] = 104.6, 104.1
    return o, h, lo, c


def test_structure_reads_rising_swings() -> None:
    h = np.array([1, 3, 1, 1, 4, 1, 1, 5, 1, 1, 6, 1, 1.0])
    lo = np.array([0, 0.5, -1, 0.5, 0.6, 0, 0.6, 0.7, 0.2, 0.7, 0.8, 0.3, 0.9])
    st = gp.structure(h, lo, k=1)
    assert st[-1] == 1
    assert st[0] == 0


def test_pbk_enters_on_the_up_close_after_the_pullback() -> None:
    cx = ctx(*touch_bars())
    lv = gp.levels(cx, with_days=False)
    cand, touches = gp.pbk_candidates(cx, lv)
    buys = cand[cand["dir"] == 1]
    assert buys[["i", "entry", "ref", "touch_bar"]].to_numpy().tolist() == [[27, 104.5, 105.0, 25]]
    assert buys["risk"].iloc[0] == pytest.approx(1.0)  # SL at least 1 ATR from the entry
    assert touches[touches["dir"] == 1]["pulled"].tolist() == [True]
    tr = (np.zeros(len(cx.c), int), np.zeros(len(cx.c), int))
    sig = gp.finalize(cx, buys, gp.Liq(lv), tr, "PBK", "R2", "NONE", "i", False)
    t = gr.simulate(sig, cx, gr.frame(cx, "5m"), "TRAIL")
    assert t[["exit"]].to_numpy().tolist() == [["tp"]]
    assert t["gross"].iloc[0] == pytest.approx(2.0)
    # the 1h / 4h filter: no trend, no trade
    assert gp.finalize(cx, buys, gp.Liq(lv), tr, "PBK", "R2", "STRUCT", "i", False).empty


def test_pbk_needs_no_future_bars() -> None:
    o, h, lo, c = touch_bars()
    full = gp.pbk_candidates(ctx(o, h, lo, c), gp.levels(ctx(o, h, lo, c), with_days=False))[0]
    cut = 28
    short = ctx(o[:cut], h[:cut], lo[:cut], c[:cut], deadline=10**6)
    part = gp.pbk_candidates(short, gp.levels(short, with_days=False))[0]
    a = full[full["i"] < cut][["i", "dir", "entry", "risk"]].to_numpy().tolist()
    assert part[["i", "dir", "entry", "risk"]].to_numpy().tolist() == a


def test_rtb_fills_the_20_percent_and_stops_at_half() -> None:
    cx = leg_bars()
    fr = gr.frame(cx, "5m")
    cand = gp.rtb_candidates(cx, gr.legs(cx, fr), 0.20)
    assert cand[["i", "dir", "m"]].to_numpy().tolist() == [[43, 1, 42]]
    assert cand["entry"].iloc[0] == pytest.approx(111.5 - 0.2 * 12)
    assert cand["risk"].iloc[0] == pytest.approx(0.3 * 12)
    lv = gp.levels(cx, with_days=False)
    tr = (np.zeros(len(cx.c), int), np.zeros(len(cx.c), int))
    sig = gp.finalize(cx, cand, gp.Liq(lv), tr, "RTB", "R2", "NONE", "m", True)
    t = gr.simulate(sig, cx, fr, "TRAIL")
    assert t[["exit", "gross"]].to_numpy().tolist() == [["sl", -1.0]]


def to_m1(cx: gl.Ctx) -> pd.DataFrame:
    """Five M1 bars a 5m bar, moving in a straight line from its open to its close."""
    rows = []
    for i, ts in enumerate(cx.m["ts_utc"]):
        o, c = cx.o[i], cx.c[i]
        for q in range(5):
            a, b = o + (c - o) * q / 5, o + (c - o) * (q + 1) / 5
            rows.append((ts + pd.Timedelta(minutes=q), a, max(a, b), min(a, b), b, 0.0))
    return pd.DataFrame(rows, columns=["ts_utc", "open", "high", "low", "close", "spread"])


def test_pbk_m1_enters_on_the_first_m1_up_close_after_the_5m_pullback() -> None:
    cx = ctx(*touch_bars())
    m1 = to_m1(cx)
    cand = gp.pbk_m1_candidates(cx, gp.levels(cx, with_days=False), m1)
    buys = cand[cand["dir"] == 1]
    assert buys[["k", "i", "touch_bar"]].to_numpy().tolist() == [[27 * 5, 27, 25]]
    assert buys["entry"].iloc[0] == pytest.approx(104.2 + 0.3 / 5)
    t = gp.simulate_m1(buys, m1, cx)
    assert t["exit"].tolist() == ["time"]  # neither +$10 nor -$10 is reached
    assert t["gross"].iloc[0] == pytest.approx((108.5 - 104.26) / 10)
