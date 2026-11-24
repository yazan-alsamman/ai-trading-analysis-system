"""Gold: how far price goes with the five demo strategies' trades (descriptive, decides nothing;
Fadi asked 2026-11-10 whether the SL and the target are wrong).

    python -m app research gold-path build [--export <GOLD M1>]

For every trade the five actually take (one at a time, M8, as the EA), from the entry (the level):

- the signed move at 5 to 240 minutes (capped at 16:45 New York), in D and in dollars, and the
  share of trades ahead;
- the furthest point in favour (MFE) and against (MAE) until the trade's end time, ignoring the
  SL, and the minutes to the MFE;
- how much of the MFE the current exit keeps (gross R / MFE).

XAUUSD 2012 to 2026-01-09; with ``--export`` also FxPro's GOLD feed from 2016-02, with 2026 apart.
Writes ``gold_path.md``."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_exam as ge
from app.research import gold_exit as gx
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_path.md"
HORIZONS = (5, 15, 30, 60, 120, 240)  # minutes
REACH = (0.25, 0.5, 1.0, 1.5, 2.0, 3.0)  # x D, before -1 D


def paths(cx: gl.Ctx) -> pd.DataFrame:
    """The five's traded entries with their path measures and their M8 result."""
    sig = gx.signals(cx)
    t = gs.finish(gl.simulate(sig, cx, "M8"), cx)
    keep = sig.drop(columns=["dir", "risk"]).drop_duplicates(["strategy", "i"])
    t = t.merge(keep, on=["strategy", "i"], how="left")
    h, lo, c = cx.h, cx.lo, cx.c
    rows = []
    for r in t.itertuples(index=False):
        i, end, d, e, D = int(r.i), int(r.end), r.dir, r.entry, r.risk
        cap = max(int(cx.deadline[i]), i)
        mv = [d * (c[min(i + m // 5, cap)] - e) for m in HORIZONS]
        hh, ll = h[i + 1 : end + 1], lo[i + 1 : end + 1]
        if len(hh):
            fav, adv = (hh - e, e - ll) if d > 0 else (e - ll, hh - e)
            mfe, mae, tmfe = float(fav.max()), float(adv.max()), 5 * (int(np.argmax(fav)) + 1)
            hit = np.flatnonzero(adv >= D)
            pre = fav[: hit[0] + 1].max() if len(hit) else fav.max()
        else:
            mfe = mae = pre = 0.0
            tmfe = 0
        rows.append((*mv, mfe, mae, tmfe, pre))
    cols = [f"m{m}" for m in HORIZONS] + ["mfe", "mae", "t_mfe", "mfe_pre_sl"]
    return pd.concat([t.reset_index(drop=True), pd.DataFrame(rows, columns=cols)], axis=1)


def _se(x: pd.Series) -> float:
    return float(x.std(ddof=1) / np.sqrt(max(len(x), 2)))


def horizon_table(p: pd.DataFrame) -> list[str]:
    lines = [
        "| Minutes | Ahead | Mean move, D (SE) | Median move, $ |",
        "| --- | --- | --- | --- |",
    ]
    for m in HORIZONS:
        x = p[f"m{m}"] / p["risk"]
        lines.append(f"| {m} | {(p[f'm{m}'] > 0).mean():.1%} | {x.mean():+.3f} ({_se(x):.3f}) "
                     f"| {p[f'm{m}'].median():+.2f} |")  # fmt: skip
    return lines


def strategy_table(p: pd.DataFrame) -> list[str]:
    lines = [
        "| Strategy | Trades | Ahead at 30 min | Move at 30 min, D | Move at 120 min, D "
        "| MFE, D (median) | MAE, D (median) | Minutes to MFE (median) | Gross R | Kept of MFE |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, g in [*p.groupby("strategy"), ("All", p)]:
        mfe = g["mfe"] / g["risk"]
        lines.append(
            f"| {name} | {len(g):,} | {(g['m30'] > 0).mean():.1%} "
            f"| {(g['m30'] / g['risk']).mean():+.3f} | {(g['m120'] / g['risk']).mean():+.3f} "
            f"| {mfe.median():.2f} | {(g['mae'] / g['risk']).median():.2f} "
            f"| {g['t_mfe'].median():.0f} | {g['gross'].mean():+.3f} "
            f"| {g['gross'].mean() / mfe.mean():.0%} |"
        )
    return lines


def reach_table(p: pd.DataFrame) -> list[str]:
    x = p["mfe_pre_sl"] / p["risk"]
    lines = [
        "| Reaches before the SL (−1 D) | Share | Random walk 1 / (1 + x) |",
        "| --- | --- | --- |",
    ]
    for q in REACH:
        lines.append(f"| +{q:g} D | {(x >= q).mean():.1%} | {1 / (1 + q):.1%} |")
    return lines


def exits_table(p: pd.DataFrame) -> list[str]:
    win = p["gross"] > 0
    return [
        "| Exit | Share | Mean gross R |",
        "| --- | --- | --- |",
        *[
            f"| {k} | {len(g) / len(p):.1%} | {g['gross'].mean():+.3f} |"
            for k, g in p.groupby("exit")
        ],
        "",
        f"Winners {win.mean():.1%}, mean +{p.loc[win, 'gross'].mean():.3f} R; losers mean "
        f"{p.loc[~win, 'gross'].mean():+.3f} R. The best 10% of trades make "
        f"{p['gross'].nlargest(max(len(p) // 10, 1)).sum() / max(p['gross'].sum(), 1e-9):.0%} of "
        f"the total gross R ({p['gross'].sum():+.1f} R).",
    ]


def section(title: str, p: pd.DataFrame) -> list[str]:
    return [
        f"## {title} ({len(p):,} trades, median D ${p['risk'].median():.2f})",
        "",
        "**After the entry: share of trades ahead and the mean move.**",
        "",
        *horizon_table(p),
        "",
        "**By strategy.**",
        "",
        *strategy_table(p),
        "",
        "**How far before the SL.**",
        "",
        *reach_table(p),
        "",
        "**How the current exits end the trades (M8).**",
        "",
        *exits_table(p),
        "",
    ]


def build(export: Path | None) -> str:
    cx = gl.context(gl.load())
    p = paths(cx)
    yr = p["year"]
    lines = [
        "# Gold: how far price goes with the five strategies' trades (descriptive)",
        "",
        "_`python -m app research gold-path build`. The five demo strategies' own trades (one at "
        "a time, M8, as the EA), measured from the entry level. D = each trade's SL distance. "
        "Moves are before costs. Decides nothing._",
        "",
        *section("XAUUSD 2012-2021", p[yr <= 2021]),
        *section("XAUUSD 2022 to 2026-01-09", p[yr > 2021]),
    ]
    if export is not None:
        fx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
        q = paths(fx)
        when = pd.to_datetime(fx.m["close_utc"].to_numpy()[q["i"]], utc=True)
        q = q[when >= gv.FX_START]
        y26 = pd.to_datetime(fx.m["close_utc"].to_numpy()[q["i"]], utc=True).year == 2026
        lines += [
            *section(f"FxPro GOLD 2016-02 to 2025 (`{export.name}`)", q[~y26]),
            *section("FxPro GOLD 2026", q[y26]),
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-path")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
