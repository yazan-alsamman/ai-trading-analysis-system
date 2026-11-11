"""L1, discovery (``docs/levels/SPEC.md`` §6): the 24 families on gold 2012-2021 against 200
shifted copies of each.

    python -m app levels discover

- **Shifted copies** (seed 20261116): a grid moves by u x its step (u uniform in [0, 1); the
  percent grids in log price); a real family moves every level by u x its median spacing (u
  uniform in [-0.5, 0.5); the spacing is the median distance from a signal's level to its
  target), keeping each level's life.
- **Primary tests (8):** each kind of family x behaviour, the families' trades pooled. Gates: mean
  net R (Raw) >= +0.03, > 0 at 2x cost, the excess over the shifted copies with a 4-week block
  bootstrap t >= 3, Holm over the 8 at 5% (one-sided).
- **Secondary (48):** each family x behaviour: mean >= +0.05, >= 300 trades, t >= 3, Benjamini-
  Hochberg 10% over the 48, no year above half of the total R. Reported; the primary decides."""

from __future__ import annotations

import dataclasses
import multiprocessing as mp
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from app.discovery import markout as mk
from app.levels import events as ev
from app.levels import families as fm
from app.levels import trades as tr
from app.research import gold_lab as gl

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "levels" / "discovery.md"
OUT = ROOT / "data" / "processed" / "levels"
FROM, TO = pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC")
COPIES, SEED = 200, 20261116
PRIMARY = dict(mean=0.03, t=3.0, alpha=0.05)
SECONDARY = dict(mean=0.05, t=3.0, fdr=0.10, trades=300)
KINDS = ("real", "round", "percent", "anchored")

_W: dict = {}


# --- one run of every family ----------------------------------------------------------------------


def shift(fam, u: float, spacing: float):
    if isinstance(fam, fm.Lattice):
        return dataclasses.replace(fam, origin=fam.origin + u * fam.step)
    recs = fam.recs.assign(level=fam.recs["level"] + (u - 0.5) * spacing)
    return dataclasses.replace(fam, recs=recs)


def run_families(cx: gl.Ctx, fams: list, dl: np.ndarray, in_period: np.ndarray) -> pd.DataFrame:
    parts = []
    for fam in fams:
        s = ev.signals(cx, fam)
        s = s[in_period[s["i"].to_numpy()]]
        e = tr.entries(cx, s, dl)
        if len(e):
            parts.append(tr.simulate(cx, e))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def blocks(cx: gl.Ctx, k: np.ndarray) -> np.ndarray:
    m = cx.m["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[m]")
    start = np.datetime64(FROM.tz_convert(None), "m")
    return ((m[k] - start).astype("int64") // mk.BLOCK_MIN).astype(int)


def setup() -> tuple:
    fr = gl.load()
    cx = gl.context(fr)
    fams = fm.all_families(cx, fr)
    dl = tr.deadline(cx)
    t = pd.to_datetime(cx.m["close_utc"].to_numpy(), utc=True)
    in_period = np.asarray((t >= FROM) & (t < TO))
    return cx, fams, dl, in_period


def spacings(cx: gl.Ctx, fams: list, in_period: np.ndarray) -> dict[str, float]:
    out = {}
    for fam in fams:
        if isinstance(fam, fm.Lattice):
            continue
        s = ev.signals(cx, fam)
        s = s[in_period[s["i"].to_numpy()]]
        out[fam.name] = float(np.median(np.abs(s["target"] - s["level"]))) if len(s) else 0.0
    return out


def _init() -> None:
    _W["cx"], _W["fams"], _W["dl"], _W["in"] = setup()


def _copy(job: tuple[int, dict[str, float], dict[str, float]]) -> pd.DataFrame:
    """One shifted copy of every family: block sums of net R (1x and 2x cost) and counts."""
    q, us, sp = job
    cx = _W["cx"]
    fams = [shift(f, us[f.name], sp.get(f.name, 0.0)) for f in _W["fams"]]
    t = run_families(cx, fams, _W["dl"], _W["in"])
    if t.empty:
        return pd.DataFrame()
    t["blk"] = blocks(cx, t["k"].to_numpy())
    t["net2"] = t["net"] - (t["gross"] - t["net"])  # cost (and slip) twice
    g = t.groupby(["family", "kind", "behaviour", "blk"]).agg(
        s=("net", "sum"), s2=("net2", "sum"), n=("net", "size")
    )
    return g.reset_index().assign(copy=q)


# --- statistics -----------------------------------------------------------------------------------


def boot_t(idx, real: pd.DataFrame, plc: pd.DataFrame) -> tuple[float, float, float]:
    """(real mean, placebo mean, t of the difference) under a joint block bootstrap."""
    nb = idx.shape[1]
    ra = np.bincount(real["blk"], real["net"], minlength=nb)[:nb]
    rn = np.bincount(real["blk"], minlength=nb)[:nb].astype(float)
    pa = np.bincount(plc["blk"], plc["s"], minlength=nb)[:nb]
    pn = np.bincount(plc["blk"], plc["n"], minlength=nb)[:nb].astype(float)
    if rn.sum() < 2 or pn.sum() < 2:
        return np.nan, np.nan, np.nan
    obs_r, obs_p = ra.sum() / rn.sum(), pa.sum() / pn.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        star = ra[idx].sum(1) / rn[idx].sum(1) - pa[idx].sum(1) / pn[idx].sum(1)
    se = np.nanstd(star, ddof=1)
    return obs_r, obs_p, (obs_r - obs_p) / se if se > 0 else np.nan


def stable(t: pd.DataFrame) -> bool:
    s = t.groupby("year")["net"].sum()
    total = s.sum()
    return bool(total > 0 and (s / total).max() <= 0.5)


def evaluate(real: pd.DataFrame, plc: pd.DataFrame, n_blocks: int) -> tuple[pd.DataFrame, ...]:
    idx = mk.resamples(n_blocks)
    prim, sec = [], []
    for kind in KINDS:
        for beh in ("break", "rejection"):
            r = real[(real["kind"] == kind) & (real["behaviour"] == beh)]
            p = plc[(plc["kind"] == kind) & (plc["behaviour"] == beh)]
            mr, mp_, t = boot_t(idx, r, p)
            prim.append(
                {
                    "kind": kind,
                    "behaviour": beh,
                    "families": r["family"].nunique(),
                    "trades": len(r),
                    "mean": mr,
                    "mean2": r["net2"].mean() if len(r) else np.nan,
                    "mean_std": r["net_std"].mean() if len(r) else np.nan,
                    "placebo": mp_,
                    "t": t,
                    "win": (r["gross"] > 0).mean() if len(r) else np.nan,
                }
            )
    for (fam, kind, beh), r in real.groupby(["family", "kind", "behaviour"]):
        p = plc[(plc["family"] == fam) & (plc["behaviour"] == beh)]
        mr, mp_, t = boot_t(idx, r, p)
        sec.append(
            {
                "family": fam,
                "kind": kind,
                "behaviour": beh,
                "trades": len(r),
                "mean": mr,
                "mean2": r["net2"].mean(),
                "mean_std": r["net_std"].mean(),
                "placebo": mp_,
                "t": t,
                "stable": stable(r),
            }
        )
    prim, sec = pd.DataFrame(prim), pd.DataFrame(sec)
    pp = np.where(np.isfinite(prim["t"]), norm.sf(prim["t"]), 1.0)
    prim["holm"] = mk.holm(pp, PRIMARY["alpha"])
    prim["passed"] = (
        (prim["mean"] >= PRIMARY["mean"])
        & (prim["mean2"] > 0)
        & (prim["t"] >= PRIMARY["t"])
        & prim["holm"]
    )
    ps = np.where(np.isfinite(sec["t"]), norm.sf(sec["t"]), 1.0)
    sec["bh"] = mk.benjamini_hochberg(ps, SECONDARY["fdr"])
    sec["passed"] = (
        (sec["mean"] >= SECONDARY["mean"])
        & (sec["trades"] >= SECONDARY["trades"])
        & (sec["t"] >= SECONDARY["t"])
        & sec["bh"]
        & sec["stable"]
    )
    return prim, sec


# --- report ---------------------------------------------------------------------------------------


def report(prim: pd.DataFrame, sec: pd.DataFrame, real: pd.DataFrame, days: int) -> str:
    lines = [
        "# Level families: discovery (L1, gold 2012-2021)",
        "",
        "_`python -m app levels discover`, registered in `SPEC.md` (tag `levels-spec`). Net R a "
        "trade, Raw costs unless stated; placebo = 200 shifted copies of each family; t from a "
        "4-week block bootstrap (B = 20,000)._",
        "",
        f"**Primary tests passed: {int(prim['passed'].sum())} of 8.**"
        + (
            ""
            if prim["passed"].any()
            else " By `SPEC.md` §7 the study ends with a negative report."
        ),
        "",
        "| Kind | Behaviour | Families | Trades | A day | Mean net R | At 2x cost | Standard "
        "| Shifted copies | t | Win | Holm | Passed |",
        "|" + " --- |" * 13,
    ]
    for x in prim.itertuples():
        lines.append(
            f"| {x.kind} | {x.behaviour} | {x.families} | {x.trades:,} "
            f"| {x.trades / days:.2f} | {x.mean:+.3f} | {x.mean2:+.3f} | {x.mean_std:+.3f} "
            f"| {x.placebo:+.3f} | {x.t:+.2f} | {x.win:.0%} | {'yes' if x.holm else ''} "
            f"| {'yes' if x.passed else ''} |"
        )
    lines += [
        "",
        "## Per family (secondary)",
        "",
        "| Family | Behaviour | Trades | Mean net R | At 2x | Standard | Shifted | t | Stable "
        "| BH | Passed |",
        "|" + " --- |" * 11,
    ]
    for x in sec.sort_values(["kind", "family", "behaviour"]).itertuples():
        lines.append(
            f"| {x.family} | {x.behaviour} | {x.trades:,} | {x.mean:+.3f} "
            f"| {x.mean2:+.3f} | {x.mean_std:+.3f} | {x.placebo:+.3f} | {x.t:+.2f} "
            f"| {'yes' if x.stable else ''} | {'yes' if x.bh else ''} "
            f"| {'yes' if x.passed else ''} |"
        )
    years = sorted(real["year"].unique())
    lines += [
        "",
        "## By year (mean net R, the primary pools)",
        "",
        "| Kind | Behaviour | " + " | ".join(str(y) for y in years) + " |",
        "|" + " --- |" * (2 + len(years)),
    ]
    for (kind, beh), g in real.groupby(["kind", "behaviour"]):
        v = g.groupby("year")["net"].mean()
        lines.append(
            f"| {kind} | {beh} | " + " | ".join(f"{v.get(y, np.nan):+.3f}" for y in years) + " |"
        )
    exits = real["exit"].value_counts(normalize=True)
    lines += ["", "Exits, all trades: " + ", ".join(f"{k} {v:.0%}" for k, v in exits.items()) + "."]
    return "\n".join(lines) + "\n"


def main() -> int:
    cx, fams, dl, in_period = setup()
    real = run_families(cx, fams, dl, in_period)
    real["blk"] = blocks(cx, real["k"].to_numpy())
    real["net2"] = real["net"] - (real["gross"] - real["net"])
    sp = spacings(cx, fams, in_period)
    rng = np.random.default_rng(SEED)
    jobs = []
    for q in range(COPIES):
        us = {}
        for f in fams:
            us[f.name] = float(rng.uniform(0.0, 1.0))
        jobs.append((q, us, sp))
    with mp.Pool(max(1, (os.cpu_count() or 2) - 2), initializer=_init) as pool:
        parts = pool.map(_copy, jobs, chunksize=1)
    plc = pd.concat([p for p in parts if len(p)], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    real.to_parquet(OUT / "discovery_trades.parquet", index=False)
    plc.to_parquet(OUT / "discovery_placebo.parquet", index=False)
    n_blocks = int(blocks(cx, np.array([np.flatnonzero(in_period)[-1]]))[0]) + 1
    prim, sec = evaluate(real, plc, n_blocks)
    days = len(np.unique(cx.ny_day[in_period & (cx.weekday < 5)]))
    REPORT.write_text(report(prim, sec, real, days), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}: {int(prim['passed'].sum())} primary passed")
    return 0
