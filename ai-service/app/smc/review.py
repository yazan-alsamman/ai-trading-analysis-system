"""Charts for the manual detector review (Phase 2 gate: detection precision of 90% or more).

    python -m app.smc.review            # docs/phase2/review/*.png and docs/phase2/review/REVIEW.md

Samples setups of the frozen v2 rules (``FROZEN_V2``) that reached a full trade plan on the
development period (2012-2017), stratified by year, and draws each one on 5m candles with every
element the rules used: the swept level, the sweep extreme, the CHoCH reference and bar, the FVG,
and entry, SL and TP. A reviewer marks each chart correct or not against the written definitions."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from app.data.sessions import MARKET_TZ  # noqa: E402
from app.smc.engine import Setup, run  # noqa: E402
from app.smc.params import FROZEN_V2, CostParams  # noqa: E402
from app.smc.report import DATA_DIR, DEV_END, OUT_DIR  # noqa: E402

PLANNED = {"CLOSED", "EXPIRED", "INVALIDATED"}
BEFORE, AFTER, MAX_BARS = 36, 18, 240


def sample(setups: list[Setup], ts: pd.Series, n: int, seed: int) -> list[Setup]:
    """``n`` setups with a full plan, spread evenly over the years, in time order."""
    planned = [s for s in setups if s.state in PLANNED and s.tp is not None]
    by_year: dict[int, list[Setup]] = {}
    for s in planned:
        by_year.setdefault(ts.iloc[s.sweep_idx].year, []).append(s)
    rng = np.random.default_rng(seed)
    years = sorted(by_year)
    per_year = [n // len(years) + (1 if i < n % len(years) else 0) for i in range(len(years))]
    chosen: list[Setup] = []
    for y, k in zip(years, per_year, strict=True):
        pool = by_year[y]
        idx = rng.choice(len(pool), size=min(k, len(pool)), replace=False)
        chosen.extend(pool[i] for i in sorted(idx))
    return sorted(chosen, key=lambda s: s.sweep_idx)


def _ny(t: pd.Timestamp) -> str:
    return t.tz_convert(MARKET_TZ).strftime("%Y-%m-%d %H:%M")


def _level_label(lv) -> str:
    if lv.source == "pd":
        return f"previous-day {lv.kind} (trading day {lv.origin_day})"
    if lv.source in ("asia", "london"):
        return f"{lv.source} session {lv.kind} ({lv.origin_day})"
    return f"{lv.source} swing {lv.kind} (bar of {_ny(lv.origin_ts)} NY)"


def draw(s: Setup, bars: pd.DataFrame, path: Path, number: int) -> None:
    last = s.exit_idx if s.exit_idx is not None else s.events[-1][0]
    start = max(0, min(s.ref_idx, s.extreme_idx) - BEFORE)
    end = min(len(bars) - 1, last + AFTER, start + MAX_BARS)
    w = bars.iloc[start : end + 1]
    x = np.arange(start, end + 1)
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=80)

    for xi, (o, h, lo, c) in zip(x, w[["open", "high", "low", "close"]].to_numpy(), strict=True):
        up = c >= o
        color = "#4c9a6a" if up else "#c0504d"
        ax.vlines(xi, lo, h, color=color, linewidth=0.8)
        ax.add_patch(
            Rectangle((xi - 0.35, min(o, c)), 0.7, max(abs(c - o), 1e-6), color=color, lw=0)
        )

    lv = s.level
    ax.axhline(lv.price, color="#7f7f7f", ls="--", lw=1)
    ax.text(
        start + 1,
        lv.price,
        f" swept {_level_label(lv)}",
        va="bottom",
        fontsize=8,
        color="#555555",
    )
    ax.plot(
        s.extreme_idx,
        s.extreme,
        marker="v" if s.direction == "sell" else "^",
        ms=9,
        color="#000000",
        zorder=5,
    )
    ax.annotate(
        "sweep extreme",
        (s.extreme_idx, s.extreme),
        textcoords="offset points",
        xytext=(6, -12 if s.direction == "buy" else 8),
        fontsize=8,
    )
    ax.hlines(s.ref_price, s.ref_idx, s.choch_idx, colors="#1f77b4", linestyles=":", lw=1.4)
    ax.annotate(
        "CHoCH ref",
        (s.ref_idx, s.ref_price),
        textcoords="offset points",
        xytext=(0, 4),
        fontsize=8,
        color="#1f77b4",
    )
    ax.axvline(s.choch_idx, color="#1f77b4", lw=0.8, alpha=0.6)
    ax.text(s.choch_idx, ax.get_ylim()[1], " CHoCH", va="top", fontsize=8, color="#1f77b4")

    fvg_end = s.fill_idx if s.fill_idx is not None else end
    gap = s.fvg_high - s.fvg_low
    ax.add_patch(
        Rectangle(
            (s.fvg_idx - 2 - 0.4, s.fvg_low),
            fvg_end - (s.fvg_idx - 2) + 0.8,
            gap,
            facecolor="#9467bd",
            alpha=0.25,
            edgecolor="#6a3d9a",
            lw=1.0,
        )
    )
    # Bracket the three bars that make the gap, so a thin gap is still easy to find.
    ax.axvspan(s.fvg_idx - 2 - 0.45, s.fvg_idx + 0.45, color="#9467bd", alpha=0.08, lw=0)
    ax.text(
        s.fvg_idx - 2,
        s.fvg_high,
        f" FVG {gap:.2f} ({s.choch_idx - s.fvg_idx} bars before CHoCH)",
        va="bottom",
        fontsize=8,
        color="#6a3d9a",
    )

    for name, price, color in (
        ("entry", s.entry, "#333333"),
        ("SL", s.sl, "#c0504d"),
        ("TP", s.tp, "#4c9a6a"),
    ):
        ax.hlines(price, s.choch_idx, end, colors=color, lw=1.2)
        ax.text(end, price, f" {name} {price:.2f}", va="center", fontsize=8, color=color)
    if s.fill_idx is not None:
        ax.plot(s.fill_idx, s.entry, marker="o", color="#333333", ms=6)
    if s.exit_idx is not None:
        ax.plot(s.exit_idx, s.exit_price, marker="X", color="#333333", ms=8)

    ticks = x[:: max(1, len(x) // 8)]
    ax.set_xticks(
        ticks,
        [bars["ts_utc"].iloc[t].tz_convert(MARKET_TZ).strftime("%m-%d %H:%M") for t in ticks],
        fontsize=8,
    )
    ax.set_xlim(start - 1, end + 12)
    ax.set_xlabel("New York time, 5m bars")
    outcome = s.outcome or s.state.lower()
    ax.set_title(f"#{number:02d}  {s.setup_id}  ·  {s.direction}  ·  {outcome}", fontsize=10)
    ax.grid(alpha=0.15)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


CHECKLIST = """# Phase 2 detector review (frozen v2 rules, 2012–2017)

Generated by `python -m app.smc.review` (seed {seed}). Mark a chart **✅ correct** only if every
item below holds when you look at the candles. Otherwise mark it **❌** with a short note. The gate
is a precision of **90% or more** ({need} of {n} correct).

**What to check on each chart:**

1. **Swept level:** the dashed line is a real earlier high (sell) or low (buy) of the named kind,
   and price had not traded through it before the sweep.
2. **Sweep:** price trades beyond the level by a small amount and closes back on the original side.
   In v1 a short continuation is allowed while the depth stays within 1.5 ATR.
3. **CHoCH:** the blue dotted line is the last confirmed swing on the 5m bars before the extreme,
   and the CHoCH bar closes beyond it.
4. **FVG:** the purple box is a real three-bar gap in the move away from the extreme, created by
   the CHoCH bar or one of the 6 bars before it (v2 rule). Its size is printed on the chart.
5. **Plan:** entry sits at the FVG's near edge, SL is beyond the sweep extreme, and TP is at a
   visible opposite level (or at 4R).

Markers: ▲/▼ sweep extreme · ● fill · ✕ exit. Times are New York time.

| # | Chart | Direction | Sweep (NY) | Outcome | Correct? | Note |
| --- | --- | --- | --- | --- | --- | --- |
"""


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=OUT_DIR / "review")
    args = ap.parse_args(argv)

    params = FROZEN_V2
    tf = f"{params.entry_tf_minutes}m"
    bars, h1, h4 = (pd.read_parquet(DATA_DIR / f"{t}.parquet") for t in (tf, "1h", "4h"))
    bars = bars[bars["ts_utc"] < DEV_END].reset_index(drop=True)
    setups = run(bars, h1, h4, params, CostParams())
    chosen = sample(setups, bars["ts_utc"], args.n, args.seed)

    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("*.png"):
        old.unlink()
    rows = []
    for i, s in enumerate(chosen, 1):
        name = f"{i:02d}_{s.direction}_{bars['ts_utc'].iloc[s.sweep_idx]:%Y%m%d_%H%M}.png"
        draw(s, bars, args.out / name, i)
        outcome = s.outcome or s.state.lower()
        when = _ny(bars["ts_utc"].iloc[s.sweep_idx])
        rows.append(f"| {i} | [{name}]({name}) | {s.direction} | {when} | {outcome} | | |")
    need = int(np.ceil(0.9 * len(chosen)))
    text = CHECKLIST.format(seed=args.seed, need=need, n=len(chosen)) + "\n".join(rows) + "\n"
    text += f"\n**Result:** __ of {len(chosen)} correct (precision __%).\n"
    (args.out / "REVIEW.md").write_text(text, encoding="utf-8")
    print(f"wrote {len(chosen)} charts to {args.out}")


if __name__ == "__main__":
    main()
