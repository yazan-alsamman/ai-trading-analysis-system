"""Strategies S1-S8 (docs/strategies/PREREG.md, section 5), as entry rules on closed bars.

Each ``sN(frames, inst, spec)`` returns the candidates of one instrument (``base.finish`` applies
the common filters); ``thesis_sN(frames, spec)`` returns the L5 series of the strategies whose
invalidation is not a broken level (S2, S5, S6). Indicators come from ``libs/indicators`` (TA-Lib
conventions); a channel a breakout is measured against uses the bars before the signal bar. A
bar whose indicators are still warming up (NaN) triggers nothing.

Choices the PREREG text leaves open, fixed here before any count (docs/strategies/STAGE_A.md):

* one signal a day (S1, S4): the day's first breakout in either direction is its only trigger,
  whatever the filters then decide; a later breakout that day is not a trigger;
* a range needs every bar of its window (S1: 28 15m bars, S4: 6 5m bars); with a bar missing,
  the day's first breakout of the bars present is rejected as ``incomplete_range`` (a day without
  any range bar has no range and no trigger);
* S7: the squeeze episode's first close outside the Bollinger band, from the bar where the
  squeeze ends; a new squeeze before that resets it;
* S8: the fix close is the close of the 5m bar ending at the fix, the earlier close that of the
  bar ending ``move_minutes`` before; both bars and the signal bar must be present;
* a regime or width filter that fails is a rejection reason of the trigger, so counts show it;
* L5 of a breakout uses the level broken at the signal bar (range edge, channel, band), fixed."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
import trading_indicators as ti

from app.config import Instrument, SignalSpec
from app.data.sessions import MARKET_TZ, hhmm_minutes
from app.strategies.base import (
    BUY,
    SELL,
    STEP,
    Candidate,
    Thesis,
    Trigger,
    at_time,
    between,
    finish,
    last_closed,
    local,
    ns,
    spread_of,
    take,
)
from app.strategies.vwap import session_vwap

Frames = dict[str, pd.DataFrame]


def _ohlc(frame: pd.DataFrame) -> tuple[np.ndarray, ...]:
    return tuple(frame[k].to_numpy(float) for k in ("open", "high", "low", "close"))


def _atr(frame: pd.DataFrame, period: int) -> np.ndarray:
    return ti.atr(frame, period).to_numpy()


def _bars_in(window: list[str], frame: str) -> int:
    """The number of ``frame`` bars opening in the time window ``[start, end)``."""
    lo, hi = (hhmm_minutes(t) for t in window)
    return int((hi - lo) * pd.Timedelta(minutes=1) / STEP[frame])


def _range_breakouts(
    e: pd.DataFrame,
    days: np.ndarray,
    in_range: np.ndarray,
    n_range: int,
    in_window: np.ndarray,
    atr: np.ndarray,
    trigger_atr: float,
    width_ref: Callable[[np.datetime64, int], float],
    width: tuple[float, float],
    spread: np.ndarray,
    tp_r: float,
) -> list[Trigger]:
    """S1 and S4: per day, the range of the bars in ``in_range`` (all ``n_range`` of them, else
    ``incomplete_range``), then the first close beyond it by ``trigger_atr`` x ATR among the
    ``in_window`` bars."""
    _, high, low, close = _ohlc(e)
    out = []
    for day in np.unique(days[in_window]):
        r = np.flatnonzero(in_range & (days == day))
        w = np.flatnonzero(in_window & (days == day))
        if not len(r):
            continue
        hi, lo = high[r].max(), low[r].min()
        mid = (hi + lo) / 2
        for j in w[w > r[-1]]:
            if np.isnan(atr[j]):
                continue
            up = close[j] > hi + trigger_atr * atr[j]
            down = close[j] < lo - trigger_atr * atr[j]
            if not (up or down):
                continue
            if len(r) < n_range:
                reason = "incomplete_range"
            else:
                ref = width_ref(day, j)
                if np.isnan(ref):
                    break  # warm-up: no trigger that day
                ok = width[0] <= (hi - lo) / ref <= width[1]
                reason = "" if ok else "range_width"
            if up:
                out.append(Trigger(j, BUY, mid - spread[j], tp_r=tp_r, reason=reason, level=hi))
            else:
                out.append(Trigger(j, SELL, mid + spread[j], tp_r=tp_r, reason=reason, level=lo))
            break
    return out


def s1(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    """London breakout of the Asian range (intraday, 15m)."""
    p = spec.params
    e, d1 = frames[spec.frame], frames["D1"]
    mins, days = local(e["ts_utc"], p["zone"])
    atr = _atr(e, p["atr_period"])
    atr_d1 = take(_atr(d1, p["d1_atr_period"]), last_closed(d1, e["close_utc"]))
    trig = _range_breakouts(
        e,
        days,
        between(mins, p["range"]),
        _bars_in(p["range"], spec.frame),
        between(mins, p["window"]),
        atr,
        p["trigger_atr"],
        lambda day, j: atr_d1[j],  # the previous closed D1 bar at the signal bar
        tuple(p["width_atr"]),
        spread_of(e),
        p["tp_r"],
    )
    return finish(e, trig, spec, inst, atr)


def s2(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    """Bollinger mean reversion in a range (intraday, 1h)."""
    p = spec.params
    e = frames[spec.frame]
    _, _, _, c = _ohlc(e)
    bb = ti.bollinger(e["close"], p["bb_period"], p["bb_std"])
    up, mid, lo = (bb[k].to_numpy() for k in ("upper", "middle", "lower"))
    adx = ti.adx(e, p["adx_period"])["adx"].to_numpy()
    atr = _atr(e, p["atr_period"])
    inside = (c >= lo) & (c <= up)
    prev_inside = np.r_[False, inside[:-1]]
    ok = ~np.isnan(adx) & ~np.isnan(atr)
    trig = []
    for j in np.flatnonzero(ok & prev_inside & ((c < lo) | (c > up))):
        d, s = (BUY, 1.0) if c[j] < lo[j] else (SELL, -1.0)
        reason = "" if adx[j] < p["adx_max"] else "regime"
        trig.append(
            Trigger(
                j,
                d,
                c[j] - s * p["sl_atr"] * atr[j],
                tp=mid[j],
                r_range=tuple(p["r_range"]),
                reason=reason,
            )
        )
    return finish(e, trig, spec, inst, atr)


def s3(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    """Donchian trend breakout (swing, 4h)."""
    p = spec.params
    e = frames[spec.frame]
    _, _, _, c = _ohlc(e)
    ch = ti.donchian(e, p["channel_bars"])  # includes the current bar: shift by one
    hh = np.r_[np.nan, ch["upper"].to_numpy()[:-1]]
    ll = np.r_[np.nan, ch["lower"].to_numpy()[:-1]]
    atr = _atr(e, p["atr_period"])
    trig = []
    for j in np.flatnonzero(~np.isnan(atr) & ~np.isnan(hh) & ((c > hh) | (c < ll))):
        if c[j] > hh[j]:
            trig.append(Trigger(j, BUY, c[j] - p["sl_atr"] * atr[j], tp_r=p["tp_r"], level=hh[j]))
        else:
            trig.append(Trigger(j, SELL, c[j] + p["sl_atr"] * atr[j], tp_r=p["tp_r"], level=ll[j]))
    return finish(e, trig, spec, inst, atr)


def s4(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    """New York opening-range breakout (scalp, 5m)."""
    p = spec.params
    e, h1 = frames[spec.frame], frames["1h"]
    mins, days = local(e["ts_utc"], MARKET_TZ)
    atr = _atr(e, p["atr_period"])
    atr_h1 = _atr(h1, p["h1_atr_period"])
    start = p["range"][0]

    def width_ref(day: np.datetime64, j: int) -> float:
        t = at_time(day, start, MARKET_TZ)  # the last 1h bar closed by 08:30 New York
        i = int(last_closed(h1, pd.Series([t]))[0])
        return float(atr_h1[i]) if i >= 0 else np.nan

    trig = _range_breakouts(
        e,
        days,
        between(mins, p["range"]),
        _bars_in(p["range"], spec.frame),
        between(mins, p["window"]),
        atr,
        p["trigger_atr"],
        width_ref,
        tuple(p["width_atr"]),
        spread_of(e),
        p["tp_r"],
    )
    return finish(e, trig, spec, inst, atr)


def _h1_trend(frames: Frames, spec: SignalSpec) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """S5's 1h trend at each entry bar (+1 up, -1 down, 0 none) and the 1h close-vs-EMA side
    with its source close time (for L5)."""
    p = spec.params
    e, h1 = frames[spec.frame], frames["1h"]
    c1 = h1["close"].to_numpy(float)
    ema = ti.ema(h1["close"], p["trend_ema"]).to_numpy()
    k = p["trend_slope_bars"]
    before = np.r_[np.full(k, np.nan), ema[:-k]] if len(ema) > k else np.full(len(ema), np.nan)
    with np.errstate(invalid="ignore"):
        trend = np.where(
            (c1 > ema) & (ema > before), 1, np.where((c1 < ema) & (ema < before), -1, 0)
        )
        side = np.where(c1 > ema, 1, np.where(c1 < ema, -1, 0))
    idx = last_closed(h1, e["close_utc"])
    ok = idx >= 0
    at = np.zeros(len(e), dtype=int)
    at[ok] = trend[idx[ok]]
    sd = np.zeros(len(e), dtype=int)
    sd[ok] = side[idx[ok]]
    src = np.full(len(e), np.iinfo(np.int64).min)
    src[ok] = ns(h1["close_utc"])[idx[ok]]
    return at, sd, src


def s5(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    """Trend pullback (scalp, 5m entry, 1h trend)."""
    p = spec.params
    e = frames[spec.frame]
    o, h, lo, c = _ohlc(e)
    trend, _, _ = _h1_trend(frames, spec)
    ema = ti.ema(e["close"], p["pullback_ema"]).to_numpy()
    atr = _atr(e, p["atr_period"])
    spread = spread_of(e)
    n = p["swing_bars"]
    lowest = pd.Series(lo).rolling(n, min_periods=n).min().to_numpy()
    highest = pd.Series(h).rolling(n, min_periods=n).max().to_numpy()
    ok = ~np.isnan(ema) & ~np.isnan(atr) & ~np.isnan(lowest)
    with np.errstate(invalid="ignore"):
        buy = ok & (trend == 1) & (lo <= ema) & (c > ema) & (c > o)
        sell = ok & (trend == -1) & (h >= ema) & (c < ema) & (c < o)
    trig = []
    for j in np.flatnonzero(buy | sell):
        buf = p["sl_buffer_atr"] * atr[j]
        far = p["min_sl_atr"] * atr[j]
        if buy[j]:
            sl = min(lowest[j] - buf - spread[j], c[j] - far)
            trig.append(Trigger(j, BUY, sl, tp_r=p["tp_r"]))
        else:
            sl = max(highest[j] + buf + spread[j], c[j] + far)
            trig.append(Trigger(j, SELL, sl, tp_r=p["tp_r"]))
    return finish(e, trig, spec, inst, atr)


def thesis_s5(frames: Frames, spec: SignalSpec) -> dict[str, Thesis]:
    """L5 of S5: a 1h close against EMA(50, 1h)."""
    _, side, src = _h1_trend(frames, spec)
    return {BUY: Thesis(side == -1, src), SELL: Thesis(side == 1, src)}


def _h1_adx(frames: Frames, spec: SignalSpec, period: int) -> tuple[np.ndarray, np.ndarray]:
    """ADX of the last 1h bar closed by each entry bar's close, and that bar's close time."""
    e, h1 = frames[spec.frame], frames["1h"]
    idx = last_closed(h1, e["close_utc"])
    adx = take(ti.adx(h1, period)["adx"].to_numpy(), idx)
    src = np.full(len(e), np.iinfo(np.int64).min)
    src[idx >= 0] = ns(h1["close_utc"])[idx[idx >= 0]]
    return adx, src


def s6(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    """VWAP reversion in a range (scalp, 5m)."""
    p = spec.params
    e = frames[spec.frame]
    _, h, lo, c = _ohlc(e)
    vw = session_vwap(e, p["anchor"], p["band_std"])
    v, up, dn, sess = (vw[k].to_numpy() for k in ("vwap", "upper", "lower", "session"))
    adx, _ = _h1_adx(frames, spec, p["adx_period"])
    atr = _atr(e, p["atr_period"])
    mins, _ = local(e["ts_utc"], MARKET_TZ)
    k = p["extreme_bars"]
    lowest = pd.Series(lo).rolling(k, min_periods=k).min().to_numpy()
    highest = pd.Series(h).rolling(k, min_periods=k).max().to_numpy()
    same = np.r_[False, sess[1:] == sess[:-1]]
    pc, pup, pdn = (np.r_[np.nan, x[:-1]] for x in (c, up, dn))
    ok = same & between(mins, p["window"]) & ~np.isnan(atr) & ~np.isnan(adx) & ~np.isnan(lowest)
    with np.errstate(invalid="ignore"):
        buy = ok & (pc < pdn) & (c > dn)
        sell = ok & (pc > pup) & (c < up)
    trig = []
    for j in np.flatnonzero(buy | sell):
        reason = "" if adx[j] < p["adx_max"] else "regime"
        if buy[j]:
            sl = lowest[j] - p["sl_atr"] * atr[j]
            trig.append(Trigger(j, BUY, sl, tp=v[j], r_range=tuple(p["r_range"]), reason=reason))
        else:
            sl = highest[j] + p["sl_atr"] * atr[j]
            trig.append(Trigger(j, SELL, sl, tp=v[j], r_range=tuple(p["r_range"]), reason=reason))
    return finish(e, trig, spec, inst, atr)


def thesis_adx(frames: Frames, spec: SignalSpec, adx_max: float) -> dict[str, Thesis]:
    """L5 of the range strategies (S2, S6): ADX(14, 1h) above ``adx_max`` at a 1h close."""
    adx, src = _h1_adx(frames, spec, spec.params["adx_period"])
    with np.errstate(invalid="ignore"):
        against = adx > adx_max
    return {BUY: Thesis(against, src), SELL: Thesis(against, src)}


def squeeze_breakouts(
    squeeze: np.ndarray, close: np.ndarray, upper: np.ndarray, lower: np.ndarray, min_bars: int
) -> list[tuple[int, str]]:
    """S7's episodes: after a run of at least ``min_bars`` squeeze bars ends, the first close
    above ``upper`` (buy) or below ``lower`` (sell), from the bar where it ends; a new squeeze bar
    before that resets it. NaN bands never trigger."""
    out = []
    run, armed = 0, False
    for j in range(len(close)):
        if squeeze[j]:
            run, armed = run + 1, False
            continue
        if run >= min_bars:
            armed = True
        run = 0
        if armed and close[j] > upper[j]:
            out.append((j, BUY))
            armed = False
        elif armed and close[j] < lower[j]:
            out.append((j, SELL))
            armed = False
    return out


def s7(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    """Volatility squeeze breakout (intraday, 15m)."""
    p = spec.params
    e = frames[spec.frame]
    _, _, _, c = _ohlc(e)
    bb = ti.bollinger(e["close"], p["bb_period"], p["bb_std"])
    kc = ti.keltner(e, p["kc_period"], p["kc_mult"], p["kc_atr_period"])
    bu, bl = bb["upper"].to_numpy(), bb["lower"].to_numpy()
    with np.errstate(invalid="ignore"):
        squeeze = (bu < kc["upper"].to_numpy()) & (bl > kc["lower"].to_numpy())
    atr = _atr(e, p["atr_period"])
    trig = []
    for j, d in squeeze_breakouts(squeeze, c, bu, bl, p["min_squeeze_bars"]):
        if np.isnan(atr[j]):
            continue  # warm-up (the squeeze needs 20 bars, the ATR 14: never in practice)
        s = 1.0 if d == BUY else -1.0
        lvl = bu[j] if d == BUY else bl[j]
        trig.append(Trigger(j, d, c[j] - s * p["sl_atr"] * atr[j], tp_r=p["tp_r"], level=lvl))
    return finish(e, trig, spec, inst, atr)


def s8(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    """Fix reversal (scalp, 5m)."""
    p = spec.params
    e, h1 = frames[spec.frame], frames["1h"]
    _, _, _, c = _ohlc(e)
    atr = _atr(e, p["atr_period"])
    atr_h1 = _atr(h1, p["h1_atr_period"])
    fix = p["fix"].get(inst.symbol, p["fix"]["default"])
    _, days = local(e["ts_utc"], p["zone"])
    opens = ns(e["ts_utc"])
    five = pd.Timedelta(minutes=5).value

    def bar_at(t: int) -> int | None:
        i = int(np.searchsorted(opens, t))
        return i if i < len(opens) and opens[i] == t else None

    trig = []
    for day in np.unique(days):
        t_fix = at_time(day, fix, p["zone"]).value
        j = bar_at(t_fix)  # the signal bar: opens at the fix, closes 5 minutes after it
        at_fix = bar_at(t_fix - five)  # ends at the fix
        before = bar_at(t_fix - pd.Timedelta(minutes=p["move_minutes"]).value - five)
        if j is None or at_fix is None or before is None or np.isnan(atr[j]):
            continue
        i = int(np.searchsorted(ns(h1["close_utc"]), t_fix, side="right") - 1)
        if i < 0 or np.isnan(atr_h1[i]):
            continue
        m = c[at_fix] - c[before]
        reason = "" if abs(m) >= p["min_move_atr"] * atr_h1[i] else "move_too_small"
        d, s = (SELL, -1.0) if m > 0 else (BUY, 1.0)
        trig.append(
            Trigger(
                j,
                d,
                c[j] - s * p["sl_atr"] * atr[j],
                tp=c[at_fix] - m / 2,
                r_range=tuple(p["r_range"]),
                reason=reason,
            )
        )
    return finish(e, trig, spec, inst, atr)


Rule = Callable[[Frames, Instrument, SignalSpec], list[Candidate]]

# name -> (entry rule, L5 kind): "level" = two closes back inside the broken level; "series" =
# the strategy's thesis series (``thesis``); None = no L5 (S8).
STRATEGIES: dict[str, tuple[Rule, str | None]] = {
    "S1": (s1, "level"),
    "S2": (s2, "series"),
    "S3": (s3, "level"),
    "S4": (s4, "level"),
    "S5": (s5, "series"),
    "S6": (s6, "series"),
    "S7": (s7, "level"),
    "S8": (s8, None),
}


def candidates(frames: Frames, inst: Instrument, spec: SignalSpec) -> list[Candidate]:
    return STRATEGIES[spec.name][0](frames, inst, spec)


def thesis(frames: Frames, spec: SignalSpec, l5_adx_max: float) -> dict[str, Thesis] | None:
    """The L5 series of a ``series`` strategy, None otherwise."""
    if spec.name == "S5":
        return thesis_s5(frames, spec)
    if spec.name in ("S2", "S6"):
        return thesis_adx(frames, spec, l5_adx_max)
    return None
