"""Break and rejection signals of a family (``docs/levels/SPEC.md`` §3-4), decided at the close of a
5m bar from that bar and earlier ones only.

- **Break** up: previous close <= L and close > L + b (b = 0.25 x ATR(14, 5m)); down mirrored. If
  several levels are broken, the farthest one counts.
- **Rejection:** the bar trades through L from the previous close's side and closes within
  tau = 0.05 x ATR of L (the level nearest the close). From below: sell; from above: buy.
- **Target and stop (both behaviours, trade direction d):** target = the next level of the same
  family beyond L in direction d; stop = the midpoint between L and the next level on the other
  side. No neighbour on either side: no signal."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.levels import families as fm
from app.research import gold_lab as gl

COLS = ["family", "kind", "behaviour", "i", "dir", "level", "target", "stop"]


def _frame(fam, behaviour, i, d, lv, tgt, stp) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "i": np.asarray(i, int),
            "dir": np.asarray(d, float),
            "level": lv,
            "target": tgt,
            "stop": stp,
        }
    )
    out.insert(0, "behaviour", behaviour)
    out.insert(0, "kind", fam.kind)
    out.insert(0, "family", fam.name)
    ok = np.isfinite(out[["level", "target", "stop"]]).all(axis=1)
    return out[ok][COLS].reset_index(drop=True)


# --- lattices -------------------------------------------------------------------------------------


def lattice_signals(cx: gl.Ctx, fam: fm.Lattice) -> pd.DataFrame:
    c, h, lo = cx.c, cx.h, cx.lo
    prev = np.r_[np.nan, c[:-1]]
    b, tau = fm.B_ATR * cx.atr5, fm.TAU_ATR * cx.atr5
    o, s = fam.origin, fam.step
    fx = np.log if fam.log else (lambda v: v)
    fp = np.exp if fam.log else (lambda v: v)

    def level(k):
        return fp(o + k * s)

    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(o) & np.isfinite(s) & (s > 0) & np.isfinite(prev)
        ku = np.floor((fx(c - b) - o) / s)
        lu = level(ku)
        up = ok & (lu >= prev) & (c > lu + b)
        kd = np.ceil((fx(c + b) - o) / s)
        ld = level(kd)
        dn = ok & (ld <= prev) & (c < ld - b)
        kr = np.round((fx(c) - o) / s)
        lr = level(kr)
        near = ok & (np.abs(c - lr) <= tau)
        from_below = near & (prev < lr) & (h >= lr)
        from_above = near & (prev > lr) & (lo <= lr)

    def at(k, i):
        return fp(o[i] + k * s[i])

    parts = []
    for mask, kk, d in ((up, ku, 1.0), (dn, kd, -1.0), (from_below & ~from_above, kr, -1.0),
                        (from_above & ~from_below, kr, 1.0)):  # fmt: skip
        i = np.flatnonzero(mask)
        k = kk[i]
        beh = "break" if kk is not kr else "rejection"
        lv = at(k, i)
        parts.append(_frame(fam, beh, i, np.full(len(i), d), lv, at(k + d, i),
                            (lv + at(k - d, i)) / 2))  # fmt: skip
    return pd.concat(parts, ignore_index=True).sort_values(["i", "behaviour"], kind="stable")


# --- discrete families ----------------------------------------------------------------------------


def _touches(cx: gl.Ctx, recs: pd.DataFrame) -> pd.DataFrame:
    """Every (bar, level, behaviour, dir) where a live level is broken or rejected."""
    c, h, lo = cx.c, cx.h, cx.lo
    b, tau = fm.B_ATR * cx.atr5, fm.TAU_ATR * cx.atr5
    rows = []
    for lv, a, e in zip(
        recs["level"].to_numpy(), recs["start"].to_numpy(), recs["end"].to_numpy(), strict=True
    ):
        a = max(int(a), 1)
        if e <= a:
            continue
        cc, pp = c[a:e], c[a - 1 : e - 1]
        hh, ll, bb, tt = h[a:e], lo[a:e], b[a:e], tau[a:e]
        idx = np.arange(a, e)
        for m, beh, d in (
            ((pp <= lv) & (cc > lv + bb), "break", 1.0),
            ((pp >= lv) & (cc < lv - bb), "break", -1.0),
            ((pp < lv) & (hh >= lv) & (np.abs(cc - lv) <= tt), "rejection", -1.0),
            ((pp > lv) & (ll <= lv) & (np.abs(cc - lv) <= tt), "rejection", 1.0),
        ):
            k = idx[m]
            if len(k):
                rows.append(pd.DataFrame({"i": k, "level": lv, "behaviour": beh, "dir": d}))
    if not rows:
        return pd.DataFrame(columns=["i", "level", "behaviour", "dir"])
    return pd.concat(rows, ignore_index=True)


def discrete_signals(cx: gl.Ctx, fam: fm.Discrete) -> pd.DataFrame:
    recs = fam.recs
    t = _touches(cx, recs)
    if t.empty:
        return pd.DataFrame(columns=COLS)
    # one per bar and behaviour: a break at the farthest level, a rejection at the nearest one
    t["far"] = t["dir"] * t["level"]
    t["dist"] = np.abs(cx.c[t["i"].to_numpy()] - t["level"])
    brk = t[t["behaviour"] == "break"].sort_values(["i", "far"]).groupby("i").tail(1)
    rej = t[t["behaviour"] == "rejection"].sort_values(["i", "dist"]).groupby("i").head(1)
    t = pd.concat([brk, rej]).sort_values("i", kind="stable")
    st, en, lvl = recs["start"].to_numpy(), recs["end"].to_numpy(), recs["level"].to_numpy()
    span = int((en - st).max()) if len(st) else 0
    tgt, stp = np.full(len(t), np.nan), np.full(len(t), np.nan)
    for q, (i, lv, d) in enumerate(
        zip(t["i"].to_numpy(), t["level"].to_numpy(), t["dir"].to_numpy(), strict=True)
    ):
        a, z = np.searchsorted(st, i - span, "left"), np.searchsorted(st, i, "right")
        live = lvl[a:z][en[a:z] > i]
        ahead = live[d * (live - lv) > 1e-9]
        behind = live[d * (live - lv) < -1e-9]
        if len(ahead) and len(behind):
            nxt = ahead[np.argmin(np.abs(ahead - lv))]
            back = behind[np.argmin(np.abs(behind - lv))]
            tgt[q], stp[q] = nxt, (lv + back) / 2
    return _frame(
        fam,
        t["behaviour"].to_numpy(),
        t["i"].to_numpy(),
        t["dir"].to_numpy(),
        t["level"].to_numpy(),
        tgt,
        stp,
    )


def signals(cx: gl.Ctx, fam: fm.Lattice | fm.Discrete) -> pd.DataFrame:
    return lattice_signals(cx, fam) if isinstance(fam, fm.Lattice) else discrete_signals(cx, fam)
