"""Gold: do the breaks' bad runs persist? (``docs/strategies/GOLD_REGIME.md``, registered
2026-11-08).

    python -m app research gold-regime --export <GOLD M1 export>

Two detectors, each known at a trade's entry, classify the regime as BAD or GOOD:

- PERF: the mean net R of the last N closed break trades;
- FALSE: the false-break rate of the previous 20 days against its 75th percentile so far.

The report gives the break trades' mean in each regime, RECLAIM's mean in BAD, and three
portfolios (ALWAYS, PAUSE, SWITCH), on FxPro GOLD and on XAUUSD. It trades nothing. The lockbox
is not read."""

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

REPORT = gl.OUT_DIR / "gold_regime_report.md"
NS = (20, 30, 50)
BAD_MEAN = -0.10
FALSE_DAYS, FALSE_PCT = 20, 0.75
RECLAIM_BARS, RECLAIM_TP, RECLAIM_CAP = 6, 1.5, 0.10


def specs(cx: gl.Ctx) -> dict:
    """The five break strategies as the EA trades them: levels, distance, horizon, cost cap."""
    four = (0.75 * cx.atr4h, ge.LVL_HORIZON, ge.LVL_CAP)
    return {"LVL4H": (gc.day_levels(cx), *four),
            "PIVOT": (gc.pivot_levels(cx), cx.atr1h, ge.PIV_HORIZON, None),
            **{k: (lv, *four) for k, lv in gs.shadow_levels(cx).items()}}  # fmt: skip


def reclaim(cx: gl.Ctx, name: str, lv_days: dict[str, np.ndarray]) -> pd.DataFrame:
    """At each level's first break of the day inside 02:00-16:00, the first close back inside
    within 6 bars: a trade against the break, SL beyond its extreme + 0.1 x ATR(5m), TP 1.5 R."""
    win = gc.WINDOWS["02-16"]
    prev = np.r_[np.nan, cx.c[:-1]]
    ok_t = (cx.weekday < 5) & (cx.ny_min >= win[0]) & (cx.ny_min < win[1])
    rows = []
    for lv_day in lv_days.values():
        lv = lv_day[np.maximum(cx.day_idx, 0)]
        up, dn = (prev < lv) & (cx.h >= lv), (prev > lv) & (cx.lo <= lv)
        idx = np.flatnonzero(ok_t & (up | dn) & np.isfinite(lv))
        for i in pd.Series(idx).groupby(cx.day_idx[idx]).min().to_numpy():
            d, level = (1 if up[i] else -1), lv[i]
            for j in range(i, min(i + RECLAIM_BARS, len(cx.c) - 1)):
                if (cx.c[j] < level) if d > 0 else (cx.c[j] > level):
                    ext = cx.h[i : j + 1].max() if d > 0 else cx.lo[i : j + 1].min()
                    e, sl = cx.c[j], ext + d * 0.1 * cx.atr5[j]
                    risk = d * (sl - e)
                    if (risk > 0 and (cx.spread[j] + gl.COMMISSION) / risk <= RECLAIM_CAP
                            and cx.deadline[j] > j):  # fmt: skip
                        rows.append((name, j, -float(d), e, risk, RECLAIM_TP, int(cx.deadline[j])))
                    break
    return pd.DataFrame(rows, columns=gl.COLS).sort_values("i", kind="stable")


def trades(cx: gl.Ctx, start: pd.Timestamp) -> pd.DataFrame:
    """The break trades (kind BREAK) and RECLAIM's (kind RECLAIM), each strategy one at a time,
    with the entry and exit times."""
    out = []
    for name, (lv, dist, hor, cap) in specs(cx).items():
        sig = gc.levels(cx, name, lv, dist, gc.WINDOWS["02-16"], hor, cap)
        brk = gc.run(sig, cx).drop(columns=["year", "net", "net_slip"])
        out.append(gs.finish(brk, cx).assign(kind="BREAK"))
        out.append(
            gs.finish(gl.simulate(reclaim(cx, name, lv), cx, "M0"), cx).assign(kind="RECLAIM")
        )
    t = pd.concat(out, ignore_index=True)
    close = cx.m["close_utc"].to_numpy()
    t["t_in"] = pd.to_datetime(close[t["i"]], utc=True)
    t["t_out"] = pd.to_datetime(close[t["j"]], utc=True)
    return t[t["t_in"] >= start].sort_values("t_in", kind="stable").reset_index(drop=True)


def perf_bad(t: pd.DataFrame, n: int) -> np.ndarray:
    """PERF: BAD when the mean net R of the last n break trades closed before each entry is below
    -0.10 (not BAD before n trades have closed)."""
    b = t[t["kind"] == "BREAK"].sort_values("t_out", kind="stable")
    cum = np.r_[0.0, b["net_slip"].cumsum().to_numpy()]
    k = np.searchsorted(b["t_out"].to_numpy(), t["t_in"].to_numpy(), side="left")
    mean = np.where(k >= n, (cum[k] - cum[np.maximum(k - n, 0)]) / n, np.nan)
    return np.nan_to_num(mean, nan=0.0) < BAD_MEAN


def false_bad(cx: gl.Ctx, t: pd.DataFrame) -> np.ndarray:
    """FALSE: BAD when the share of the PDH / PDL first breaks of the previous 20 trading days
    whose day closed back inside the level is above its 75th percentile over the earlier days."""
    lv = {k: v for k, v in gc.day_levels(cx).items() if k in ("PDH", "PDL")}
    sig = gc.levels(cx, "X", lv, np.ones(len(cx.c)), gc.WINDOWS["02-16"], 1, None)
    day = cx.day_idx[sig["i"].to_numpy()]
    close = cx.d1["close"].to_numpy()[day]
    failed = np.where(sig["dir"] > 0, close < sig["level"], close > sig["level"])
    per = pd.DataFrame({"d": day, "f": failed}).groupby("d")["f"].agg(["sum", "size"])
    per = per.reindex(np.arange(len(cx.d1)), fill_value=0)
    roll = per["sum"].rolling(FALSE_DAYS).sum() / per["size"].rolling(FALSE_DAYS).sum()
    rate = roll.shift(1)  # the previous 20 days, known when the day starts
    q = rate.expanding(min_periods=250).quantile(FALSE_PCT).shift(1)
    bad_day = (rate > q).to_numpy()
    return bad_day[cx.day_idx[t["i"].to_numpy()]]


def _t(x: pd.Series) -> float:
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else np.nan


def measures(t: pd.DataFrame, bad: np.ndarray) -> dict:
    brk, rec = t["kind"] == "BREAK", t["kind"] == "RECLAIM"
    b_bad, b_good = t[brk & bad], t[brk & ~bad]
    always = t[brk]
    pause = t[brk & ~bad]
    switch = pd.concat([t[brk & ~bad], t[rec & bad]])

    def port(x: pd.DataFrame) -> dict:
        return gn.portfolio([x.assign(j=x["t_out"].astype("int64"), i=x["t_in"].astype("int64"))])

    return {"bad_share": float(bad[brk].mean()), "n_bad": len(b_bad),
            "bad": b_bad["net_slip"].mean(),
            "t_bad": _t(b_bad["net_slip"]), "good": b_good["net_slip"].mean(),
            "reclaim_bad": t[rec & bad]["net_slip"].mean(), "n_rec_bad": int((rec & bad).sum()),
            "ALWAYS": port(always), "PAUSE": port(pause), "SWITCH": port(switch)}  # fmt: skip


def section(name: str, cx: gl.Ctx, t: pd.DataFrame) -> tuple[list[str], dict]:
    dets = {**{f"PERF {n}": perf_bad(t, n) for n in NS}, "FALSE": false_bad(cx, t)}
    res = {k: measures(t, v) for k, v in dets.items()}
    lines = [
        f"## {name}",
        "",
        "| Detector | Break trades in BAD | Breaks in BAD (t) | Breaks in GOOD "
        "| RECLAIM in BAD (n) |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {k} | {r['n_bad']:,} ({r['bad_share']:.0%}) | {r['bad']:+.3f} ({r['t_bad']:+.2f}) "
            f"| {r['good']:+.3f} | {r['reclaim_bad']:+.3f} ({r['n_rec_bad']:,}) |"
            for k, r in res.items()
        ],  # fmt: skip
        "",
        "| Detector | Portfolio | Trades | Mean | Sum | Largest drawdown |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for k, r in res.items():
        for p in ("ALWAYS", "PAUSE", "SWITCH"):
            x = r[p]
            lines.append(f"| {k} | {p} | {x['trades']:,} | {x['mean']:+.3f} | {x['sum']:+.1f} "
                         f"| {x['dd']:.1f} |")  # fmt: skip
    return lines, res


def passes(r: dict) -> bool:
    best = max(("PAUSE", "SWITCH"), key=lambda p: r[p]["sum"])
    return (r["bad"] < 0 and r["t_bad"] <= -2 and r[best]["sum"] > r["ALWAYS"]["sum"]
            and r[best]["dd"] < r["ALWAYS"]["dd"])  # fmt: skip


def build(export: Path) -> str:
    fx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
    fx_lines, fx_res = section(
        "FxPro GOLD, 2016-02 to 2026-11-05 (primary)", fx, trades(fx, gv.FX_START)
    )
    xa = gl.context(gl.load())
    xa_lines, xa_res = section("XAUUSD, 2012 to 2026-01-09 (second feed)", xa, trades(xa, gl.START))
    verdict = []
    for k in fx_res:
        ok = passes(fx_res[k]) and xa_res[k]["bad"] < 0
        verdict.append(f"- {k}: **{'passes' if ok else 'does not pass'}**.")
    lines = [
        "# Gold: do the breaks' bad runs persist? (exploratory)",
        "",
        "_`python -m app research gold-regime`, registered in `GOLD_REGIME.md` (2026-11-08). "
        "Net R with slip; portfolios in R, in exit order. Seen data on both feeds._",
        "",
        *fx_lines,
        "",
        *xa_lines,
        "",
        "## Decision (section 4)",
        "",
        *verdict,
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-regime")
    ap.add_argument("--export", type=Path, required=True, help="the FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
