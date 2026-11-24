"""Manual review of detected patterns (P2 gate: detection precision of 90% or more).

    python -m app smc review sample --symbol XAUUSD   # charts + docs/phase2/review/REVIEW.md
    python -m app smc review score  --symbol XAUUSD   # precision from the filled-in REVIEW.md

The sample is fixed before any chart is drawn: ``SAMPLE_SIZE`` patterns of the development period,
spread evenly over years and directions, drawn with ``SEED``. Each chart shows the bars up to two
bars after the CHoCH, never later, so the reviewer judges the pattern, not what price did next.

The reviewer writes ``yes`` or ``no`` in the Valid column of every row (and a note for a ``no``).
``score`` counts them: precision = yes / (yes + no), with a Wilson 95% interval; rows left blank
are reported, not counted."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import strategy
from app.data.importer import DEFAULT_OUT as STORE
from app.smc.detector import development_frames, suffix

SAMPLE_SIZE = 50
SEED = 20261022  # v1: fixed on 2026-10-22, before any chart was drawn
SEEDS = {"v1": SEED, "V5-S": 731205, "L1": 410733}  # each fixed before its sample (definitions §9)
BARS_BEFORE = 40
BARS_AFTER_CHOCH = 2
REVIEW_DIR = Path(__file__).resolve().parents[2] / "docs" / "phase2" / "review"
MARKET_TZ = "America/New_York"

CHECKLIST = """# P2 detector review: {symbol}

Sample: {n} of {total} patterns of the development period ({years}), spread evenly over {spread},
seed {seed} (fixed before the charts were drawn). Each chart ends two bars after the
CHoCH. Times are New York.

A pattern is **valid** (`yes`) when all of these hold on the chart:

1. **Liquidity.** The dashed line is a real resting level: a clear swing high/low on its timeframe
   or the previous trading day's high/low, still untaken when it was swept.
2. **Sweep.** Price trades through it and closes back on that bar or the next; the move looks like a
   grab of the liquidity, not a breakout that happens to close back.
3. **CHoCH.** The close (blue marker) breaks the swing (dotted line) that structurally matters for
   the move into the sweep.
4. **FVG.** The shaded gap is an imbalance left by the displacement away from the sweep.{fvg_note}

Write `yes` or `no` in **Valid**; for a `no`, say in **Notes** which point fails. The written
conditions themselves are already checked by the tests; this review asks whether the result is a
genuine trading pattern.

| # | Chart | Pattern | Sweep (NY) | Direction | Level | Valid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
"""


def sample(
    df: pd.DataFrame,
    n: int = SAMPLE_SIZE,
    seed: int = SEED,
    by: tuple[str, ...] = ("year", "direction"),
) -> pd.DataFrame:
    """``n`` rows spread evenly over the ``by`` cells, the rest by largest remainder."""
    rng = np.random.default_rng(seed)
    cells = df.groupby(list(by)).groups
    keys = sorted(cells)
    sizes = np.array([len(cells[k]) for k in keys])
    want = np.minimum(sizes, n // len(keys))
    while want.sum() < min(n, sizes.sum()):
        room = sizes - want
        order = sorted(range(len(keys)), key=lambda i: (-room[i], keys[i]))
        for i in order:
            if want.sum() >= n:
                break
            if room[i] > 0:
                want[i] += 1
    picked = []
    for k, w in zip(keys, want, strict=True):
        idx = np.sort(np.asarray(cells[k]))
        picked += sorted(rng.choice(idx, size=int(w), replace=False).tolist())
    return df.loc[sorted(picked, key=lambda i: df.loc[i, "sweep_utc"])].reset_index(drop=True)


def _ny(t: pd.Timestamp) -> str:
    return t.tz_convert(MARKET_TZ).strftime("%Y-%m-%d %H:%M")


def draw(row: pd.Series, entry: pd.DataFrame, path: Path, number: int, decimals: int = 2) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    lo = max(0, int(row["sweep_first_idx"]) - BARS_BEFORE)
    hi = min(len(entry) - 1, int(row["choch_idx"]) + BARS_AFTER_CHOCH)
    bars = entry.iloc[lo : hi + 1]
    x = np.arange(lo, hi + 1)
    fig, ax = plt.subplots(figsize=(12, 6), dpi=80)
    up = bars["close"].to_numpy() >= bars["open"].to_numpy()
    for xi, (o, h, low, c), u in zip(
        x, bars[["open", "high", "low", "close"]].to_numpy(), up, strict=True
    ):
        color = "#26a69a" if u else "#ef5350"
        ax.vlines(xi, low, h, color=color, lw=1)
        ax.add_patch(Rectangle((xi - 0.3, min(o, c)), 0.6, max(abs(c - o), 1e-9), color=color))
    buy = row["direction"] == "buy"
    s, ch, f = int(row["sweep_first_idx"]), int(row["choch_idx"]), int(row["fvg_idx"])
    has_fvg = f >= 0
    ax.hlines(row["level_price"], lo, s, colors="#555555", linestyles="--", lw=1.2)
    ax.text(
        lo,
        row["level_price"],
        f" {row['level_source']} {row['level_price']:.{decimals}f}",
        va="bottom",
        fontsize=8,
    )
    ext = int(row["extreme_idx"])
    ax.plot(ext, row["extreme"], marker="^" if buy else "v", color="#8e24aa", ms=9)
    ref = int(row["choch_ref_idx"])
    if ref >= lo:
        ax.hlines(row["choch_ref_price"], ref, ch, colors="#1e88e5", linestyles=":", lw=1.4)
    ax.plot(ch, entry["close"].iloc[ch], marker="o", color="#1e88e5", ms=7)
    if has_fvg:
        ax.add_patch(
            Rectangle(
                (f - 2 - 0.4, row["fvg_low"]),
                hi - (f - 2) + 0.8,
                row["fvg_high"] - row["fvg_low"],
                color="#ffb300",
                alpha=0.3,
            )
        )
    ticks = list(range(lo, hi + 1, max(1, (hi - lo) // 8)))
    ax.set_xticks(
        ticks,
        [entry["ts_utc"].iloc[t].tz_convert(MARKET_TZ).strftime("%m-%d %H:%M") for t in ticks],
        fontsize=8,
    )
    fvg = f"FVG {row['fvg_size_atr']:.2f} ATR" if has_fvg else "no FVG"
    symbol = f"{row['symbol']}  " if "symbol" in row else ""
    ax.set_title(
        f"#{number}  {symbol}{row['direction']}  {row['level_source']} level"
        f"  sweep {_ny(row['sweep_utc'])} NY  depth {row['depth_atr']:.2f} ATR  {fvg}",
        fontsize=10,
    )
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def review_dir(rules: str) -> Path:
    return REVIEW_DIR if rules == "v1" else REVIEW_DIR.parent / f"review_{rules}"


def write_sample(
    symbol: str, store: Path = STORE, out: Path = REVIEW_DIR, rules: str = "v1"
) -> Path:
    p = strategy(rules)
    df = pd.read_parquet(store / symbol / f"p2_patterns{suffix(p)}.parquet")
    seed = SEEDS[rules]
    picked = sample(df, seed=seed)
    entry = development_frames(symbol, store, p)[p.entry_timeframe]
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, row in picked.iterrows():
        assert entry["ts_utc"].iloc[int(row["sweep_first_idx"])] == row["sweep_utc"]
        name = f"{i + 1:02d}_{row['direction']}_{row['sweep_utc']:%Y%m%d_%H%M}.png"
        draw(row, entry, out / name, i + 1)
        rows.append(
            f"| {i + 1} | [{name}]({name}) | `{row['pattern_id']}` | {_ny(row['sweep_utc'])} |"
            f" {row['direction']} | {row['level_source']} {row['level_price']:.2f} |  |  |"
        )
    years = f"{df['year'].min()}-{df['year'].max()}"
    text = CHECKLIST.format(
        symbol=f"{symbol} ({rules})",
        n=len(picked),
        total=len(df),
        years=years,
        spread="years and directions",
        seed=seed,
        fvg_note="",
    )
    path = out / "REVIEW.md"
    if path.exists():
        raise FileExistsError(f"{path} exists; a filled-in review is never overwritten")
    path.write_text(text + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    picked.to_csv(out / "sample.csv", index=False)
    return path


def write_pooled_sample(symbols: list[str], store: Path, out: Path, rules: str) -> Path:
    """One sample over several instruments, spread over (instrument, with / without FVG) cells."""
    from app.config import instruments
    from app.smc.detector import detect, table

    p = strategy(rules)
    seed = SEEDS[rules]
    tables, entries = [], {}
    for sym in symbols:
        frames = development_frames(sym, store, p)
        entries[sym] = frames[p.entry_timeframe]
        t = table(detect(frames, p), entries[sym])
        if t.empty:
            continue
        t.insert(0, "symbol", sym)
        t["has_fvg"] = t["fvg_idx"] >= 0
        tables.append(t)
    df = pd.concat(tables, ignore_index=True)
    picked = sample(df, seed=seed, by=("symbol", "has_fvg"))
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, row in picked.iterrows():
        entry = entries[row["symbol"]]
        assert entry["ts_utc"].iloc[int(row["sweep_first_idx"])] == row["sweep_utc"]
        dec = instruments()[row["symbol"]].price_decimals
        name = f"{i + 1:02d}_{row['symbol']}_{row['direction']}_{row['sweep_utc']:%Y%m%d_%H%M}.png"
        draw(row, entry, out / name, i + 1, dec)
        fvg = "FVG" if row["has_fvg"] else "no FVG"
        rows.append(
            f"| {i + 1} | [{name}]({name}) | {row['symbol']} `{row['pattern_id']}` ({fvg}) |"
            f" {_ny(row['sweep_utc'])} | {row['direction']} |"
            f" {row['level_source']} {row['level_price']:.{dec}f} |  |  |"
        )
    cells = df.groupby(["symbol", "has_fvg"]).size().to_dict()
    per_cell = ", ".join(
        f"{k[0]} {'with' if k[1] else 'without'} FVG {v}" for k, v in sorted(cells.items())
    )
    text = CHECKLIST.format(
        symbol=f"{', '.join(symbols)} ({rules})",
        n=len(picked),
        total=len(df),
        years=f"{df['year'].min()}-{df['year'].max()}",
        spread=f"instrument x with / without FVG (patterns per cell: {per_cell})",
        seed=seed,
        fvg_note=" **Only when a gap is shaded**: a pattern without an FVG (title"
        ' "no FVG") is judged on points 1-3.',
    )
    path = out / "REVIEW.md"
    if path.exists():
        raise FileExistsError(f"{path} exists; a filled-in review is never overwritten")
    path.write_text(text + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    picked.to_csv(out / "sample.csv", index=False)
    return path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 4), round(c + h, 4))


def score(path: Path) -> dict:
    verdicts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and re.fullmatch(r"\d+", cells[0]):
            verdicts.append(cells[6].lower())
    yes = sum(v in ("yes", "y", "✓") for v in verdicts)
    no = sum(v in ("no", "n", "✗") for v in verdicts)
    blank = len(verdicts) - yes - no
    n = yes + no
    return {
        "rows": len(verdicts),
        "yes": yes,
        "no": no,
        "not_reviewed": blank,
        "precision": round(yes / n, 4) if n else None,
        "wilson_95": wilson(yes, n),
        "gate": 0.9,
        "passed": bool(n and blank == 0 and yes / n >= 0.9),
    }


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m app smc review")
    ap.add_argument("action", choices=["sample", "score"])
    ap.add_argument("--symbol", action="append", help="repeat for a pooled sample")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--rules", default="v1", help="v1 or a variant of strategy.toml")
    ap.add_argument("--out", type=Path, help="default: docs/phase2/review[_<rules>]")
    args = ap.parse_args(argv)
    out = args.out or review_dir(args.rules)
    symbols = args.symbol or ["XAUUSD"]
    if args.action == "sample":
        if len(symbols) > 1:
            print(f"wrote {write_pooled_sample(symbols, args.store, out, args.rules)}")
        else:
            print(f"wrote {write_sample(symbols[0], args.store, out, args.rules)}")
        return 0
    result = score(out / "REVIEW.md")
    (out / "score.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0
