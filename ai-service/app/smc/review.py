"""Charts for the manual detector review (Phase 2 gate: detection precision of 90% or more).

    python -m app.smc.review            # docs/phase2/review/*.png and docs/phase2/review/REVIEW.md

Samples setups of the current frozen rules (``CURRENT``) that reached a full trade plan on the
development period (2012-2017), stratified by year, and draws each one on 5m candles with every
element the rules used: the swept level, the sweep extreme, the CHoCH reference and bar, the FVG,
and entry, SL and TP. A reviewer judges whether each is a genuine trading pattern; the written
conditions themselves are checked automatically by ``app.smc.conditions``."""

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
from app.smc.params import CURRENT, CURRENT_NAME, CostParams  # noqa: E402
from app.smc.report import DATA_DIR, DEV_END, OUT_DIR  # noqa: E402

PLANNED = {"CLOSED", "EXPIRED", "INVALIDATED"}
BEFORE, AFTER, AFTER_CHOCH = 36, 18, 60  # bars shown; the pattern stays legible


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


def _panel(s: Setup, bars: pd.DataFrame) -> list[str]:
    """The numbers behind each check, read from the bars, so a reviewer can verify them on the
    chart."""
    buy = s.direction == "buy"
    side = "above" if buy else "below"
    level = s.level.price
    sweep_close = float(bars["close"].iloc[s.sweep_idx])
    choch_close = float(bars["close"].iloc[s.choch_idx])
    back = sweep_close > level if buy else sweep_close < level
    beyond = choch_close > s.ref_price if buy else choch_close < s.ref_price
    depth = abs(level - s.extreme)
    gap = s.fvg_high - s.fvg_low

    p = CURRENT

    def ok(flag: bool) -> str:
        return "OK" if flag else "FAIL"

    return [
        f"1 Level   {_level_label(s.level)} = {level:.2f}",
        f"2 Sweep   close {sweep_close:.2f} {side} level {level:.2f}: {ok(back)}"
        f" | extreme {s.extreme:.2f}, depth {depth:.2f} = {depth / s.atr:.2f} ATR"
        f" (first bar min {p.min_sweep_atr}, max {p.max_sweep_atr}) | extensions {s.extensions}",
        f"3 CHoCH   close {choch_close:.2f} {side} ref {s.ref_price:.2f}"
        f" ({choch_close - s.ref_price:+.2f}): {ok(beyond)} | ref swing k={p.k_ltf}",
        f"4 FVG     {s.fvg_low:.2f}-{s.fvg_high:.2f} = {gap:.2f}"
        f" (min {p.min_fvg_atr * s.atr:.2f} = {p.min_fvg_atr} ATR)"
        f" | {s.choch_idx - s.fvg_idx} bars before CHoCH (max {p.fvg_max_bars_before_choch})",
        f"5 Plan    entry {s.entry:.2f} | SL {s.sl:.2f} | TP {s.tp:.2f}"
        f" ({'4R cap' if s.tp_source == 'cap' else 'opposite level'}) | R {s.r_multiple:.2f}",
        f"6 Result  {_result(s, bars)}",
    ]


def _result(s: Setup, bars: pd.DataFrame) -> str:
    when = _ny(bars["ts_utc"].iloc[s.events[-1][0]])
    if s.outcome is None:
        return f"{s.state.lower()} at {when} NY ({s.reason})"
    return f"{s.outcome} at {s.exit_price:.2f}, {when} NY, net {s.net_r:+.2f}R"


def draw(s: Setup, bars: pd.DataFrame, path: Path, number: int) -> None:
    last = s.exit_idx if s.exit_idx is not None else s.events[-1][0]
    start = max(0, min(s.ref_idx, s.extreme_idx) - BEFORE)
    # Show the pattern and the fill, not the whole holding period; the outcome is in the panel.
    end = min(len(bars) - 1, last + AFTER, s.choch_idx + AFTER_CHOCH)
    w = bars.iloc[start : end + 1]
    x = np.arange(start, end + 1)
    fig, ax = plt.subplots(figsize=(11, 7.0), dpi=80)

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
    ax.text(s.choch_idx, ax.get_ylim()[0], " CHoCH", va="bottom", fontsize=8, color="#1f77b4")

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
    # The numbers panel sits under the chart, so it never hides candles or markers.
    fig.subplots_adjust(left=0.07, right=0.89, top=0.94, bottom=0.27)
    fig.text(
        0.01,
        0.015,
        "\n".join(_panel(s, bars)),
        va="bottom",
        ha="left",
        fontsize=8,
        family="monospace",
        bbox={"boxstyle": "round,pad=0.4", "fc": "white", "ec": "#999999"},
    )
    fig.savefig(path)
    plt.close(fig)


CHECKLIST = """# Phase 2 human review — pattern validity ({rules}, 2012–2017)

Generated by `python -m app.smc.review` (seed {seed}).

**What is already checked by code:** the five written conditions (level, sweep, CHoCH, FVG and plan)
are re-derived from the raw bars for every setup in `conditions.md`. They are not re-checked here.

**The one question for each chart:** would an SMC trader recognise this as a genuine liquidity
sweep, then a change of character, then a fair value gap?

- **✅ valid pattern**
- **❌ not a genuine pattern.** Name what you see on the chart, for example "the sweep is noise
  inside a range" or "the CHoCH breaks a trivial micro-swing".
- **⚠️ unsure**

Use the last column for feedback on the definition itself, for example "minimum sweep depth too
small". Definition feedback is decided once, after the review. The gate is **{need} or more ✅ of
{n}**.

| # | Chart | Dir | Sweep (NY) | Outcome | Valid? | Visible reason | Definition feedback |
| --- | --- | --- | --- | --- | --- | --- | --- |
"""


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=OUT_DIR / "review")
    ap.add_argument(
        "--reset-sheet", action="store_true", help="rewrite REVIEW.md even if it has verdicts"
    )
    args = ap.parse_args(argv)

    params = CURRENT
    tf = f"{params.entry_tf_minutes}m"
    bars, h1, h4 = (pd.read_parquet(DATA_DIR / f"{t}.parquet") for t in (tf, "1h", "4h"))
    bars = bars[bars["ts_utc"] < DEV_END].reset_index(drop=True)
    setups = run(bars, h1, h4, params, CostParams())
    chosen = sample(setups, bars["ts_utc"], args.n, args.seed)

    ap_reset = args.reset_sheet
    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("*.png"):
        old.unlink()
    rows = []
    for i, s in enumerate(chosen, 1):
        name = f"{i:02d}_{s.direction}_{bars['ts_utc'].iloc[s.sweep_idx]:%Y%m%d_%H%M}.png"
        draw(s, bars, args.out / name, i)
        outcome = s.outcome or s.state.lower()
        when = _ny(bars["ts_utc"].iloc[s.sweep_idx])
        rows.append(f"| {i} | [{name}]({name}) | {s.direction} | {when} | {outcome} | | | |")
    need = int(np.ceil(0.9 * len(chosen)))
    text = (
        CHECKLIST.format(seed=args.seed, need=need, n=len(chosen), rules=CURRENT_NAME)
        + "\n".join(rows)
        + "\n"
    )
    text += f"\n**Result:** __ of {len(chosen)} correct (precision __%).\n"
    sheet = args.out / "REVIEW.md"
    if ap_reset or not sheet.exists():
        sheet.write_text(text, encoding="utf-8")
    else:  # keep recorded verdicts; the sample is deterministic, so rows still match
        existing = sheet.read_text(encoding="utf-8")
        missing = [r.split(" | ")[1] for r in rows if r.split(" | ")[1] not in existing]
        if missing:
            raise SystemExit(f"REVIEW.md does not match this sample: {missing[:3]}")
    print(f"wrote {len(chosen)} charts to {args.out}")


if __name__ == "__main__":
    main()
