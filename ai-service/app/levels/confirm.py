"""Confirmed breaks and rejections: a screen of 15 methods (``docs/levels/CONFIRM_SCREEN.md``,
registered 2026-11-12 before any outcome).

    python -m app levels confirm

XAUUSD 5m, 2024-01-01 to 2026-01-09; 17 families (13 real, 4 round); each method's trades (all
families pooled) against 200 shifted copies of the families."""

from __future__ import annotations

import multiprocessing as mp
import os

import numpy as np
import pandas as pd

from app.discovery import markout as mk
from app.levels import discover as dc
from app.levels import families as fm
from app.research import gold_lab as gl
from app.research import gold_magnet as gm

REPORT = dc.ROOT / "docs" / "levels" / "confirm_screen_result.md"
FROM, TO = pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2026-01-10", tz="UTC")
BREAKS = ("B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8")
REJECTS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
METHODS = BREAKS + REJECTS
B, PAD = fm.B_ATR, 0.1
COPIES, SEED = 200, 20261119
WORKERS = int(os.environ.get("LEVELS_WORKERS", "2"))
WIN_FROM, WIN_TO = 2 * 60, 13 * 60
OPEN_HOURS = ((180, 240), (570, 630))
_W: dict = {}


# --- base events ----------------------------------------------------------------------------------


def _frame(rows: list) -> pd.DataFrame:
    cols = ["i", "kind", "d", "level", "target", "behind"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.concat([pd.DataFrame(r, columns=cols) for r in rows], ignore_index=True)


def base_discrete(cx: gl.Ctx, fam: fm.Discrete, days: np.ndarray) -> pd.DataFrame:
    """Per bar: the farthest break and the nearest rejection of the family's live levels, with
    the next live level ahead (target) and behind, in the trade's direction."""
    recs = fam.recs
    if recs.empty:
        return _frame([])
    st, en, lvl = (recs[k].to_numpy() for k in ("start", "end", "level"))
    span = int((en - st).max())
    first, end = fm.day_bounds(cx)
    c, h, lo, bb = cx.c, cx.h, cx.lo, B * cx.atr5
    rows = []
    for d in days:
        a, e = max(int(first[d]), 1), int(end[d])
        if first[d] < 0 or e <= a:
            continue
        sel = np.arange(np.searchsorted(st, a - span, "left"), np.searchsorted(st, e, "left"))
        sel = sel[en[sel] > a]
        if not len(sel):
            continue
        L, S, E = lvl[sel][None, :], st[sel][None, :], en[sel][None, :]
        idx = np.arange(a, e)
        col = idx[:, None]
        live = (S <= col) & (E > col)
        pp, cc = c[idx - 1][:, None], c[idx][:, None]
        hh, ll, b_ = h[idx][:, None], lo[idx][:, None], bb[idx][:, None]
        up = live & (pp <= L) & (cc > L + b_)
        dn = live & (pp >= L) & (cc < L - b_)
        rs = live & (pp < L) & (hh >= L) & (cc < L)
        rb = live & (pp > L) & (ll <= L) & (cc > L)
        far = np.where(up, L, np.where(dn, -L, -np.inf))
        r = np.flatnonzero(np.isfinite(far.max(axis=1)))
        picks = []
        if len(r):
            k = far[r].argmax(axis=1)
            picks.append(("break", r, k, np.where(up[r, k], 1.0, -1.0)))
        dist = np.where(rs | rb, np.abs(cc - L), np.inf)
        r = np.flatnonzero(np.isfinite(dist.min(axis=1)))
        if len(r):
            k = dist[r].argmin(axis=1)
            picks.append(("reject", r, k, np.where(rs[r, k], -1.0, 1.0)))
        for kind, r, k, dr in picks:
            lv = L[0, k]
            diff = dr[:, None] * (L - lv[:, None])
            m = live[r]
            ahead = np.where(m & (diff > 1e-9), diff, np.inf)
            behind = np.where(m & (diff < -1e-9), -diff, np.inf)
            ka, kb = ahead.argmin(axis=1), behind.argmin(axis=1)
            n = np.arange(len(r))
            tgt = np.where(np.isfinite(ahead[n, ka]), L[0, ka], np.nan)
            bhd = np.where(np.isfinite(behind[n, kb]), L[0, kb], np.nan)
            rows.append(
                [
                    (int(idx[x]), kind, float(dr[q]), float(lv[q]), float(tgt[q]), float(bhd[q]))
                    for q, x in enumerate(r)
                ]
            )
    return _frame(rows)


def base_lattice(cx: gl.Ctx, fam: fm.Lattice) -> pd.DataFrame:
    c, h, lo = cx.c, cx.h, cx.lo
    prev = np.r_[np.nan, c[:-1]]
    b = B * cx.atr5
    o, s = fam.origin, fam.step
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(o) & np.isfinite(s) & (s > 0) & np.isfinite(prev)
        lu = o + np.floor((c - b - o) / s) * s
        up = ok & (lu >= prev) & (c > lu + b)
        ld = o + np.ceil((c + b - o) / s) * s
        dn = ok & (ld <= prev) & (c < ld - b)
        lr = o + (np.floor((prev - o) / s) + 1) * s  # the first level above the last close
        res = ok & (h >= lr) & (c < lr)
        ls = o + (np.ceil((prev - o) / s) - 1) * s  # the first below
        sup = ok & (lo <= ls) & (c > ls)
    both = res & sup
    res, sup = res & ~both, sup & ~both
    rows = []
    for kind, mask, lv, d in (
        ("break", up, lu, 1.0),
        ("break", dn, ld, -1.0),
        ("reject", res, lr, -1.0),
        ("reject", sup, ls, 1.0),
    ):
        i = np.flatnonzero(mask)
        rows.append(
            pd.DataFrame(
                {
                    "i": i,
                    "kind": kind,
                    "d": d,
                    "level": lv[i],
                    "target": lv[i] + d * s[i],
                    "behind": lv[i] - d * s[i],
                }
            )
        )
    out = pd.concat(rows, ignore_index=True)
    return out.sort_values(["i", "kind"], kind="stable").reset_index(drop=True)


# --- indicators -----------------------------------------------------------------------------------


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100 - 100 / (1 + up / dn)


class Ind:
    def __init__(self, cx: gl.Ctx, h1: pd.DataFrame | None):
        self.atr = cx.atr5
        tv = cx.m["tick_volume"].to_numpy(float) if "tick_volume" in cx.m else np.ones(len(cx.c))
        self.tv = tv
        self.tv20 = pd.Series(tv).rolling(20).mean().shift(1).to_numpy()
        self.trend = gm.trend_1h(cx, h1) if h1 is not None else np.zeros(len(cx.c))
        self.rsi = rsi(cx.c)
        self.day_first = fm.day_bounds(cx)[0]


# --- the methods ----------------------------------------------------------------------------------


def methods(cx: gl.Ctx, ind: Ind, ev: pd.DataFrame) -> pd.DataFrame:
    """The 15 methods' signals: confirming bar i, direction, stop, target."""
    o, h, lo, c, atr = cx.o, cx.h, cx.lo, cx.c, ind.atr
    n = len(c)
    out = []

    def add(m, i, d, stop, tgt):
        out.append((m, int(i), float(d), float(stop), float(tgt)))

    def far_stop(j, d):
        return lo[j] - PAD * atr[j] if d > 0 else h[j] + PAD * atr[j]

    brk = ev[ev["kind"] == "break"]
    for i, d, L, tgt, bhd in zip(
        brk["i"], brk["d"], brk["level"], brk["target"], brk["behind"], strict=True
    ):
        if i < 50 or i + 2 >= n:
            continue
        if d * (c[i + 1] - L) > 0:
            add("B1", i + 1, d, far_stop(i + 1, d), tgt)
        lim = min(i + 24, n - 2)
        k0 = -1
        for k in range(i + 1, lim + 1):
            if d * (c[k] - L) < -B * atr[k]:
                break
            if k0 < 0 and (lo[k] <= L + PAD * atr[k] if d > 0 else h[k] >= L - PAD * atr[k]):
                k0 = k
            if k0 >= 0 and d * (c[k] - L) >= B * atr[k]:
                ext = (
                    lo[k0 : k + 1].min() - PAD * atr[k]
                    if d > 0
                    else h[k0 : k + 1].max() + PAD * atr[k]
                )
                add("B2", k, d, ext, tgt)
                break
        rng = h[i] - lo[i]
        body = d * (c[i] - o[i])
        outer = ((c[i] - lo[i]) if d > 0 else (h[i] - c[i])) / rng if rng > 0 else 0.0
        if rng > 0 and body >= atr[i] and outer >= 0.75:
            add("B3", i, d, far_stop(i, d), tgt)
        if np.isfinite(ind.tv20[i]) and ind.tv[i] >= 1.5 * ind.tv20[i]:
            add("B4", i, d, far_stop(i, d), tgt)
        w = slice(i - 12, i)
        if np.all(np.abs(c[w] - L) <= atr[i]) and h[w].max() - lo[w].min() <= 2 * atr[i]:
            add("B5", i, d, far_stop(i, d), tgt)
        a = int(ind.day_first[cx.day_idx[i]]) if cx.day_idx[i] >= 0 else i
        seg = slice(max(a, 0), i)
        if i > a:
            touched = (h[seg] >= L) & (c[seg] <= L) if d > 0 else (lo[seg] <= L) & (c[seg] >= L)
            if touched.any():
                add("B6", i, d, far_stop(i, d), tgt)
        if ind.trend[i] == d:
            add("B7", i, d, far_stop(i, d), tgt)
        if any(f <= cx.ny_min[i] < t for f, t in OPEN_HOURS):
            add("B8", i, d, far_stop(i, d), tgt)
        for k in range(i + 1, min(i + 3, n - 2) + 1):  # R4: a failed break
            if d * (c[k] - L) < 0:
                ext = (
                    h[i : k + 1].max() + PAD * atr[k]
                    if d > 0
                    else lo[i : k + 1].min() - PAD * atr[k]
                )
                add("R4", k, -d, ext, bhd)
                break
    rej = ev[ev["kind"] == "reject"]
    last: dict[tuple[float, float], int] = {}
    for i, d, L, tgt in zip(rej["i"], rej["d"], rej["level"], rej["target"], strict=True):
        if i < 50 or i + 1 >= n:
            continue
        wick_stop = lo[i] - PAD * atr[i] if d > 0 else h[i] + PAD * atr[i]
        key = (round(L, 6), d)
        j = last.get(key, -1)
        if j >= 0 and 2 <= i - j <= 48:
            mid = slice(j + 1, i)
            away = (
                (h[mid].max() >= L + 0.5 * atr[i]) if d > 0 else (lo[mid].min() <= L - 0.5 * atr[i])
            )
            if i - j > 1 and away:
                st = min(lo[j], lo[i]) - PAD * atr[i] if d > 0 else max(h[j], h[i]) + PAD * atr[i]
                add("R1", i, d, st, tgt)
        last[key] = i
        body = abs(c[i] - o[i])
        rng = h[i] - lo[i]
        wick = min(o[i], c[i]) - lo[i] if d > 0 else h[i] - max(o[i], c[i])
        if rng > 0 and wick >= 2 * body and wick >= 0.6 * rng:
            add("R2", i, d, wick_stop, tgt)
        if (
            d * (c[i] - o[i]) > 0
            and d * (c[i - 1] - o[i - 1]) < 0
            and max(o[i], c[i]) >= max(o[i - 1], c[i - 1])
            and min(o[i], c[i]) <= min(o[i - 1], c[i - 1])
        ):
            add("R3", i, d, wick_stop, tgt)
        if d < 0:
            div = h[i] >= h[i - 48 : i].max() and ind.rsi[i] < ind.rsi[i - 48 : i - 2].max()
        else:
            div = lo[i] <= lo[i - 48 : i].min() and ind.rsi[i] > ind.rsi[i - 48 : i - 2].min()
        if div:
            add("R5", i, d, wick_stop, tgt)
        if -d * (c[i - 1] - c[i - 13]) >= 3 * atr[i]:
            add("R6", i, d, wick_stop, tgt)
        if ind.trend[i] == d:
            add("R7", i, d, wick_stop, tgt)
    return pd.DataFrame(out, columns=["method", "i", "d", "stop", "target"])


# --- trades ---------------------------------------------------------------------------------------


def simulate(cx: gl.Ctx, sig: pd.DataFrame, family: str) -> pd.DataFrame:
    o, h, lo, c = cx.o, cx.h, cx.lo, cx.c
    out = []
    for m, g in sig.sort_values("i", kind="stable").groupby("method", sort=False):
        busy = -1
        for r in g.itertuples(index=False):
            i, d = int(r.i), float(r.d)
            k = i + 1
            if k <= busy or k >= len(c) or not (WIN_FROM <= cx.ny_min[i] < WIN_TO):
                continue
            end = int(cx.deadline[k])
            if end < k or cx.ny_day[k] != cx.ny_day[i]:
                continue
            e = o[k]
            risk = d * (e - r.stop)
            cost = cx.spread[k] + gl.COMMISSION
            if not (risk > 0 and np.isfinite(r.target) and d * (r.target - e) >= 3 * cost):
                continue
            hh, ll, oo = h[k : end + 1], lo[k : end + 1], o[k : end + 1]
            hit_sl = ll <= r.stop if d > 0 else hh >= r.stop
            hit_tp = hh >= r.target if d > 0 else ll <= r.target
            js = int(np.argmax(hit_sl)) if hit_sl.any() else -1
            jt = int(np.argmax(hit_tp)) if hit_tp.any() else -1
            if js >= 0 and (jt < 0 or js <= jt):
                px = min(oo[js], r.stop) if d > 0 else max(oo[js], r.stop)
                j, why = k + js, "stop"
            elif jt >= 0:
                px, j, why = r.target, k + jt, "target"
            else:
                px, j, why = c[end], end, "time"
            busy = j
            gross = d * (px - e) / risk
            net = gross - cost / risk - (gl.SL_SLIP / risk if why == "stop" else 0.0)
            out.append((family, m, i, k, j, gross, net, why))
    cols = ["family", "method", "i", "k", "j", "gross", "net", "exit"]
    return pd.DataFrame(out, columns=cols)


def run(cx: gl.Ctx, ind: Ind, fams: list, days: np.ndarray, in_period: np.ndarray) -> pd.DataFrame:
    parts = []
    for fam in fams:
        ev = base_lattice(cx, fam) if isinstance(fam, fm.Lattice) else base_discrete(cx, fam, days)
        ev = ev[in_period[ev["i"].to_numpy().astype(int)]] if len(ev) else ev
        sig = methods(cx, ind, ev)
        if len(sig):
            parts.append(simulate(cx, sig, fam.name))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# --- the screen -----------------------------------------------------------------------------------


def setup() -> tuple:
    fr = gl.load()
    cx = gl.context(fr)
    fams = [*fm.real(cx, fr), *[fm.rnd(cx, d) for d in fm.RND_STEPS]]
    t = pd.to_datetime(cx.m["close_utc"].to_numpy(), utc=True)
    in_period = np.asarray((t >= FROM) & (t < TO))
    days = dc.period_days(cx, in_period)
    return cx, Ind(cx, fr["1h"]), fams, days, in_period


def _init() -> None:
    _W["cx"], _W["ind"], _W["fams"], _W["days"], _W["in"] = setup()


def _copy(job: tuple) -> pd.DataFrame:
    q, us, sp = job
    fams = [dc.shift(f, us[f.name], sp.get(f.name, 0.0)) for f in _W["fams"]]
    t = run(_W["cx"], _W["ind"], fams, _W["days"], _W["in"])
    if t.empty:
        return t
    t["blk"] = blocks(_W["cx"], t["k"].to_numpy())
    g = t.groupby(["method", "blk"]).agg(s=("net", "sum"), n=("net", "size")).reset_index()
    return g.assign(copy=q)


def blocks(cx: gl.Ctx, k: np.ndarray) -> np.ndarray:
    m = cx.m["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[m]")
    start = np.datetime64(FROM.tz_convert(None), "m")
    return ((m[k] - start).astype("int64") // mk.BLOCK_MIN).astype(int)


def main() -> int:
    cx, ind, fams, days, in_period = setup()
    real = run(cx, ind, fams, days, in_period)
    real["blk"] = blocks(cx, real["k"].to_numpy())
    sp = dc.spacings(cx, fams, in_period)
    rng = np.random.default_rng(SEED)
    jobs = [(q, {f.name: float(rng.uniform(0.0, 1.0)) for f in fams}, sp) for q in range(COPIES)]
    with mp.Pool(WORKERS, initializer=_init) as pool:
        parts = pool.map(_copy, jobs, chunksize=1)
    plc = pd.concat([p for p in parts if len(p)], ignore_index=True)
    nb = int(blocks(cx, np.array([np.flatnonzero(in_period)[-1]]))[0]) + 1
    idx = mk.resamples(nb)
    n_days = len(np.unique(cx.ny_day[in_period & (cx.weekday < 5)]))
    lines = [
        "# Confirmed breaks and rejections: the screen (XAUUSD 2024 to 2026-01-09)",
        "",
        "_`python -m app levels confirm`, registered in `CONFIRM_SCREEN.md` (2026-11-12) "
        "before the run. 17 families pooled per method; net R a trade with slip; shifted = "
        "the same rules on 200 shifted copies of the families; t from a 4-week block "
        "bootstrap. Pass: net > 0 and t >= 1.5._",
        "",
        "| Method | Trades | A day | Win | Gross R | Net R | Shifted copies | t | Passes |",
        "|" + " --- |" * 9,
    ]
    for m in METHODS:
        r = real[real["method"] == m]
        p = plc[plc["method"] == m]
        if len(r) < 2 or p["n"].sum() < 2:
            lines.append(f"| {m} | {len(r)} | - | - | - | - | - | - | |")
            continue
        ra = np.bincount(r["blk"], r["net"], minlength=nb)[:nb]
        rn = np.bincount(r["blk"], minlength=nb)[:nb].astype(float)
        pa = np.bincount(p["blk"], p["s"], minlength=nb)[:nb]
        pn = np.bincount(p["blk"], p["n"], minlength=nb)[:nb].astype(float)
        mr, mp_ = ra.sum() / rn.sum(), pa.sum() / pn.sum()
        with np.errstate(invalid="ignore", divide="ignore"):
            star = ra[idx].sum(1) / rn[idx].sum(1) - pa[idx].sum(1) / pn[idx].sum(1)
        se = np.nanstd(star, ddof=1)
        t = (mr - mp_) / se if se > 0 else np.nan
        ok = mr > 0 and t >= 1.5
        lines.append(
            f"| {m} | {len(r):,} | {len(r) / n_days:.2f} | {(r['gross'] > 0).mean():.0%} "
            f"| {r['gross'].mean():+.3f} | {mr:+.3f} | {mp_:+.3f} | {t:+.2f} "
            f"| {'**yes**' if ok else ''} |"
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
