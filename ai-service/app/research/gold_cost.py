"""The demo strategies at Standard-account costs (Fadi, 2026-11-12; descriptive, decides nothing).

    python -m app research gold-cost

Reads the FxPro trades of ``gold-live fxpro`` (the five and ROUND, 2016-02 to 2026-11-05, the
export's summary bars dropped). Raw (the backtests): the bar's spread + $0.07 commission. Standard
(Fadi's live account): no commission and a wider spread, modelled two ways: the recorded spread +
a markup of $0.20, 0.25 or 0.30, and max(recorded spread, $0.35) (``docs/levels/SPEC.md`` D10).
$0.10 slip on stop exits in every case."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from app.research import gold_lab as gl
from app.research import gold_live as gv

REPORT = gl.OUT_DIR / "gold_cost_standard.md"
MARKUPS = (0.20, 0.25, 0.30)
FLOOR = 0.35


def costed(t: pd.DataFrame) -> pd.DataFrame:
    """Net R with slip under each cost model."""
    t = t.copy()
    spread = t["cost"] * t["risk"] - gl.COMMISSION  # the recorded spread, $ an ounce
    slip = np.where(t["exit"] == "sl", gl.SL_SLIP / t["risk"], 0.0)
    t["raw"] = t["gross"] - t["cost"] - slip
    for m in MARKUPS:
        t[f"std+{m:.2f}"] = t["gross"] - (spread + m) / t["risk"] - slip
    t[f"std>={FLOOR:.2f}"] = t["gross"] - np.maximum(spread, FLOOR) / t["risk"] - slip
    t["spread"] = spread
    return t


def build() -> str:
    t = costed(pd.read_parquet(gv.FX_TRADES))
    models = ["raw", *[f"std+{m:.2f}" for m in MARKUPS], f"std>={FLOOR:.2f}"]
    head = "| Set | Trades | Median risk ($) | " + " | ".join(models) + " |"
    sep = "|" + " --- |" * (3 + len(models))

    def row(name: str, g: pd.DataFrame) -> str:
        return (f"| {name} | {len(g):,} | {g['risk'].median():.2f} | "
                + " | ".join(f"{g[m].mean():+.3f}" for m in models) + " |")  # fmt: skip

    five = t[t["strategy"] != "ROUND"]
    lines = [
        "# The demo strategies at Standard-account costs (descriptive)",
        "",
        "_`python -m app research gold-cost`. FxPro GOLD 2016-02 to 2026-11-05 (summary bars "
        "dropped). Mean net R a trade with $0.10 slip on stop exits. raw = spread + $0.07 "
        "commission (every backtest so far); std+m = spread + markup m, no commission; std>=0.35 = "
        "max(spread, $0.35). Decides nothing._",
        "",
        "Recorded spread, median by year ($): "
        + ", ".join(f"{y} {v:.2f}" for y, v in t.groupby("year")["spread"].median().items())
        + ".",
        "",
        head,
        sep,
        row("The five", five),
        row("The five + ROUND", t),
        *[
            row(s, t[t["strategy"] == s])
            for s in ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL", "ROUND")
        ],
        "",
        "By year, the five + ROUND:",
        "",
        head.replace("Set", "Year"),
        sep,
        *[row(str(y), g) for y, g in t.groupby("year")],
        "",
        "Sum and largest drawdown (R, in exit order), the five + ROUND:",
        "",
        "| Model | Sum | Largest drawdown |",
        "| --- | --- | --- |",
    ]
    order = t.sort_values(["j", "i"], kind="stable")
    for m in models:
        cum = order[m].cumsum().to_numpy()
        dd = float(np.max(np.maximum.accumulate(np.r_[0.0, cum])[1:] - cum))
        lines.append(f"| {m} | {cum[-1]:+.1f} | {dd:.1f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="python -m app research gold-cost").parse_args(argv)
    REPORT.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
