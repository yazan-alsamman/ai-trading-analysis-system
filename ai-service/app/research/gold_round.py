"""Gold: breaks of round numbers (``docs/strategies/GOLD_ROUND.md``, registered 2026-11-10).

    python -m app research gold-round build                     # XAUUSD: tune, check, report
    python -m app research gold-round fxpro --export <GOLD M1>  # FxPro GOLD, correlations

Each day: the multiples of $X on either side of the previous day's close (RU above, RD at or
below), traded with LVL4H's frozen engine (stop entry with the break, D = 0.75 x ATR(4h), M8)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_round_xauusd.md"  # not gold_round.md: GOLD_ROUND.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_round_fxpro.md"
CHOICE = gl.STORE / "gold_round_choice.json"
TUNE_END = gc.TUNE_END
STEPS = (10.0, 25.0, 50.0, 100.0)


def round_levels(cx: gl.Ctx, step: float) -> dict[str, np.ndarray]:
    """Per daily bar: RU and RD from the previous day's close (NaN on the first day)."""
    c = np.r_[np.nan, cx.d1["close"].to_numpy()[:-1]]
    rd = np.floor(c / step) * step
    return {"RU": rd + step, "RD": rd}


def run(cx: gl.Ctx, step: float) -> pd.DataFrame:
    return gn.with_day(gs.level_run(cx, "ROUND", round_levels(cx, step)), cx)


def tune(cx: gl.Ctx) -> pd.DataFrame:
    rows = []
    days = len(np.unique(cx.ny_day[(cx.m["close_utc"] >= gl.START).to_numpy() & (cx.weekday < 5)]))
    for step in STEPS:
        t = run(cx, step)
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        rows.append({"step": step, "per_day": len(t) / days,
                     **{f"tune_{k}": v for k, v in a.items()},
                     **{f"check_{k}": v for k, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (g["tune_net"] > 0) & (g["tune_years_pos"] >= 0.6)
    g["eligible"] &= g["tune_trades"] >= gn.MIN_TRADES
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


def _grid(g: pd.DataFrame) -> list[str]:
    return [
        "| Step | Trades a day | Tune trades | Tune net | Tune years + | Tune cost R "
        "| Check trades | Check net (SE) | Check with slip | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| ${r.step:g} | {r.per_day:.2f} | {r.tune_trades:,} | {r.tune_net:+.3f} "
            f"| {r.tune_years_pos:.0%} | {r.tune_cost:.3f} | {r.check_trades:,} "
            f"| {r.check_net:+.3f} ({r.check_se:.3f}) | {r.check_net_slip:+.3f} "
            f"| {'yes' if r.eligible else ''} |"
            for r in g.itertuples()
        ],
    ]


def build() -> str:
    cx = gl.context(gl.load())
    g = tune(cx)
    ok = g[g["eligible"]]
    lines = [
        "# Gold: breaks of round numbers, XAUUSD feed (exploratory)",
        "",
        "_`python -m app research gold-round build`, registered in `GOLD_ROUND.md` (2026-11-10). "
        "XAUUSD 5m bars 2012-01 to 2026-01-09; LVL4H's frozen engine; cost = the signal bar's "
        "spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 to "
        "2026-01-09. Seen data: optimistic. The lockbox was not read._",
        "",
        "## 1. The four steps (by net R on 2012-2021)",
        "",
        *_grid(g),
        "",
    ]
    choice = {}
    if len(ok):
        choice = {"step": float(ok.iloc[0]["step"])}
        t = run(cx, choice["step"])
        corr = gn.correlations(t, gn.day_strategies(cx))
        lines += [
            f"Chosen: ${choice['step']:g}.",
            "",
            *gs.HEAD,
            gs._row("2012-2021", t[t["year"] <= TUNE_END]),
            gs._row("Check", t[t["year"] > TUNE_END]),
            gs._row("Buys", t[t["dir"] > 0]),
            gs._row("Sells", t[t["dir"] < 0]),
            "",
            "Daily net R correlation with the five, 2012 to 2026-01-09 (decides nothing here): "
            + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
            + ".",
            "",
            *gn._by_year(t),
        ]
    else:
        lines.append("**No step qualifies: ROUND is dropped.**")
    CHOICE.write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    if not choice:
        return "# Gold: round numbers on FxPro's GOLD feed\n\nDropped on XAUUSD.\n"
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))

    def since(t: pd.DataFrame) -> pd.DataFrame:
        return t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= gv.FX_START]

    t = since(run(cx, choice["step"]))
    day = {k: since(d) for k, d in gn.day_strategies(cx).items()}
    corr = gn.correlations(t, day)
    sm = gs.summary(t)
    met = sm["net_slip"] > 0 and all(abs(v) <= gn.MAX_CORR for v in corr.values())
    exam = pd.Timestamp("2026-01-12", tz="UTC")
    in26 = t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= exam]
    five, six = gn.portfolio(list(day.values())), gn.portfolio([*day.values(), t])
    lines = [
        "# Gold: breaks of round numbers, FxPro's GOLD feed (exploratory)",
        "",
        f"_`python -m app research gold-round fxpro`: `{export.name}`, trades from "
        f"{gv.FX_START.date()}. Step chosen on XAUUSD 2012-2021: ${choice['step']:g}._",
        "",
        *gs.HEAD,
        gs._row("ROUND, all", t),
        gs._row("ROUND, 2026-01-12 on", in26),
        "",
        "Daily net R correlation: " + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items()) + ".",
        "",
        f"**Conditions 3 and 4: {'met' if met else 'not met'}** (net with slip "
        f"{sm['net_slip']:+.3f}).",
        "",
        "| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {n} | {p['trades']:,} | {p['mean']:+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} |"
            for n, p in (("The five", five), ("The five and ROUND", six))
        ],
        "",
        *gn._by_year(t),
    ]
    return "\n".join(lines) + "\n"


COMBO_REPORT = gl.OUT_DIR / "gold_round_combo.md"
COMBO_STEPS = (25.0, 50.0, 100.0)


def combo(export: Path) -> str:
    """Descriptive (Fadi, 2026-11-11; decides nothing): the five with ROUND at $25, $50 or $100
    added, on XAUUSD 2012 to 2026-01-09 and on FxPro 2016-02 to the export's end."""
    lines = ["# Gold: the five with round-number breaks added (descriptive)", "",
             "_`python -m app research gold-round combo`. Net R with slip; ROUND traded with "
             "LVL4H's frozen engine, as in `GOLD_ROUND.md`. Decides nothing; logged in "
             "`TRIALS.md`._", ""]  # fmt: skip
    feeds = {"XAUUSD 2012 to 2026-01-09": (gl.context(gl.load()), gl.START),
             "FxPro 2016-02 to 2026-11-05": (gl.context(ge.frames_from_lines(gv.fx_lines(export))),
                                             gv.FX_START)}  # fmt: skip
    exam = pd.Timestamp("2026-01-12", tz="UTC")
    for name, (cx, start) in feeds.items():
        when = pd.to_datetime(cx.m["close_utc"], utc=True).to_numpy()

        def since(t: pd.DataFrame, a=start, w=when) -> pd.DataFrame:
            return t[pd.to_datetime(w[t["i"]], utc=True) >= a]

        days = len(np.unique(cx.ny_day[(cx.m["close_utc"] >= start).to_numpy() & (cx.weekday < 5)]))
        day = {k: since(d) for k, d in gn.day_strategies(cx).items()}
        rows = [("The five", list(day.values()), None)]
        for step in COMBO_STEPS:
            t = since(run(cx, step))
            rows.append((f"The five + ROUND ${step:g}", [*day.values(), t], t))
        lines += [f"## {name}", "",
                  "| Set | Trades | Trades a day | Mean | Sum | Largest drawdown | ROUND alone "
                  "| ROUND from 2026-01-12 | Correlation with the five |",
                  "|" + " --- |" * 9]  # fmt: skip
        for label, parts, t in rows:
            p = gn.portfolio(parts)
            extra = "| | |"
            if t is not None:
                corr = gn.correlations(t, day)
                in26 = since(t, exam)
                late = f"{in26['net_slip'].mean():+.3f} ({len(in26)})" if len(in26) else "-"
                extra = (f"| {t['net_slip'].mean():+.3f} ({len(t):,}) | {late} "
                         f"| {min(corr.values()):+.2f} to {max(corr.values()):+.2f}")  # fmt: skip
            lines.append(f"| {label} | {p['trades']:,} | {p['trades'] / days:.2f} "
                         f"| {p['mean']:+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} "
                         f"{extra} |")  # fmt: skip
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-round")
    ap.add_argument("step", choices=("build", "fxpro", "combo"))
    ap.add_argument("--export", type=Path, help="fxpro, combo: the GOLD M1 export")
    args = ap.parse_args(argv)
    if args.step == "build":
        REPORT.write_text(build(), encoding="utf-8", newline="\n")
        print(f"wrote {REPORT}")
    elif args.step == "combo":
        COMBO_REPORT.write_text(combo(args.export), encoding="utf-8", newline="\n")
        print(f"wrote {COMBO_REPORT}")
    else:
        FX_REPORT.write_text(fxpro(args.export), encoding="utf-8", newline="\n")
        print(f"wrote {FX_REPORT}")
    return 0
