"""Gold: the dollar's breaks as a gold signal (``docs/strategies/GOLD_USD.md``, registered
2026-11-10).

    python -m app research gold-usd build                      # XAUUSD: tune, check, report
    python -m app research gold-usd fxpro --export <GOLD M1>   # FxPro GOLD, correlations

When EURUSD breaks one of its day levels (first touch of the day, 02:00-16:00 New York), gold is
traded the same way at the close of its bar with the same open time, with LVL4H's frozen exits.
EURUSD is read only to 2026-01-09: its lockbox file stays sealed."""

from __future__ import annotations

import argparse
import itertools
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

REPORT = gl.OUT_DIR / "gold_usd_xauusd.md"  # not gold_usd.md: GOLD_USD.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_usd_fxpro.md"
CHOICE = gl.STORE / "gold_usd_choice.json"
TUNE_END = gc.TUNE_END
LEVELS, FILTERS = ("PD", "ALL"), ("NONE", "LAG")
LAG_BARS, LAG_FRAC = 12, 0.25
EUR_END = gl.LOCKBOX  # no EURUSD bar from the lockbox start on


def eur_breaks(ecx: gl.Ctx, levels: str) -> pd.DataFrame:
    """EURUSD's first touches of its day levels: the bar's UTC open and the direction."""
    lv = gc.day_levels(ecx)
    if levels == "PD":
        lv = {k: lv[k] for k in ("PDH", "PDL")}
    s = gc.levels(ecx, "EUR", lv, np.ones(len(ecx.c)), gc.WINDOWS[ge.LVL_WINDOW], 1, None)
    ts = pd.to_datetime(ecx.m["ts_utc"].to_numpy()[s["i"]], utc=True)
    return pd.DataFrame({"ts": ts, "dir": s["dir"].to_numpy()}).sort_values("ts")


def signals(cx: gl.Ctx, br: pd.DataFrame, filt: str) -> pd.DataFrame:
    """Gold market entries at the close of the bar with the same open time as each break."""
    ts = pd.to_datetime(cx.m["ts_utc"], utc=True).to_numpy()
    k = np.searchsorted(ts, br["ts"].to_numpy())
    ok = (k < len(ts)) & (ts[np.minimum(k, len(ts) - 1)] == br["ts"].to_numpy())
    k, d = k[ok], br["dir"].to_numpy()[ok]
    dist = ge.LVL_MULT * cx.atr4h[k]
    w0, w1 = gc.WINDOWS[ge.LVL_WINDOW]
    keep = (cx.weekday[k] < 5) & (cx.ny_min[k] >= w0) & (cx.ny_min[k] < w1) & np.isfinite(dist)
    keep &= (dist > 0) & (k > LAG_BARS) & (cx.deadline[k] > k)
    keep &= (cx.spread[k] + gl.COMMISSION) / np.where(dist > 0, dist, np.nan) <= ge.LVL_CAP
    if filt == "LAG":
        moved = d * (cx.c[k] - cx.c[np.maximum(k - LAG_BARS, 0)])
        keep &= moved < LAG_FRAC * dist
    k, d, dist = k[keep], d[keep], dist[keep]
    end = np.minimum(k + ge.LVL_HORIZON, cx.deadline[k])
    t = pd.to_datetime(cx.m["close_utc"].to_numpy()[k], utc=True)
    s = pd.DataFrame({"strategy": "USD", "i": k, "dir": d, "entry": cx.c[k], "risk": dist,
                      "tp_r": np.nan, "end": end})  # fmt: skip
    return s[(t >= gl.START) & (t < EUR_END)].drop_duplicates("i").reset_index(drop=True)


def run(cx: gl.Ctx, br: pd.DataFrame, filt: str) -> pd.DataFrame:
    return gn.with_day(gs.finish(gl.simulate(signals(cx, br, filt), cx, "M8"), cx), cx)


def lead(cx: gl.Ctx, ecx: gl.Ctx) -> tuple[float, float, int]:
    """Correlation of EURUSD's 5m return with gold's in the same bar and in the next one."""
    g = pd.Series(np.log(cx.c), index=pd.to_datetime(cx.m["ts_utc"], utc=True)).diff()
    e = pd.Series(np.log(ecx.c), index=pd.to_datetime(ecx.m["ts_utc"], utc=True)).diff()
    j = pd.concat([g.rename("g"), e.rename("e")], axis=1, join="inner").dropna()
    j["g_next"] = j["g"].shift(-1)
    j = j.dropna()
    return float(j["e"].corr(j["g"])), float(j["e"].corr(j["g_next"])), len(j)


def tune(cx: gl.Ctx, breaks: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for lv, filt in itertools.product(LEVELS, FILTERS):
        t = run(cx, breaks[lv], filt)
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        rows.append({"levels": lv, "filt": filt, **{f"tune_{k}": v for k, v in a.items()},
                     **{f"check_{k}": v for k, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (g["tune_net"] > 0) & (g["tune_years_pos"] >= 0.6)
    g["eligible"] &= g["tune_trades"] >= gn.MIN_TRADES
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


def build() -> str:
    cx = gl.context(gl.load())
    ecx = gl.context(gl.load("EURUSD"))
    breaks = {lv: eur_breaks(ecx, lv) for lv in LEVELS}
    same, nxt, n = lead(cx, ecx)
    g = tune(cx, breaks)
    ok = g[g["eligible"]]
    lines = [
        "# Gold: the dollar's breaks as a gold signal, XAUUSD feed (exploratory)",
        "",
        "_`python -m app research gold-usd build`, registered in `GOLD_USD.md` (2026-11-10). "
        "EURUSD and XAUUSD 5m bars, 2016-01 to 2026-01-09; LVL4H's frozen exits; cost = gold's "
        "signal bar spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2016-2021, "
        "check 2022 to 2026-01-09. No lockbox file was read._",
        "",
        "## 1. Does EURUSD lead gold? (descriptive)",
        "",
        f"Correlation of 5m log returns over {n:,} common bars: same bar {same:+.3f}, "
        f"EURUSD then gold's next bar {nxt:+.3f}.",
        "",
        "## 2. The four settings (by net R on 2016-2021)",
        "",
        "| Levels | Filter | Tune trades | Tune net | Tune years + | Tune cost R | Check trades "
        "| Check net (SE) | Check with slip | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.levels} | {r.filt} | {r.tune_trades:,} | {r.tune_net:+.3f} "
            f"| {r.tune_years_pos:.0%} | {r.tune_cost:.3f} | {r.check_trades:,} "
            f"| {r.check_net:+.3f} ({r.check_se:.3f}) | {r.check_net_slip:+.3f} "
            f"| {'yes' if r.eligible else ''} |"
            for r in g.itertuples()
        ],
        "",
    ]
    choice = {}
    if len(ok):
        choice = {"levels": ok.iloc[0]["levels"], "filt": ok.iloc[0]["filt"]}
        t = run(cx, breaks[choice["levels"]], choice["filt"])
        corr = gn.correlations(t, gn.day_strategies(cx))
        lines += [
            f"Chosen: {choice}.",
            "",
            *gs.HEAD,
            gs._row("2016-2021", t[t["year"] <= TUNE_END]),
            gs._row("Check", t[t["year"] > TUNE_END]),
            gs._row("Buys", t[t["dir"] > 0]),
            gs._row("Sells", t[t["dir"] < 0]),
            "",
            "Daily net R correlation with the five (decides nothing here): "
            + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
            + ".",
            "",
            *gn._by_year(t),
        ]
    else:
        lines.append("**No setting qualifies: USD is dropped.**")
    CHOICE.write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    if not choice:
        return "# Gold: the dollar's breaks on FxPro's GOLD feed\n\nDropped on XAUUSD.\n"
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
    ecx = gl.context(gl.load("EURUSD"))

    def window(t: pd.DataFrame) -> pd.DataFrame:
        when = pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True)
        return t[(when >= gv.FX_START) & (when < EUR_END)]

    t = window(run(cx, eur_breaks(ecx, choice["levels"]), choice["filt"]))
    day = {k: window(d) for k, d in gn.day_strategies(cx).items()}
    corr = gn.correlations(t, day)
    sm = gs.summary(t)
    met = sm["net_slip"] > 0 and all(abs(v) <= gn.MAX_CORR for v in corr.values())
    five, six = gn.portfolio(list(day.values())), gn.portfolio([*day.values(), t])
    lines = [
        "# Gold: the dollar's breaks as a gold signal, FxPro's GOLD feed (exploratory)",
        "",
        f"_`python -m app research gold-usd fxpro`: `{export.name}`, trades {gv.FX_START.date()} "
        f"to 2026-01-09 (EURUSD's lockbox stays sealed). Setting chosen on XAUUSD: {choice}._",
        "",
        *gs.HEAD,
        gs._row("USD", t),
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
            for n, p in (("The five", five), ("The five and USD", six))
        ],
        "",
        *gn._by_year(t),
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-usd")
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
