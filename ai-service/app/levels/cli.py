"""``python -m app levels <stage>``: the level-families study (``docs/levels/SPEC.md``).

    python -m app levels count     # L0: signals and orders per family, behaviour and year; power
    python -m app levels discover  # L1: discovery, gold 2012-2021, against 200 shifted copies
    python -m app levels discover --from 2024-01-01 --to 2026-01-10   # the same, another period

L0 reads no outcome: no price after an order's entry bar."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from app.levels import events as ev
from app.levels import families as fm
from app.levels import trades as tr
from app.research import gold_lab as gl

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "levels" / "counts.md"
DISCOVERY = (2012, 2021)
T_GATE = 3.0


def count() -> str:
    fr = gl.load()
    cx = gl.context(fr)
    dl = tr.deadline(cx)
    rows, sig_n = [], {}
    for fam in fm.all_families(cx, fr):
        s = ev.signals(cx, fam)
        yr = pd.to_datetime(cx.m["close_utc"].to_numpy()[s["i"].to_numpy()], utc=True).year
        s = s[(yr >= DISCOVERY[0]) & (yr <= DISCOVERY[1])]
        e = tr.entries(cx, s, dl)
        for beh in ("break", "rejection"):
            sig_n[(fam.name, beh)] = int((s["behaviour"] == beh).sum())
            g = e[e["behaviour"] == beh]
            rows.append(
                {
                    "family": fam.name,
                    "kind": fam.kind,
                    "behaviour": beh,
                    "signals": sig_n[(fam.name, beh)],
                    "orders": len(g),
                    "m": g["m"].mean(),
                    "cost_raw": g["cost_raw"].median(),
                    "cost_std": g["cost_std"].median(),
                    **{
                        int(y): int((g["year"] == y).sum())
                        for y in range(DISCOVERY[0], DISCOVERY[1] + 1)
                    },
                }
            )
    r = pd.DataFrame(rows)
    days = len(
        np.unique(
            cx.ny_day[
                (cx.weekday < 5)
                & (pd.to_datetime(cx.m["close_utc"]).dt.year.between(*DISCOVERY)).to_numpy()
            ]
        )
    )
    r["per_day"] = r["orders"] / days
    years = list(range(DISCOVERY[0], DISCOVERY[1] + 1))
    lines = [
        "# Level families: counts and power (L0, no outcome)",
        "",
        "_`python -m app levels count`, registered in `SPEC.md` (tag `levels-spec`). XAUUSD 5m, "
        f"{DISCOVERY[0]}-{DISCOVERY[1]}. Orders = signals in the window with the target and stop "
        "far enough for the cost (before the one-trade-per-book rule, which needs exits). m = "
        "target / stop distance. No price after an entry bar was read._",
        "",
        "## Power of the 8 primary tests",
        "",
        "Under a random walk a trade with target m R and stop 1 R has mean 0 and variance m R^2, "
        "so the smallest mean net R a pooled test sees at t = 3 is about 3 x sqrt(mean m / n). n "
        "counts orders before the book rule, so it is an upper bound and the real minimum is "
        "larger.",
        "",
        "| Type | Behaviour | Families | Orders (n) | Orders a day | Mean m | Smallest R at t = 3 "
        "| Median cost R (Raw / Standard) |",
        "|" + " --- |" * 8,
    ]
    for (kind, beh), g in r.groupby(["kind", "behaviour"], sort=True):
        n = g["orders"].sum()
        m = (g["m"] * g["orders"]).sum() / max(n, 1)
        mde = T_GATE * np.sqrt(m / n) if n else np.nan
        lines.append(
            f"| {kind} | {beh} | {len(g)} | {n:,} | {n / days:.2f} | {m:.2f} | {mde:.3f} "
            f"| {g['cost_raw'].median():.3f} / {g['cost_std'].median():.3f} |"
        )
    lines += [
        "",
        "## Per family",
        "",
        "| Family | Kind | Behaviour | Signals | Orders | A day | Mean m | Cost R Raw / Std | "
        + " | ".join(str(y) for y in years)
        + " |",
        "|" + " --- |" * (8 + len(years)),
    ]
    for _, x in r.iterrows():
        yv = " | ".join(f"{int(x[y]):,}" for y in years)
        lines.append(
            f"| {x['family']} | {x['kind']} | {x['behaviour']} | {x['signals']:,} "
            f"| {x['orders']:,} | {x['per_day']:.2f} | {x['m']:.2f} "
            f"| {x['cost_raw']:.3f} / {x['cost_std']:.3f} | {yv} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    warnings.simplefilter("ignore", RuntimeWarning)
    if argv and argv[0] == "count":
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(count(), encoding="utf-8", newline="\n")
        print(f"wrote {REPORT}")
        return 0
    if argv and argv[0] == "discover":
        import os

        for flag, var in (("--from", "LEVELS_FROM"), ("--to", "LEVELS_TO")):
            if flag in argv:
                os.environ[var] = argv[argv.index(flag) + 1]
        from app.levels.discover import main as discover

        return discover()
    print(__doc__, file=sys.stderr)
    return 2
