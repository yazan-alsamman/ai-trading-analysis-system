"""The markout map and its confirmation (``docs/discovery/PREREG_2.md`` §6-7, stages D4-D5).

    python -m app discovery map        # discovery, 2018-2021 (F1: 2020-2021): gates 1-4, PBO, DSR
    python -m app discovery confirm    # the survivors only, 2022 to 2026-01-09, read once

Writes ``docs/discovery/map.md`` / ``confirm.md`` and ``data/processed/discovery/map_*.parquet``."""

from __future__ import annotations

import argparse
import itertools
import warnings
from math import e as EULER_E
from pathlib import Path

import numpy as np
import pandas as pd

from app.discovery import events as ev
from app.discovery import markout as mk
from app.research import gold_ah as ah

ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / "data" / "processed" / "calendar.parquet"
DRIVERS = ROOT / "data" / "processed" / "drivers"
OUT = ROOT / "data" / "processed" / "discovery"
DOCS = ROOT / "docs" / "discovery"
PERIODS = {"discovery": ("2018-01-01", "2022-01-01"), "confirm": ("2022-01-01", "2026-01-10")}
F1_DISCOVERY_START = "2020-01-01"
MARGIN_BEFORE, MARGIN_AFTER = pd.Timedelta(days=30), pd.Timedelta(days=3)
SIZE, T_GATE, FDR = 2.0, 3.0, 0.10
CONF_SIZE, CONF_ALPHA = 1.5, 0.05
PBO_BLOCKS = 16
DSR_N = (210, 1000)
EULER_GAMMA = 0.5772156649


# --- events ---------------------------------------------------------------------------------------


def window(m1: pd.DataFrame, period: str) -> pd.DataFrame:
    a, b = (pd.Timestamp(x, tz="UTC") for x in PERIODS[period])
    ts = m1["ts_utc"]
    return m1[(ts >= a - MARGIN_BEFORE) & (ts < b + MARGIN_AFTER)].reset_index(drop=True)


def events_and_placebos(m1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cal = pd.read_parquet(CAL)
    dxy = pd.read_parquet(DRIVERS / "DOLLARIDXUSD.parquet")
    bond = pd.read_parquet(DRIVERS / "USTBONDTRUSD.parquet")
    e = pd.concat([ev.f3(m1, cal), ev.f2(m1), ev.f1(m1, dxy, bond), ev.f5(m1)], ignore_index=True)
    grid = mk.f5_placebo(m1, np.random.default_rng(mk.SEED_PLACEBO))
    p = pd.concat([mk.f3_placebo(m1, cal), mk.f2_placebo(m1), mk.f1_placebo(m1, dxy, bond), grid],
                  ignore_index=True)  # fmt: skip
    return e, p


def in_period(m1: pd.DataFrame, x: pd.DataFrame, period: str) -> pd.DataFrame:
    a, b = (pd.Timestamp(v, tz="UTC") for v in PERIODS[period])
    t = m1["ts_utc"].to_numpy()[x["i"].to_numpy()]
    t = pd.to_datetime(t, utc=True)
    keep = (t >= a) & (t < b)
    if period == "discovery":
        f1_start = pd.Timestamp(F1_DISCOVERY_START, tz="UTC")
        keep &= ~((x["family"] == "F1").to_numpy() & (t < f1_start))
    return x[keep].reset_index(drop=True)


# --- one period -----------------------------------------------------------------------------------


def measure(m1: pd.DataFrame, e: pd.DataFrame, p: pd.DataFrame, period: str,
            cells: list[tuple[str, str, int]] | None = None) -> pd.DataFrame:  # fmt: skip
    """Every (family, cell, h) row of the period (or only ``cells``)."""
    bx = mk.bars(m1)
    start = int(ev.minutes(pd.Series([pd.Timestamp(PERIODS[period][0], tz="UTC")]))[0])
    end = int(ev.minutes(pd.Series([pd.Timestamp(PERIODS[period][1], tz="UTC")]))[0])
    nb = int((end - start) // mk.BLOCK_MIN) + 1
    idx = mk.resamples(nb)
    rng = np.random.default_rng(mk.SEED_E0)
    q_edges = np.linspace(start, end, PBO_BLOCKS + 1)
    rows = []
    for (fam, cell), g in e.groupby(["family", "cell"], sort=True):
        hs = [h for f, c, h in cells if f == fam and c == cell] if cells is not None else mk.H
        if not hs:
            continue
        i, s = g["i"].to_numpy(), g["sign"].to_numpy().astype(float)
        pl = p[(p["family"] == fam) & (p["cell"] == cell)]
        pi, ps = pl["i"].to_numpy(), pl["sign"].to_numpy().astype(float)
        draws = mk.e0_draws(bx, i, rng)
        blk, pblk = mk.block_ids(bx.mins[i], start), mk.block_ids(bx.mins[pi], start)
        years = bx.year[i]
        quarter = np.clip(np.searchsorted(q_edges, bx.mins[i], "right") - 1, 0, PBO_BLOCKS - 1)
        for h in hs:
            z = mk.z_markout(bx, i, s, h)
            e0 = mk.e0_z(bx, draws, s, h)
            d = z - e0
            zp = mk.z_markout(bx, pi, ps, h)
            d0, t0 = mk.boot_t(idx, blk, d)
            dp, tp = mk.boot_t(idx, blk, z, pblk, zp)
            ok = np.isfinite(d)
            perf = [np.nanmean(d[ok & (quarter == q)]) if (ok & (quarter == q)).any() else np.nan
                    for q in range(PBO_BLOCKS)]  # fmt: skip
            dd = d[ok]
            rows.append({
                "family": fam, "cell": cell, "h": h, "n": int(np.isfinite(z).sum()),
                "mean_z": np.nanmean(z), "mean_e0": np.nanmean(e0), "ex_e0": d0, "t_e0": t0,
                "n_pl": int(np.isfinite(zp).sum()), "mean_pl": np.nanmean(zp), "ex_pl": dp,
                "t_pl": tp, "mean_atr": np.nanmean(mk.atr_markout(bx, i, s, h)),
                "stable": mk.stable(years, d, two_years=(fam == "F1" and period == "discovery")),
                "sr": dd.mean() / dd.std(ddof=1) if len(dd) > 2 and dd.std() > 0 else np.nan,
                "skew": pd.Series(dd).skew(), "kurt": pd.Series(dd).kurt() + 3,
                **{f"q{q}": v for q, v in enumerate(perf)},
            })  # fmt: skip
    return pd.DataFrame(rows)


def discovery_gates(r: pd.DataFrame) -> pd.DataFrame:
    r = r.copy()
    sg = np.sign(r["mean_z"])
    r["size_ok"] = r["mean_z"].abs() >= SIZE
    r["beyond_ok"] = (sg * r["t_e0"] >= T_GATE) & (sg * r["t_pl"] >= T_GATE)
    r["p"] = np.maximum(mk.p_two_sided(r["t_e0"].to_numpy()), mk.p_two_sided(r["t_pl"].to_numpy()))
    r["bh"] = mk.benjamini_hochberg(r["p"].to_numpy(), FDR)
    r["passed"] = r["size_ok"] & r["beyond_ok"] & r["bh"] & r["stable"]
    return r


# --- PBO and DSR ----------------------------------------------------------------------------------


def pbo(perf: np.ndarray) -> float:
    """CSCV: the share of half / half splits of the time blocks where the in-sample best cell
    (by |mean|, its sign kept) ranks at or below the out-of-sample median."""
    t, n = perf.shape
    lam = []
    for is_rows in itertools.combinations(range(t), t // 2):
        oos_rows = [k for k in range(t) if k not in is_rows]
        with np.errstate(invalid="ignore"):
            mis = np.nanmean(perf[list(is_rows)], axis=0)
            moos = np.nanmean(perf[oos_rows], axis=0)
        v = np.sign(mis) * moos
        ok = np.isfinite(mis) & np.isfinite(v)
        if ok.sum() < 2:
            continue
        best = np.flatnonzero(ok)[np.argmax(np.abs(mis[ok]))]
        w = ((v[ok] <= v[best]).sum()) / (ok.sum() + 1)
        lam.append(np.log(w / (1 - w)))
    return float(np.mean(np.asarray(lam) <= 0)) if lam else np.nan


def dsr(r: pd.DataFrame, n_trials: int) -> tuple[str, float]:
    """The Deflated Sharpe probability of the map's best |SR| cell (per event), N trials."""
    from scipy.stats import norm

    sr = r["sr"].to_numpy()
    ok = np.isfinite(sr)
    if ok.sum() < 2:
        return "", np.nan
    k = np.flatnonzero(ok)[np.argmax(np.abs(sr[ok]))]
    row = r.iloc[k]
    s = abs(sr[k])
    var = np.var(sr[ok], ddof=1)
    sr0 = np.sqrt(var) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials)
                          + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * EULER_E)))  # fmt: skip
    g3 = row["skew"] * np.sign(sr[k])
    den = np.sqrt(max(1 - g3 * s + (row["kurt"] - 1) / 4 * s**2, 1e-12))
    p = norm.cdf((s - sr0) * np.sqrt(row["n"] - 1) / den)
    return f"{row['family']} {row['cell']} h{row['h']}", float(p)


# --- reports --------------------------------------------------------------------------------------


def map_report(r: pd.DataFrame, n_events: int, n_placebo: int) -> str:
    perf = r[[f"q{q}" for q in range(PBO_BLOCKS)]].to_numpy().T
    pb = pbo(perf)
    lines = [
        "# Discovery round 2: the markout map (D4, 2018-2021)",
        "",
        "_`python -m app discovery map`, registered in `PREREG_2.md` (approved 2026-11-11, tag "
        "`discovery-prereg-2`). XAUUSD M1, 2018-2021 (F1: 2020-2021). z = markout / cost unit; "
        "t from a 4-week block bootstrap (B = 20,000)._",
        "",
        f"{n_events:,} events, {n_placebo:,} placebo events, {len(r)} map cells.",
        "",
        "## Gates",
        "",
        f"- 1 size (|mean z| >= {SIZE:g}): {int(r['size_ok'].sum())} cells",
        f"- 2 beyond chance (t >= {T_GATE:g} against E0 and the placebo): "
        f"{int(r['beyond_ok'].sum())}",
        f"- 3 Benjamini-Hochberg at {FDR:.0%}: {int(r['bh'].sum())}",
        f"- 4 stability: {int(r['stable'].sum())}",
        f"- **All four: {int(r['passed'].sum())}**",
        "",
    ]
    if r["passed"].any():
        lines += ["**Survivors (to confirmation):**", "",
                  "| Family | Cell | h | n | mean z | excess vs E0 (t) | vs placebo (t) |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
        for x in r[r["passed"]].itertuples():
            lines.append(f"| {x.family} | {x.cell} | {x.h} | {x.n:,} | {x.mean_z:+.2f} "
                         f"| {x.ex_e0:+.2f} ({x.t_e0:+.1f}) "
                         f"| {x.ex_pl:+.2f} ({x.t_pl:+.1f}) |")  # fmt: skip
    else:
        lines += ["**No cell passes discovery. By `PREREG_2.md` §6.6 the round ends with this "
                  "negative report.**"]
    names = [f"N = {n}" for n in DSR_N]
    ds = [dsr(r, n) for n in DSR_N]
    lines += ["", f"PBO (CSCV, {PBO_BLOCKS} blocks): {pb:.2f}. Deflated Sharpe of the best cell "
              f"({ds[0][0]}): " + ", ".join(f"{a} {b[1]:.3f}" for a, b in zip(names, ds,
                                                                                  strict=True))
              + " (N = 1,000 bounds every earlier setting plus this map).", ""]  # fmt: skip
    lines += ["## The map: mean z (t against E0)", "",
              "| Family | Cell | n (h = 5) | " + " | ".join(f"h = {h}" for h in mk.H) + " |",
              "| --- | --- | --- |" + " --- |" * len(mk.H)]  # fmt: skip
    for (fam, cell), g in r.groupby(["family", "cell"], sort=True):
        g = g.set_index("h")
        cellv = []
        for h in mk.H:
            if h not in g.index:
                cellv.append("-")
                continue
            x = g.loc[h]
            txt = f"{x['mean_z']:+.2f} ({x['t_e0']:+.1f})"
            cellv.append(f"**{txt}**" if x["size_ok"] else txt)
        n5 = int(g.loc[5, "n"]) if 5 in g.index else 0
        lines.append(f"| {fam} | {cell} | {n5:,} | " + " | ".join(cellv) + " |")
    top = r.reindex(r["mean_z"].abs().sort_values(ascending=False).index).head(15)
    lines += ["", "Bold: |mean z| >= 2. The 15 largest |mean z| with every gate:", "",
              "| Family | Cell | h | n | mean z | E0 | excess (t) | placebo | excess (t) | ATR "
              "| stable | BH | passed |",
              "|" + " --- |" * 13]  # fmt: skip
    for x in top.itertuples():
        lines.append(
            f"| {x.family} | {x.cell} | {x.h} | {x.n:,} | {x.mean_z:+.2f} | {x.mean_e0:+.2f} "
            f"| {x.ex_e0:+.2f} ({x.t_e0:+.1f}) | {x.mean_pl:+.2f} | {x.ex_pl:+.2f} ({x.t_pl:+.1f}) "
            f"| {x.mean_atr:+.3f} | {'yes' if x.stable else ''} | {'yes' if x.bh else ''} "
            f"| {'yes' if x.passed else ''} |"
        )
    return "\n".join(lines) + "\n"


def confirm_report(r: pd.DataFrame, disc: pd.DataFrame) -> str:
    lines = ["# Discovery round 2: confirmation (D5, 2022 to 2026-01-09, read once)", ""]
    if r.empty:
        return "\n".join(lines + ["No cell passed discovery; nothing to confirm."]) + "\n"
    m = r.merge(disc[["family", "cell", "h", "mean_z"]].rename(columns={"mean_z": "disc_z"}),
                on=["family", "cell", "h"])  # fmt: skip
    m["p"] = mk.p_two_sided(m["t_e0"].to_numpy())
    m["holm"] = mk.holm(m["p"].to_numpy(), CONF_ALPHA)
    m["confirmed"] = ((np.sign(m["mean_z"]) == np.sign(m["disc_z"]))
                      & (m["mean_z"].abs() >= CONF_SIZE) & m["holm"])  # fmt: skip
    lines += ["| Family | Cell | h | n | discovery z | mean z | excess vs E0 (t) | Holm "
              "| confirmed |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for x in m.itertuples():
        lines.append(f"| {x.family} | {x.cell} | {x.h} | {x.n:,} | {x.disc_z:+.2f} "
                     f"| {x.mean_z:+.2f} | {x.ex_e0:+.2f} ({x.t_e0:+.1f}) "
                     f"| {'yes' if x.holm else ''} | {'yes' if x.confirmed else ''} |")  # fmt: skip
    return "\n".join(lines) + "\n"


# --- commands -------------------------------------------------------------------------------------


def run_map() -> pd.DataFrame:
    m1 = window(ah.load_store(), "discovery")
    e, p = events_and_placebos(m1)
    e, p = in_period(m1, e, "discovery"), in_period(m1, p, "discovery")
    r = discovery_gates(measure(m1, e, p, "discovery"))
    OUT.mkdir(parents=True, exist_ok=True)
    r.to_parquet(OUT / "map_discovery.parquet", index=False)
    (DOCS / "map.md").write_text(map_report(r, len(e), len(p)), encoding="utf-8", newline="\n")
    return r


def run_confirm() -> pd.DataFrame:
    disc = pd.read_parquet(OUT / "map_discovery.parquet")
    surv = disc[disc["passed"]]
    cells = list(zip(surv["family"], surv["cell"], surv["h"], strict=True))
    r = pd.DataFrame()
    if cells:
        m1 = window(ah.load_store(), "confirm")
        e, p = events_and_placebos(m1)
        e, p = in_period(m1, e, "confirm"), in_period(m1, p, "confirm")
        r = measure(m1, e, p, "confirm", cells)
        r.to_parquet(OUT / "map_confirm.parquet", index=False)
    (DOCS / "confirm.md").write_text(confirm_report(r, disc), encoding="utf-8", newline="\n")
    return r


def main(argv: list[str] | None = None, step: str = "map") -> int:
    warnings.simplefilter("ignore", RuntimeWarning)  # empty means of short cells and blocks
    ap = argparse.ArgumentParser(prog=f"python -m app discovery {step}")
    ap.parse_args(argv)
    r = run_map() if step == "map" else run_confirm()
    extra = f", {int(r['passed'].sum())} passed" if step == "map" else ""
    print(f"{step}: {len(r)} rows{extra}")
    return 0
