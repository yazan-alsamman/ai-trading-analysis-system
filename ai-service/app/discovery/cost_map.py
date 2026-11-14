"""Is the cost the binding constraint? (``docs/discovery/COST_SENSITIVITY.md``, registered
2026-11-14).

    python -m app discovery cost-map [--export <GOLD M1 export>]

Every trade of the 96 pooled cells (``pooled.build``'s code), re-priced: net_m = gross − m x
c_trade − c_slip, with c_trade = (spread at entry + $0.07) / risk and c_slip = $0.10 / risk on a
stop exit; m in 1, 0.75, 0.5, 0.25, 0. No new rule, no new trade."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.discovery import pooled as pl
from app.research import decide as dc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "discovery" / "cost_map_result.md"  # not COST_SENSITIVITY.md
MS = (1.0, 0.75, 0.5, 0.25, 0.0)
DECIDE_M, MIN_ALIVE, MIN_LOW_CORR, LOW_CORR, T_MIN = 0.5, 5, 2, 0.3, 2.0
P1, P2 = (20120101, 20191231), (20220101, 20260109)
BOOT, SEED = 10_000, 20261123
STOP_EXITS = ("sl", "stop")


def priced(c: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    """The trades with c_trade, c_slip and the check against their own net."""
    c = c.copy()
    e = c["e"].to_numpy()
    c["c_trade"] = (cx.spread[e] + gl.COMMISSION) / c["risk"].to_numpy()
    c["c_spread"] = cx.spread[e] / c["risk"].to_numpy()
    c["c_slip"] = np.where(c["exit"].isin(STOP_EXITS), gl.SL_SLIP / c["risk"], 0.0)
    c["resid"] = c["gross"] - c["c_trade"] - c["c_slip"] - c["net"]
    return c


def net_at(c: pd.DataFrame, m: float) -> pd.Series:
    return c["gross"] - m * c["c_trade"] - c["c_slip"]


def in_period(c: pd.DataFrame, p: tuple[int, int]) -> pd.DataFrame:
    return c[(c["ny_day"] >= p[0]) & (c["ny_day"] <= p[1])]


def boot_t(x: np.ndarray, days: np.ndarray) -> tuple[float, float]:
    """(t, one-sided p) of the mean of ``x`` under a 4-week block bootstrap of days."""
    ts = pd.to_datetime(pd.Series(days).astype(str), format="%Y%m%d").dt.tz_localize("UTC")
    ids, inv = np.unique(dc.block_ids(ts), return_inverse=True)
    k = len(ids)
    s, n = np.bincount(inv, x, k), np.bincount(inv, minlength=k).astype(float)
    dr = np.random.default_rng(SEED).integers(0, k, size=(BOOT, k))
    star = s[dr].sum(1) / n[dr].sum(1)
    sd = float(np.std(star, ddof=1))
    t = float(np.mean(x) / sd) if sd > 0 else 0.0
    return t, float((1 + np.count_nonzero(star <= 0)) / (BOOT + 1))


def holm_count(p: dict[str, float], alpha: float = 0.05) -> int:
    order = sorted(p.values())
    n = len(order)
    for i, v in enumerate(order):
        if v > alpha / (n - i):
            return i
    return n


def cell_table(c: pd.DataFrame, five_days: pd.Series) -> pd.DataFrame:
    rows = []
    days2 = np.sort(in_period(c, P2)["ny_day"].unique())
    years1 = (P1[1] // 10000) - (P1[0] // 10000) + 1
    for cell, g in c.groupby("cell"):
        a, b = in_period(g, P1), in_period(g, P2)
        r = {
            "cell": cell,
            "group": g["group"].iloc[0],
            "n1": len(a),
            "n2": len(b),
            "a_day": len(a) / (years1 * 258),
            "gross1": a["gross"].mean(),
            "gross2": b["gross"].mean(),
            "c_trade1": a["c_trade"].mean(),
            "c_trade2": b["c_trade"].mean(),
            "c_slip2": b["c_slip"].mean(),
            "spread_share": b["c_spread"].mean() / b["c_trade"].mean() if len(b) else np.nan,
            "resid": g["resid"].abs().mean(),
        }
        for tag, x in (("1", a), ("2", b)):
            ct = x["c_trade"].mean()
            r[f"mstar{tag}"] = (
                (x["gross"].mean() - x["c_slip"].mean()) / ct if len(x) and ct else np.nan
            )
        for m in MS:
            r[f"net1_{m}"] = net_at(a, m).mean() if len(a) else np.nan
            r[f"net2_{m}"] = net_at(b, m).mean() if len(b) else np.nan
            if len(b) >= 30:
                r[f"t2_{m}"], r[f"p2_{m}"] = boot_t(net_at(b, m).to_numpy(), b["ny_day"].to_numpy())
            else:
                r[f"t2_{m}"], r[f"p2_{m}"] = np.nan, 1.0
            daily = net_at(b, m).groupby(b["ny_day"]).sum().reindex(days2, fill_value=0.0)
            fd = five_days.reindex(days2, fill_value=0.0)
            r[f"corr_{m}"] = float(np.corrcoef(daily, fd)[0, 1]) if daily.std() > 0 else np.nan
        rows.append(r)
    t = pd.DataFrame(rows).set_index("cell")
    for m in MS:
        t[f"alive_{m}"] = (
            (t[f"net1_{m}"] > 0)
            & (t[f"net2_{m}"] > 0)
            & (t[f"t2_{m}"] >= T_MIN)
            & (t["group"] != "six")
        )
    return t


def spread_by_hour(cx: gl.Ctx) -> pd.Series:
    ok = (cx.ny_day >= P2[0]) & (cx.ny_day <= P2[1]) & (cx.weekday < 5)
    return pd.Series(cx.spread[ok]).groupby(cx.ny_min[ok] // 60).median()


def fx_readout(export: Path, cells: list[str]) -> pd.DataFrame:
    fr = ge.frames_from_lines(gv.fx_lines(export))
    cx = gl.context(fr)
    end = pd.Timestamp("2026-11-07", tz="UTC")
    parts = [
        pl.lab_from_frames(fr, cx),
        pl.level_trades(cx, fr, pl.FX_WARM, end),
        pl.six_trades(fr, pl.FX_WARM),
    ]
    c = pl.finish(pd.concat(parts, ignore_index=True), cx)
    c = c[(c["ny_day"] >= pl.FX_FROM) & (c["ny_day"] <= pl.FX_TO) & c["cell"].isin(cells)]
    return priced(c, cx)


def report(c: pd.DataFrame, t: pd.DataFrame, hours: pd.Series, fx: pd.DataFrame | None) -> str:
    alive = t[t[f"alive_{DECIDE_M}"]]
    low = alive[alive[f"corr_{DECIDE_M}"] < LOW_CORR]
    lever = len(alive) >= MIN_ALIVE and len(low) >= MIN_LOW_CORR
    holm = {m: holm_count(t.loc[t["group"] != "six", f"p2_{m}"].to_dict()) for m in MS}
    lines = [
        "# The cost-sensitivity map: result",
        "",
        "_`python -m app discovery cost-map`, registered in `COST_SENSITIVITY.md`. "
        f"{len(t)} cells, {len(c):,} trades, XAUUSD 5m. net_m = gross − m x c_trade − c_slip. "
        f"t from a 4-week block bootstrap of days ({BOOT:,} resamples)._",
        "",
        f"Check: mean |gross − c_trade − c_slip − net| per cell, largest {t['resid'].max():.4f} R "
        f"({(t['resid'] > 0.001).sum()} cells above 0.001).",
        "",
        "## Decision (m = 0.5)",
        "",
        f"Cells alive at half the trading cost (net > 0 on 2012-2019 and on 2022-2026 with t >= 2, "
        f"not the six): **{len(alive)}**; of them with correlation below +0.3 with the five: "
        f"**{len(low)}**.",
        "",
        "**Cost is a lever worth pursuing:** a venue search gets its own registration."
        if lever
        else "**Cost is not the key:** nothing follows.",
        "",
        "## How many cells are positive at each m",
        "",
        "| m | Net > 0, 2012-2019 | Net > 0, 2022-2026 | Alive (rule §4) | Holm count, 2022-2026 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for m in MS:
        lines.append(
            f"| {m} | {(t[f'net1_{m}'] > 0).sum()} | {(t[f'net2_{m}'] > 0).sum()} "
            f"| {int(t[f'alive_{m}'].sum())} | {holm[m]} |"
        )
    lines += [
        "",
        "## Cells alive at some m <= 0.5",
        "",
        "| Cell | A day | Gross 12-19 / 22-26 | c_trade 22-26 | m* 12-19 / 22-26 "
        "| Net at 0.5, 12-19 / 22-26 (t) | Corr with the five | Alive at |",
        "|" + " --- |" * 8,
    ]
    show = t[t[[f"alive_{m}" for m in MS if m <= DECIDE_M]].any(axis=1)]
    for cell, x in show.sort_values("mstar2", ascending=False).iterrows():
        at = ", ".join(str(m) for m in MS if x[f"alive_{m}"])
        lines.append(
            f"| {cell} | {x['a_day']:.2f} | {x['gross1']:+.3f} / {x['gross2']:+.3f} "
            f"| {x['c_trade2']:.3f} | {x['mstar1']:.2f} / {x['mstar2']:.2f} "
            f"| {x['net1_0.5']:+.3f} / {x['net2_0.5']:+.3f} ({x['t2_0.5']:+.2f}) "
            f"| {x['corr_0.5']:+.2f} | {at} |"
        )
    lines += [
        "",
        "## The six at each m (2022-2026, mean net R a trade)",
        "",
        "| Cell | " + " | ".join(f"m {m}" for m in MS) + " | m* |",
        "|" + " --- |" * (len(MS) + 2),
    ]
    for cell, x in t[t["group"] == "six"].iterrows():
        lines.append(
            f"| {cell} | "
            + " | ".join(f"{x[f'net2_{m}']:+.3f}" for m in MS)
            + f" | {x['mstar2']:.2f} |"
        )
    lines += [
        "",
        "## Every cell (sorted by m* on 2022-2026)",
        "",
        "| Cell | Trades 12-19 / 22-26 | Gross 12-19 / 22-26 | c_trade / c_slip 22-26 "
        "| Spread share | m* 12-19 / 22-26 |",
        "|" + " --- |" * 6,
    ]
    for cell, x in t.sort_values("mstar2", ascending=False).iterrows():
        lines.append(
            f"| {cell} | {int(x['n1']):,} / {int(x['n2']):,} | {x['gross1']:+.3f} / "
            f"{x['gross2']:+.3f} | {x['c_trade2']:.3f} / {x['c_slip2']:.3f} "
            f"| {x['spread_share']:.0%} | {x['mstar1']:.2f} / {x['mstar2']:.2f} |"
        )
    lines += [
        "",
        "## Median spread by New York hour (gold store, 2022-2026, $)",
        "",
        "| Hour | " + " | ".join(str(h) for h in hours.index) + " |",
        "|" + " --- |" * (len(hours) + 1),
        "| Spread | " + " | ".join(f"{v:.2f}" for v in hours.to_numpy()) + " |",
        "",
    ]
    if fx is not None and len(fx):
        lines += [
            "## FxPro 2026-01-12 to 2026-11-05 (the cells alive at m = 0.5)",
            "",
            "| Cell | Trades | Net at 1 | Net at 0.5 |",
            "| --- | --- | --- | --- |",
        ]
        for cell, g in fx.groupby("cell"):
            lines.append(
                f"| {cell} | {len(g):,} | {net_at(g, 1.0).mean():+.3f} "
                f"| {net_at(g, 0.5).mean():+.3f} |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cost-map")
    ap.add_argument("--export", type=Path, default=pl.FX_EXPORT)
    a = ap.parse_args(argv or [])
    fr = gl.load()
    cx = gl.context(fr)
    parts = [
        pl.lab_trades(cx),
        pl.level_trades(cx, fr, pl.START, pl.END),
        pl.six_trades(fr, pl.START),
    ]
    c = pl.finish(pd.concat(parts, ignore_index=True), cx)
    c = priced(c[c["entry_utc"] < pl.END].reset_index(drop=True), cx)
    six = c[c["cell"].isin([f"six:{k}" for k in pl.FIVE])]
    five_days = in_period(six, P2).groupby("ny_day")["net"].sum()
    t = cell_table(c, five_days)
    alive = list(t.index[t[f"alive_{DECIDE_M}"]])
    fx = fx_readout(a.export, alive) if alive else None
    REPORT.write_text(report(c, t, spread_by_hour(cx), fx), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
