"""Setup builder (L3, P3 task 1): a pattern becomes a trade plan, or a recorded rejection.

    python -m app setups build --symbol XAUUSD --rules V5-S   # development period only

Writes ``docs/phase3/setups_<SYMBOL>_<rules>.md`` (counts, committed) and
``data/processed/<SYMBOL>/p3_setups_<rules>.parquet`` (one row per pattern, untracked).

Rules (Strategy v1, CLAUDE.md; choices of 2026-10-22 in ``strategy.toml``), for a buy (a sell is
the mirror), all fixed at the close of the CHoCH bar, the decision bar:

* **entry**: a limit order at the FVG's near edge (its top for a buy);
* **SL**: the sweep extreme minus ``sl_buffer_atr`` x the sweep's ATR minus the spread of the
  decision bar (``spread_stat``: the mean of its M1 recorded spreads; missing spread counts as 0);
* **TP**: the nearest opposite liquidity level still active at the decision bar (the level book
  after that bar: unspent, usable, not older than its age limit) above the entry with
  R >= ``min_r``; if that nearest level is beyond ``max_r`` the pattern is rejected
  (``beyond_max_r = "reject"``), never capped;
* the decision bar must close beyond the entry (above it for a buy): a limit order cannot be
  placed on the wrong side of price.

States: ``ARMED`` (a plan, waiting for its fill: task 2) or ``REJECTED`` with one reason:
``REJECT_NON_POSITIVE_RISK``, ``REJECT_PRICE_AT_ENTRY``, ``REJECT_NO_TARGET``,
``REJECT_TARGET_BEYOND_MAX_R``. The setup id is the pattern id (direction and swept level)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Strategy, splits, strategy
from app.data.importer import DEFAULT_OUT as STORE
from app.smc.detector import Pattern, detect, development_frames, levels_for, suffix
from app.smc.primitives import Level, LevelBook

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "phase3"


@dataclass(frozen=True)
class Plan:
    state: str  # "ARMED" or "REJECTED"
    reason: str  # "" when armed
    entry: float
    sl: float
    tp: float | None
    risk: float
    r_multiple: float | None
    target: Level | None


def plan(
    direction: str,
    extreme: float,
    atr: float,
    spread: float,
    fvg_low: float | None,
    fvg_high: float | None,
    close: float,
    targets: list[Level],
    p: Strategy,
) -> Plan:
    """The trade plan of one pattern at its decision bar. ``targets`` are the active levels on the
    opposite side (``high`` levels for a buy, ``low`` for a sell)."""
    sign = 1.0 if direction == "buy" else -1.0
    at_close = p.entry_mode == "close"
    entry = close if at_close else (fvg_high if sign > 0 else fvg_low)
    sl = extreme - sign * (p.sl_buffer_atr * atr + spread)
    risk = sign * (entry - sl)
    if not risk > 0:
        return Plan("REJECTED", "REJECT_NON_POSITIVE_RISK", entry, sl, None, risk, None, None)
    if not at_close and not sign * (close - entry) > 0:
        return Plan("REJECTED", "REJECT_PRICE_AT_ENTRY", entry, sl, None, risk, None, None)
    side = "high" if sign > 0 else "low"
    beyond = sorted(
        (lv for lv in targets if lv.side == side and sign * (lv.price - entry) > 0),
        key=lambda lv: (sign * (lv.price - entry), lv.key),
    )
    for lv in beyond:
        r = sign * (lv.price - entry) / risk
        if r < p.min_r:
            continue
        if r > p.max_r:
            if p.beyond_max_r != "reject":
                raise ValueError(f"unsupported beyond_max_r {p.beyond_max_r!r}")
            return Plan("REJECTED", "REJECT_TARGET_BEYOND_MAX_R", entry, sl, lv.price, risk, r, lv)
        return Plan("ARMED", "", entry, sl, lv.price, risk, r, lv)
    return Plan("REJECTED", "REJECT_NO_TARGET", entry, sl, None, risk, None, None)


@dataclass(frozen=True)
class Setup:
    setup_id: str
    pattern: Pattern
    decision_idx: int
    spread: float
    plan: Plan


def build(frames: dict[str, pd.DataFrame], patterns: list[Pattern], p: Strategy) -> list[Setup]:
    """One setup per pattern, each planned with the level book as it stood after its decision
    bar (nothing later is used)."""
    entry = frames[p.entry_timeframe]
    col = f"spread_{p.spread_stat}"
    spread = entry[col].fillna(0.0).to_numpy(float) if col in entry else np.zeros(len(entry))
    close = entry["close"].to_numpy(float)
    by_bar: dict[int, list[Pattern]] = {}
    for pt in patterns:
        by_bar.setdefault(pt.choch.idx, []).append(pt)
    book = LevelBook(entry, levels_for(frames, p), p.max_age_days)
    out = []
    for j in range(max(by_bar, default=-1) + 1):
        book.step(j)
        for pt in by_bar.get(j, []):
            opposite = book.active["high" if pt.direction == "buy" else "low"]
            pl = plan(
                pt.direction,
                pt.sweep.extreme,
                pt.sweep.atr,
                float(spread[j]),
                pt.fvg.low if pt.fvg else None,
                pt.fvg.high if pt.fvg else None,
                float(close[j]),
                list(opposite),
                p,
            )
            out.append(Setup(pt.pattern_id, pt, j, float(spread[j]), pl))
    return out


def table(setups: list[Setup], entry: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for s in setups:
        pl, pt = s.plan, s.pattern
        rows.append(
            {
                "setup_id": s.setup_id,
                "direction": pt.direction,
                "decision_idx": s.decision_idx,
                "decision_utc": entry["ts_utc"].iloc[s.decision_idx],
                "year": entry["ts_utc"].iloc[s.decision_idx].year,
                "state": pl.state,
                "reason": pl.reason,
                "entry": pl.entry,
                "sl": pl.sl,
                "tp": pl.tp,
                "risk": pl.risk,
                "r_multiple": pl.r_multiple,
                "target_source": pl.target.source if pl.target else None,
                "spread": s.spread,
                "atr": pt.sweep.atr,
                "risk_atr": pl.risk / pt.sweep.atr,
            }
        )
    return pd.DataFrame(rows)


def render(symbol: str, df: pd.DataFrame, p: Strategy) -> str:
    armed = df[df["state"] == "ARMED"]
    by_year = df.pivot_table(index="year", columns="state", values="setup_id", aggfunc="count")
    by_year = by_year.fillna(0).astype(int)
    lines = [
        f"# P3: setups, {symbol} ({p.rule_set})",
        "",
        "_Generated by `python -m app setups build`; rules in `app/setups/builder.py`. Development"
        " period only._",
        "",
        f"Patterns: **{len(df)}**; armed setups: **{len(armed)}**.",
        "",
        "| Year | " + " | ".join(by_year.columns) + " |",
        "|" + " --- |" * (len(by_year.columns) + 1),
        *[f"| {y} | " + " | ".join(str(v) for v in r) + " |" for y, r in by_year.iterrows()],
        "",
        "| Reason | Patterns |",
        "| --- | --- |",
        *[f"| {k or 'ARMED'} | {v} |" for k, v in df["reason"].value_counts().items()],
        "",
    ]
    if len(armed):
        q = armed[["r_multiple", "risk_atr"]].quantile([0.1, 0.5, 0.9])
        lines += [
            "| Armed setups | 10% | median | 90% |",
            "| --- | --- | --- | --- |",
            *[
                f"| {name} | {q.loc[0.1, c]:.2f} | {q.loc[0.5, c]:.2f} | {q.loc[0.9, c]:.2f} |"
                for c, name in (("r_multiple", "R"), ("risk_atr", "Risk (ATR)"))
            ],
            "",
            "| Target level | Setups |",
            "| --- | --- |",
            *[f"| {k} | {v} |" for k, v in armed["target_source"].value_counts().items()],
            "",
        ]
    lines += [
        f"Entry at the FVG's near edge; SL beyond the sweep extreme by {p.sl_buffer_atr} ATR plus"
        f" the decision bar's {p.spread_stat} spread; TP the nearest opposite liquidity with R"
        f" {p.min_r}-{p.max_r} (beyond {p.max_r}: {p.beyond_max_r}).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="setups of the development period")
    b.add_argument("--symbol", default="XAUUSD")
    b.add_argument("--rules", default="V5-S")
    b.add_argument("--store", type=Path, default=STORE)
    b.add_argument("--out", type=Path, default=OUT_DIR)
    if argv and argv[0] == "label":
        from app.setups.labels import main as label

        return label(argv[1:])
    if argv and argv[0] == "count":
        from app.setups.counts import main as count

        return count(argv[1:])
    args = ap.parse_args(argv)

    p = strategy(args.rules)
    splits()  # the development period is the only one loaded (development_frames)
    frames = development_frames(args.symbol, args.store, p)
    setups = build(frames, detect(frames, p), p)
    df = table(setups, frames[p.entry_timeframe])
    if df.empty:
        print("no setups", file=sys.stderr)
        return 1
    df.to_parquet(args.store / args.symbol / f"p3_setups{suffix(p) or '_v1'}.parquet", index=False)
    args.out.mkdir(parents=True, exist_ok=True)
    name = f"setups_{args.symbol}{suffix(p) or '_v1'}.md"
    (args.out / name).write_text(render(args.symbol, df, p), encoding="utf-8", newline="\n")
    print(f"{args.symbol} {p.rule_set}: {len(df)} patterns, {(df['state'] == 'ARMED').sum()} armed")
    return 0
