"""Strategies S1-S8 on hand-built bars, the common filters, and an append-future-bars test for each
strategy on a synthetic market (docs/strategies/PREREG.md, sections 3-5)."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
import trading_indicators as ti

from app.config import instruments, signal_specs
from app.strategies.base import BUY, SELL, last_closed
from app.strategies.rules import STRATEGIES, candidates, squeeze_breakouts, thesis
from app.strategies.vwap import session_vwap
from tests.strategy_data import cut, market

XAU = instruments()["XAUUSD"]
SPECS = signal_specs()
SPREAD = 0.02
UTC = "UTC"


def bars(start: str, freq: str, rows: list[tuple], spread: float = SPREAD, volume=10):
    data = np.asarray(rows, float).reshape(-1, 4)
    ts = pd.date_range(start, periods=len(data), freq=freq, tz=UTC).as_unit("ns")
    vol = volume if np.ndim(volume) else [volume] * len(data)
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "close_utc": ts + pd.Timedelta(freq),
            "open": data[:, 0],
            "high": data[:, 1],
            "low": data[:, 2],
            "close": data[:, 3],
            "tick_volume": pd.array(vol, dtype="Int64"),
            "spread_min": spread,
            "spread_mean": spread,
            "spread_max": spread,
            "n_bars": 1,
        }
    )


def flat(n: int, mid: float = 100.0, half: float = 0.5) -> list[tuple]:
    return [(mid, mid + half, mid - half, mid)] * n


def at(frame: pd.DataFrame, t: str) -> int:
    return int(np.flatnonzero(frame["ts_utc"] == pd.Timestamp(t, tz=UTC))[0])


def armed(cands):
    return [c for c in cands if c.state == "ARMED"]


# --- S1 London breakout ----------------------------------------------------------------------
# 2024-06-12 (Wednesday): London = UTC+1, New York = UTC-4. Asian range 23:00-06:00 UTC.


def s1_frames(breakout=(100, 102.8, 99.8, 102.5), later=None, d1_half=4.0):
    e = bars("2024-06-11 17:00", "15min", flat(76))
    e.loc[at(e, "2024-06-12 01:00"), ["high"]] = 102.0  # range high
    e.loc[at(e, "2024-06-12 02:00"), ["low"]] = 98.0  # range low
    e.loc[at(e, "2024-06-12 06:30"), ["open", "high", "low", "close"]] = breakout
    if later is not None:
        e.loc[at(e, "2024-06-12 07:30"), ["open", "high", "low", "close"]] = later
    d1 = bars("2024-05-22 21:00", "1D", flat(20, half=d1_half))
    return {"15m": e, "D1": d1}


def test_s1_buys_the_first_close_above_the_asian_range() -> None:
    f = s1_frames()
    (c,) = candidates(f, XAU, SPECS["S1"])
    assert (c.direction, c.state, c.idx) == (BUY, "ARMED", at(f["15m"], "2024-06-12 06:30"))
    assert c.entry == 102.5 and c.level == 102.0
    assert c.sl == pytest.approx(100.0 - SPREAD)  # range midpoint minus the spread
    assert c.tp == pytest.approx(102.5 + 1.5 * (102.5 - c.sl))
    assert c.deadline == pd.Timestamp("2024-06-12 20:45", tz=UTC)  # 16:45 New York


def test_s1_needs_the_close_beyond_the_range_by_a_tenth_of_atr() -> None:
    assert candidates(s1_frames(breakout=(100, 102.1, 99.8, 102.05)), XAU, SPECS["S1"]) == []


def test_s1_one_signal_a_day_whatever_comes_later() -> None:
    f = s1_frames(later=(100, 100.2, 96.5, 97.0))  # a sell breakout after the buy
    assert [c.direction for c in candidates(f, XAU, SPECS["S1"])] == [BUY]


def test_s1_range_width_outside_the_band_is_a_rejection() -> None:
    (c,) = candidates(s1_frames(d1_half=1.0), XAU, SPECS["S1"])  # width 4 = 2 x ATR(D1)
    assert (c.state, c.reason) == ("REJECTED", "range_width")


def test_s1_and_s4_need_every_bar_of_the_range() -> None:
    f = s1_frames()
    f["15m"] = f["15m"].drop(index=at(f["15m"], "2024-06-12 03:00")).reset_index(drop=True)
    (c,) = candidates(f, XAU, SPECS["S1"])  # 27 of the 28 Asian-range bars
    assert (c.state, c.reason, c.direction) == ("REJECTED", "incomplete_range", BUY)
    g = s4_frames()
    g["5m"] = g["5m"].drop(index=at(g["5m"], "2024-06-12 12:40")).reset_index(drop=True)
    (c,) = candidates(g, XAU, SPECS["S4"])  # 5 of the 6 opening-range bars
    assert (c.state, c.reason) == ("REJECTED", "incomplete_range")


# --- S2 Bollinger reversion ------------------------------------------------------------------


def s2_frame():
    rows = [(100, 101.5, 98.5, 99 if i % 2 else 101) for i in range(40)]
    rows.append((99, 99.5, 95.5, 96))  # 2024-06-11 16:00 UTC = 12:00 New York
    return {"1h": bars("2024-06-10 00:00", "1h", rows)}


def test_s2_buys_a_close_below_the_lower_band_after_a_close_inside() -> None:
    f = s2_frame()
    (c,) = candidates(f, XAU, SPECS["S2"])
    e = f["1h"]
    mid = ti.bollinger(e["close"], 20, 2.0)["middle"].iloc[40]
    atr = ti.atr(e, 14).iloc[40]
    assert (c.direction, c.state, c.idx) == (BUY, "ARMED", 40)
    assert c.sl == pytest.approx(96 - 1.5 * atr)
    assert c.tp == pytest.approx(mid)
    assert c.r_multiple == pytest.approx((mid - 96) / (1.5 * atr))


def test_s2_trending_market_is_rejected_by_adx() -> None:
    rows = [(100 + i, 101.5 + i, 98.5 + i, 100 + i) for i in range(40)]  # ADX high
    rows.append((139, 139.5, 109, 110))
    (c,) = candidates({"1h": bars("2024-06-10 00:00", "1h", rows)}, XAU, SPECS["S2"])
    assert c.reason == "regime"


# --- S3 Donchian breakout --------------------------------------------------------------------


def s3_frame(last):
    return {"4h": bars("2024-05-01 01:00", "4h", flat(80, half=1.0) + [last])}


def test_s3_buys_a_close_above_the_55_bars_before() -> None:
    f = s3_frame((100, 103.5, 99.8, 103))
    (c,) = candidates(f, XAU, SPECS["S3"])
    atr = ti.atr(f["4h"], 20).iloc[80]
    assert (c.direction, c.state, c.level) == (BUY, "ARMED", 101.0)
    assert c.sl == pytest.approx(103 - 2 * atr)
    assert c.tp == pytest.approx(103 + 3 * 2 * atr)
    assert c.deadline is None  # swing: horizon only


def test_s3_sells_and_ignores_a_close_inside_the_channel() -> None:
    (c,) = candidates(s3_frame((100, 100.2, 96.5, 97)), XAU, SPECS["S3"])
    assert (c.direction, c.level) == (SELL, 99.0)
    assert candidates(s3_frame((100, 101.2, 99.5, 100.9)), XAU, SPECS["S3"]) == []


# --- S4 opening range ------------------------------------------------------------------------
# New York 08:30 = 12:30 UTC.


def s4_frames(breakout=(100, 101.8, 99.9, 101.6), h1_half=2.0):
    e = bars("2024-06-12 10:00", "5min", flat(60))
    e.loc[at(e, "2024-06-12 12:35"), "high"] = 101.0
    e.loc[at(e, "2024-06-12 12:50"), "low"] = 99.0
    e.loc[at(e, "2024-06-12 13:15"), ["open", "high", "low", "close"]] = breakout
    h1 = bars("2024-06-11 10:00", "1h", flat(26, half=h1_half))  # ATR 4, last closes 12:00 UTC
    return {"5m": e, "1h": h1}


def test_s4_buys_the_first_close_above_the_opening_range() -> None:
    f = s4_frames()
    (c,) = armed(candidates(f, XAU, SPECS["S4"]))
    assert (c.direction, c.idx, c.level) == (BUY, at(f["5m"], "2024-06-12 13:15"), 101.0)
    assert c.sl == pytest.approx(100.0 - SPREAD)
    assert c.tp == pytest.approx(101.6 + 1.5 * (101.6 - c.sl))


def test_s4_width_uses_the_1h_atr_known_at_0830() -> None:
    (c,) = candidates(s4_frames(h1_half=0.5), XAU, SPECS["S4"])  # width 2 = 2 x ATR(1h)
    assert c.reason == "range_width"


# --- S5 trend pullback -----------------------------------------------------------------------


def s5_frames(h1_step=0.5, signal=(99.6, 101.2, 97.9, 101.0)):
    h1 = bars("2024-06-08 00:00", "1h", [(100 + h1_step * i,) * 4 for i in range(90)])
    e = bars("2024-06-11 12:00", "5min", flat(40, half=2.0))
    e.loc[at(e, "2024-06-11 14:00"), ["open", "high", "low", "close"]] = signal
    return {"5m": e, "1h": h1}


def test_s5_buys_a_pullback_to_ema20_in_a_1h_up_trend() -> None:
    f = s5_frames()
    (c,) = candidates(f, XAU, SPECS["S5"])
    e = f["5m"]
    j = at(e, "2024-06-11 14:00")
    atr = ti.atr(e, 14).iloc[j]
    lowest = e["low"].iloc[j - 5 : j + 1].min()
    assert (c.direction, c.idx, c.state) == (BUY, j, "ARMED")
    assert c.sl == pytest.approx(min(lowest - 0.1 * atr - SPREAD, 101.0 - atr))
    assert c.tp == pytest.approx(101.0 + 1.5 * (101.0 - c.sl))


def test_s5_no_buy_in_a_1h_down_trend() -> None:
    assert candidates(s5_frames(h1_step=-0.5), XAU, SPECS["S5"]) == []


def test_s5_thesis_is_a_1h_close_against_ema50() -> None:
    f = s5_frames(h1_step=-0.5)
    th = thesis(f, SPECS["S5"], 25.0)
    assert th[BUY].against.all() and not th[SELL].against.any()
    j = 10
    i = last_closed(f["1h"], f["5m"]["close_utc"])[j]
    assert th[BUY].source_close[j] == f["1h"]["close_utc"].iloc[i].value


# --- S6 VWAP reversion -----------------------------------------------------------------------


def test_session_vwap_by_hand() -> None:
    # New York 03:00 = 07:00 UTC; the 06:55 bar belongs to the previous session.
    rows = [(10, 11, 9, 10), (10, 12, 9, 12), (12, 13, 11, 12), (12, 12, 6, 6)]
    f = bars("2024-06-12 06:55", "5min", rows, volume=[5, 1, 3, 1])
    vw = session_vwap(f, "03:00", 2.0)
    tp = np.array([10, 11, 12, 8], float)
    assert vw["vwap"].iloc[0] == pytest.approx(10.0)  # its own session
    assert vw["vwap"].iloc[1] == pytest.approx(11.0)  # a new session starts at 07:00 UTC
    assert vw["vwap"].iloc[2] == pytest.approx((11 + 3 * 12) / 4)
    m = (11 + 36 + 8) / 5
    sd = np.sqrt((tp[1] ** 2 + 3 * tp[2] ** 2 + tp[3] ** 2) / 5 - m * m)
    assert vw["vwap"].iloc[3] == pytest.approx(m)
    assert vw["lower"].iloc[3] == pytest.approx(m - 2 * sd)


def s6_frames():
    rows = [(100, 100.6, 99.4, 99.8 if i % 2 else 100.2) for i in range(30)]
    rows[25] = (99.8, 99.9, 96.5, 97.0)  # closes below the lower band
    rows[26] = (97.0, 100.0, 96.8, 99.7)  # and back above it: the signal bar
    e = bars("2024-06-12 07:00", "5min", rows)  # 03:00 New York
    h1 = bars("2024-06-10 00:00", "1h", flat(55))
    return {"5m": e, "1h": h1}


def test_s6_buys_the_close_back_inside_the_lower_band() -> None:
    f = s6_frames()
    vw = session_vwap(f["5m"], "03:00", 2.0)
    assert f["5m"]["close"].iloc[25] < vw["lower"].iloc[25] < f["5m"]["close"].iloc[26]
    (c,) = [c for c in candidates(f, XAU, SPECS["S6"]) if c.idx == 26]
    atr = ti.atr(f["5m"], 14).iloc[26]
    assert (c.direction, c.idx) == (BUY, 26)
    assert c.sl == pytest.approx(96.5 - atr)
    assert c.tp == pytest.approx(vw["vwap"].iloc[26])
    assert c.state == "ARMED" or c.reason == "r_out_of_range"


# --- S7 squeeze ------------------------------------------------------------------------------


def test_squeeze_breakouts_episode_rules() -> None:
    sq = np.array([1, 1, 1, 0, 0, 0, 1, 1, 0, 0], bool)
    up = np.full(10, 10.0)
    lo = np.full(10, 0.0)
    close = np.array([5, 5, 5, 5, 11, 12, 5, 5, 11, -1], float)
    assert squeeze_breakouts(sq, close, up, lo, 3) == [(4, BUY)]  # once per episode
    assert squeeze_breakouts(sq, close, up, lo, 4) == []  # the run was too short
    close2 = close.copy()
    close2[3] = 11
    assert squeeze_breakouts(sq, close2, up, lo, 3)[0] == (3, BUY)  # the bar where it ends


# --- S8 fix reversal -------------------------------------------------------------------------
# Gold fix 15:00 London = 14:00 UTC.


def s8_frames(move=4.0):
    e = bars("2024-06-12 12:00", "5min", flat(36))
    for i, t in enumerate(pd.date_range("2024-06-12 13:30", periods=6, freq="5min", tz=UTC)):
        lvl = 100 + move * (i + 1) / 6
        e.loc[at(e, str(t.tz_localize(None))), ["open", "high", "low", "close"]] = (
            lvl - move / 6, lvl + 0.3, lvl - move / 6 - 0.3, lvl
        )  # fmt: skip
    top = 100 + move
    e.loc[at(e, "2024-06-12 14:00"), ["open", "high", "low", "close"]] = (top, top + .2, top - .4,
                                                                          top - 0.2)  # fmt: skip
    h1 = bars("2024-06-11 00:00", "1h", flat(38, half=2.0))
    return {"5m": e, "1h": h1}


def test_s8_fades_the_move_into_the_fix() -> None:
    f = s8_frames()
    (c,) = candidates(f, XAU, SPECS["S8"])
    e = f["5m"]
    j = at(e, "2024-06-12 14:00")
    atr = ti.atr(e, 14).iloc[j]
    assert (c.direction, c.idx) == (SELL, j)
    assert c.sl == pytest.approx(103.8 + 1.5 * atr)
    assert c.tp == pytest.approx(104.0 - 4.0 / 2)  # half of m back
    assert c.state == "ARMED" or c.reason == "r_out_of_range"


def test_s8_small_move_is_a_rejection() -> None:
    (c,) = candidates(s8_frames(move=1.0), XAU, SPECS["S8"])  # 1 < 0.5 x ATR(1h) 4
    assert c.reason == "move_too_small"


# --- common filters --------------------------------------------------------------------------


def test_cost_filter_and_liquid_window() -> None:
    f = s3_frame((100, 103.5, 99.8, 103))
    f["4h"]["spread_mean"] = 0.5  # (0.5 + 0.25 + 0.1) / risk ~4.15 > 0.15
    (c,) = candidates(f, XAU, SPECS["S3"])
    assert c.reason == "cost_filter"
    early = bars("2024-06-10 00:00", "1h", s2_frame()["1h"][["open", "high", "low", "close"]]
                 .to_numpy().tolist())  # fmt: skip
    early["ts_utc"] -= pd.Timedelta(hours=15)  # the signal bar opens 01:00 UTC = 21:00 New York
    early["close_utc"] -= pd.Timedelta(hours=15)
    (c,) = candidates({"1h": early}, XAU, SPECS["S2"])
    assert c.reason == "outside_liquid_window"


def test_holiday_is_a_rejection_even_for_swing() -> None:
    f = s3_frame((100, 103.5, 99.8, 103))
    shift = pd.Timestamp("2024-07-04 13:00", tz=UTC) - f["4h"]["ts_utc"].iloc[-1]
    f["4h"]["ts_utc"] += shift
    f["4h"]["close_utc"] += shift
    (c,) = candidates(f, XAU, SPECS["S3"])
    assert c.reason == "holiday"


def test_no_time_left_before_the_session_end() -> None:
    # S2 on 1h: a signal bar opening 15:00 New York closes 16:00; the next would close 17:00.
    f = s2_frame()
    shift = pd.Timestamp("2024-06-11 19:00", tz=UTC) - f["1h"]["ts_utc"].iloc[-1]
    f["1h"]["ts_utc"] += shift
    f["1h"]["close_utc"] += shift
    (c,) = candidates(f, XAU, SPECS["S2"])
    assert c.reason == "no_time_left"


# --- no look-ahead ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(STRATEGIES))
@pytest.mark.parametrize("symbol", ["XAUUSD", "EURUSD"])
def test_append_future_bars_changes_no_candidate(name: str, symbol: str) -> None:
    full = market(symbol)
    spec, inst = SPECS[name], instruments()[symbol]
    every = candidates(full, inst, spec)
    assert len(every) >= 3, "the synthetic market must exercise the rule"
    close = full[spec.frame]["close_utc"]
    for t in close.iloc[[len(close) // 4, len(close) // 2, 3 * len(close) // 4]]:
        part = cut(full, t)
        seen = candidates(part, inst, spec)
        assert seen == [c for c in every if close.iloc[c.idx] <= t]
        th_full, th_part = thesis(full, spec, 25.0), thesis(part, spec, 25.0)
        if th_full is not None:
            n = len(part[spec.frame])
            for d in (BUY, SELL):
                assert (th_part[d].against == th_full[d].against[:n]).all()
                assert (th_part[d].source_close == th_full[d].source_close[:n]).all()


def test_rejection_order_is_deterministic_and_complete() -> None:
    reasons = set()
    for symbol in ("XAUUSD", "EURUSD"):
        inst = replace(instruments()[symbol])
        for spec in SPECS.values():
            reasons |= {c.reason for c in candidates(market(symbol), inst, spec)}
    known = {"", "holiday", "outside_liquid_window", "incomplete_range", "range_width", "regime",
             "move_too_small",
             "non_positive_risk", "r_out_of_range", "cost_filter", "no_time_left"}  # fmt: skip
    assert reasons <= known
