"""Addendum 2 origin (`docs/strategies/ADDENDUM_2_LEVEL_BREAK.md`). Run from ai-service:
`uv run python tools/research/levels_explore.py`.

Exploratory (decides nothing, not a registered trial): do prices react to support and resistance
levels more than to arbitrary price levels? Six instruments, touches from 2018-01-01, bars only to
the holdout start (2024-07-01). Design fixed before any outcome was computed (2026-11-04).

Levels per New York trading day: previous day high and low (PDH, PDL), previous five days high and
low (5DH, 5DL), round numbers (gold every $10, FX every 50 pips, USDJPY every 0.50). Placebo: the
same day levels moved by a random 0.3-1.0 x ATR(14, D1) with a random sign; round numbers moved by
half a step. A touch is the first 5m bar of the day (02:00-16:00 New York, weekdays) that crosses a
level from the previous close. Distance D = ATR(14) of the last closed 1h bar. Bounce: price goes
D back to the side it came from before going D beyond (first passage, 48 bars = 4 h; the touch bar
counts only for the break side; a bar reaching both is ambiguous and left out). After a break:
continuation if price reaches 2D beyond before returning to the level. No costs in the rates; cost
in D = (mean spread of the touch bar + commission) / D."""

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

from app.strategies import frames as F
from app.strategies.counts import bounds

HZ = 48
START = pd.Timestamp("2018-01-01", tz="UTC")
_, holdout, _ = bounds()
rng = np.random.default_rng(20261104)
STEP = {"XAUUSD": 10.0, "USDJPY": 0.5}
SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]


def wilder(h, low, c, n=14):
    prev = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - low, np.abs(h - prev), np.abs(low - prev)], axis=1)
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def first_passage(hi, lo, i, lv, d, up):
    """Outcome of touches at bar i of level lv, approached from below (up=True) or above."""
    s = np.where(up, 1.0, -1.0)
    brk_t, bnc_t = lv + s * d, lv - s * d
    h0, l0 = hi[i], lo[i]
    brk0 = np.where(up, h0 >= brk_t, l0 <= brk_t)
    H, L = swv(hi, HZ)[i + 1], swv(lo, HZ)[i + 1]
    brk = np.where(up[:, None], H >= brk_t[:, None], L <= brk_t[:, None])
    bnc = np.where(up[:, None], L <= bnc_t[:, None], H >= bnc_t[:, None])
    fb = np.where(brk.any(1), brk.argmax(1), HZ)
    fn = np.where(bnc.any(1), bnc.argmax(1), HZ)
    out = np.where(
        fb < fn, "break", np.where(fn < fb, "bounce", np.where(fb == HZ, "none", "ambiguous"))
    )
    out = np.where(brk0, "break", out)
    jb = np.where(brk0, i, i + 1 + np.minimum(fb, HZ - 1))  # bar of the break
    # continuation after a break: 2D beyond before back to the level
    H2, L2 = (
        swv(hi, HZ)[np.minimum(jb + 1, len(hi) - HZ)],
        swv(lo, HZ)[np.minimum(jb + 1, len(hi) - HZ)],
    )
    far, back = lv + 2 * s * d, lv
    go = np.where(up[:, None], H2 >= far[:, None], L2 <= far[:, None])
    ret = np.where(up[:, None], L2 <= back[:, None], H2 >= back[:, None])
    fg = np.where(go.any(1), go.argmax(1), HZ)
    fr = np.where(ret.any(1), ret.argmax(1), HZ)
    cont = np.where(fg < fr, 1.0, np.where(fr < fg, 0.0, np.nan))
    cont = np.where(out == "break", cont, np.nan)
    return out, cont


rows = []
for sym in SYMBOLS:
    fr = F.load(sym, pd.Timestamp("2017-06-01", tz="UTC"), holdout)
    m, h1, d1 = fr["5m"], fr["1h"], fr["D1"]
    hi, lo, cl = (m[k].to_numpy() for k in ("high", "low", "close"))
    n = len(m)
    prev = np.r_[np.nan, cl[:-1]]
    a1 = wilder(*(h1[k].to_numpy() for k in ("high", "low", "close")))
    k1 = np.searchsorted(h1["close_utc"].to_numpy(), m["ts_utc"].to_numpy(), "right") - 1
    D = np.where(k1 >= 0, a1[np.maximum(k1, 0)], np.nan)
    ad = wilder(*(d1[k].to_numpy() for k in ("high", "low", "close")))
    kd = (
        np.searchsorted(d1["ts_utc"].to_numpy(), m["ts_utc"].to_numpy(), "right") - 1
    )  # current day
    dh, dl = d1["high"].to_numpy(), d1["low"].to_numpy()
    pdh = np.r_[np.nan, dh[:-1]]
    pdl = np.r_[np.nan, dl[:-1]]
    h5 = pd.Series(dh).rolling(5).max().shift(1).to_numpy()
    l5 = pd.Series(dl).rolling(5).min().shift(1).to_numpy()
    atrd = np.r_[np.nan, ad[:-1]]
    ny = m["ts_utc"].dt.tz_convert("America/New_York")
    ok = ((ny.dt.day_of_week < 5) & ny.dt.hour.between(2, 15)).to_numpy().copy()
    ok &= (
        (m["ts_utc"] >= START).to_numpy()
        & (np.arange(n) < n - 2 * HZ - 2)
        & np.isfinite(D)
        & (kd >= 6)
    )
    price = cl
    comm = 0.07 if sym == "XAUUSD" else (7e-5 * price if sym.startswith("USD") else 7e-5)
    cost = m["spread_mean"].to_numpy() + comm

    def events(level_of_day, name, placebo, kd=kd, prev=prev, hi=hi, lo=lo, ok=ok):
        lv = level_of_day[np.maximum(kd, 0)]
        up = (prev < lv) & (hi >= lv)
        dn = (prev > lv) & (lo <= lv)
        hit = ok & (up | dn) & np.isfinite(lv)
        idx = np.flatnonzero(hit)
        first = pd.Series(idx).groupby(kd[idx]).min().to_numpy()  # first touch of the day
        return pd.DataFrame(
            {"i": first, "lv": lv[first], "up": up[first], "kind": name, "placebo": placebo}
        )

    ev = []
    for name, arr in (("PDH", pdh), ("PDL", pdl), ("5DH", h5), ("5DL", l5)):
        ev.append(events(arr, name, False))
        off = rng.uniform(0.3, 1.0, len(arr)) * rng.choice([-1.0, 1.0], len(arr)) * atrd
        ev.append(events(arr + off, name, True))
    step = STEP.get(sym, 0.005)
    for placebo, shift in ((False, 0.0), (True, step / 2)):
        rows_r = []
        for up_side in (True, False):
            base = prev - shift
            lvl = (np.ceil(base / step) * step if up_side else np.floor(base / step) * step) + shift
            cross = (prev < lvl) & (hi >= lvl) if up_side else (prev > lvl) & (lo <= lvl)
            idx = np.flatnonzero(ok & cross)
            rows_r.append(pd.DataFrame({"i": idx, "lv": lvl[idx], "up": up_side, "day": kd[idx]}))
        r = pd.concat(rows_r).sort_values("i").drop_duplicates(["day", "lv"]).drop(columns="day")
        ev.append(r.assign(kind="ROUND", placebo=placebo))
    e = pd.concat(ev, ignore_index=True)
    i = e["i"].to_numpy()
    out, cont = first_passage(hi, lo, i, e["lv"].to_numpy(), D[i], e["up"].to_numpy())
    e = e.assign(
        symbol=sym, outcome=out, cont=cont, cost_d=cost[i] / D[i], t=m["ts_utc"].to_numpy()[i]
    )
    rows.append(e)

d = pd.concat(rows, ignore_index=True)
d["t"] = pd.to_datetime(d["t"], utc=True)
d["block"] = ((d["t"] - START).dt.days // 28).astype(int)
d["bounce"] = np.where(d.outcome == "bounce", 1.0, np.where(d.outcome == "break", 0.0, np.nan))


def diff_ci(g, col, B=2000):
    """Real minus placebo rate of ``col`` with a 4-week block bootstrap 95% interval."""
    x = g.dropna(subset=[col])
    agg = x.groupby(["block", "placebo"])[col].agg(["sum", "size"]).unstack(fill_value=0)
    s_r, n_r = agg[("sum", False)].to_numpy(), agg[("size", False)].to_numpy()
    s_p, n_p = agg[("sum", True)].to_numpy(), agg[("size", True)].to_numpy()
    k = rng.integers(0, len(agg), (B, len(agg)))
    dif = s_r[k].sum(1) / n_r[k].sum(1) - s_p[k].sum(1) / n_p[k].sum(1)
    real, plac = s_r.sum() / n_r.sum(), s_p.sum() / n_p.sum()
    lo_, hi_ = np.percentile(dif, [2.5, 97.5])
    return (
        f"{n_r.sum():6d} | {real:.3f} | {n_p.sum():6d} | {plac:.3f} | {real - plac:+.3f} "
        f"({lo_:+.3f} to {hi_:+.3f})"
    )


hdr = "n real | rate real | n placebo | rate placebo | real - placebo (95%)"
print("A. BOUNCE rate (bounce before break, D = 1 ATR 1h), by level type, all instruments")
print("level |", hdr)
for k, g in [*d.groupby("kind"), ("ALL", d)]:
    print(k, "|", diff_ci(g, "bounce"))
print("\nB. BOUNCE rate by instrument, all level types")
for k, g in d.groupby("symbol"):
    print(k, "|", diff_ci(g, "bounce"))
print("\nC. CONTINUATION after a break (2D beyond before back to the level), by level type")
for k, g in [*d.groupby("kind"), ("ALL", d)]:
    print(k, "|", diff_ci(g, "cont"))
print("\nD. CONTINUATION after a break, by instrument")
for k, g in d.groupby("symbol"):
    print(k, "|", diff_ci(g, "cont"))
print(
    "\nE. Outcome mix (real levels):",
    d[~d.placebo].outcome.value_counts(normalize=True).round(3).to_dict(),
)
print(
    "   Outcome mix (placebo)    :",
    d[d.placebo].outcome.value_counts(normalize=True).round(3).to_dict(),
)
print("\nF. Economics per touch in D (gross = 2p - 1 for a fade with TP = SL = D; cost in D)")
for k, g in d[~d.placebo].groupby("symbol"):
    p = g.bounce.mean()
    q = g.cont.mean()
    print(
        k,
        f"| fade gross {2 * p - 1:+.3f} | breakout gross {2 * q - 1:+.3f} "
        f"| cost {g.cost_d.mean():.3f}",
    )
print("\nG. Gold by year, bounce rate real vs placebo")
gy = d[d.symbol == "XAUUSD"].groupby([d.t.dt.year, "placebo"]).bounce.mean().unstack().round(3)
print(gy.to_string())
