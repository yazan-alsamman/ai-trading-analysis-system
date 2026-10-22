"""Sweep -> CHoCH -> FVG patterns (P2): the events of ``app.smc.events`` put together.

    python -m app smc detect --symbol XAUUSD     # development period only (D23)

Writes ``docs/phase2/patterns_<SYMBOL>.md`` (counts and distributions, committed) and
``data/processed/<SYMBOL>/p2_patterns.parquet`` (one row per pattern, untracked) for the review.

A pattern is a sweep, the CHoCH after it and the first FVG of the displacement. When one sweep
bar takes several levels (a 1h low and the previous day's low just below it, say), each is a sweep
of its own, but they lead to the same CHoCH and FVG: that is one pattern. It is kept once, with
every level it took; its ``primary`` level, which names it, is the one from the highest context
(4h, then previous day, then 1h), then the furthest from price. This module only detects; entry,
stop, target and lifecycle are the setup builder's (P3)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Strategy, splits, strategy
from app.data.importer import DEFAULT_OUT as STORE
from app.smc.events import Choch, Fvg, Side, Sweep, detect_sweeps, find_choch, find_fvg
from app.smc.primitives import Level, previous_day_levels, swing_levels

SOURCE_RANK = {"4h": 0, "pd": 1, "1h": 2}
OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "phase2"


@dataclass(frozen=True)
class Pattern:
    direction: str
    sweep: Sweep  # of the primary level
    levels: tuple[Level, ...]  # every level the sweep bar(s) took, primary first
    choch: Choch
    fvg: Fvg

    @property
    def primary(self) -> Level:
        return self.levels[0]

    @property
    def pattern_id(self) -> str:
        lv = self.primary
        return f"{self.direction}:{lv.source}:{lv.side}:{lv.origin_utc:%Y%m%d%H%M}:{lv.price!r}"


def levels_for(frames: dict[str, pd.DataFrame], p: Strategy) -> list[Level]:
    out = []
    for tf in p.context_timeframes:
        out += swing_levels(frames[tf], p.k_context, tf)
    if p.previous_day:
        out += previous_day_levels(frames["D1"])
    return out


def _primary_order(s: Sweep) -> tuple:
    # Highest context first, then the level furthest from price (lowest for a buy).
    sign = 1.0 if s.direction == "buy" else -1.0
    return (SOURCE_RANK.get(s.level.source, 9), sign * s.level.price, s.level.key)


def detect(frames: dict[str, pd.DataFrame], p: Strategy) -> list[Pattern]:
    """Every Sweep -> CHoCH -> FVG pattern in the frames, in the order the FVG is known."""
    entry = frames[p.entry_timeframe].reset_index(drop=True)
    sides = {d: Side.of(entry, d) for d in ("buy", "sell")}
    groups: dict[tuple, list[tuple[Sweep, Choch, Fvg]]] = {}
    for s in detect_sweeps(entry, levels_for(frames, p), p):
        if s.kind != "sweep":
            continue
        side = sides[s.direction]
        choch, _ = find_choch(side, s, p.k_entry, p.choch_window_bars)
        if choch is None:
            continue
        fvg = find_fvg(side, s, choch, p.fvg_min_size_atr)
        if fvg is None:
            continue
        key = (s.direction, s.extreme_idx, choch.idx, fvg.idx)
        groups.setdefault(key, []).append((s, choch, fvg))
    out = []
    for found in groups.values():
        found.sort(key=lambda x: _primary_order(x[0]))
        s, choch, fvg = found[0]
        out.append(Pattern(s.direction, s, tuple(x[0].level for x in found), choch, fvg))
    return sorted(out, key=lambda pt: (pt.choch.idx, pt.direction, pt.pattern_id))


def load_frames(symbol: str, end: pd.Timestamp, store: Path = STORE) -> dict[str, pd.DataFrame]:
    """The store frames of every bar that closed by ``end``; later rows are filtered out while
    the file is read, so they are never loaded."""
    frames = {}
    for tf in ("15m", "1h", "4h", "D1"):
        path = store / symbol / f"{tf}.parquet"
        frames[tf] = pd.read_parquet(path, filters=[("close_utc", "<=", end)]).reset_index(
            drop=True
        )
    return frames


def development_frames(symbol: str, store: Path = STORE) -> dict[str, pd.DataFrame]:
    """The frames of the development period (D23): bars that opened on or after its start and
    closed by its end. Bar indices in the pattern table refer to the entry frame built here."""
    start, end = splits().development
    lo, hi = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    return {
        k: v[v["ts_utc"] >= lo].reset_index(drop=True)
        for k, v in load_frames(symbol, hi, store).items()
    }


def table(patterns: list[Pattern], entry: pd.DataFrame) -> pd.DataFrame:
    ts = entry["ts_utc"]
    rows = []
    for pt in patterns:
        s, c, f = pt.sweep, pt.choch, pt.fvg
        rows.append(
            {
                "pattern_id": pt.pattern_id,
                "direction": pt.direction,
                "level_source": pt.primary.source,
                "level_price": pt.primary.price,
                "levels_taken": len(pt.levels),
                "sweep_first_idx": s.first_idx,
                "sweep_settled_idx": s.settled_idx,
                "extreme_idx": s.extreme_idx,
                "choch_idx": c.idx,
                "choch_ref_idx": c.ref_idx,
                "fvg_idx": f.idx,
                "sweep_utc": ts.iloc[s.first_idx],
                "choch_utc": ts.iloc[c.idx],
                "extreme": s.extreme,
                "choch_ref_price": c.ref_price,
                "fvg_low": f.low,
                "fvg_high": f.high,
                "atr": s.atr,
                "depth_atr": s.depth_atr,
                "fvg_size_atr": f.size_atr,
                "bars_sweep_to_choch": c.idx - s.settled_idx,
                "year": ts.iloc[c.idx].year,
            }
        )
    return pd.DataFrame(rows)


def render(symbol: str, df: pd.DataFrame, period: tuple, p: Strategy) -> str:
    def q(col: str) -> str:
        x = df[col]
        return f"{x.quantile(0.1):.2f} / {x.median():.2f} / {x.quantile(0.9):.2f}"

    by_year = df.groupby(["year", "direction"]).size().unstack(fill_value=0)
    lines = [
        f"# P2: Sweep → CHoCH → FVG patterns, {symbol}",
        "",
        "_Generated by `python -m app smc detect`; rules in `app/smc/events.py`, parameters in"
        " `app/config/strategy.toml`. Development period only._",
        "",
        f"Period: {period[0]} → {period[1]} (UTC, bars closed before the end).",
        f"Patterns: **{len(df)}** ({(df['direction'] == 'buy').sum()} buy,"
        f" {(df['direction'] == 'sell').sum()} sell).",
        "",
        "| Year | Buy | Sell | Total |",
        "| --- | --- | --- | --- |",
        *[
            f"| {y} | {r.get('buy', 0)} | {r.get('sell', 0)} | {r.sum()} |"
            for y, r in by_year.iterrows()
        ],
        "",
        "| Primary level | Patterns |",
        "| --- | --- |",
        *[f"| {k} | {v} |" for k, v in df["level_source"].value_counts().items()],
        "",
        "| Measure | 10% / median / 90% |",
        "| --- | --- |",
        f"| Sweep depth (ATR) | {q('depth_atr')} |",
        f"| FVG size (ATR) | {q('fvg_size_atr')} |",
        f"| Bars from the sweep to the CHoCH | {q('bars_sweep_to_choch')} |",
        f"| Levels taken by the sweep | {q('levels_taken')} |",
        "",
        f"Parameters: k = {p.k_context} (context) / {p.k_entry} (entry), ATR {p.atr_period},"
        f" sweep {p.min_depth_atr}-{p.breakout_depth_atr} ATR with a close back within"
        f" {p.close_back_bars} bar, CHoCH within {p.choch_window_bars} bars, FVG ≥"
        f" {p.fvg_min_size_atr} ATR, levels for {p.max_age_days} trading days.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)
    d = sub.add_parser("detect", help="patterns of the development period")
    d.add_argument("--symbol", default="XAUUSD")
    d.add_argument("--store", type=Path, default=STORE)
    d.add_argument("--out", type=Path, default=OUT_DIR)
    if argv and argv[0] == "review":
        from app.smc.review import main as review

        return review(argv[1:])
    args = ap.parse_args(argv)

    p = strategy()
    start, end = splits().development
    frames = development_frames(args.symbol, args.store)
    patterns = detect(frames, p)
    df = table(patterns, frames[p.entry_timeframe])
    if df.empty:
        print("no patterns", file=sys.stderr)
        return 1
    df.to_parquet(args.store / args.symbol / "p2_patterns.parquet", index=False)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"patterns_{args.symbol}.md").write_text(
        render(args.symbol, df, (start, end), p), encoding="utf-8", newline="\n"
    )
    print(f"{args.symbol}: {len(df)} patterns, {np.unique(df['year']).tolist()}")
    return 0
