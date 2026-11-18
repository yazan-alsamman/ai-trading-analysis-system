"""Tool check: plant an edge of known size in real gold prices and see whether the frozen tools
find it (``docs/discovery/INJECT.md``, registered 2026-11-11 before the run).

    python -m app discovery inject [--part a|b|all]

- **A, the markout map:** for each event of one cell, the price moves by sign x delta x c(t0) over
  the next 15 M1 bars and stays moved; the map (all 210 cells, frozen code) runs on the planted
  prices with the original events and placebos.
- **B, the trade simulator:** one random entry a trading day, random side, SL 1 x ATR(1h), 60-minute
  exit; after each entry the price moves by side x delta x risk over 3 5m bars and stays moved;
  ``gold_lab.simulate`` (M0) on the planted prices."""

from __future__ import annotations

import argparse
import dataclasses
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from app.discovery import map as mp
from app.discovery import markout as mk
from app.research import gold_ah as ah
from app.research import gold_lab as gl

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "discovery" / "inject_result.md"
A_CELLS = (("F2", "PM-30"), ("F3", "HIGH+5"), ("F5p", "BREAK-25"), ("F3", "TOP3+5"))
A_DELTAS = (1.0, 2.0, 3.0, 5.0)
A_RAMP, B_RAMP = 15, 3
B_DELTAS = (0.0, 0.03, 0.05, 0.10, 0.20)
B_SEED, B_HOLD = 20261115, 12
B_FROM, B_TO = 2 * 60, 16 * 60
B_END_YEAR = 2021


def planted(n: int, i: np.ndarray, amount: np.ndarray, ramp: int) -> np.ndarray:
    """The price change added to each bar: for each event, linear over the ``ramp`` bars after
    bar i, then constant to the end."""
    add = np.zeros(n)
    step = np.zeros(n + ramp + 2)
    frac = np.arange(1, ramp + 1) / ramp
    for k, a in zip(i, amount, strict=True):
        hi = min(k + ramp, n - 1)
        if k + 1 <= hi:
            add[k + 1 : hi + 1] += a * frac[: hi - k]
        step[k + ramp + 1] += a
    return add + np.cumsum(step)[:n]


def plant_m1(m1: pd.DataFrame, i: np.ndarray, amount: np.ndarray,
             ramp: int = A_RAMP) -> pd.DataFrame:  # fmt: skip
    add = planted(len(m1), i, amount, ramp)
    out = m1.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = out[col].to_numpy() + add
    return out


# --- part A ---------------------------------------------------------------------------------------


def part_a() -> list[str]:
    m1 = mp.window(ah.load_store(), "discovery")
    e, p = mp.events_and_placebos(m1)
    e, p = mp.in_period(m1, e, "discovery"), mp.in_period(m1, p, "discovery")
    base = mp.discovery_gates(mp.measure(m1, e, p, "discovery")).set_index(["family", "cell", "h"])
    bx = mk.bars(m1)
    lines = ["## Part A: the markout map", "",
             "Per planted cell and delta (cost units): mean z planted (lift over the unplanted "
             "map), t against E0 / the placebo, and the gates passed (S size, T t-gates, B BH, "
             "Y stability; PASS = all four). False alarms = other cells passing all four.",
             ""]  # fmt: skip
    for fam, cell in A_CELLS:
        g = e[(e["family"] == fam) & (e["cell"] == cell)]
        lines += [f"### {fam} {cell} ({len(g):,} events)", "",
                  "| delta | " + " | ".join(f"h = {h}" for h in mk.H) + " | false alarms |",
                  "| --- |" + " --- |" * (len(mk.H) + 1)]  # fmt: skip
        for d in A_DELTAS:
            amt = g["sign"].to_numpy() * d * bx.cost[g["i"].to_numpy()]
            m2 = plant_m1(m1, g["i"].to_numpy(), amt)
            r = mp.discovery_gates(mp.measure(m2, e, p, "discovery"))
            r = r.set_index(["family", "cell", "h"])
            cells = []
            for h in mk.H:
                x, b0 = r.loc[(fam, cell, h)], base.loc[(fam, cell, h)]
                gates = "".join(k for k, f in (("S", "size_ok"), ("T", "beyond_ok"), ("B", "bh"),
                                               ("Y", "stable")) if x[f])  # fmt: skip
                tag = "**PASS**" if x["passed"] else (gates or "-")
                cells.append(f"{x['mean_z']:+.2f} ({x['mean_z'] - b0['mean_z']:+.2f}); "
                             f"t {x['t_e0']:+.1f}/{x['t_pl']:+.1f}; {tag}")  # fmt: skip
            others = r.drop(index=[(fam, cell, h) for h in mk.H])
            lines.append(f"| {d:g} | " + " | ".join(cells) + f" | {int(others['passed'].sum())} |")
        lines.append("")
    return lines


# --- part B ---------------------------------------------------------------------------------------


def random_signals(cx: gl.Ctx) -> pd.DataFrame:
    rng = np.random.default_rng(B_SEED)
    year = pd.to_datetime(cx.m["close_utc"]).dt.year.to_numpy()
    ok = (cx.weekday < 5) & (cx.ny_min >= B_FROM) & (cx.ny_min < B_TO) & np.isfinite(cx.atr1h)
    ok &= (cx.atr1h > 0) & (year >= gl.START.year) & (year <= B_END_YEAR)
    ok &= cx.deadline > np.arange(len(cx.c)) + 1
    idx = np.flatnonzero(ok)
    rows = []
    for _, grp in pd.Series(idx).groupby(cx.ny_day[idx]):
        rows.append(int(grp.iloc[rng.integers(len(grp))]))
    i = np.array(rows)
    d = np.where(rng.random(len(i)) < 0.5, 1.0, -1.0)
    return pd.DataFrame({"strategy": "RAND", "i": i, "dir": d, "entry": cx.c[i],
                         "risk": cx.atr1h[i], "tp_r": np.nan,
                         "end": np.minimum(i + B_HOLD, cx.deadline[i])})  # fmt: skip


def part_b() -> list[str]:
    cx = gl.context(gl.load())
    sig = random_signals(cx)
    lines = ["## Part B: the trade simulator", "",
             f"{len(sig):,} random entries, 2012-2021; M0, SL 1 x ATR(1h), 60-minute exit.", "",
             "| delta (R) | mean gross R (SE) | lift over 0 | lift - delta in SEs | t of gross "
             "| cost check |",
             "| --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    base = None
    for d in B_DELTAS:
        amount = sig["dir"].to_numpy() * d * sig["risk"].to_numpy()
        add = planted(len(cx.c), sig["i"].to_numpy(), amount, B_RAMP)
        cx2 = dataclasses.replace(cx, o=cx.o + add, h=cx.h + add, lo=cx.lo + add, c=cx.c + add)
        t = gl.simulate(sig.assign(entry=cx2.c[sig["i"].to_numpy()]), cx2, "M0")
        g = t["gross"].to_numpy()
        se = g.std(ddof=1) / np.sqrt(len(g))
        want = (cx.spread[t["i"].to_numpy()] + gl.COMMISSION) / t["risk"].to_numpy()
        cost_ok = np.allclose(t["cost"].to_numpy(), want, atol=1e-9, rtol=0)
        if base is None:
            base = g.mean()
        lift = g.mean() - base
        lines.append(f"| {d:g} | {g.mean():+.4f} ({se:.4f}) | {lift:+.4f} "
                     f"| {(lift - d) / se:+.1f} | {g.mean() / se:+.1f} "
                     f"| {'exact' if cost_ok else 'MISMATCH'} |")  # fmt: skip
    return lines


def main(argv: list[str] | None = None) -> int:
    warnings.simplefilter("ignore", RuntimeWarning)
    ap = argparse.ArgumentParser(prog="python -m app discovery inject")
    ap.add_argument("--part", choices=("a", "b", "all"), default="all")
    args = ap.parse_args(argv)
    lines = ["# Tool check: planted edges (`INJECT.md`)", "",
             "_`python -m app discovery inject`, registered 2026-11-11 before the run. Planted "
             "data: nothing here measures a real edge._", ""]  # fmt: skip
    if args.part in ("a", "all"):
        lines += part_a()
    if args.part in ("b", "all"):
        lines += part_b()
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
