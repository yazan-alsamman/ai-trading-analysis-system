"""Range exhaustion (``docs/vol/EXHAUSTION.md``, registered 2026-11-13).

    python -m app research exhaustion [--export <GOLD M1 export>]

u = the day's range from 02:00 New York to the bar before the entry / (p02 x sqrt(F)), F = M3's
out-of-sample forecast (part 1's walk-forward). Cut-off: the 2/3 quantile of u over the five's
2018-2021 trades. Test: top tercile minus the rest, 2022 to 2026-01-09, 4-week block bootstrap;
readout on FxPro 2026-01-12 to 2026-11-05 (M3 fitted on every store day)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import decide as dc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import vol_forecast as vf
from app.scoring.volatility import M3

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "vol" / "exhaustion_result.md"  # not EXHAUSTION.md (Windows case)
DEFAULT_EXPORT = Path("D:/GOLD_M1_201501020000_202611052359.csv")
FIVE = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")
CUT_FROM, CUT_TO, TEST_FROM, TEST_TO = 20180101, 20211231, 20220101, 20260109
FX_FROM, FX_TO = 20260112, 20261105
BOOT, SEED = 10_000, 20261119
BLOCKS = ((120, 480, "02-08"), (480, 720, "08-12"), (720, 960, "12-16"))


def day_int(index: pd.DatetimeIndex) -> np.ndarray:
    return (index.year * 10000 + index.month * 100 + index.day).to_numpy()


def range_before(cx: gl.Ctx, i: np.ndarray) -> np.ndarray:
    """High minus low of the entry day's 5m bars opening 02:00 New York or later and before bar i
    (0 when there is none)."""
    win = cx.ny_min >= 120
    day = pd.Series(cx.ny_day)
    hi = pd.Series(np.where(win, cx.h, np.nan)).groupby(day).cummax()
    lo = pd.Series(np.where(win, cx.lo, np.nan)).groupby(day).cummin()
    rng = (hi - lo).to_numpy()
    prev = np.asarray(i) - 1
    same = (prev >= 0) & (cx.ny_day[np.maximum(prev, 0)] == cx.ny_day[i])
    r = np.where(same, rng[np.maximum(prev, 0)], np.nan)
    return np.nan_to_num(r, nan=0.0)


def with_u(
    t: pd.DataFrame, cx: gl.Ctx, days: np.ndarray, level: np.ndarray, p02: np.ndarray
) -> pd.DataFrame:
    """The trades with ny_day, entry minute and u (NaN on days without a forecast)."""
    t = t.copy()
    i = t["i"].to_numpy()
    t["ny_day"] = cx.ny_day[i]
    t["minute"] = cx.ny_min[i]
    scale = pd.Series(p02 * np.sqrt(level), index=days)
    t["u"] = range_before(cx, i) / t["ny_day"].map(scale).to_numpy()
    return t


def split(t: pd.DataFrame, cut: float) -> float:
    top = t["u"] > cut
    return float(t.loc[top, "net_slip"].mean() - t.loc[~top, "net_slip"].mean())


def boot(t: pd.DataFrame, cut: float) -> dict:
    ts = pd.to_datetime(t["ny_day"].astype(str), format="%Y%m%d").dt.tz_localize("UTC")
    ids, inv = np.unique(dc.block_ids(ts), return_inverse=True)
    k = len(ids)
    top = (t["u"] > cut).to_numpy()
    x = t["net_slip"].to_numpy()
    s1, n1 = np.bincount(inv, x * top, k), np.bincount(inv, top.astype(float), k)
    s0, n0 = np.bincount(inv, x * ~top, k), np.bincount(inv, (~top).astype(float), k)
    dr = np.random.default_rng(SEED).integers(0, k, size=(BOOT, k))
    star = s1[dr].sum(1) / n1[dr].sum(1) - s0[dr].sum(1) / n0[dr].sum(1)
    return {
        "d": split(t, cut),
        "lo": float(np.percentile(star, 2.5)),
        "hi": float(np.percentile(star, 97.5)),
        "p": float((1 + np.count_nonzero(star >= 0)) / (BOOT + 1)),
        "blocks": k,
    }


def store_side() -> dict:
    fr = gl.load()
    cal = pd.read_parquet(vf.CAL)
    u5 = vf.features(fr["5m"], fr["4h"], cal)
    f, _ = vf.walk(u5)
    level = np.exp(f["f_M3"].to_numpy() + f["s2_M3"].to_numpy() / 2)
    _, every, _, cx = gv.five_trades(
        fr, start=pd.Timestamp("2018-01-01", tz="UTC"), with_round=True
    )
    t = with_u(every, cx, day_int(f.index), level, f["p02"].to_numpy())
    return {"t": t.dropna(subset=["u"]), "u5": u5, "cal": cal}


def fx_side(export: Path, u5: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    fr = ge.frames_from_lines(gv.fx_lines(export))
    beta, s2 = vf.ols(u5[M3].to_numpy(), u5["y"].to_numpy())
    first = pd.Timestamp(str(FX_FROM))
    w = vf.features(fr["5m"], fr["4h"], cal, first, pd.Timestamp(str(FX_TO)))
    level = np.exp(np.c_[np.ones(len(w)), w[M3].to_numpy()] @ beta + s2 / 2)
    _, every, _, cx = gv.five_trades(
        fr, start=vf.at_ny(pd.DatetimeIndex([first]), 0)[0], with_round=True
    )
    t = with_u(every, cx, day_int(w.index), level, w["p02"].to_numpy())
    return t[(t["ny_day"] >= FX_FROM) & (t["ny_day"] <= FX_TO)].dropna(subset=["u"])


# --- report ---------------------------------------------------------------------------------------


def by_tercile(t: pd.DataFrame, cut: float, label: str) -> list[str]:
    out = []
    for name, g in (("top (u > cut)", t[t["u"] > cut]), ("rest", t[t["u"] <= cut])):
        out.append(
            f"| {label} | {name} | {len(g):,} | {g['net_slip'].mean():+.4f} "
            f"| {g['gross'].mean():+.4f} | {(g['net_slip'] > 0).mean():.1%} "
            f"| {(g['exit'] == 'sl').mean():.1%} |"
        )
    return out


def report(st: dict, fx: pd.DataFrame) -> str:
    t = st["t"]
    five = t[t["strategy"].isin(FIVE)]
    cut_set = five[(five["ny_day"] >= CUT_FROM) & (five["ny_day"] <= CUT_TO)]
    cut = float(cut_set["u"].quantile(2 / 3))
    test = five[(five["ny_day"] >= TEST_FROM) & (five["ny_day"] <= TEST_TO)]
    fx5 = fx[fx["strategy"].isin(FIVE)]
    b = boot(test, cut)
    top_mean = float(test.loc[test["u"] > cut, "net_slip"].mean())
    fx_d = split(fx5, cut) if (fx5["u"] > cut).any() else np.nan
    c1, c2, c3 = b["d"] < 0 and b["p"] < 0.05, top_mean < 0, fx_d < 0
    lines = [
        "# Range exhaustion: result",
        "",
        "_`python -m app research exhaustion`, registered in `EXHAUSTION.md`. u = the day's range "
        "from 02:00 New York to the bar before the entry / (p02 x sqrt(F)), F = M3's out-of-sample "
        f"forecast. 4-week block bootstrap, {BOOT:,} resamples, seed {SEED}._",
        "",
        f"Cut-off (2/3 quantile of u, the five's 2018-2021 trades, n = {len(cut_set):,}): "
        f"**{cut:.3f}**.",
        "",
        "## Decision",
        "",
        f"1. d < 0 with p < 0.05 (2022 to 2026-01-09): **{'yes' if c1 else 'no'}** "
        f"(d {b['d']:+.4f} R, 95% {b['lo']:+.4f} to {b['hi']:+.4f}, p {b['p']:.4f}, "
        f"{b['blocks']} blocks)",
        f"2. top tercile's mean net R < 0: **{'yes' if c2 else 'no'}** ({top_mean:+.4f})",
        f"3. d < 0 on FxPro 2026-01-12 to 2026-11-05: **{'yes' if c3 else 'no'}** ({fx_d:+.4f})",
        "",
        "**Hypothesis X passes.** The filter needs its own registration and an EA step."
        if (c1 and c2 and c3)
        else "**Hypothesis X does not pass.** The five stay as they are.",
        "",
        "## By tercile",
        "",
        "| Data | Group | Trades | Mean net R with slip | Gross R | Win share | Stop exits |",
        "|" + " --- |" * 7,
        *by_tercile(cut_set, cut, "2018-2021"),
        *by_tercile(test, cut, "2022 to 2026-01-09"),
        *by_tercile(fx5, cut, "FxPro 2026"),
        *by_tercile(t[t["strategy"] == "ROUND"], cut, "ROUND, 2018 to 2026-01-09"),
        "",
        "## Per strategy (2018 to 2026-01-09): mean net R, top / rest",
        "",
        "| Strategy | Trades top / rest | Top | Rest |",
        "| --- | --- | --- | --- |",
    ]
    for s in FIVE:
        g = five[five["strategy"] == s]
        a, r = g[g["u"] > cut], g[g["u"] <= cut]
        lines.append(
            f"| {s} | {len(a):,} / {len(r):,} | {a['net_slip'].mean():+.4f} "
            f"| {r['net_slip'].mean():+.4f} |"
        )
    lines += [
        "",
        "## Within entry-time blocks (New York; 2018 to 2026-01-09)",
        "",
        "| Block | Trades | Share top | Top | Rest |",
        "| --- | --- | --- | --- | --- |",
    ]
    for lo, hi, name in BLOCKS:
        g = five[(five["minute"] >= lo) & (five["minute"] < hi)]
        a, r = g[g["u"] > cut], g[g["u"] <= cut]
        lines.append(
            f"| {name} | {len(g):,} | {len(a) / max(len(g), 1):.0%} "
            f"| {a['net_slip'].mean():+.4f} | {r['net_slip'].mean():+.4f} |"
        )
    q = pd.qcut(five["u"].rank(method="first"), 10, labels=False)
    lines += [
        "",
        "## u deciles (the five, 2018 to 2026-01-09)",
        "",
        "| Decile | u range | Trades | Mean net R with slip |",
        "| --- | --- | --- | --- |",
    ]
    for k, g in five.groupby(q):
        lines.append(
            f"| {k + 1} | {g['u'].min():.3f} to {g['u'].max():.3f} | {len(g):,} "
            f"| {g['net_slip'].mean():+.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="exhaustion")
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    a = ap.parse_args(argv or [])
    st = store_side()
    fx = fx_side(a.export, st["u5"], st["cal"])
    REPORT.write_text(report(st, fx), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
