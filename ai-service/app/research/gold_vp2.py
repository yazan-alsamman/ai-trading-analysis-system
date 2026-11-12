"""Gold: value-area re-entry and accepted break (``docs/strategies/GOLD_VP2.md``, registered
2026-11-12 before any outcome).

    python -m app research gold-vp2 build --export <GOLD M1>

The previous trading day's profile (TPO or tick volume; VAH, VAL, POC), 15m signals, entry at the
next real 15m open, exit at the target, the stop or 16:45 New York; against 200 copies with the
value area shifted."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.discovery import markout as mk
from app.levels import families as fm
from app.research import gold_exam as ge
from app.research import gold_ha as ha
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_vp2_result.md"  # not gold_vp2.md: GOLD_VP2.md on Windows
BINS, SHARE = 100, 0.70
WIN_FROM, WIN_TO = 2 * 60, 13 * 60
RE_PAD, BREAK_PAD, MIN_R, COST_X = 0.1, 0.25, 1.5, 3.0
COPIES, SEED = 200, 20261118
TUNE_END = 2021
SETUPS, WEIGHTS = ("REENTRY", "ACCEPTED"), ("TPO", "TICK")


# --- profiles -------------------------------------------------------------------------------------


def profile(h: np.ndarray, lo: np.ndarray, w: np.ndarray) -> tuple[float, float, float]:
    """(VAH, VAL, POC) of a set of bars: each bar's weight spread evenly over the bins its range
    touches; the area grows from the POC toward the heavier side until 70%."""
    top, bot = float(h.max()), float(lo.min())
    if not top > bot or w.sum() <= 0:
        return np.nan, np.nan, np.nan
    step = (top - bot) / BINS
    a = np.clip(((lo - bot) / step).astype(int), 0, BINS - 1)
    b = np.clip(((h - bot) / step).astype(int), 0, BINS - 1)
    prof = np.zeros(BINS)
    for ai, bi, wi in zip(a.tolist(), b.tolist(), w.tolist(), strict=True):
        prof[ai : bi + 1] += wi / (bi - ai + 1)
    poc = int(np.argmax(prof))
    lo_i = hi_i = poc
    acc, need = prof[poc], SHARE * prof.sum()
    while acc < need:
        up = prof[hi_i + 1] if hi_i + 1 < BINS else -1.0
        dn = prof[lo_i - 1] if lo_i > 0 else -1.0
        if up >= dn:
            hi_i += 1
            acc += up
        else:
            lo_i -= 1
            acc += dn
    return bot + (hi_i + 1) * step, bot + lo_i * step, bot + (poc + 0.5) * step


def previous_profiles(cx: gl.Ctx, weight: str) -> tuple[np.ndarray, ...]:
    """The previous trading day's VAH, VAL, POC, by D1 bar."""
    n = len(cx.d1)
    out = [np.full(n, np.nan) for _ in range(3)]
    w = np.ones(len(cx.c)) if weight == "TPO" else cx.m["tick_volume"].to_numpy(float)
    order = np.argsort(cx.day_idx, kind="stable")
    days, starts = np.unique(cx.day_idx[order], return_index=True)
    bounds = np.r_[starts, len(order)]
    for d, s0, s1 in zip(days.tolist(), bounds[:-1].tolist(), bounds[1:].tolist(), strict=True):
        if 0 <= d < n:
            idx = order[s0:s1]
            v = profile(cx.h[idx], cx.lo[idx], w[idx])
            for k in range(3):
                out[k][d] = v[k]
    return tuple(np.r_[np.nan, x[:-1]] for x in out)


# --- the 15m view ---------------------------------------------------------------------------------


class View:
    """15m bars with their trading day, clock, ATR, cut bars and the liquidity levels."""

    def __init__(self, cx: gl.Ctx, fr: dict[str, pd.DataFrame]):
        f = fr["15m"]
        self.f = f
        self.o, self.h, self.lo, self.c = (
            f[k].to_numpy() for k in ("open", "high", "low", "close")
        )
        self.spread = f["spread_mean"].to_numpy()
        self.atr = gl.wilder(self.h, self.lo, self.c)
        d1 = cx.d1["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
        ts = f["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
        self.day = np.searchsorted(d1, ts, "right") - 1
        self.omin = ha.clock(f)[0]
        cut, _ = ha.cut_bars(f, "DAY")
        idx = np.arange(len(f))
        nxt = pd.Series(np.where(cut, idx, np.nan)).bfill().to_numpy()
        self.deadline = np.where(np.isfinite(nxt), nxt, -1).astype(int)
        self.year = f["close_utc"].dt.year.to_numpy()
        # liquidity: previous day and week highs and lows, live 1h swings (on the 5m index)
        self.pdh = np.r_[np.nan, cx.d1["high"].to_numpy()[:-1]]
        self.pdl = np.r_[np.nan, cx.d1["low"].to_numpy()[:-1]]
        wk = gs.week_levels(cx)
        self.pwh, self.pwl = wk["PWH"], wk["PWL"]
        pts, start, end = fm._ends(cx, fm.swing_points(fr["1h"]))
        self.sw = pd.DataFrame({"level": pts["level"].to_numpy(), "start": start, "end": end})
        self.sw = self.sw.sort_values("start").reset_index(drop=True)
        t5 = cx.m["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
        close15 = (
            f["close_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
        )
        self.i5 = np.searchsorted(t5, close15, "left") - 1  # the 5m bar ending with the 15m bar

    def liquidity(self, t: int, d: float, entry: float) -> float:
        """The nearest liquidity level beyond ``entry`` in direction d at 15m bar t; NaN: none."""
        day = self.day[t]
        cands = [self.pdh[day], self.pdl[day], self.pwh[day], self.pwl[day]]
        i5 = self.i5[t]
        sw = self.sw
        a = np.searchsorted(sw["start"].to_numpy(), i5 - 3000, "left")
        b = np.searchsorted(sw["start"].to_numpy(), i5, "right")
        live = sw.iloc[a:b]
        cands += live.loc[live["end"].to_numpy() > i5, "level"].tolist()
        x = np.array([v for v in cands if np.isfinite(v) and d * (v - entry) > 0])
        return float(x[np.argmin(np.abs(x - entry))]) if len(x) else np.nan


# --- signals and trades ---------------------------------------------------------------------------


def signals(v: View, vah: np.ndarray, val: np.ndarray, poc: np.ndarray) -> pd.DataFrame:
    """The first RE-ENTRY and the first ACCEPTED signal of each trading day (levels by D1 bar)."""
    rows = []
    c, h, lo = v.c, v.h, v.lo
    cur, out_side, ext, inside_n, done_re = -1, 0, np.nan, 0, False
    run_side, run_n, fresh, done_br = 0, 0, False, False
    prev_inside_or_edge = {1: False, -1: False}
    for t in range(1, len(c) - 1):
        d = v.day[t]
        if d != cur:
            cur, out_side, ext, inside_n, done_re = d, 0, np.nan, 0, False
            run_side, run_n, fresh, done_br = 0, 0, False, False
            prev_inside_or_edge = {1: False, -1: False}
        if d < 0 or not np.isfinite(vah[d]):
            continue
        hi_, lo_, p_ = vah[d], val[d], poc[d]
        side = 1 if c[t] > hi_ else (-1 if c[t] < lo_ else 0)
        window = WIN_FROM <= v.omin[t] < WIN_TO and v.deadline[t] > t
        atr = v.atr[t]
        # RE-ENTRY
        if side != 0:
            if out_side != side:
                out_side, ext = side, (h[t] if side > 0 else lo[t])
            inside_n = 0
        elif out_side != 0:
            inside_n += 1
        if out_side != 0:
            ext = max(ext, h[t]) if out_side > 0 else min(ext, lo[t])
        if inside_n == 2 and out_side != 0 and not done_re and window:
            dr = -float(out_side)
            stop = ext + out_side * RE_PAD * atr
            rows.append(("REENTRY", t, dr, stop, p_))
            done_re = True
        # ACCEPTED
        if side != 0 and side == run_side:
            run_n += 1
        else:
            fresh = side != 0 and prev_inside_or_edge[side]
            run_side, run_n = side, 1 if side != 0 else 0
        if run_n == 2 and fresh and not done_br and window:
            dr = float(run_side)
            edge = hi_ if run_side > 0 else lo_
            stop = edge - dr * BREAK_PAD * atr
            rows.append(("ACCEPTED", t, dr, stop, np.nan))
            done_br = True
        prev_inside_or_edge = {1: c[t] <= hi_, -1: c[t] >= lo_}
    return pd.DataFrame(rows, columns=["setup", "i", "dir", "stop", "target"])


def simulate(v: View, sig: pd.DataFrame) -> pd.DataFrame:
    out = []
    for r in sig.itertuples(index=False):
        k, d = r.i + 1, r.dir
        e = v.o[k]
        risk = d * (e - r.stop)
        if not risk > 0:
            continue
        tgt = r.target if r.setup == "REENTRY" else v.liquidity(r.i, d, e)
        if not np.isfinite(tgt) or d * (tgt - e) <= 0:
            continue
        if r.setup == "ACCEPTED" and d * (tgt - e) < MIN_R * risk:
            continue
        cost = v.spread[k] + gl.COMMISSION
        if d * (tgt - e) < COST_X * cost:
            continue
        end = v.deadline[k]
        if end < k:
            continue
        hh, ll, oo = v.h[k : end + 1], v.lo[k : end + 1], v.o[k : end + 1]
        hit_sl = ll <= r.stop if d > 0 else hh >= r.stop
        hit_tp = hh >= tgt if d > 0 else ll <= tgt
        js = int(np.argmax(hit_sl)) if hit_sl.any() else -1
        jt = int(np.argmax(hit_tp)) if hit_tp.any() else -1
        if js >= 0 and (jt < 0 or js <= jt):
            px, why = (min(oo[js], r.stop) if d > 0 else max(oo[js], r.stop)), "stop"
            j = k + js
        elif jt >= 0:
            px, why, j = tgt, "target", k + jt
        else:
            px, why, j = v.c[end], "time", end
        gross = d * (px - e) / risk
        net = gross - cost / risk - (gl.SL_SLIP / risk if why == "stop" else 0.0)
        out.append((r.setup, r.i, k, j, d, risk, gross, cost / risk, net, why, v.year[r.i]))
    cols = ["setup", "i", "k", "j", "dir", "risk", "gross", "cost", "net", "exit", "year"]
    return pd.DataFrame(out, columns=cols)


def run_all(v: View, cx: gl.Ctx, shift: float = 0.0) -> dict[str, pd.DataFrame]:
    """Trades of the four cells; ``shift`` moves the value area by shift x its width."""
    out = {}
    for w in WEIGHTS:
        vah, val, poc = (x.copy() for x in v.prof[w])
        width = vah - val
        vah, val, poc = vah + shift * width, val + shift * width, poc + shift * width
        t = simulate(v, signals(v, vah, val, poc))
        for s in SETUPS:
            out[f"{s}-{w}"] = t[t["setup"] == s].reset_index(drop=True)
    return out


def blocks(v: View, k: np.ndarray) -> np.ndarray:
    m = v.f["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[m]")[k]
    return ((m - np.datetime64("2012-01-01T00:00", "m")).astype("int64") // mk.BLOCK_MIN).astype(
        int
    )


def prepare(fr: dict[str, pd.DataFrame]) -> tuple[View, gl.Ctx]:
    cx = gl.context(fr)
    v = View(cx, fr)
    v.prof = {w: previous_profiles(cx, w) for w in WEIGHTS}
    return v, cx


# --- report ---------------------------------------------------------------------------------------


def build(export: Path) -> str:
    v, cx = prepare(gl.load())
    real = run_all(v, cx)
    rng = np.random.default_rng(SEED)
    plc = {k: [] for k in real}
    for _ in range(COPIES):
        u = float(rng.uniform(-0.5, 0.5))
        for k, t in run_all(v, cx, u).items():
            plc[k].append(t)
    plc = {k: pd.concat(x, ignore_index=True) for k, x in plc.items()}
    lines = [
        "# Gold: value-area re-entry and accepted break, XAUUSD and FxPro",
        "",
        "_`python -m app research gold-vp2 build`, registered in `GOLD_VP2.md` (2026-11-12) "
        "before the run. Net R a trade with slip; shifted copies: the value area moved by "
        "u x its width, 200 copies; t from a 4-week block bootstrap._",
        "",
        "| Cell | Period | Trades | Net R | Gross R | Cost R | Years + | Win | Shifted copies "
        "| Excess t | Eligible |",
        "|" + " --- |" * 11,
    ]
    best, best_net = None, -np.inf
    for name, t in real.items():
        for per, (a, b) in (("2012-2021", (2012, TUNE_END)), ("2022 to 2026-01-09", (2022, 2026))):
            g = t[(t["year"] >= a) & (t["year"] <= b)]
            p = plc[name][(plc[name]["year"] >= a) & (plc[name]["year"] <= b)]
            if len(g) < 2 or len(p) < 2:
                lines.append(f"| {name} | {per} | {len(g)} | - | - | - | - | - | - | - | |")
                continue
            bg, bp = blocks(v, g["k"].to_numpy()), blocks(v, p["k"].to_numpy())
            off = min(bg.min(), bp.min())
            idx = mk.resamples(int(max(bg.max(), bp.max()) - off) + 1)
            ex, tt = mk.boot_t(idx, bg - off, g["net"].to_numpy(), bp - off, p["net"].to_numpy())
            yr = g.groupby("year")["net"].mean()
            elig = (
                per == "2012-2021"
                and g["net"].mean() > 0
                and (yr > 0).mean() >= 0.6
                and len(g) >= 300
                and ex > 0
            )
            if elig and g["net"].mean() > best_net:
                best, best_net = name, g["net"].mean()
            lines.append(
                f"| {name} | {per} | {len(g):,} | {g['net'].mean():+.3f} "
                f"| {g['gross'].mean():+.3f} | {g['cost'].mean():.3f} | {(yr > 0).mean():.0%} "
                f"| {(g['gross'] > 0).mean():.0%} | {p['net'].mean():+.3f} | {tt:+.2f} "
                f"| {'yes' if elig else ''} |"
            )
    lines.append("")
    if best is None:
        lines += ["**No cell qualifies on 2012-2021 (condition 1): dropped.**", ""]
    else:
        t = real[best]
        chk = t[t["year"] > TUNE_END]
        fx_fr = ge.frames_from_lines(gv.fx_lines(export))
        fv, fcx = prepare(fx_fr)
        ft = run_all(fv, fcx)[best]
        when = pd.to_datetime(fv.f["ts_utc"].to_numpy()[ft["k"]], utc=True)
        ft = ft[when >= gv.FX_START]
        ftd = ft.assign(tday=fv.day[ft["i"].to_numpy()])
        since = pd.to_datetime(fcx.m["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
        day = {
            k: d[since[d["i"]] >= np.datetime64(gv.FX_START.tz_convert(None))]
            for k, d in gn.day_strategies(fcx).items()
        }
        corr = gn.correlations(ftd, day)
        ok = [
            True,
            chk["net"].mean() > 0,
            ft["net"].mean() > 0,
            all(x < 0.2 for x in corr.values()),
        ]
        lines += [
            f"**Chosen {best}.** Check {chk['net'].mean():+.3f} ({len(chk):,}); FxPro "
            f"{ft['net'].mean():+.3f} ({len(ft):,}); correlation with the five "
            + ", ".join(f"{k} {x:+.2f}" for k, x in corr.items())
            + f". Conditions 1-4: {'/'.join('yes' if x else 'no' for x in ok)}. "
            f"**{'passes' if all(ok) else 'dropped'}.**",
            "",
        ]
    years = sorted(set().union(*[set(t["year"]) for t in real.values()]))
    lines += [
        "By year, net R:",
        "",
        "| Cell | " + " | ".join(map(str, years)) + " |",
        "|" + " --- |" * (1 + len(years)),
    ]
    for name, t in real.items():
        m = t.groupby("year")["net"].mean()
        lines.append(f"| {name} | " + " | ".join(f"{m.get(y, np.nan):+.3f}" for y in years) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-vp2")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
