"""Entries and trades of the level families (``docs/levels/SPEC.md`` §4-5).

Prices are bid 5m bars, as ``gold_lab``: entry at the next bar's open, the stop and target checked
bar by bar (a bar reaching both counts as the stop; a gap through the stop fills at the open), the
cost charged as R (Raw: the entry bar's spread + $0.07, + $0.10 on stop exits; Standard: no
commission, spread at least $0.35, + $0.10 on stop exits)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.research import gold_lab as gl

ENTRY_FROM, ENTRY_TO, EOD = 2 * 60, 13 * 60, 13 * 60  # New York minutes (D12)
HOLD = 60  # 5 hours of 5m bars (D9)
TARGET_COST, STOP_COST = 3.0, 1.5  # SPEC §4 (D8)
COMMISSION, SLIP, STD_SPREAD = 0.07, 0.10, 0.35  # D10


def deadline(cx: gl.Ctx, minute: int = EOD) -> np.ndarray:
    """Per bar: the last bar of its New York day that closes by ``minute``; -1 if none."""
    close_ny = cx.m["close_utc"].dt.tz_convert(gl.NY)
    cmin = (close_ny.dt.hour * 60 + close_ny.dt.minute).to_numpy()
    same = (
        close_ny.dt.normalize() == cx.m["ts_utc"].dt.tz_convert(gl.NY).dt.normalize()
    ).to_numpy()
    ok = (cmin <= minute) & same
    idx = np.arange(len(cx.c))
    return pd.Series(np.where(ok, idx, -1)).groupby(cx.ny_day).transform("max").to_numpy()


def entries(cx: gl.Ctx, sig: pd.DataFrame, dl: np.ndarray | None = None) -> pd.DataFrame:
    """The signals that become orders: in the window, the target and stop on the right sides of
    the entry, and far enough from it for the cost."""
    dl = deadline(cx) if dl is None else dl
    i = sig["i"].to_numpy()
    k = i + 1
    n = len(cx.c)
    ok = k < n
    k = np.minimum(k, n - 1)
    ok &= (cx.ny_day[k] == cx.ny_day[i]) & (cx.weekday[i] < 5)
    ok &= (cx.ny_min[i] >= ENTRY_FROM) & (cx.ny_min[i] < ENTRY_TO) & (dl[k] >= k)
    e = cx.o[k]
    d = sig["dir"].to_numpy()
    tgt, stp = sig["target"].to_numpy(), sig["stop"].to_numpy()
    cost = cx.spread[k] + COMMISSION
    with np.errstate(invalid="ignore"):
        ok &= (d * (tgt - e) >= TARGET_COST * cost) & (d * (e - stp) >= STOP_COST * cost)
    out = sig[ok].copy()
    kk, ee = k[ok], e[ok]
    out["k"], out["entry"] = kk, ee
    out["risk"] = np.abs(ee - stp[ok])
    out["m"] = np.abs(tgt[ok] - ee) / out["risk"]
    out["cost_raw"] = (cx.spread[kk] + COMMISSION) / out["risk"]
    out["cost_std"] = np.maximum(cx.spread[kk], STD_SPREAD) / out["risk"]
    out["end"] = dl[kk]
    out["year"] = pd.to_datetime(cx.m["close_utc"].to_numpy()[i[ok]], utc=True).year
    return out.reset_index(drop=True)


def _first(mask: np.ndarray) -> int:
    k = int(np.argmax(mask)) if len(mask) else 0
    return k if len(mask) and mask[k] else -1


def one_trade(
    cx: gl.Ctx, k: int, end: int, d: float, e: float, stop: float, target: float
) -> tuple[int, float, str]:
    """(exit bar, exit price, reason) of one trade from bar k (its entry at the open) to ``end``."""
    risk = abs(e - stop)
    sl = stop
    h5 = k + HOLD - 1
    for a, b, phase in ((k, min(h5, end), 1), (h5 + 1, end, 2)):
        if b < a:
            break
        hh, ll, oo = cx.h[a : b + 1], cx.lo[a : b + 1], cx.o[a : b + 1]
        hit_sl = ll <= sl if d > 0 else hh >= sl
        hit_tp = hh >= target if d > 0 else ll <= target
        js, jt = _first(hit_sl), _first(hit_tp)
        if js >= 0 and (jt < 0 or js <= jt):
            px = min(oo[js], sl) if d > 0 else max(oo[js], sl)
            return a + js, px, "stop"
        if jt >= 0:
            return a + jt, target, "target"
        if phase == 1:
            if end <= h5:
                return end, cx.c[end], "eod"
            if d * (cx.c[h5] - e) >= risk:  # the 5-hour rule: +1 R or more: lock +1 R and run
                sl = e + d * risk
            else:
                return h5, cx.c[h5], "5h"
    return end, cx.c[end], "eod"


def simulate(cx: gl.Ctx, ent: pd.DataFrame) -> pd.DataFrame:
    """One open trade per family and behaviour; a signal while one is open is skipped."""
    out = []
    for (fam, beh), g in ent.sort_values("k").groupby(["family", "behaviour"], sort=False):
        busy = -1
        for r in g.itertuples(index=False):
            if r.k <= busy or r.end < r.k:
                continue
            j, px, why = one_trade(cx, int(r.k), int(r.end), r.dir, r.entry, r.stop, r.target)
            busy = j
            gross = r.dir * (px - r.entry) / r.risk
            slip = SLIP / r.risk if why == "stop" else 0.0
            out.append(
                (
                    fam,
                    r.kind,
                    beh,
                    r.i,
                    int(r.k),
                    j,
                    r.dir,
                    r.risk,
                    r.m,
                    gross,
                    gross - r.cost_raw - slip,
                    gross - r.cost_std - slip,
                    why,
                    r.year,
                )
            )
    cols = [
        "family",
        "kind",
        "behaviour",
        "i",
        "k",
        "j",
        "dir",
        "risk",
        "m",
        "gross",
        "net",
        "net_std",
        "exit",
        "year",
    ]
    return pd.DataFrame(out, columns=cols)
