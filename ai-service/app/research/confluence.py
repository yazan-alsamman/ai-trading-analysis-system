"""Confluence on six markets never read for it (``docs/portfolio/CONFLUENCE.md``, registered
2026-11-12).

    python -m app research confluence [--nas <#USNDAQ100 M1 export>]

The frozen five on NAS100 (FxPro) and the five FX pairs (research store, to 2026-01-09); k = the
five's trades open in the same direction at the entry (``risk_split.open_same``). Per market d_m =
mean gross R (k >= 1) - mean gross R (k = 0); pooled D = the mean of d_m, a 4-week block
bootstrap on calendar time (the same blocks for every market)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import decide as dc
from app.research import five_nas as fn
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import risk_split as rs

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "portfolio" / "confluence_result.md"  # not CONFLUENCE.md (Windows case)
NAS_EXPORT = ROOT.parent / "data" / "raw" / "#USNDAQ100_M1_201501040000_202611092359.csv"
FX = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD")
START = pd.Timestamp("2016-02-01", tz="UTC")
FX_COMM = 0.00007  # x the pair's median price, a round trip (FxPro Raw, as LEAD_GRID.md)
BOOT, SEED = 10_000, 20261116
MIN_MARKETS = 4


def with_costs(commission: float, slip: float, fn_):
    old = gl.COMMISSION, gl.SL_SLIP
    gl.COMMISSION, gl.SL_SLIP = commission, slip
    try:
        return fn_()
    finally:
        gl.COMMISSION, gl.SL_SLIP = old


def market_trades(
    fr: dict[str, pd.DataFrame], start: pd.Timestamp, commission: float, slip: float
) -> pd.DataFrame:
    """The five's trades with k, gross and net R with slip, day and entry time."""

    def run():
        _, every, _, cx = gv.five_trades(fr, start=start)
        return every, cx

    every, cx = with_costs(commission, slip, run)
    every = every[every["strategy"].isin(rs.FIVE)].copy()
    every["ny_day"] = cx.ny_day[every["i"].to_numpy()]
    every["t"] = pd.to_datetime(cx.m["ts_utc"].to_numpy()[every["i"].to_numpy()], utc=True)
    every = every.reset_index(drop=True)
    o = rs.open_same(every, rs.FIVE)
    every["k"] = o["k"].reindex(every.index).to_numpy()
    return every


def diff(t: pd.DataFrame, col: str = "gross") -> float:
    return float(t.loc[t["k"] >= 1, col].mean() - t.loc[t["k"] == 0, col].mean())


def boot(markets: dict[str, pd.DataFrame]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Resampled pooled D and per-market d_m on the same calendar blocks."""
    blk = {m: dc.block_ids(t["t"]) for m, t in markets.items()}
    ids = np.unique(np.concatenate(list(blk.values())))
    pos = {b: n for n, b in enumerate(ids)}
    stats = {}
    for m, t in markets.items():
        b = np.array([pos[x] for x in blk[m]])
        one = (t["k"] >= 1).to_numpy()
        g = t["gross"].to_numpy()
        stats[m] = [
            np.bincount(b, w, len(ids))
            for w in (g * one, one.astype(float), g * ~one, (~one).astype(float))
        ]
    draws = np.random.default_rng(SEED).integers(0, len(ids), size=(BOOT, len(ids)))
    per = {}
    for m, (s1, n1, s0, n0) in stats.items():
        a1, c1 = s1[draws].sum(1), n1[draws].sum(1)
        a0, c0 = s0[draws].sum(1), n0[draws].sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            per[m] = a1 / c1 - a0 / c0
    pooled = np.nanmean(np.vstack(list(per.values())), axis=0)
    return pooled, per


def load_markets(nas: Path) -> dict[str, pd.DataFrame]:
    out = {}
    fr = ge.frames_from_lines(fn.lines(nas))
    out["NAS100"] = market_trades(fr, fn.START, fn.COMMISSION, fn.SL_SLIP)
    for sym in FX:
        fr = gl.load(sym)
        first = fr["5m"]["ts_utc"].iloc[0] + pd.Timedelta(days=30)
        start = max(START, first.normalize() + pd.offsets.MonthBegin(0))
        comm = FX_COMM * float(fr["5m"]["close"].median())
        out[sym] = market_trades(fr, start, comm, 0.0)
        del fr
    return out


def report(mk: dict[str, pd.DataFrame]) -> str:
    pooled, per = boot(mk)
    d = {m: diff(t) for m, t in mk.items()}
    big = float(np.mean(list(d.values())))
    p = float((1 + np.count_nonzero(pooled <= 0)) / (BOOT + 1))
    pos = sum(v > 0 for v in d.values())
    ok = big > 0 and p < 0.05 and pos >= MIN_MARKETS
    lines = [
        "# Confluence on six markets: result",
        "",
        "_`python -m app research confluence`, registered in `CONFLUENCE.md`. The frozen five; k = "
        "the five's trades open in the same direction at the entry. d = mean gross R (k >= 1) - "
        f"mean gross R (k = 0). 4-week calendar blocks, {BOOT:,} resamples, seed {SEED}._",
        "",
        "## Decision",
        "",
        f"Pooled D = {big:+.4f} R (95% {np.nanpercentile(pooled, 2.5):+.4f} to "
        f"{np.nanpercentile(pooled, 97.5):+.4f}), one-sided p {p:.4f}; d > 0 in {pos} of 6 "
        "markets.",
        "",
        (
            "**Hypothesis C passes: confluence is general.** Using it on gold still needs its own "
            "registration, the demo check and an EA step (`CONFLUENCE.md` §6)."
        )
        if ok
        else (
            "**Hypothesis C does not pass.** The gold pattern is treated as specific to the data "
            "it was found on; nothing changes."
        ),
        "",
        "## Per market",
        "",
        "| Market | Period | Trades | k >= 1 | d gross (95%) | Gross R k = 0 / 1 / 2 / 3+ "
        "| Net R with slip k = 0 / k >= 1 |",
        "|" + " --- |" * 7,
    ]
    for m, t in mk.items():
        g = t.assign(kk=t["k"].clip(upper=3)).groupby("kk")["gross"].mean().reindex(range(4))
        lo, hi = np.nanpercentile(per[m], [2.5, 97.5])
        lines.append(
            f"| {m} | {t['t'].min():%Y-%m-%d} to {t['t'].max():%Y-%m-%d} | {len(t):,} "
            f"| {(t['k'] >= 1).mean():.1%} | {d[m]:+.4f} ({lo:+.4f} to {hi:+.4f}) | "
            + " / ".join(f"{v:+.3f}" for v in g.to_numpy())
            + f" | {t.loc[t['k'] == 0, 'net_slip'].mean():+.4f} / "
            f"{t.loc[t['k'] >= 1, 'net_slip'].mean():+.4f} |"
        )
    allt = pd.concat(mk.values())
    lines += [
        "",
        f"All six pooled by trade: {len(allt):,} trades; net R with slip k = 0 "
        f"{allt.loc[allt['k'] == 0, 'net_slip'].mean():+.4f}, k >= 1 "
        f"{allt.loc[allt['k'] >= 1, 'net_slip'].mean():+.4f}; gross k = 0 "
        f"{allt.loc[allt['k'] == 0, 'gross'].mean():+.4f}, k >= 1 "
        f"{allt.loc[allt['k'] >= 1, 'gross'].mean():+.4f}.",
        "",
        "FX costs are approximate (commission 0.00007 x the median price, no SL slip); the "
        "decision uses gross R.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="confluence")
    ap.add_argument("--nas", type=Path, default=NAS_EXPORT)
    a = ap.parse_args(argv or [])
    mk = load_markets(a.nas)
    REPORT.write_text(report(mk), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
