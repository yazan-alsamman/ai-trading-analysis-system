"""Gold: the previous day's value area, VAH and VAL (``docs/strategies/GOLD_VP.md``, registered
2026-11-08).

    python -m app research gold-vp build                      # XAUUSD
    python -m app research gold-vp fxpro --export <GOLD M1>   # FxPro GOLD

VPVA trades the breaks of the previous trading day's VAH and VAL with LVL4H's frozen engine and
settings. The profile is built from the 5m bars' tick volume over 100 bins of the day's range,
and the value area holds 70% of the volume. The lockbox is not read."""

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
from app.research import gold_swing as sw

REPORT = gl.OUT_DIR / "gold_vp_xauusd.md"  # not gold_vp.md: GOLD_VP.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_vp_fxpro.md"
TUNE_END = gc.TUNE_END
BINS, SHARE, RISK = 100, 0.70, 0.25


def value_area(h: np.ndarray, lo: np.ndarray, v: np.ndarray) -> tuple[float, float]:
    """(VAH, VAL) of a set of bars: each bar's volume spread evenly over the bins its range
    touches; the area grows from the POC towards the side with more volume until 70%."""
    top, bot = float(h.max()), float(lo.min())
    if not top > bot or v.sum() <= 0:
        return np.nan, np.nan
    w = (top - bot) / BINS
    a = np.clip(((lo - bot) / w).astype(int), 0, BINS - 1)
    b = np.clip(((h - bot) / w).astype(int), 0, BINS - 1)
    prof = np.zeros(BINS)
    for ai, bi, vi in zip(a.tolist(), b.tolist(), v.tolist(), strict=True):
        prof[ai : bi + 1] += vi / (bi - ai + 1)
    lo_i = hi_i = int(np.argmax(prof))
    acc, need = prof[lo_i], SHARE * prof.sum()
    while acc < need:
        up = prof[hi_i + 1] if hi_i + 1 < BINS else -1.0
        dn = prof[lo_i - 1] if lo_i > 0 else -1.0
        if up >= dn:
            hi_i += 1
            acc += up
        else:
            lo_i -= 1
            acc += dn
    return bot + (hi_i + 1) * w, bot + lo_i * w


def vp_levels(cx: gl.Ctx) -> dict[str, np.ndarray]:
    """The previous trading day's VAH and VAL, by D1 bar."""
    n = len(cx.d1)
    vah, val = np.full(n, np.nan), np.full(n, np.nan)
    vol = cx.m["tick_volume"].to_numpy(float)
    order = np.argsort(cx.day_idx, kind="stable")
    days, starts = np.unique(cx.day_idx[order], return_index=True)
    bounds = np.r_[starts, len(order)]
    for d, s0, s1 in zip(days.tolist(), bounds[:-1].tolist(), bounds[1:].tolist(), strict=True):
        if 0 <= d < n:
            idx = order[s0:s1]
            vah[d], val[d] = value_area(cx.h[idx], cx.lo[idx], vol[idx])
    return {"VAH": np.r_[np.nan, vah[:-1]], "VAL": np.r_[np.nan, val[:-1]]}


def run(cx: gl.Ctx) -> pd.DataFrame:
    sig = gc.levels(cx, "VPVA", vp_levels(cx), ge.LVL_MULT * cx.atr4h, gc.WINDOWS[ge.LVL_WINDOW],
                    ge.LVL_HORIZON, ge.LVL_CAP)  # fmt: skip
    t = gc.run(sig, cx).drop(columns=["year", "net", "net_slip"])
    return gn.with_day(gs.finish(t, cx), cx)


def extras(cx: gl.Ctx, t: pd.DataFrame, since: pd.Timestamp | None) -> list[str]:
    five_r, five_pct = sw.five_daily(cx, since)
    corr = gn.correlations(t, {"FIVE": five_r})["FIVE"]
    a = sw.account(five_pct, None)
    daily = t.groupby("tday", as_index=False)["net_slip"].sum()
    # account() weighs by SWING's 0.5%; scale to VPVA's risk
    daily = daily.rename(columns={"net_slip": "net"}).assign(net=lambda x: x["net"] * RISK / 0.5)
    b = sw.account(five_pct, daily)
    return [
        *gs.HEAD,
        gs._row("Buys", t[t["dir"] > 0]),
        gs._row("Sells", t[t["dir"] < 0]),
        "",
        f"Daily net R correlation with the five together: **{corr:+.3f}**.",
        "",
        "| Account at demo risk | Total % | Largest drawdown % |",
        "| --- | --- | --- |",
        f"| The five | {a['total']:+.1f} | {a['dd']:.1f} |",
        f"| The five + VPVA at {RISK}% | {b['total']:+.1f} | {b['dd']:.1f} |",
        "",
        *gn._by_year(t),
    ]


def build() -> str:
    cx = gl.context(gl.load())
    t = run(cx)
    lines = [
        "# Gold: the previous day's value area (VAH, VAL), XAUUSD feed (exploratory)",
        "",
        "_`python -m app research gold-vp build`, registered in `GOLD_VP.md` (2026-11-08). XAUUSD "
        "5m bars 2012-01 to 2026-01-09, tick volume; cost = the signal bar's recorded spread + "
        "$0.07 per oz; with slip adds $0.10 on stop exits. One fixed setting. Seen data._",
        "",
        *gs.HEAD,
        gs._row("2012-2021", t[t["year"] <= TUNE_END]),
        gs._row("2022 to 2026-01-09 (check)", t[t["year"] > TUNE_END]),
        "",
        *extras(cx, t, None),
    ]
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
    t = run(cx)
    t = t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= gv.FX_START]
    since26 = pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= pd.Timestamp(
        "2026-01-12", tz="UTC"
    )
    s = gs.summary(t)
    lines = [
        "# Gold: the previous day's value area (VAH, VAL), FxPro's GOLD feed (exploratory)",
        "",
        f"_`python -m app research gold-vp fxpro`: `{export.name}`, trades from "
        f"{gv.FX_START.date()}. Costs as `gold_vp_xauusd.md`._",
        "",
        *gs.HEAD,
        gs._row("All", t),
        gs._row("2026-01-12 on", t[since26]),
        "",
        *extras(cx, t, gv.FX_START),
        "",
        f"Condition 3 (net with slip > 0): **{'met' if s['net_slip'] > 0 else 'not met'}** "
        f"({s['net_slip']:+.3f}).",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-vp")
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
