"""Signal-based position management (L1-M; docs/MARKET_STRUCTURE_DEFINITIONS.md, section L1-M).

A **signal** is every pattern of the rule set at its decision bar's close (armed or not). Per
instrument there is at most one position. A position opens at the close of an armed setup's
decision bar when none is open; then, bar by bar after the entry:

1. a gap through the SL at the open, the SL, then the TP (an ambiguous bar counts as SL);
2. at the close: a signal in the other direction (or in both) closes it (``opposite``); a signal
   in the same direction moves the horizon to ``horizon_bars`` after it, capped at
   ``max_hold_bars`` after the entry, before the horizon is checked at that close;
3. the close of the horizon bar ends it (``timeout``, or ``max_hold`` at the cap).

A same-direction setup while a position is open opens nothing. An opposite setup may open a new
position at the close where it closed the old one. Signals in both directions on one bar open
nothing. Costs as ``labels``: round trip at the entry bar's spread, SL slippage on SL exits;
``net_r(k)`` scales both by ``k`` for the cost sensitivity. Swap is not modelled; ``rollovers``
counts the 17:00 New York day ends a trade spans."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import Instrument, Strategy, instruments
from app.data.aggregate import trading_day
from app.setups.builder import Plan, Setup, build
from app.setups.labels import Bars, round_trip
from app.smc.detector import detect

BUY, SELL, BOTH = 1, -1, 2


@dataclass(frozen=True)
class Managed:
    state: str  # CLOSED or PENDING
    reason: str  # tp, sl, opposite, timeout, max_hold (or "active" when PENDING)
    exit_idx: int | None = None
    exit_price: float | None = None
    gross_r: float | None = None
    cost_r: float = 0.0
    slip_r: float = 0.0  # applied only on SL exits
    extensions: int = 0

    def net_r(self, k: float = 1.0) -> float:
        return self.gross_r - k * (self.cost_r + self.slip_r)


def signal_sides(n: int, setups: list[Setup]) -> np.ndarray:
    """Per entry bar: BUY, SELL or BOTH when a pattern was decided at its close, else 0."""
    side = np.zeros(n, dtype=np.int8)
    for st in setups:
        j = st.decision_idx
        code = BUY if st.pattern.direction == "buy" else SELL
        side[j] = code if side[j] in (0, code) else BOTH
    return side


def manage(
    bars: Bars, d: int, pl: Plan, side: np.ndarray, spread: float, p: Strategy, inst: Instrument
) -> Managed:
    """The managed outcome of a position entered at the close of bar ``d``."""
    s = bars.sign
    own = BUY if s > 0 else SELL
    entry, sl, tp = s * pl.entry, s * pl.sl, s * pl.tp
    cost = round_trip(spread, inst) / pl.risk if inst.cost_extra_frac is not None else 0.0
    slip = (inst.sl_slippage or 0.0) / pl.risk
    cap = d + p.max_hold_bars
    last = d + p.horizon_bars
    ext = 0

    def done(j: int, raw: float, reason: str) -> Managed:
        on_sl = reason == "sl"
        return Managed(
            "CLOSED",
            reason,
            j,
            s * (raw - (inst.sl_slippage or 0.0) if on_sl else raw),
            round((raw - entry) / pl.risk, 6),
            round(cost, 6),
            round(slip if on_sl else 0.0, 6),
            ext,
        )

    for j in range(d + 1, len(bars.close)):
        if bars.open[j] <= sl:
            return done(j, bars.open[j], "sl")
        if bars.low[j] <= sl:
            return done(j, sl, "sl")
        if bars.high[j] >= tp:
            return done(j, tp, "tp")
        sig = side[j]
        if sig == BOTH or sig == -own:
            return done(j, bars.close[j], "opposite")
        if sig == own:
            last = max(last, min(j + p.horizon_bars, cap))
            ext += 1
        if j == last:
            return done(j, bars.close[j], "max_hold" if last == cap else "timeout")
    return Managed("PENDING", "active", extensions=ext)


def trades(frames: dict[str, pd.DataFrame], symbol: str, p: Strategy) -> pd.DataFrame:
    """Every position the managed rules open on these frames, in order."""
    inst = instruments()[symbol]
    entry = frames[p.entry_timeframe]
    setups = build(frames, detect(frames, p), p)
    side = signal_sides(len(entry), setups)
    sides = {d: Bars.of(entry, d) for d in ("buy", "sell")}
    ts = entry["ts_utc"]
    days = trading_day(ts).to_numpy()
    rows = []
    flat_after = -1  # the position open at bars < flat_after; flat at the close of flat_after
    for st in sorted(setups, key=lambda x: x.decision_idx):
        j = st.decision_idx
        if j < flat_after or side[j] == BOTH or st.plan.state != "ARMED":
            continue
        pl = st.plan
        m = manage(sides[st.pattern.direction], j, pl, side, st.spread, p, inst)
        closed = m.state == "CLOSED"
        rows.append(
            {
                "symbol": symbol,
                "setup_id": st.setup_id,
                "direction": st.pattern.direction,
                "year": ts.iloc[j].year,
                "decision_idx": j,
                "decision_utc": ts.iloc[j],
                "atr": st.pattern.sweep.atr,
                "risk": pl.risk,
                "r_multiple": pl.r_multiple,
                "state": m.state,
                "reason": m.reason,
                "exit_utc": entry["close_utc"].iloc[m.exit_idx] if closed else None,
                "bars_held": m.exit_idx - j if closed else None,
                "extensions": m.extensions,
                "rollovers": len(np.unique(days[j : m.exit_idx + 1])) - 1 if closed else None,
                "gross_r": m.gross_r,
                "cost_r": m.cost_r,
                "slip_r": m.slip_r,
                "net_r": m.net_r() if closed else None,
                "net_r_2x": m.net_r(2) if closed else None,
                "y": int(m.reason == "tp") if closed else None,
            }
        )
        if not closed:
            break  # nothing after an undecided position can be decided
        flat_after = m.exit_idx
    return pd.DataFrame(rows)
