"""Gold: a tighter SL with a larger lot for the five level breaks (``docs/strategies/GOLD_SL.md``,
registered 2026-11-10; Fadi's idea).

    python -m app research gold-sl build [--export <GOLD M1>]

The five strategies' own entries; only the SL distance changes (M8 on it). Each trade risks the
same share of the account in every setting, so the mean net R compares them."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_exit as gx
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_sl_xauusd.md"  # not gold_sl.md: GOLD_SL.md on Windows
TUNE_END = gc.TUNE_END
SETTINGS = ("BASE", "H50", "H67", "USD10", "USD15")
NAMES = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")


def resize(sig: pd.DataFrame, setting: str) -> pd.DataFrame:
    s = sig.copy()
    if setting == "H50":
        s["risk"] = 0.5 * s["risk"]
    elif setting == "H67":
        s["risk"] = s["risk"] * 2 / 3
    elif setting == "USD10":
        s["risk"] = 10.0
    elif setting == "USD15":
        s["risk"] = 15.0
    return s


def run(cx: gl.Ctx, sig: pd.DataFrame, setting: str) -> pd.DataFrame:
    return gn.with_day(gs.finish(gl.simulate(resize(sig, setting), cx, "M8"), cx), cx)


def mean(t: pd.DataFrame) -> float:
    return float(t["net_slip"].mean()) if len(t) else np.nan


def line(name: str, t: pd.DataFrame) -> str:
    p = gn.portfolio([t]) if len(t) else {"sum": np.nan, "dd": np.nan}
    return (f"| {name} | {len(t):,} | {t['gross'].mean():+.3f} | {t['cost'].mean():.3f} "
            f"| {mean(t):+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} "
            f"| {(t['exit'] == 'sl').mean():.0%} |")  # fmt: skip


HEAD = [
    "| Setting | Trades | Gross R | Cost R | Net R with slip | Sum R | Largest drawdown R "
    "| SL exits |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
]


def periods(cx: gl.Ctx, sig: pd.DataFrame, spans: list[tuple[str, object]]) -> tuple[list, dict]:
    lines, means = [], {}
    runs = {s: run(cx, sig, s) for s in SETTINGS}
    for title, f in spans:
        lines += [f"**{title}**", "", *HEAD]
        for s, t in runs.items():
            sub = t[f(t)]
            means[(title, s)] = mean(sub)
            lines.append(line(s, sub))
        lines.append("")
    return lines, runs, means


def build(export: Path | None) -> str:
    cx = gl.context(gl.load())
    sig = gx.signals(cx)
    spans = [("XAUUSD 2012-2021", lambda t: t["year"] <= TUNE_END),
             ("XAUUSD 2022 to 2026-01-09", lambda t: t["year"] > TUNE_END)]  # fmt: skip
    body, runs, means = periods(cx, sig, spans)
    cand = [s for s in SETTINGS if s != "BASE"]
    best = max(cand, key=lambda s: means[("XAUUSD 2012-2021", s)])
    lines = [
        "# Gold: a tighter SL with a larger lot for the five level breaks",
        "",
        "_`python -m app research gold-sl build`, registered in `GOLD_SL.md` (2026-11-10). The "
        "five strategies' own entries; only the SL distance changes, M8 on it; R = the new "
        "distance. Cost = the entry bar's spread + $0.07 per oz; slip $0.10 on SL exits._",
        "",
        "## 1. The five together",
        "",
        *body,
        f"Chosen on 2012-2021: **{best}**.",
        "",
        "By strategy, the check (net R with slip):",
        "",
        "| Strategy | " + " | ".join(SETTINGS) + " |",
        "| --- |" + " --- |" * len(SETTINGS),
    ]
    chk = spans[1][1]
    for n in NAMES:
        cells = [f"{mean(runs[s][chk(runs[s]) & (runs[s]['strategy'] == n)]):+.3f}"
                 for s in SETTINGS]  # fmt: skip
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    beat = [means[(spans[0][0], best)] > means[(spans[0][0], "BASE")],
            means[(spans[1][0], best)] > means[(spans[1][0], "BASE")]]  # fmt: skip
    if export is not None:
        fx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
        fsig = gx.signals(fx)
        when = pd.to_datetime(fx.m["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
        fsig = fsig[when[fsig["i"]] >= np.datetime64(gv.FX_START.tz_convert(None))]

        def y26(t: pd.DataFrame) -> pd.Series:
            return pd.Series(pd.to_datetime(when[t["i"]]).year == 2026, index=t.index)

        fspans = [(f"FxPro GOLD 2016-02 to the end (`{export.name}`)", lambda t: t["i"] >= 0),
                  ("FxPro GOLD 2026", y26)]  # fmt: skip
        fbody, fruns, fmeans = periods(fx, fsig, fspans)
        beat.append(fmeans[(fspans[0][0], best)] > fmeans[(fspans[0][0], "BASE")])
        lines += ["", "## 2. FxPro's GOLD feed", "", *fbody,
                  "**Could a $10,000 account take a 0.25% trade (0.01 lots at least)?** "
                  "FxPro 2026:", "",
                  "| Setting | Median D' ($) | Trades with lots >= 0.01 |",
                  "| --- | --- | --- |"]  # fmt: skip
        s26 = fsig[y26(fsig).to_numpy()]
        for s in SETTINGS:
            d = resize(s26, s)["risk"]
            lines.append(
                f"| {s} | {d.median():.2f} | {(25.0 / (d * gv.CONTRACT) >= 0.01).mean():.0%} |"
            )
    adopt = all(beat) and export is not None
    verdict = "beats BASE everywhere: shadow version" if adopt else "is not adopted"
    lines += ["", f"**Decision (§2): {best} {verdict}** "
              f"(beats BASE on 2012-2021 / check{' / FxPro' if export is not None else ''}: "
              + " / ".join("yes" if b else "no" for b in beat) + ")."]  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-sl")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
