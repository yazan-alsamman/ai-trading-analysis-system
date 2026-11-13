"""The gold level strategies served live (P7 F1, ``docs/phase7/PLAN.md``).

The five of ``GOLD_V1.md`` (LVL4H, PIVOT) and ``GOLD_SHADOW.md`` (PIVW, ASIA, PWHL) and ROUND
(``GOLD_ROUND.md`` §6), with the research code the EA is matched to (``gold_combo.levels``,
``gold_lab.simulate`` M8). Nothing is re-implemented: the same frames give the same trades as
``gold_live.five_trades`` (``check`` compares them day by day).

One setup per strategy, level and New York day, as of ``as_of``:

* ``ARMED`` from 02:00 New York (the window opens; the stop order waits at the level). Its side
  is the side a break from the current price would take, its stop D is the current D;
* ``ACTIVE`` at the close of the bar that touched the level (the fill), with the stop at
  entry ∓ D; ``SL_MOVED`` steps as M8 moves the stop;
* ``CLOSED`` at the stop (``stop``, or ``trailing_stop`` once moved), the horizon or 16:45
  (``time``), with the net R after costs and the stop slip;
* ``EXPIRED`` at 16:00 New York when the level was never touched;
* ``INVALIDATED`` at the touch when the trade is not taken: the cost cap (``cost_cap``) or the
  strategy already in a trade (``strategy_busy``).

Nothing after ``as_of`` is read: the frames end at the last bar closed by then."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.catalog import registry
from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_round as gr
from app.research import gold_shadow as gs

NY = gl.NY
WINDOW = gc.WINDOWS[ge.LVL_WINDOW]  # 02:00-16:00 New York (both v1 settings use it)
EXIT_MIN = 16 * 60 + 45
ORDER = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL", "ROUND")  # as gold_live.five_trades
D_RULE = {"PIVOT": "ATR(14, 1h)"}  # every other strategy: 0.75 x ATR(14, 4h)


@dataclass(frozen=True)
class Step:
    state: str
    at: pd.Timestamp
    reason: str | None = None
    realized_r: float | None = None
    sl: float | None = None


@dataclass(frozen=True)
class LevelSetup:
    strategy: str
    kind: str
    day: int  # New York date, yyyymmdd
    level: float
    direction: str  # buy / sell
    entry: float
    risk: float  # D
    sl: float  # the stop as of as_of
    path: tuple[Step, ...]
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def state(self) -> str:
        """The contract state: a stop move (``SL_MOVED``) keeps the trade ``ACTIVE``."""
        return next(p.state for p in reversed(self.path) if p.state != "SL_MOVED")


def specs(cx: gl.Ctx) -> dict[str, tuple[dict, np.ndarray, int, float | None]]:
    """Per strategy: its levels by D1 bar, D per 5m bar, horizon (5m bars) and cost cap."""
    d4 = ge.LVL_MULT * cx.atr4h
    lvl = (ge.LVL_HORIZON, ge.LVL_CAP)
    return {
        "LVL4H": (gc.day_levels(cx), d4, *lvl),
        "PIVOT": (gc.pivot_levels(cx), cx.atr1h, ge.PIV_HORIZON, None),
        "PIVW": (gc.pivot_levels(cx), d4, *lvl),
        "ASIA": (gs.asia_levels(cx), d4, *lvl),
        "PWHL": (gs.week_levels(cx), d4, *lvl),
        "ROUND": (gr.round_levels(cx, gr.SHADOW_STEP), d4, *lvl),
    }


def with_current_day(d1: pd.DataFrame, m5: pd.DataFrame) -> pd.DataFrame:
    """The closed D1 bars plus the trading day in progress (17:00 New York to 17:00), built from
    its 5m bars so far, as the research store holds a row for every day. The levels read only
    earlier days; the row places today's bars in their day."""
    if m5.empty:
        return d1
    t = m5["ts_utc"].iloc[-1].tz_convert(NY)
    start = t.normalize() + pd.Timedelta(hours=17)
    if t < start:
        start -= pd.Timedelta(days=1)
    start = start.tz_convert("UTC")
    if len(d1) and d1["ts_utc"].iloc[-1] >= start:
        return d1
    bars = m5[m5["ts_utc"] >= start]
    if bars.empty:
        return d1
    end = (start.tz_convert(NY) + pd.Timedelta(days=1)).normalize() + pd.Timedelta(hours=17)
    row = {c: np.nan for c in d1.columns}
    row.update(
        {
            "ts_utc": start,
            "close_utc": end.tz_convert("UTC"),
            "open": bars["open"].iloc[0],
            "high": bars["high"].max(),
            "low": bars["low"].min(),
            "close": bars["close"].iloc[-1],
        }
    )
    return pd.concat([d1, pd.DataFrame([row])[d1.columns]], ignore_index=True)


def at_ny(day: int, minutes: int) -> pd.Timestamp:
    d = pd.Timestamp(str(day)) + pd.Timedelta(minutes=minutes)
    return d.tz_localize(NY).tz_convert("UTC")


def evidence(name: str, kind: str, level: float, risk: float) -> dict[str, Any]:
    """The common evidence shape (``PLAN.md``, "Built for more strategies")."""
    e = registry()[name]
    ar, en = e.kinds[kind]
    return {
        "strategy": name,
        "version": e.version,
        "entry_type": "stop",
        "exit_type": e.exit_type,
        "window_ny": "02:00-16:00",
        "exit_by_ny": "16:45",
        "d": float(risk),
        "d_rule": D_RULE.get(name, "0.75 x ATR(14, 4h)"),
        "facts": [
            {"key": "level_kind", "value": kind, "label_ar": ar, "label_en": en},
            {
                "key": "level_price",
                "value": float(level),
                "label_ar": "سعر المستوى",
                "label_en": "level price",
            },
        ],
        "volatility": None,
    }


def trade_path(
    t: pd.Series, cx: gl.Ctx, events: list, created: pd.Timestamp, closed: bool, horizon: int
) -> tuple[list[Step], float]:
    """ARMED, ACTIVE, the stop moves and (when ``closed``) CLOSED; and the stop as of the end."""
    i, j, s = int(t["i"]), int(t["j"]), float(t["dir"])
    sl0 = float(t["entry"]) - s * float(t["risk"])
    cu = cx.m["close_utc"]
    path = [Step("ARMED", created), Step("ACTIVE", cu.iloc[i], sl=sl0)]
    sl = sl0
    for name, ei, first, new in events:
        if name == t["strategy"] and ei == i and first - 1 <= j:
            path.append(Step("SL_MOVED", cu.iloc[first - 1], sl=float(new)))
            sl = float(new)
    if closed:
        moved = sl != sl0
        why = "time" if t["exit"] == "time" else ("trailing_stop" if moved else "stop")
        path.append(Step("CLOSED", cu.iloc[j], why, float(t["net_slip"])))
    return path, sl


def scan_day(fr: dict[str, pd.DataFrame], as_of: pd.Timestamp) -> list[LevelSetup]:
    """Every setup of the New York day of ``as_of`` (empty before 02:00 and at weekends)."""
    ny = as_of.tz_convert(NY)
    day, mins = ny.year * 10000 + ny.month * 100 + ny.day, ny.hour * 60 + ny.minute
    if ny.day_of_week >= 5 or mins < WINDOW[0]:
        return []
    cx = gl.context(fr)
    last = len(cx.m) - 1
    today = np.flatnonzero((cx.ny_day == day) & (cx.ny_min >= WINDOW[0]))
    k = int(cx.day_idx[today[0]] if len(today) else cx.day_idx[last])
    created, expiry = at_ny(day, WINDOW[0]), at_ny(day, WINDOW[1])
    finished = mins >= EXIT_MIN
    out, events = [], []
    sp = specs(cx)
    for name in ORDER:
        lv_days, dist, horizon, cap = sp[name]
        sig = gc.levels(cx, name, lv_days, dist, WINDOW, horizon, None)
        sig = sig[cx.ny_day[sig["i"].to_numpy()] == day].reset_index(drop=True)
        cost = cx.spread[sig["i"].to_numpy()] + gl.COMMISSION
        capped = np.zeros(len(sig), bool) if cap is None else cost / sig["risk"].to_numpy() > cap
        # Two levels of one strategy touched on the same bar: the stop order nearer the bar's
        # open fills first (ties: the EA's level order) and the strategy is then busy. The
        # research's sort leaves this order to chance (docs/phase7/gold_levels_check.md).
        rank = {kd: n for n, kd in enumerate(lv_days)}
        near = np.abs(sig["entry"].to_numpy() - cx.o[sig["i"].to_numpy()])
        order = np.lexsort((sig["kind"].map(rank).to_numpy(), near, sig["i"].to_numpy()))
        first = np.zeros(len(sig), bool)
        seen: set[int] = set()
        for n in order:
            if not capped[n] and int(sig["i"].iloc[n]) not in seen:
                first[n] = True
                seen.add(int(sig["i"].iloc[n]))
        run_sig = sig[first].reset_index(drop=True)
        taken = gc.run(run_sig, cx, events) if len(run_sig) else None
        for kind, lv_day in lv_days.items():
            level = float(lv_day[k]) if k >= 0 else np.nan
            if not np.isfinite(level):
                continue
            touch = sig.index[sig["kind"] == kind]
            if not len(touch):  # never touched today
                d = float(dist[last])
                buy = cx.c[last] < level
                state = Step("EXPIRED", expiry) if mins >= WINDOW[1] else None
                path = [Step("ARMED", created)] + ([state] if state else [])
                out.append(
                    LevelSetup(
                        name,
                        kind,
                        day,
                        level,
                        "buy" if buy else "sell",
                        level,
                        d,
                        level - d if buy else level + d,
                        tuple(path),
                        evidence(name, kind, level, d),
                    )
                )
                continue
            r = sig.loc[touch[0]]
            i, s, risk = int(r["i"]), float(r["dir"]), float(r["risk"])
            entry = float(r["entry"])
            base = dict(
                strategy=name,
                kind=kind,
                day=day,
                level=level,
                direction="buy" if s > 0 else "sell",
                entry=entry,
                risk=risk,
                evidence=evidence(name, kind, level, risk),
            )
            row = None
            if taken is not None:
                hit = taken[(taken["i"] == i) & (taken["kind"] == kind)]
                row = hit.iloc[0] if len(hit) else None
            if row is None:
                why = "cost_cap" if capped[touch[0]] else "strategy_busy"
                path = (Step("ARMED", created), Step("INVALIDATED", cx.m["close_utc"].iloc[i], why))
                out.append(LevelSetup(**base, sl=entry - s * risk, path=path))
                continue
            j = int(row["j"])
            closed = row["exit"] == "sl" or j == i + horizon or finished
            steps, sl = trade_path(row, cx, events, created, closed, horizon)
            out.append(LevelSetup(**base, sl=sl, path=tuple(steps)))
    return out


# --- the proposed contract payload (PLAN.md F1; needs Yazan's agreement) ------------------------


def setup_id(instrument: str, profile: str, ls: LevelSetup) -> str:
    return f"{instrument.lower()}-{profile}-{ls.strategy.lower()}-{ls.kind.lower()}-{ls.day}"


def iso(t: pd.Timestamp) -> str:
    return t.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def payload(ls: LevelSetup, instrument: str, profile: str, tick: float = 0.01) -> dict[str, Any]:
    """The setup as the proposed contract would carry it: ``exit_type`` instead of a required
    ``tp`` (null here), the current ``sl``."""
    places = max(0, -int(np.floor(np.log10(tick))))
    out: dict[str, Any] = {
        "setup_id": setup_id(instrument, profile, ls),
        "state": ls.state,
        "direction": ls.direction,
        "entry": round(ls.entry, places),
        "sl": round(ls.sl, places),
        "tp": None,
        "exit_type": ls.evidence["exit_type"],
        "r_multiple": None,
        "probability": None,
        "ev_r": None,
        "ev_r_lower": None,
        "grade": None,
        "created_at": iso(ls.path[0].at),
        "valid_until": iso(at_ny(ls.day, WINDOW[1])),
        "horizon_until": iso(at_ny(ls.day, EXIT_MIN)),
        "evidence": ls.evidence,
        "features": {},
    }
    if ls.state == "CLOSED":
        out["exit_reason"] = ls.path[-1].reason
        out["realized_r"] = ls.path[-1].realized_r
    elif ls.state == "INVALIDATED":
        out["state_reason"] = ls.path[-1].reason
    return out
