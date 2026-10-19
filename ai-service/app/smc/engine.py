"""The Sweep -> CHoCH -> FVG strategy and the setup lifecycle, run bar by bar on closed 15m bars.

The rules are written once, for buys (a sweep of sell-side liquidity under a low). Sells run the
same code on mirrored prices (``primitives.mirror``) and are mapped back, so both sides follow
identical logic. Each closed bar is processed in order and only sees what was known at its close, so
running on a prefix of the data gives exactly the same setups and events up to that point.

Prices are bid. A setup's costs are charged in R at exit (``CostParams``), which keeps fills on the
bid series and the comparison between setups simple."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.data.sessions import trading_day
from app.smc.params import CostParams, StrategyParams
from app.smc.primitives import (
    Level,
    atr,
    htf_swing_levels,
    mirror,
    previous_day_levels,
    session_levels,
    swing_highs,
)

H1 = pd.Timedelta(hours=1)
H4 = pd.Timedelta(hours=4)

FINAL_STATES = {"DISCARDED", "REJECTED", "EXPIRED", "INVALIDATED", "CLOSED"}


@dataclass
class Setup:
    setup_id: str
    direction: str  # "buy" or "sell"
    level: Level  # the swept level (in real prices)
    sweep_idx: int  # bar index where the sweep was confirmed
    extreme_idx: int
    extreme: float
    atr: float
    scan_level: float  # the swept level in the scanner's frame (negated for sells); internal
    state: str = "DEVELOPING"
    extensions: int = 0  # bars that moved the sweep extreme (``StrategyParams.extend_sweep``)
    choch_idx: int | None = None
    ref_idx: int | None = None  # the 15m swing the CHoCH closed beyond
    ref_price: float | None = None
    fvg_idx: int | None = None  # bar i of the three-bar gap (i-2, i-1, i)
    fvg_low: float | None = None
    fvg_high: float | None = None
    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    tp_source: str | None = None  # the target level's key, or "cap"
    r_multiple: float | None = None
    spread: float | None = None
    fill_idx: int | None = None
    exit_idx: int | None = None
    exit_price: float | None = None
    outcome: str | None = None  # "tp", "sl" or "timeout"
    realized_r: float | None = None  # gross, before costs
    net_r: float | None = None
    reason: str | None = None  # why a setup ended without a trade
    events: list[tuple[int, str, str]] = field(default_factory=list)  # (bar index, state, reason)

    def move(self, idx: int, state: str, reason: str = "") -> None:
        self.state = state
        self.events.append((idx, state, reason))
        if state in ("DISCARDED", "REJECTED", "EXPIRED", "INVALIDATED"):
            self.reason = reason


@dataclass
class _Probe:
    level: Level
    idx: int


class _LongScanner:
    """Buy-side rules on one price frame (real prices for buys, mirrored for sells)."""

    def __init__(
        self,
        m15: pd.DataFrame,
        levels: list[Level],
        params: StrategyParams,
        costs: CostParams,
        direction: str,
    ):
        self.p, self.c, self.direction = params, costs, direction
        self.sign = 1.0 if direction == "buy" else -1.0
        self.ts = m15["ts_utc"].reset_index(drop=True)
        self.o = m15["open"].to_numpy(float)
        self.h = m15["high"].to_numpy(float)
        self.lo = m15["low"].to_numpy(float)
        self.cl = m15["close"].to_numpy(float)
        self.spread = m15["spread"].fillna(0.0).to_numpy(float)
        self.atr = atr(self.h, self.lo, self.cl, params.atr_period)
        self.day = trading_day(self.ts).to_numpy().astype("datetime64[D]")
        # 15m swing highs: the CHoCH reference for a buy. Confirmed when bar i + k closes.
        sh = np.flatnonzero(swing_highs(self.h, params.k_ltf))
        self.sh_idx = sh.tolist()
        self.sh_confirm = (sh + params.k_ltf).tolist()
        self.pending = sorted(levels, key=lambda lv: lv.available_at)
        self.next_level = 0
        self.lows: list[Level] = []  # sweep candidates
        self.highs: list[Level] = []  # TP candidates
        self.current_day = None
        self.developing: Setup | None = None
        self.probe: _Probe | None = None
        self.open_setups: list[Setup] = []
        self.setups: list[Setup] = []

    # ---- helpers -------------------------------------------------------------------------------

    def _real(self, x: float | None) -> float | None:
        return None if x is None else self.sign * x

    def _real_level(self, lv: Level) -> Level:
        if self.sign > 0:
            return lv
        kind = "high" if lv.kind == "low" else "low"
        return Level(-lv.price, kind, lv.source, lv.origin_ts, lv.available_at, lv.origin_day)

    def _update_levels(self, j: int) -> None:
        t = self.ts.iloc[j]
        pending = self.pending
        while self.next_level < len(pending) and pending[self.next_level].available_at <= t:
            lv = pending[self.next_level]
            (self.lows if lv.kind == "low" else self.highs).append(lv)
            self.next_level += 1
        day = self.day[j]
        if day == self.current_day:
            return
        self.current_day = day
        max_age = self.p.level_max_age_days

        def fresh(lv: Level) -> bool:
            return np.busday_count(lv.origin_day, day) <= max_age

        self.lows = [lv for lv in self.lows if fresh(lv)]
        self.highs = [lv for lv in self.highs if fresh(lv)]

    def _ref_high(self, extreme_idx: int, j: int) -> int | None:
        """Most recent confirmed 15m swing high (by bar j's close) formed before the extreme."""
        pos = bisect.bisect_left(self.sh_idx, extreme_idx) - 1
        while pos >= 0:
            if self.sh_confirm[pos] <= j:
                return int(self.sh_idx[pos])
            pos -= 1
        return None

    # ---- lifecycle of ARMED / ACTIVE setups -----------------------------------------------------

    def _advance(self, s: Setup, j: int) -> None:
        if s.state == "ARMED":
            if j - s.choch_idx > self.p.entry_window:
                s.move(j, "EXPIRED", "no fill within the entry window")
                return
            if self.o[j] <= s.sl:
                s.move(j, "INVALIDATED", "gapped through the SL before the fill")
                return
            if self.lo[j] <= s.entry:
                s.fill_idx = j
                s.move(j, "ACTIVE", "entry filled")
                # On the fill bar only the SL can be hit: its path before the fill is unknown.
                if self.lo[j] <= s.sl:
                    self._close(s, j, "sl")
                return
            if self.h[j] >= s.tp:
                s.move(j, "INVALIDATED", "TP level reached before the fill")
            return
        if s.state == "ACTIVE":
            if self.lo[j] <= s.sl:  # stop first when both are touched
                self._close(s, j, "sl")
            elif self.h[j] >= s.tp:
                self._close(s, j, "tp")
            elif j - s.fill_idx + 1 >= self.p.horizon:
                self._close(s, j, "timeout")

    def _close(self, s: Setup, j: int, outcome: str) -> None:
        risk = s.entry - s.sl
        if outcome == "sl":
            exit_px = s.sl - self.c.sl_slippage
        elif outcome == "tp":
            exit_px = s.tp
        else:
            exit_px = self.cl[j]
        s.exit_idx, s.exit_price, s.outcome = j, exit_px, outcome
        s.realized_r = (exit_px - s.entry) / risk
        s.net_r = s.realized_r - self.c.round_trip(s.spread) / risk
        s.move(j, "CLOSED", outcome)

    # ---- the rules ------------------------------------------------------------------------------

    def _try_choch(self, s: Setup, j: int) -> None:
        if self.lo[j] < s.extreme and j > s.sweep_idx:
            depth = s.scan_level - self.lo[j]
            if self.p.extend_sweep and depth <= self.p.max_sweep_atr * s.atr:
                s.extreme, s.extreme_idx = float(self.lo[j]), j  # the sweep is still running
                s.extensions += 1
            else:
                s.move(j, "DISCARDED", "new extreme before the CHoCH")
                self.developing = None
                return
        if j - s.sweep_idx > self.p.choch_window:
            s.move(j, "DISCARDED", "no CHoCH within the window")
            self.developing = None
            return
        ref = self._ref_high(s.extreme_idx, j)
        if ref is None or self.cl[j] <= self.h[ref]:
            return
        s.choch_idx, s.ref_idx, s.ref_price = j, ref, float(self.h[ref])
        self.developing = None
        a = s.atr
        first = s.extreme_idx + 2  # the gap's three bars lie in the move from the extreme
        if self.p.fvg_max_bars_before_choch is not None:
            first = max(first, j - self.p.fvg_max_bars_before_choch)
        for i in range(first, j + 1):
            gap_low, gap_high = self.h[i - 2], self.lo[i]
            if gap_high - gap_low >= self.p.min_fvg_atr * a:
                s.fvg_idx, s.fvg_low, s.fvg_high = i, float(gap_low), float(gap_high)
                break
        else:
            s.move(j, "DISCARDED", "no qualifying FVG")
            return
        if self.p.entry == "midpoint":
            entry = (s.fvg_low + s.fvg_high) / 2
        else:
            entry = s.fvg_high
        spread = float(self.spread[j])
        sl = s.extreme - self.p.sl_buffer_atr * a - spread
        risk = entry - sl
        s.entry, s.sl, s.spread = float(entry), float(sl), spread
        if risk <= 0:
            s.move(j, "REJECTED", "non-positive risk")
            return
        targets = [lv for lv in self.highs if lv.price > entry]
        tp = tp_source = None
        for lv in sorted(targets, key=lambda lv: lv.price):  # nearest first
            if (lv.price - entry) / risk >= self.p.min_r:
                tp, tp_source = lv.price, self._real_level(lv).key
                break
        if tp is None:
            s.move(j, "REJECTED", "no opposite liquidity at 1.5R or more")
            return
        if (tp - entry) / risk > self.p.max_r:
            tp, tp_source = entry + self.p.max_r * risk, "cap"
        s.tp, s.tp_source = float(tp), tp_source
        s.r_multiple = (tp - entry) / risk
        if self.cl[j] <= entry:
            s.move(j, "REJECTED", "price already at or below the entry")
            return
        s.move(j, "ARMED", "rules met")
        self.open_setups.append(s)

    def _new_setup(self, lv: Level, sweep_idx: int, first_idx: int) -> None:
        span = range(first_idx, sweep_idx + 1)
        extreme_idx = min(span, key=lambda i: (self.lo[i], i))
        a = self.atr[sweep_idx]
        real = self._real_level(lv)
        s = Setup(
            setup_id=f"xau-{self.direction}-{real.source}-{real.price:.2f}-{real.origin_ts:%Y%m%d%H%M}",
            direction=self.direction,
            level=real,
            sweep_idx=sweep_idx,
            extreme_idx=extreme_idx,
            extreme=float(self.lo[extreme_idx]),
            atr=float(a),
            scan_level=lv.price,
        )
        s.move(sweep_idx, "DEVELOPING", "sweep")
        self.setups.append(s)
        self.developing = s

    def step(self, j: int) -> None:
        self._update_levels(j)
        for s in list(self.open_setups):
            if j > (s.fill_idx if s.state == "ACTIVE" else s.choch_idx):
                self._advance(s, j)
            if s.state in FINAL_STATES:
                self.open_setups.remove(s)

        if self.developing is not None:
            self._try_choch(self.developing, j)

        a = self.atr[j]
        if np.isnan(a):
            return
        lo, cl = self.lo[j], self.cl[j]

        if self.probe is not None:  # a sweep whose first bar closed beyond the level
            lv, first = self.probe.level, self.probe.idx
            self.probe = None
            depth = lv.price - min(self.lo[first], lo)
            if cl > lv.price and depth <= self.p.max_sweep_atr * a and self.developing is None:
                self._new_setup(lv, j, first)
                self._try_choch(self.developing, j)

        traded = [lv for lv in self.lows if lo < lv.price]
        if not traded:
            return
        self.lows = [lv for lv in self.lows if lo >= lv.price]  # traded-through levels are spent
        if self.developing is not None:
            return
        valid = [
            lv
            for lv in traded
            if self.p.min_sweep_atr * a <= lv.price - lo <= self.p.max_sweep_atr * a
        ]
        if not valid:
            return
        lv = min(valid, key=lambda lv: lv.price)  # the deepest level swept
        if cl > lv.price:
            self._new_setup(lv, j, j)
            self._try_choch(self.developing, j)
        else:
            self.probe = _Probe(lv, j)

    def finish(self) -> list[Setup]:
        return self.setups


def _real_prices(s: Setup) -> Setup:
    """Map a mirrored (sell) setup back to real prices."""
    for name in ("extreme", "ref_price", "entry", "sl", "tp", "exit_price"):
        v = getattr(s, name)
        if v is not None:
            setattr(s, name, -v)
    if s.fvg_low is not None:
        s.fvg_low, s.fvg_high = -s.fvg_high, -s.fvg_low
    return s


def build_levels(h1: pd.DataFrame, h4: pd.DataFrame, m15: pd.DataFrame, p: StrategyParams):
    levels = (
        htf_swing_levels(h1, H1, p.k_htf, "1h")
        + htf_swing_levels(h4, H4, p.k_htf, "4h")
        + previous_day_levels(m15, p.entry_timeframe)
    )
    if p.session_levels:
        levels += session_levels(m15, p.entry_timeframe)
    return levels


def run(
    m15: pd.DataFrame,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
    params: StrategyParams | None = None,
    costs: CostParams | None = None,
) -> list[Setup]:
    """Scan every closed 15m bar and return all setups (both directions) with their lifecycle.

    Bar indices in the result refer to rows of ``m15``. Pass only bars that had closed by the time
    of interest; higher-timeframe frames are filtered to bars that closed by then as well."""
    params = params or StrategyParams()
    costs = costs or CostParams()
    m15 = m15.reset_index(drop=True)
    end = m15["ts_utc"].iloc[-1] + params.entry_timeframe if len(m15) else None
    if end is not None:
        h1 = h1[h1["ts_utc"] + H1 <= end]
        h4 = h4[h4["ts_utc"] + H4 <= end]
    result: list[Setup] = []
    for direction, frames in (
        ("buy", (m15, h1, h4)),
        ("sell", (mirror(m15), mirror(h1), mirror(h4))),
    ):
        f15, f1, f4 = frames
        scanner = _LongScanner(f15, build_levels(f1, f4, f15, params), params, costs, direction)
        for j in range(len(f15)):
            scanner.step(j)
        setups = scanner.finish()
        if direction == "sell":
            setups = [_real_prices(s) for s in setups]
        result.extend(setups)
    result.sort(key=lambda s: (s.sweep_idx, s.direction))
    return result
