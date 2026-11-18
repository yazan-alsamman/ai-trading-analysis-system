"""Event counts for discovery round 2 (``docs/discovery/PLAN.md``, stage D2): counts only.

    python -m app discovery count

Runs every detector of ``app.discovery.events`` on XAUUSD M1 (the research store, 2012 to
2026-01-09) and writes ``docs/discovery/counts.md``: events per family, cell and year, the share
signed up, and the median cost unit c(t0) by year. **No markout, no price after an event, no
outcome is computed.** F1 runs only when the drivers are stored (`discovery drivers store`)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.discovery import events as ev
from app.research import gold_ah as ah

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "discovery" / "counts.md"
CAL = ROOT / "data" / "processed" / "calendar.parquet"
DRIVERS = ROOT / "data" / "processed" / "drivers"
START = pd.Timestamp("2012-01-01", tz="UTC")


def all_events(m1: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    notes = []
    parts = [ev.f2(m1), ev.f5(m1)]
    if CAL.exists():
        parts.append(ev.f3(m1, pd.read_parquet(CAL)))
    else:
        notes.append("F3 not run: no calendar store.")
    dxy, bond = DRIVERS / "DOLLARIDXUSD.parquet", DRIVERS / "USTBONDTRUSD.parquet"
    if dxy.exists() and bond.exists():
        parts.append(ev.f1(m1, pd.read_parquet(dxy), pd.read_parquet(bond)))
    else:
        notes.append("F1 not run: the drivers are not stored yet.")
    e = pd.concat(parts, ignore_index=True)
    e["year"] = m1["ts_utc"].dt.year.to_numpy()[e["i"]]
    e["cost"] = ev.cost_unit(m1, e["i"].to_numpy())
    return e[e["year"] >= START.year].reset_index(drop=True), notes


def report(e: pd.DataFrame, notes: list[str]) -> str:
    years = sorted(e["year"].unique())
    lines = [
        "# Discovery round 2: event counts (stage D2, counts only)",
        "",
        "_`python -m app discovery count`. XAUUSD M1 (research store), 2012 to 2026-01-09. "
        "Events per cell and year; no price after an event was read. Discovery period "
        "2018-2021, confirmation 2022 to 2026-01-09 (`PLAN.md` §5)._",
        "",
        *[f"- {n}" for n in notes],
        "",
        "| Family | Cell | All | 2018-2021 | 2022 on | Up | "
        + " | ".join(str(y) for y in years)
        + " |",
        "| --- | --- | --- | --- | --- | --- |" + " --- |" * len(years),
    ]  # fmt: skip
    for (fam, cell), g in e.groupby(["family", "cell"], sort=True):
        per = g["year"].value_counts()
        disc = int(g["year"].between(2018, 2021).sum())
        conf = int((g["year"] >= 2022).sum())
        cells = " | ".join(f"{per.get(y, 0):,}" for y in years)
        lines.append(f"| {fam} | {cell} | {len(g):,} | {disc:,} | {conf:,} "
                     f"| {(g['sign'] > 0).mean():.0%} | {cells} |")  # fmt: skip
    cost = e.groupby("year")["cost"].median()
    lines += [
        "",
        "Median cost unit c(t0) = the event bar's spread + $0.07, in dollars, by year (all "
        "events):",
        "",
        "| " + " | ".join(str(y) for y in cost.index) + " |",
        "|" + " --- |" * len(cost),
        "| " + " | ".join(f"{v:.2f}" for v in cost.to_numpy()) + " |",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    m1 = ah.load_store()
    e, notes = all_events(m1)
    REPORT.write_text(report(e, notes), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}: {len(e):,} events" + (f" ({'; '.join(notes)})" if notes else ""))
    return 0
