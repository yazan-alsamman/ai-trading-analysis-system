"""Screen 2: the 15 confirmations and 9 new level sets with the five's engine
(``docs/levels/CONFIRM_SCREEN2.md``, registered 2026-11-12 before any outcome).

    python -m app levels confirm5

Part A: screen 1's base events and methods (``confirm``), traded with D = 0.75 x ATR(4h), M8, no
target. Part B: new level sets traded exactly like the five (``gold_combo.levels`` + M8). XAUUSD
2024-01-01 to 2026-01-09, against 200 shifted copies."""

from __future__ import annotations

import multiprocessing as mp

import numpy as np
import pandas as pd

from app.discovery import markout as mk
from app.levels import confirm as cf
from app.levels import discover as dc
from app.levels import families as fm
from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_night as gn
from app.research import gold_round as gr

REPORT = dc.ROOT / "docs" / "levels" / "confirm_screen2_result.md"
FROM, TO = cf.FROM, cf.TO
WINDOW = gc.WINDOWS[ge.LVL_WINDOW]  # 02:00-16:00 New York
LONDON_WINDOW = (7 * 60, 16 * 60)
SEED_A, SEED_B, COPIES = 20261120, 20261121, 200
SETS = ("PMHL", "LONDON", "OPENS", "PDC", "PIV2", "SWING", "HL3", "HL20", "R100", "NYS")
_W: dict = {}


# --- part A ---------------------------------------------------------------------------------------


def part_a(
    cx: gl.Ctx, ind: cf.Ind, fams: list, days: np.ndarray, in_period: np.ndarray
) -> pd.DataFrame:
    n = len(cx.c)
    sigs = []
    for fam in fams:
        ev = (
            cf.base_lattice(cx, fam)
            if isinstance(fam, fm.Lattice)
            else cf.base_discrete(cx, fam, days)
        )
        if not len(ev):
            continue
        ev = ev[in_period[ev["i"].to_numpy().astype(int)]]
        s = cf.methods(cx, ind, ev)
        if not len(s):
            continue
        i = s["i"].to_numpy()
        ok = (i + 1 < n) & (cx.ny_min[i] >= WINDOW[0]) & (cx.ny_min[i] < WINDOW[1])
        s, i = s[ok], i[ok]
        risk = ge.LVL_MULT * cx.atr4h[i]
        ok = np.isfinite(risk) & (risk > 0) & ((cx.spread[i] + gl.COMMISSION) / risk <= ge.LVL_CAP)
        s, i, risk = s[ok], i[ok], risk[ok]
        end = np.minimum(i + ge.LVL_HORIZON, cx.deadline[i])
        sigs.append(
            pd.DataFrame(
                {
                    "strategy": fam.name + "|" + s["method"].to_numpy(),
                    "i": i,
                    "dir": s["d"].to_numpy(),
                    "entry": cx.o[i + 1],
                    "risk": risk,
                    "tp_r": np.nan,
                    "end": end,
                }
            )[end > i]
        )
    if not sigs:
        return pd.DataFrame()
    t = gl.simulate(pd.concat(sigs, ignore_index=True), cx, "M8")
    t["net_slip"] = (
        t["gross"] - t["cost"] - np.where(t["exit"] == "sl", gl.SL_SLIP / t["risk"], 0.0)
    )
    t["cell"] = t["strategy"].str.split("|").str[1]
    return t


# --- part B ---------------------------------------------------------------------------------------


def _shift1(x: np.ndarray) -> np.ndarray:
    return np.r_[np.nan, np.asarray(x, float)[:-1]]


def swing_levels(cx: gl.Ctx, h1: pd.DataFrame) -> dict[str, np.ndarray]:
    """At each trading day's first bar: the nearest live 1h swing high above and swing low below
    the last close."""
    pts, start, end = fm._ends(cx, fm.swing_points(h1))
    order = np.argsort(start, kind="stable")
    st, en = start[order], end[order]
    lv, sd = pts["level"].to_numpy()[order], pts["side"].to_numpy()[order]
    first, _ = fm.day_bounds(cx)
    n = len(cx.d1)
    hi, lo = np.full(n, np.nan), np.full(n, np.nan)
    for d in range(min(n, len(first))):
        a = int(first[d])
        if a < 1:
            continue
        z = np.searchsorted(st, a, "right")
        w = slice(max(0, z - 600), z)
        live = en[w] > a
        prev = cx.c[a - 1]
        up = lv[w][live & (sd[w] > 0) & (lv[w] > prev)]
        dn = lv[w][live & (sd[w] < 0) & (lv[w] < prev)]
        hi[d] = up.min() if len(up) else np.nan
        lo[d] = dn.max() if len(dn) else np.nan
    return {"SWH": hi, "SWL": lo}


def level_sets(cx: gl.Ctx, fr: dict[str, pd.DataFrame]) -> dict[str, tuple[dict, tuple]]:
    d1 = cx.d1
    h, lo, c, o = (d1[k].to_numpy() for k in ("high", "low", "close", "open"))
    date = d1["close_utc"].dt.tz_convert(gl.NY).dt.tz_localize(None)
    mon, wk = date.dt.to_period("M").to_numpy(), date.dt.to_period("W-SUN").to_numpy()
    gm_ = d1.groupby(mon)
    wo = d1.groupby(wk)["open"].first()
    p = _shift1((h + lo + c) / 3)
    ph, pl = _shift1(h), _shift1(lo)
    lon_h, lon_l = fm._session(cx, (cx.ny_min >= fm.LONDON_FROM) & (cx.ny_min < fm.LONDON_TO))
    nys_h, nys_l = fm._session(cx, (cx.ny_min >= 570) & (cx.ny_min < 960))
    s = pd.Series
    return {
        "PMHL": (
            {
                "PMH": gm_["high"].max().shift(1).reindex(mon).to_numpy(),
                "PML": gm_["low"].min().shift(1).reindex(mon).to_numpy(),
            },
            WINDOW,
        ),
        "LONDON": ({"LDH": lon_h, "LDL": lon_l}, LONDON_WINDOW),
        "OPENS": ({"DO": o, "WO": wo.reindex(wk).to_numpy()}, WINDOW),
        "PDC": ({"PDC": _shift1(c)}, WINDOW),
        "PIV2": ({"P": p, "R2": p + (ph - pl), "S2": p - (ph - pl)}, WINDOW),
        "SWING": (swing_levels(cx, fr["1h"]), WINDOW),
        "HL3": (
            {
                "H3": s(h).rolling(3).max().shift(1).to_numpy(),
                "L3": s(lo).rolling(3).min().shift(1).to_numpy(),
            },
            WINDOW,
        ),
        "HL20": (
            {
                "H20": s(h).rolling(20).max().shift(1).to_numpy(),
                "L20": s(lo).rolling(20).min().shift(1).to_numpy(),
            },
            WINDOW,
        ),
        "R100": (gr.round_levels(cx, 100.0), WINDOW),
        "NYS": ({"NYH": _shift1(nys_h), "NYL": _shift1(nys_l)}, WINDOW),
    }


def part_b(
    cx: gl.Ctx, sets: dict, in_period: np.ndarray, u: float = 0.0, atr_d: np.ndarray | None = None
) -> pd.DataFrame:
    out = []
    for name, (lv, win) in sets.items():
        lvs = lv if u == 0.0 else {k: v + u * atr_d for k, v in lv.items()}
        sig = gc.levels(cx, name, lvs, ge.LVL_MULT * cx.atr4h, win, ge.LVL_HORIZON, ge.LVL_CAP)
        sig = sig[in_period[sig["i"].to_numpy()]]
        if len(sig):
            t = gc.run(sig, cx)
            t["cell"] = name
            out.append(t)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# --- the screen -----------------------------------------------------------------------------------


def setup() -> tuple:
    fr = gl.load()  # once: each worker holds one copy of the bars
    cx = gl.context(fr)
    fams = [*fm.real(cx, fr), *[fm.rnd(cx, d) for d in fm.RND_STEPS]]
    t = pd.to_datetime(cx.m["close_utc"].to_numpy(), utc=True)
    in_period = np.asarray((t >= FROM) & (t < TO))
    days = dc.period_days(cx, in_period)
    ind = cf.Ind(cx, fr["1h"])
    sets = level_sets(cx, fr)
    d1 = cx.d1
    atr_d = _shift1(gl.wilder(*(d1[k].to_numpy() for k in ("high", "low", "close"))))
    return cx, ind, fams, days, in_period, sets, atr_d


def _init() -> None:
    (_W["cx"], _W["ind"], _W["fams"], _W["days"], _W["in"], _W["sets"], _W["atr_d"]) = setup()


def _agg(cx: gl.Ctx, t: pd.DataFrame) -> pd.DataFrame:
    if t.empty:
        return t
    t = t.assign(blk=cf.blocks(cx, t["i"].to_numpy() + 1))
    return (
        t.groupby(["cell", "blk"]).agg(s=("net_slip", "sum"), n=("net_slip", "size")).reset_index()
    )


def _copy(job: tuple) -> pd.DataFrame:
    q, us, sp, ub = job
    cx = _W["cx"]
    fams = [dc.shift(f, us[f.name], sp.get(f.name, 0.0)) for f in _W["fams"]]
    a = part_a(cx, _W["ind"], fams, _W["days"], _W["in"])
    b = part_b(cx, _W["sets"], _W["in"], ub, _W["atr_d"])
    return pd.concat([_agg(cx, a), _agg(cx, b)], ignore_index=True).assign(copy=q)


def main() -> int:
    cx, ind, fams, days, in_period, sets, atr_d = setup()
    real = pd.concat(
        [part_a(cx, ind, fams, days, in_period), part_b(cx, sets, in_period)], ignore_index=True
    )
    real["blk"] = cf.blocks(cx, real["i"].to_numpy() + 1)
    sp = dc.spacings(cx, fams, in_period)
    ra, rb = np.random.default_rng(SEED_A), np.random.default_rng(SEED_B)
    jobs = []
    for q in range(COPIES):
        us = {f.name: float(ra.uniform(0.0, 1.0)) for f in fams}
        ub = float(rb.uniform(0.25, 0.75)) * (1.0 if rb.random() < 0.5 else -1.0)
        jobs.append((q, us, sp, ub))
    with mp.Pool(cf.WORKERS, initializer=_init) as pool:
        parts = pool.map(_copy, jobs, chunksize=1)
    plc = pd.concat([p for p in parts if len(p)], ignore_index=True)
    nb = int(cf.blocks(cx, np.array([np.flatnonzero(in_period)[-1]]))[0]) + 1
    idx = mk.resamples(nb)
    n_days = len(np.unique(cx.ny_day[in_period & (cx.weekday < 5)]))
    five = {k: v[in_period[v["i"].to_numpy()]] for k, v in gn.day_strategies(cx).items()}
    lines = [
        "# Screen 2: confirmations and new levels with the five's engine (XAUUSD 2024 to "
        "2026-01-09)",
        "",
        "_`python -m app levels confirm5`, registered in `CONFIRM_SCREEN2.md` (2026-11-12) "
        "before the run. D = 0.75 x ATR(4h), M8, no target, 16:45. Net R a trade with slip; "
        "shifted = 200 shifted copies; t from a 4-week block bootstrap. Pass: net > 0 and "
        "t >= 1.5._",
        "",
        "| Part | Cell | Trades | A day | Win | Gross R | Net R | Shifted copies | t | Passes "
        "| Correlation with the five (max) |",
        "|" + " --- |" * 11,
    ]
    for part, cells in (("A", cf.METHODS), ("B", SETS)):
        for m in cells:
            r = real[real["cell"] == m]
            p = plc[plc["cell"] == m]
            if len(r) < 2 or p["n"].sum() < 2:
                lines.append(f"| {part} | {m} | {len(r)} | - | - | - | - | - | - | | |")
                continue
            r_s = np.bincount(r["blk"], r["net_slip"], minlength=nb)[:nb]
            r_n = np.bincount(r["blk"], minlength=nb)[:nb].astype(float)
            p_s = np.bincount(p["blk"], p["s"], minlength=nb)[:nb]
            p_n = np.bincount(p["blk"], p["n"], minlength=nb)[:nb].astype(float)
            mr, mp_ = r_s.sum() / r_n.sum(), p_s.sum() / p_n.sum()
            with np.errstate(invalid="ignore", divide="ignore"):
                star = r_s[idx].sum(1) / r_n[idx].sum(1) - p_s[idx].sum(1) / p_n[idx].sum(1)
            se = np.nanstd(star, ddof=1)
            t = (mr - mp_) / se if se > 0 else np.nan
            ok = mr > 0 and t >= 1.5
            corr = "-"
            if part == "B":
                rr = gn.with_day(r.drop(columns=["tday"], errors="ignore"), cx).assign(
                    net=r["net_slip"]
                )
                cc = gn.correlations(rr, five)
                corr = f"{max(cc.values()):+.2f}"
            lines.append(
                f"| {part} | {m} | {len(r):,} | {len(r) / n_days:.2f} "
                f"| {(r['gross'] > 0).mean():.0%} | {r['gross'].mean():+.3f} | {mr:+.3f} "
                f"| {mp_:+.3f} | {t:+.2f} | {'**yes**' if ok else ''} | {corr} |"
            )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
