"""The five's hindsight ceiling (a thought experiment, Fadi 2026-11-14; decides nothing).

    python -m app research gold-oracle

Every trade of the five and ROUND (``gold_live.five_trades``, XAUUSD store, 2012 to 2026-01-09)
closed at the best price it reached between its fill and its real exit (MFE), which no rule can
know in advance:

- **A, every trade at its best:** a trade that was ever in profit exits at its MFE (net of the
  trading cost, no stop slip: a limit at the peak); one that never was keeps its real result.
- **B, only the real winners at their best:** trades that really ended above zero exit at their
  MFE; the real losers keep their real result (the stop).

The fill bar's own high / low is not used (the fill happened somewhere inside it), nor the stop
bar's when the trade ended at its stop (the order of the high and the stop inside it is unknown)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_lab as gl
from app.research import gold_live as gv

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "strategies" / "gold_oracle_result.md"
FIVE = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")
LADDER = (0.5, 1.0, 1.5, 2.0, 3.0, 5.0)


def mfe(t: pd.DataFrame, cx: gl.Ctx) -> np.ndarray:
    """The best open profit in R between the fill and the real exit."""
    out = np.zeros(len(t))
    for n, r in enumerate(t.itertuples(index=False)):
        i, j, s = int(r.i), int(r.j), float(r.dir)
        last = j - 1 if r.exit == "sl" else j
        if last <= i:
            continue
        seg = slice(i + 1, last + 1)
        best = (cx.h[seg].max() - r.entry) if s > 0 else (r.entry - cx.lo[seg].min())
        out[n] = max(best / r.risk, 0.0)
    return out


def table(t: pd.DataFrame, label: str) -> list[str]:
    def row(name: str, g: pd.DataFrame) -> str:
        return (
            f"| {name} | {len(g):,} | {(g['net_slip'] > 0).mean():.0%} "
            f"| {g['net_slip'].mean():+.3f} "
            f"| {g['A'].mean():+.3f} | {g['B'].mean():+.3f} | {g['mfe'].median():.2f} "
            f"| {g['net_slip'].sum() / max(g['A'].sum(), 1e-9):.0%} |"
        )

    lines = [
        f"### {label}",
        "",
        "| Strategy | Trades | Real winners | **Real** net R | **A** every trade at its best "
        "| **B** real winners at their best | MFE median (R) | Real / A |",
        "|" + " --- |" * 8,
    ]
    lines += [row(k, t[t["strategy"] == k]) for k in (*FIVE, "ROUND")]
    lines += [row("**The five**", t[t["strategy"].isin(FIVE)]), row("**All six**", t), ""]
    return lines


def main(argv: list[str] | None = None) -> int:
    fr = gl.load()
    _, t, _, cx = gv.five_trades(fr, start=pd.Timestamp("2012-01-01", tz="UTC"), with_round=True)
    t = t.copy()
    t["mfe"] = mfe(t, cx)
    cost = t["cost"].to_numpy()
    reached = t["mfe"].to_numpy() > 0
    best = np.maximum(t["mfe"].to_numpy() - cost, t["net_slip"].to_numpy())
    t["A"] = np.where(reached, best, t["net_slip"])
    t["B"] = np.where(t["net_slip"] > 0, best, t["net_slip"])
    lines = [
        "# The five's hindsight ceiling (a thought experiment)",
        "",
        "_`python -m app research gold-oracle`: every trade of the five and ROUND, XAUUSD store, "
        "closed at the best price it reached before its real exit. **No rule can do this: it needs "
        "the future.** It shows how much of the move the real management keeps. Net R after the "
        "trading cost; the real results include the stop slip._",
        "",
        *table(t, "2012 to 2026-01-09"),
        *table(t[t["year"] >= 2022], "2022 to 2026-01-09"),
        "## How far the trades went (the five, 2012 to 2026-01-09)",
        "",
        "| Best open profit reached | " + " | ".join(f">= {x}R" for x in LADDER) + " |",
        "|" + " --- |" * (len(LADDER) + 1),
        "| Share of trades | "
        + " | ".join(f"{(t.loc[t['strategy'].isin(FIVE), 'mfe'] >= x).mean():.0%}" for x in LADDER)
        + " |",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
