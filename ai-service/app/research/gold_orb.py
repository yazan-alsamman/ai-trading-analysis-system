"""Gold: the New York opening range breakout (``docs/strategies/GOLD_ORB.md``, registered
2026-11-07).

    python -m app research gold-orb build                      # XAUUSD
    python -m app research gold-orb fxpro --export <GOLD M1>   # FxPro GOLD, the decision

ORB breaks the 08:20-08:50 New York range (the COMEX open and the 08:30 data) between 08:50 and
16:00, with LVL4H's frozen engine and settings. The lockbox is not read."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_orb_xauusd.md"  # not gold_orb.md: GOLD_ORB.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_orb_fxpro.md"
TUNE_END = gc.TUNE_END
RANGE_FROM, RANGE_TO = 8 * 60 + 20, 8 * 60 + 50  # bars opening 08:20 to 08:45
WINDOW = (RANGE_TO, 16 * 60)
MIN_BARS = 5


def orb_levels(cx: gl.Ctx) -> dict[str, np.ndarray]:
    """The high and low of each trading day's 08:20-08:50 New York bars (known at 08:50), by D1
    bar; NaN when fewer than five bars."""
    rng = (cx.ny_min >= RANGE_FROM) & (cx.ny_min < RANGE_TO)
    g = pd.DataFrame({"d": cx.day_idx[rng], "h": cx.h[rng], "l": cx.lo[rng]}).groupby("d")
    agg = g.agg(h=("h", "max"), l=("l", "min"), n=("h", "size"))
    agg = agg[(agg["n"] >= MIN_BARS) & (agg.index >= 0)]
    n = max(len(cx.d1), int(cx.day_idx.max()) + 1)
    hi, lo = np.full(n, np.nan), np.full(n, np.nan)
    hi[agg.index.to_numpy()] = agg["h"].to_numpy()
    lo[agg.index.to_numpy()] = agg["l"].to_numpy()
    return {"ORH": hi, "ORL": lo}


def run(cx: gl.Ctx) -> pd.DataFrame:
    sig = gc.levels(cx, "ORB", orb_levels(cx), ge.LVL_MULT * cx.atr4h, WINDOW, ge.LVL_HORIZON,
                    ge.LVL_CAP)  # fmt: skip
    t = gc.run(sig, cx).drop(columns=["year", "net", "net_slip"])
    return gn.with_day(gs.finish(t, cx), cx)


def _portfolio(day: dict[str, pd.DataFrame], t: pd.DataFrame) -> list[str]:
    five, six = gn.portfolio(list(day.values())), gn.portfolio([*day.values(), t])
    return [
        "| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {n} | {p['trades']:,} | {p['mean']:+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} |"
            for n, p in (("The five day strategies", five), ("With ORB", six))
        ],
    ]


def build() -> str:
    cx = gl.context(gl.load())
    t = run(cx)
    day = gn.day_strategies(cx)
    corr = gn.correlations(t, day)
    lines = [
        "# Gold: the New York opening range breakout, XAUUSD feed (exploratory)",
        "",
        "_`python -m app research gold-orb build`, registered in `GOLD_ORB.md` (2026-11-07). "
        "XAUUSD 5m bars 2012-01 to 2026-01-09; cost = the signal bar's recorded spread + $0.07 "
        "per oz; with slip adds $0.10 on stop exits. One fixed setting. Seen data: optimistic. "
        "The lockbox was not read._",
        "",
        *gs.HEAD,
        gs._row("2012-2021", t[t["year"] <= TUNE_END]),
        gs._row("2022 to 2026-01-09 (check)", t[t["year"] > TUNE_END]),
        gs._row("Buys", t[t["dir"] > 0]),
        gs._row("Sells", t[t["dir"] < 0]),
        "",
        "Daily net R correlation (decides nothing here): "
        + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
        + ".",
        "",
        *_portfolio(day, t),
        "",
        *gn._by_year(t),
    ]
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))

    def since(t: pd.DataFrame, when: pd.Timestamp) -> pd.DataFrame:
        return t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= when]

    t = since(run(cx), gv.FX_START)
    day = {k: since(d, gv.FX_START) for k, d in gn.day_strategies(cx).items()}
    corr = gn.correlations(t, day)
    s = gs.summary(t)
    met3 = s["net_slip"] > 0
    met4 = all(abs(v) <= gn.MAX_CORR for v in corr.values())
    lines = [
        "# Gold: the New York opening range breakout, FxPro's GOLD feed (exploratory)",
        "",
        f"_`python -m app research gold-orb fxpro`: `{export.name}`, trades from "
        f"{gv.FX_START.date()}. Costs as `gold_orb_xauusd.md`._",
        "",
        *gs.HEAD,
        gs._row("All", t),
        gs._row(
            "2026-01-12 on (used by no choice)", since(t, pd.Timestamp("2026-01-12", tz="UTC"))
        ),
        "",
        "Daily net R correlation: " + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items()) + ".",
        "",
        *_portfolio(day, t),
        "",
        *gn._by_year(t),
        "",
        f"Condition 3 (net with slip > 0): **{'met' if met3 else 'not met'}** "
        f"({s['net_slip']:+.3f}). Condition 4 (|correlation| <= {gn.MAX_CORR}): "
        f"**{'met' if met4 else 'not met'}**.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-orb")
    ap.add_argument("step", choices=("build", "fxpro"))
    ap.add_argument("--export", type=Path, help="fxpro: the GOLD M1 export")
    args = ap.parse_args(argv)
    if args.step == "build":
        REPORT.write_text(build(), encoding="utf-8", newline="\n")
        print(f"wrote {REPORT}")
    else:
        FX_REPORT.write_text(fxpro(args.export), encoding="utf-8", newline="\n")
        print(f"wrote {FX_REPORT}")
    return 0
