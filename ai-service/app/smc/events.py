"""SMC events on closed entry bars: sweep or breakout of a liquidity level, CHoCH, FVG.

Every rule is written once for the buy side (sell-side liquidity, a ``low`` level, swept from
above) and run on mirrored prices for the sell side (``Side``), so both directions follow the
same code. Prices in the results are real prices.

Rules (Strategy v1, ``app/config/strategy.toml``):

* **Sweep.** A bar trades below a ``low`` level (the ``LevelBook`` spends it). Depth = how far
  below, the lowest low of the sweep bars, in ATR(14) of the first sweep bar. It is a *sweep* when
  a bar closes back above the level, on the first bar or within ``close_back_bars`` after it, with
  depth from ``min_depth_atr`` to ``breakout_depth_atr``. Deeper than ``breakout_depth_atr`` at
  any point, or no close back in time, is a *breakout*; a close back with less depth than
  ``min_depth_atr`` is *shallow*. The event is known at the close of the bar that settles it.
* **CHoCH.** After a sweep, a close above the most recent confirmed entry-timeframe swing high
  (``k_entry``) formed before the sweep extreme, on the settling bar or within
  ``choch_window_bars`` after it. A lower low than the sweep extreme first ends the search
  (``new_extreme``).
* **FVG.** The first three-bar gap of the displacement (from the sweep extreme to the CHoCH bar):
  bars ``i - 2, i - 1, i`` consecutive in time with ``low[i] > high[i - 2]`` and a gap of at least
  ``fvg_min_size_atr`` ATR (the sweep's ATR). Bars across a break in the data (weekend, daily
  break, a hole) cannot form a gap.

A result that needs bars the data does not have yet is ``pending``: it is never decided early."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import Strategy
from app.data.sessions import MARKET_TZ, hhmm_minutes, market_holidays
from app.smc.primitives import Level, LevelBook, atr, swing_highs


@dataclass(frozen=True)
class Side:
    """Entry bars seen from one direction: real prices for ``buy``, negated for ``sell``."""

    direction: str
    sign: float
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    ts: np.ndarray  # bar open, int64 ns
    step_ns: int
    after_gap: np.ndarray  # True for the first bar after a gap (and for the first bar)

    @classmethod
    def of(cls, entry: pd.DataFrame, direction: str) -> Side:
        h, lo, c = (entry[k].to_numpy(float) for k in ("high", "low", "close"))
        ts = pd.DatetimeIndex(entry["ts_utc"]).as_unit("ns").asi8
        step = (
            int((entry["close_utc"].iloc[0] - entry["ts_utc"].iloc[0]).value) if len(entry) else 0
        )
        gap = np.r_[True, np.diff(ts) > step] if len(ts) else np.zeros(0, dtype=bool)
        if direction == "buy":
            return cls("buy", 1.0, h, lo, c, ts, step, gap)
        return cls("sell", -1.0, -lo, -h, -c, ts, step, gap)

    def real(self, x: float) -> float:
        return float(self.sign * x)


@dataclass(frozen=True)
class Sweep:
    direction: str  # "buy" after sell-side liquidity is swept, "sell" after buy-side
    kind: str  # "sweep", "breakout", "shallow", or "off_session" (rule sets with a session rule)
    level: Level
    first_idx: int  # first bar beyond the level
    settled_idx: int  # bar whose close decided the kind
    extreme_idx: int
    extreme: float  # lowest low (buy) / highest high (sell) of the sweep bars
    atr: float  # ATR of the first bar
    depth_atr: float
    reason: str = ""  # for a breakout: "too_deep" or "no_close_back"


@dataclass(frozen=True)
class Choch:
    idx: int
    ref_idx: int  # the swing the close broke
    ref_price: float


@dataclass(frozen=True)
class Fvg:
    idx: int  # third bar of the gap
    low: float
    high: float
    size_atr: float


def classify(side: Side, level_price: float, j: int, a: float, p: Strategy) -> tuple | None:
    """(kind, settled, extreme_idx, depth, reason) of a level traded through at bar ``j`` on the
    side's frame (the level is below price), or None while it is pending."""
    n = len(side.close)
    lowest, ext = side.low[j], j
    for m in range(p.close_back_bars + 1):
        b = j + m
        if b >= n:
            return None
        if side.low[b] < lowest:
            lowest, ext = side.low[b], b
        depth = (level_price - lowest) / a
        if depth > p.breakout_depth_atr:
            return "breakout", b, ext, depth, "too_deep"
        if side.close[b] > level_price:
            kind = "sweep" if depth >= p.min_depth_atr else "shallow"
            return kind, b, ext, depth, ""
    return "breakout", j + p.close_back_bars, ext, depth, "no_close_back"


def sweep_allowed(entry: pd.DataFrame, after_gap: np.ndarray, p: Strategy) -> np.ndarray:
    """Bars that may start a sweep: all of them in v1; with V5-S only bars opening in the session
    window (New York, Monday to Friday, not a US market holiday) and not right after a gap."""
    n = len(entry)
    ok = np.ones(n, dtype=bool)
    if p.break_is_gap:
        ok &= ~after_gap
    if p.sweep_session is not None or p.skip_us_holidays:
        ny = entry["ts_utc"].dt.tz_convert(MARKET_TZ)
        if p.sweep_session is not None:
            mins = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
            lo, hi = (hhmm_minutes(t) for t in p.sweep_session)
            ok &= (mins >= lo) & (mins < hi) & (ny.dt.dayofweek < 5).to_numpy()
        if p.skip_us_holidays and n:
            day = ny.dt.tz_localize(None).dt.normalize()
            holidays = market_holidays(int(day.dt.year.min()), int(day.dt.year.max()))
            ok &= ~day.isin(list(holidays)).to_numpy()
    return ok


def detect_sweeps(entry: pd.DataFrame, levels: list[Level], p: Strategy) -> list[Sweep]:
    """Every level traded through, classified, in the order it was settled (both directions)."""
    a = atr(*(entry[k].to_numpy(float) for k in ("high", "low", "close")), p.atr_period)
    sides = {"buy": Side.of(entry, "buy"), "sell": Side.of(entry, "sell")}
    allowed = sweep_allowed(entry, sides["buy"].after_gap, p)
    book = LevelBook(entry, levels, p.max_age_days)
    out = []
    for j in range(len(entry)):
        traded = book.step(j)
        if np.isnan(a[j]):
            continue
        for direction, lvs in (("buy", traded["low"]), ("sell", traded["high"])):
            side = sides[direction]
            for lv in lvs:
                if not allowed[j]:
                    extreme = side.real(side.low[j])
                    out.append(
                        Sweep(direction, "off_session", lv, j, j, j, extreme, float(a[j]), 0.0)
                    )
                    continue
                res = classify(side, side.sign * lv.price, j, a[j], p)
                if res is None:
                    continue
                kind, settled, ext, depth, reason = res
                out.append(
                    Sweep(
                        direction,
                        kind,
                        lv,
                        j,
                        settled,
                        ext,
                        side.real(side.low[ext]),
                        float(a[j]),
                        round(float(depth), 6),
                        reason,
                    )
                )
    return sorted(out, key=lambda s: (s.settled_idx, s.first_idx, s.direction, s.level.key))


def find_choch(
    side: Side, sweep: Sweep, k: int, window: int, no_swing_after_gap: bool = False
) -> tuple[Choch | None, str]:
    """The CHoCH after a sweep, or (None, "no_reference" | "new_extreme" | "window" | "pending").
    With ``no_swing_after_gap`` (V5-S) the first bar after a gap cannot be the reference swing."""
    n = len(side.close)
    extreme = sweep.extreme * side.sign
    mask = swing_highs(side.high, k)
    if no_swing_after_gap:
        mask &= ~side.after_gap
    pivots = np.flatnonzero(mask)
    before = pivots[pivots < sweep.extreme_idx]
    if not len(before):
        return None, "no_reference"
    for j in range(sweep.settled_idx, sweep.settled_idx + window + 1):
        if j >= n:
            return None, "pending"
        if j > sweep.settled_idx and side.low[j] < extreme:
            return None, "new_extreme"
        usable = before[before + k <= j]
        if not len(usable):
            continue
        ref = int(usable[-1])
        if side.close[j] > side.high[ref]:
            return Choch(j, ref, side.real(side.high[ref])), ""
    return None, "window"


def find_fvg(side: Side, sweep: Sweep, choch: Choch, min_size_atr: float) -> Fvg | None:
    """The first gap of the displacement from the sweep extreme to the CHoCH bar."""
    for i in range(sweep.extreme_idx + 2, choch.idx + 1):
        if side.ts[i] - side.ts[i - 2] != 2 * side.step_ns:
            continue
        lo, hi = side.high[i - 2], side.low[i]
        if hi > lo and (hi - lo) / sweep.atr >= min_size_atr:
            a, b = side.real(lo), side.real(hi)
            return Fvg(i, min(a, b), max(a, b), round(float((hi - lo) / sweep.atr), 6))
    return None
