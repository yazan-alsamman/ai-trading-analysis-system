"""Setup lifecycle and triple-barrier labels (P3 task 2).

    python -m app setups label --symbol XAUUSD --rules V5-S   # development period only

Writes ``docs/phase3/labels_<SYMBOL>_<rules>.md`` (counts) and
``data/processed/<SYMBOL>/p3_labels_<rules>.parquet`` (one row per setup, untracked).

For an ``ARMED`` setup (written for a buy; a sell runs on mirrored prices), bar by bar after the
decision bar ``d``:

**Waiting for the fill** (bars ``d + 1 ... d + entry_window_bars``), in this order on each bar:
1. it opens at or below the SL: ``INVALIDATED`` (``gap_through_sl``);
2. its low reaches the entry: filled at the entry price, ``ACTIVE`` from this bar. On the fill bar
   only the SL can be hit (its path inside the bar is unknown, so the TP is not counted there);
3. its high reaches the TP: ``INVALIDATED`` (``tp_before_fill``);
4. no fill by the last bar: ``EXPIRED``.

**Active** (bars after the fill, up to ``horizon_bars`` bars counting the fill bar), in order:
1. it opens at or below the SL: exit at the open minus the SL slippage;
2. its low reaches the SL: exit at the SL minus the slippage (also when the TP is reached in the
   same bar: an ambiguous bar counts as SL);
3. its high reaches the TP: exit at the TP;
4. the last bar of the horizon: exit at its close (``timeout``).

The label is ``y = 1`` for TP and ``0`` for SL or timeout (``CLOSED``); ``EXPIRED`` and
``INVALIDATED`` setups have no label and are kept for analysis. Realized R is kept: gross
``(exit - entry) / risk``, and net after the round-trip cost
``spread + max(cost_extra_frac * spread, cost_extra_min)`` (the decision bar's spread) divided by
the risk; the 2x stress run doubles the cost and the SL slippage. A setup whose bars are not all
there yet is ``PENDING``: nothing is decided early."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Instrument, Strategy, instruments, strategy
from app.data.importer import DEFAULT_OUT as STORE
from app.setups.builder import OUT_DIR, Plan, build
from app.setups.costs import round_trip
from app.smc.detector import detect, development_frames, suffix


@dataclass(frozen=True)
class Label:
    state: str  # CLOSED, EXPIRED, INVALIDATED, PENDING (or REJECTED, from the builder)
    reason: str  # gap_through_sl, tp_before_fill, or the outcome: tp, sl, timeout
    fill_idx: int | None = None
    exit_idx: int | None = None
    exit_price: float | None = None
    y: int | None = None
    gross_r: float | None = None
    net_r: float | None = None
    net_r_2x: float | None = None


@dataclass(frozen=True)
class Bars:
    """Entry-frame prices seen from one direction (negated for a sell)."""

    sign: float
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray

    @classmethod
    def of(cls, entry: pd.DataFrame, direction: str) -> Bars:
        o, h, lo, c = (entry[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        if direction == "buy":
            return cls(1.0, o, h, lo, c)
        return cls(-1.0, -o, -lo, -h, -c)


def resolve(bars: Bars, d: int, pl: Plan, spread: float, p: Strategy, inst: Instrument) -> Label:
    """The lifecycle and label of one armed setup decided at bar ``d``."""
    s = bars.sign
    entry, sl, tp = s * pl.entry, s * pl.sl, s * pl.tp
    n = len(bars.close)
    if p.entry_mode == "close":
        # Market entry at the decision bar's close: nothing of that bar is left to trade, so the
        # trade starts on the next bar and is held for horizon_bars bars after the decision bar.
        fill, fill_bar_counts, last = d, False, d + p.horizon_bars
    else:
        fill = None
        for j in range(d + 1, d + p.entry_window_bars + 1):
            if j >= n:
                return Label("PENDING", "waiting_for_fill")
            if bars.open[j] <= sl:
                return Label("INVALIDATED", "gap_through_sl")
            if bars.low[j] <= entry:
                fill = j
                break
            if bars.high[j] >= tp:
                return Label("INVALIDATED", "tp_before_fill")
        if fill is None:
            return Label("EXPIRED", "no_fill")
        fill_bar_counts, last = True, fill + p.horizon_bars - 1

    def close(j: int, raw_exit: float, outcome: str, slip: bool) -> Label:
        gross = (raw_exit - entry) / pl.risk
        if inst.cost_extra_frac is None:  # no cost model for this instrument yet: no net R
            return Label(
                "CLOSED", outcome, fill, j, s * raw_exit, int(outcome == "tp"), round(gross, 6)
            )
        cost = round_trip(spread, inst) / pl.risk
        slip_r = inst.sl_slippage / pl.risk if slip else 0.0
        return Label(
            "CLOSED",
            outcome,
            fill,
            j,
            s * (raw_exit - (inst.sl_slippage if slip else 0.0)),
            int(outcome == "tp"),
            round(gross, 6),
            round(gross - slip_r - cost, 6),
            round(gross - 2 * slip_r - 2 * cost, 6),
        )

    if fill_bar_counts and bars.low[fill] <= sl:
        return close(fill, sl, "sl", True)
    for j in range(fill + 1, last + 1):
        if j >= n:
            return Label("PENDING", "active", fill)
        if bars.open[j] <= sl:
            return close(j, bars.open[j], "sl", True)
        if bars.low[j] <= sl:
            return close(j, sl, "sl", True)
        if bars.high[j] >= tp:
            return close(j, tp, "tp", False)
        if j == last:
            return close(j, bars.close[j], "timeout", False)
    return Label("PENDING", "active", fill)  # horizon of one bar: decided on the fill bar above


def label_all(frames: dict[str, pd.DataFrame], symbol: str, p: Strategy) -> pd.DataFrame:
    inst = instruments()[symbol]
    entry = frames[p.entry_timeframe]
    setups = build(frames, detect(frames, p), p)
    sides = {d: Bars.of(entry, d) for d in ("buy", "sell")}
    rows = []
    for st in setups:
        pl = st.plan
        lab = (
            resolve(sides[st.pattern.direction], st.decision_idx, pl, st.spread, p, inst)
            if pl.state == "ARMED"
            else Label("REJECTED", pl.reason)
        )
        rows.append(
            {
                "setup_id": st.setup_id,
                "direction": st.pattern.direction,
                "year": entry["ts_utc"].iloc[st.decision_idx].year,
                "decision_idx": st.decision_idx,
                "decision_utc": entry["ts_utc"].iloc[st.decision_idx],
                "atr": st.pattern.sweep.atr,
                "risk": pl.risk,
                "bars_sweep_to_choch": st.decision_idx - st.pattern.sweep.settled_idx,
                "spread": st.spread,
                "level_source": st.pattern.primary.source,
                "levels_taken": len(st.pattern.levels),
                "depth_atr": st.pattern.sweep.depth_atr,
                "extreme": st.pattern.sweep.extreme,
                "choch_ref_price": st.pattern.choch.ref_price,
                "fvg_size_atr": st.pattern.fvg.size_atr if st.pattern.fvg else np.nan,
                "target_source": pl.target.source if pl.target else None,
                "entry": pl.entry,
                "sl": pl.sl,
                "tp": pl.tp,
                "r_multiple": pl.r_multiple,
                "state": lab.state,
                "reason": lab.reason,
                "exit_utc": entry["ts_utc"].iloc[lab.exit_idx]
                if lab.exit_idx is not None
                else None,
                "bars_held": lab.exit_idx - lab.fill_idx + 1 if lab.exit_idx is not None else None,
                "exit_price": lab.exit_price,
                "y": lab.y,
                "gross_r": lab.gross_r,
                "net_r": lab.net_r,
                "net_r_2x": lab.net_r_2x,
            }
        )
    return pd.DataFrame(rows)


def render(symbol: str, df: pd.DataFrame, p: Strategy) -> str:
    closed = df[df["state"] == "CLOSED"]
    states = df.pivot_table(index="year", columns="state", values="setup_id", aggfunc="count")
    states = states.fillna(0).astype(int)
    lines = [
        f"# P3: labels, {symbol} ({p.rule_set})",
        "",
        "_Generated by `python -m app setups label`; rules in `app/setups/labels.py`. Development"
        " period only. Counts and labels; the E0/E1 comparison is P3 task 4._",
        "",
        f"Setups: **{len(df)}**; labelled (CLOSED): **{len(closed)}**.",
        "",
        "| Year | " + " | ".join(states.columns) + " |",
        "|" + " --- |" * (len(states.columns) + 1),
        *[f"| {y} | " + " | ".join(str(v) for v in r) + " |" for y, r in states.iterrows()],
        "",
        "| State | Reason | Setups |",
        "| --- | --- | --- |",
        *[f"| {s} | {r} | {n} |" for (s, r), n in df.groupby(["state", "reason"]).size().items()],
        "",
    ]
    if len(closed):
        lines += [
            "| Labelled setups | Value |",
            "| --- | --- |",
            f"| TP before SL (y = 1) | {closed['y'].mean():.1%} |",
            f"| Mean R gross / net / net at 2x costs | {closed['gross_r'].mean():.3f} /"
            f" {closed['net_r'].mean():.3f} / {closed['net_r_2x'].mean():.3f} |",
            f"| Bars held (median) | {closed['bars_held'].median():.0f} |",
            "",
        ]
    lines += [
        f"Entry window {p.entry_window_bars} bars; horizon {p.horizon_bars} bars counting the fill"
        " bar; an ambiguous bar counts as SL; on the fill bar only the SL counts.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m app setups label")
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--rules", default="V5-S")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    p = strategy(args.rules)
    frames = development_frames(args.symbol, args.store, p)
    df = label_all(frames, args.symbol, p)
    if df.empty:
        print("no setups", file=sys.stderr)
        return 1
    tag = suffix(p) or "_v1"
    df.to_parquet(args.store / args.symbol / f"p3_labels{tag}.parquet", index=False)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"labels_{args.symbol}{tag}.md").write_text(
        render(args.symbol, df, p), encoding="utf-8", newline="\n"
    )
    closed = (df["state"] == "CLOSED").sum()
    print(f"{args.symbol} {p.rule_set}: {len(df)} setups, {closed} labelled")
    return 0
