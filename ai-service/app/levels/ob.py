"""Order blocks as a level family (``docs/levels/ORDER_BLOCKS.md``, registered 2026-11-12).

    python -m app levels ob

OB-15 and OB-1H on gold 2012-2021 with the level-family machinery (``discover``): their trades
against 200 shifted copies; 2 primary tests (break, rejection; both families pooled) and 4
secondary (family x behaviour)."""

from __future__ import annotations

import multiprocessing as mp

import numpy as np
import pandas as pd
from scipy.stats import norm

from app.discovery import markout as mk
from app.levels import discover as dc
from app.levels import events as ev
from app.levels import families as fm
from app.levels import trades as tr
from app.research import gold_lab as gl

REPORT = dc.ROOT / "docs" / "levels" / "ob_result.md"
PRIMARY = dict(mean=0.03, t=3.0, alpha=0.05)
SECONDARY = dict(mean=0.05, t=3.0, fdr=0.10, trades=300)


def setup() -> tuple:
    fr = gl.load()
    cx = gl.context(fr)
    fams = [fm.order_blocks(cx, fr["15m"], "15"), fm.order_blocks(cx, fr["1h"], "1H")]
    dl = tr.deadline(cx)
    t = pd.to_datetime(cx.m["close_utc"].to_numpy(), utc=True)
    in_period = np.asarray((t >= dc.FROM) & (t < dc.TO))
    return cx, fams, dl, in_period


def _init() -> None:
    dc._W["cx"], dc._W["fams"], dc._W["dl"], dc._W["in"] = setup()


def power(cx, fams, dl, in_period) -> list[str]:
    days = dc.period_days(cx, in_period)
    lines = ["| Behaviour | Orders (before the book rule) | A day | Mean m | Smallest R at t = 3 |",
             "| --- | --- | --- | --- | --- |"]  # fmt: skip
    ent = []
    for f in fams:
        s = ev.signals(cx, f, days)
        s = s[in_period[s["i"].to_numpy()]]
        ent.append(tr.entries(cx, s, dl))
    e = pd.concat(ent, ignore_index=True)
    n_days = len(np.unique(cx.ny_day[in_period & (cx.weekday < 5)]))
    for beh, g in e.groupby("behaviour"):
        mde = 3 * np.sqrt(g["m"].mean() / len(g))
        lines.append(f"| {beh} | {len(g):,} | {len(g) / n_days:.2f} | {g['m'].mean():.2f} "
                     f"| {mde:.3f} |")  # fmt: skip
    return lines


def evaluate(real: pd.DataFrame, plc: pd.DataFrame, n_blocks: int):
    idx = mk.resamples(n_blocks)
    prim, sec = [], []
    for beh in ("break", "rejection"):
        r, p = real[real["behaviour"] == beh], plc[plc["behaviour"] == beh]
        mr, mp_, t = dc.boot_t(idx, r, p)
        prim.append({"behaviour": beh, "trades": len(r), "mean": mr, "mean2": r["net2"].mean(),
                     "mean_std": r["net_std"].mean(), "placebo": mp_, "t": t,
                     "win": (r["gross"] > 0).mean()})  # fmt: skip
    for (fam, beh), r in real.groupby(["family", "behaviour"]):
        p = plc[(plc["family"] == fam) & (plc["behaviour"] == beh)]
        mr, mp_, t = dc.boot_t(idx, r, p)
        sec.append({"family": fam, "behaviour": beh, "trades": len(r), "mean": mr,
                    "mean2": r["net2"].mean(), "mean_std": r["net_std"].mean(), "placebo": mp_,
                    "t": t, "stable": dc.stable(r)})  # fmt: skip
    prim, sec = pd.DataFrame(prim), pd.DataFrame(sec)
    pp = np.where(np.isfinite(prim["t"]), norm.sf(prim["t"]), 1.0)
    prim["holm"] = mk.holm(pp, PRIMARY["alpha"])
    prim["passed"] = ((prim["mean"] >= PRIMARY["mean"]) & (prim["mean2"] > 0)
                      & (prim["t"] >= PRIMARY["t"]) & prim["holm"])  # fmt: skip
    ps = np.where(np.isfinite(sec["t"]), norm.sf(sec["t"]), 1.0)
    sec["bh"] = mk.benjamini_hochberg(ps, SECONDARY["fdr"])
    sec["passed"] = ((sec["mean"] >= SECONDARY["mean"]) & (sec["trades"] >= SECONDARY["trades"])
                     & (sec["t"] >= SECONDARY["t"]) & sec["bh"] & sec["stable"])  # fmt: skip
    return prim, sec


def main() -> int:
    cx, fams, dl, in_period = setup()
    pw = power(cx, fams, dl, in_period)
    real = dc.run_families(cx, fams, dl, in_period)
    real["blk"] = dc.blocks(cx, real["k"].to_numpy())
    real["net2"] = real["net"] - (real["gross"] - real["net"])
    sp = dc.spacings(cx, fams, in_period)
    rng = np.random.default_rng(dc.SEED)
    jobs = [(q, {f.name: float(rng.uniform(0.0, 1.0)) for f in fams}, sp) for q in range(dc.COPIES)]
    with mp.Pool(dc.WORKERS, initializer=_init) as pool:
        parts = pool.map(dc._copy, jobs, chunksize=1)
    plc = pd.concat([p for p in parts if len(p)], ignore_index=True)
    n_blocks = int(dc.blocks(cx, np.array([np.flatnonzero(in_period)[-1]]))[0]) + 1
    prim, sec = evaluate(real, plc, n_blocks)
    days = len(np.unique(cx.ny_day[in_period & (cx.weekday < 5)]))
    lines = [
        "# Order blocks as a level family (gold 2012-2021)",
        "",
        "_`python -m app levels ob`, registered in `ORDER_BLOCKS.md` (2026-11-12) before the run. "
        "Net R a trade, Raw costs unless stated; 200 shifted copies; 4-week block bootstrap._",
        "",
        f"Blocks: OB-15 {len(fams[0].recs) // 2:,}, OB-1H {len(fams[1].recs) // 2:,} (2011-2026).",
        "",
        "Power (orders before the one-trade-per-book rule, no outcome):",
        "",
        *pw,
        "",
        f"**Primary tests passed: {int(prim['passed'].sum())} of 2.**",
        "",
        "| Behaviour | Trades | A day | Mean net R | At 2x | Standard | Shifted copies | t | Win "
        "| Holm | Passed |",
        "|" + " --- |" * 11,
    ]
    for x in prim.itertuples():
        lines.append(f"| {x.behaviour} | {x.trades:,} | {x.trades / days:.2f} | {x.mean:+.3f} "
                     f"| {x.mean2:+.3f} | {x.mean_std:+.3f} | {x.placebo:+.3f} | {x.t:+.2f} "
                     f"| {x.win:.0%} | {'yes' if x.holm else ''} "
                     f"| {'yes' if x.passed else ''} |")  # fmt: skip
    lines += ["", "| Family | Behaviour | Trades | Mean net R | At 2x | Standard | Shifted | t "
              "| Stable | BH | Passed |", "|" + " --- |" * 11]  # fmt: skip
    for x in sec.itertuples():
        lines.append(f"| {x.family} | {x.behaviour} | {x.trades:,} | {x.mean:+.3f} "
                     f"| {x.mean2:+.3f} | {x.mean_std:+.3f} | {x.placebo:+.3f} | {x.t:+.2f} "
                     f"| {'yes' if x.stable else ''} | {'yes' if x.bh else ''} "
                     f"| {'yes' if x.passed else ''} |")  # fmt: skip
    years = sorted(real["year"].unique())
    lines += ["", "By year (mean net R):", "",
              "| Behaviour | " + " | ".join(str(y) for y in years) + " |",
              "|" + " --- |" * (1 + len(years))]  # fmt: skip
    for beh, g in real.groupby("behaviour"):
        v = g.groupby("year")["net"].mean()
        lines.append(f"| {beh} | " + " | ".join(f"{v.get(y, np.nan):+.3f}" for y in years) + " |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}: {int(prim['passed'].sum())} primary passed")
    return 0
