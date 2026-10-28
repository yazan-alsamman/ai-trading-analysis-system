"""Trade management: the rules T1-T4, L1-L5 and the bundles M0-M8 (docs/strategies/PREREG.md,
section 7) as one bar-by-bar engine shared by research and live.

Written for a buy; a sell runs on mirrored prices (``labels.Bars``). The trade enters at the close
of the signal bar ``d``; then, on each bar ``j = d + 1 ... d + horizon_bars``, in this order:

1. an exit alert given at the previous close fills at this bar's open, minus the SL slippage
   (the user's reaction);
2. the open at or below the SL: exit at the open minus the slippage. The exit reason is the rule
   that set the SL: ``sl``, ``breakeven`` (L1), ``trail`` (L2, L3) or ``time_tighten`` (L4);
3. a bar that closes after the session end of a scalp or intraday trade (bars missing before it,
   so the trade could not leave at the session end): the resting orders fill at the open if it
   reaches them (T2 at +1 R, the TP at its level), and the rest leaves at the open minus the
   slippage (``session_end_gap``). No price is invented, and swap runs to that actual exit time;
4. the low at or below the SL: exit at the SL minus the slippage (reason as in 2). An ambiguous bar
   counts as SL;
5. T2: the high reaches +1 R: half closes there (a resting limit, no slippage) when the TP is
   further away;
6. the high reaches the TP: exit at the TP (``tp``, or ``scale_out_tp`` for the rest after T2);
7. at the close: the last bar of the horizon exits at its close (``timeout``); a scalp or intraday
   trade exits at the close of the last bar that can close by its session end (``session_end``,
   the first bar with ``close + one bar > deadline``). Both are exits at a close, without
   slippage, as the timeout of ``labels.resolve``;
8. at the close, the exit rules give an alert for the next open, first in this order:
   L5 ``invalidation``, T3 ``dead_trade``, T1 ``profit_lock``, T4 ``fade``;
9. at the close, the SL rules move the SL up (never down), in force from the next bar.

Without rules (M0) this is ``labels.resolve`` with ``entry_mode = "close"``, bar for bar.

Definitions fixed here (PREREG section 7 leaves them open; docs/strategies/STAGE_A.md):
"+1 R" for L1-L3 is the best excursion so far (highs) at a close; T4 arms at a close with open
profit >= 0.5 R and fires at a later close: a body that engulfs the previous body against the
trade, or a close beyond EMA(20) against the trade (whatever side the earlier closes were on);
L3 uses the last swing low confirmed by the close (k bars after it) and the ATR at that close; L5
of a breakout counts consecutive closes strictly back inside the level broken at the signal; a
series L5 (pullback, ranges) fires only on source bars that closed after the entry. Net R =
gross R (weighted over the parts of a scale-out) - slippage on the parts that left by a stop or
an alert - the round-trip cost; the 2x stress run doubles both. Exit time: the bar's open for an
exit at the open, its close otherwise (for swap)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import trading_indicators as ti

from app.config import Bundle, Instrument, Rules
from app.setups.labels import Bars, round_trip
from app.smc.primitives import swing_lows
from app.strategies.base import STEP, Candidate, Thesis, ns

EXIT_REASONS = (
    "tp",
    "profit_lock",
    "scale_out_tp",
    "trail",
    "breakeven",
    "dead_trade",
    "fade",
    "invalidation",
    "time_tighten",
    "sl",
    "timeout",
    "session_end",
    "session_end_gap",
)
SL_TAGS = {"L1": "breakeven", "L2": "trail", "L3": "trail", "L4": "time_tighten"}


@dataclass(frozen=True)
class Market:
    """Entry-frame data the rules read, seen from one direction (prices negated for a sell)."""

    bars: Bars
    atr: np.ndarray  # ATR(14) of the entry frame (a distance, not mirrored)
    ema: np.ndarray  # EMA(20) of the entry frame, mirrored
    swing: np.ndarray  # last swing low (mirrored) confirmed by each bar's close; NaN before any
    close_ns: np.ndarray
    step_ns: int

    @classmethod
    def of(cls, frame: pd.DataFrame, direction: str, timeframe: str, rp: Rules) -> Market:
        bars = Bars.of(frame, direction)
        k = rp.L3_swing_k
        lows = swing_lows(bars.low, k)
        swing = np.full(len(frame), np.nan)
        confirmed = np.flatnonzero(lows) + k  # known at the close of bar i + k
        ok = confirmed < len(frame)
        swing[confirmed[ok]] = bars.low[np.flatnonzero(lows)[ok]]
        swing = pd.Series(swing).ffill().to_numpy()
        return cls(
            bars=bars,
            atr=ti.atr(frame, rp.atr_period).to_numpy(),
            ema=bars.sign * ti.ema(frame["close"], rp.T4_ema).to_numpy(),
            swing=swing,
            close_ns=ns(frame["close_utc"]),
            step_ns=STEP[timeframe].value,
        )


@dataclass(frozen=True)
class Outcome:
    state: str  # CLOSED or PENDING
    reason: str  # an EXIT_REASONS value, or "active" when PENDING
    exit_idx: int | None = None
    exit_price: float | None = None  # the final exit, real price, slippage included
    exit_ns: int | None = None
    gross: float | None = None  # weighted gross R, unrounded
    cost_r: float = 0.0
    slip_r: float = 0.0  # applied slippage in R (weighted)
    scaled: bool = False

    @property
    def gross_r(self) -> float | None:
        return None if self.gross is None else round(self.gross, 6)

    def net_r(self, k: float = 1.0) -> float | None:
        if self.gross is None:
            return None
        return round(self.gross - k * self.slip_r - k * self.cost_r, 6)


def manage(
    m: Market,
    c: Candidate,
    bundle: Bundle,
    rp: Rules,
    inst: Instrument,
    l5: str | None = None,
    thesis: Thesis | None = None,
) -> Outcome:
    """The managed outcome of the armed candidate ``c`` under ``bundle``. ``l5`` is the
    strategy's L5 kind ("level", "series" or None) and ``thesis`` its series for that direction."""
    b = m.bars
    s = b.sign
    if s != c.sign:
        raise ValueError("the market is seen from the other direction")
    rules = set(bundle.rules)
    if "L5" in rules and l5 == "series" and thesis is None:
        raise ValueError(f"{c.strategy}: L5 needs the thesis series")
    d, n = c.idx, len(b.close)
    entry, sl, risk = s * c.entry, s * c.sl, c.risk
    tp = s * c.tp if bundle.tp and c.tp is not None else None
    level = s * c.level if c.level is not None else None
    rt = round_trip(c.spread, inst)
    cost, slip_px = rt / risk, inst.sl_slippage
    slip = slip_px / risk
    h = c.horizon_bars
    deadline = c.deadline.value if c.deadline is not None else None
    entry_ns = m.close_ns[d]
    one_r = entry + rp.T2_at_r * risk

    origin, pending = "sl", None
    weight, scaled = 1.0, False
    parts: list[tuple[float, float, bool]] = []  # (weight, gross R, left by a stop or an alert)
    mfe, hh, armed, back = -np.inf, -np.inf, False, 0

    def done(j: int, raw: float, reason: str, slipped: bool, at_open: bool = False) -> Outcome:
        allp = [*parts, (weight, (raw - entry) / risk, slipped)]
        return Outcome(
            "CLOSED",
            reason,
            j,
            s * (raw - slip_px) if slipped else s * raw,
            int(m.close_ns[j] - (m.step_ns if at_open else 0)),
            sum(w * g for w, g, _ in allp),
            cost,
            sum(w * slip for w, _, sl_ in allp if sl_),
            scaled,
        )

    for j in range(d + 1, d + h + 1):
        if j >= n:
            return Outcome("PENDING", "active", scaled=scaled)
        o, hi, lo, cl = b.open[j], b.high[j], b.low[j], b.close[j]
        if pending is not None:
            return done(j, o, pending, True, at_open=True)
        if o <= sl:
            return done(j, o, origin, True, at_open=True)
        if deadline is not None and m.close_ns[j] > deadline:  # bars missing before the end
            if "T2" in rules and not scaled and o >= one_r and (tp is None or tp > one_r):
                parts.append((rp.T2_fraction, rp.T2_at_r, False))
                weight, scaled = 1.0 - rp.T2_fraction, True
            if tp is not None and o >= tp:
                return done(j, tp, "scale_out_tp" if scaled else "tp", False, at_open=True)
            return done(j, o, "session_end_gap", True, at_open=True)
        if lo <= sl:
            return done(j, sl, origin, True)
        if "T2" in rules and not scaled and hi >= one_r and (tp is None or tp > one_r):
            parts.append((rp.T2_fraction, rp.T2_at_r, False))
            weight, scaled = 1.0 - rp.T2_fraction, True
        if tp is not None and hi >= tp:
            return done(j, tp, "scale_out_tp" if scaled else "tp", False)

        mfe, hh = max(mfe, (hi - entry) / risk), max(hh, hi)
        if j == d + h:
            return done(j, cl, "timeout", False)
        if deadline is not None and m.close_ns[j] + m.step_ns > deadline:
            return done(j, cl, "session_end", False)
        elapsed = j - d

        if "L5" in rules and l5 == "level" and level is not None:
            back = back + 1 if cl < level else 0
            if back >= rp.L5_closes:
                pending = "invalidation"
        elif "L5" in rules and l5 == "series":
            if thesis.against[j] and thesis.source_close[j] > entry_ns:
                pending = "invalidation"
        if pending is None and "T3" in rules:
            if elapsed >= rp.T3_elapsed * h and mfe < rp.T3_max_mfe_r:
                pending = "dead_trade"
        if pending is None and "T1" in rules and tp is not None:
            if elapsed >= rp.T1_elapsed * h and cl - entry >= rp.T1_progress * (tp - entry):
                pending = "profit_lock"
        if "T4" in rules:
            if pending is None and armed:
                po, pc = b.open[j - 1], b.close[j - 1]
                engulf = cl < o and o >= max(po, pc) and cl <= min(po, pc)
                if engulf or cl < m.ema[j]:
                    pending = "fade"
            if (cl - entry) / risk >= rp.T4_arm_r:
                armed = True

        moves: list[tuple[float, str]] = []
        if mfe >= rp.L_from_r:
            if "L1" in rules:
                moves.append((entry + rt, "L1"))
            if "L2" in rules and not np.isnan(m.atr[j]):
                moves.append((hh - rp.L2_atr_mult * m.atr[j], "L2"))
            if "L3" in rules and not np.isnan(m.swing[j]) and not np.isnan(m.atr[j]):
                moves.append((m.swing[j] - rp.L3_buffer_atr * m.atr[j], "L3"))
        if "L4" in rules and elapsed >= rp.L4_elapsed * h:
            floor = entry + rp.L4_sl_r * risk
            if cl > floor:
                moves.append((floor, "L4"))
        for price, rule in moves:
            if price > sl:
                sl, origin = price, SL_TAGS[rule]
    return Outcome("PENDING", "active", scaled=scaled)  # horizon of 0 bars
