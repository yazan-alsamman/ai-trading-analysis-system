"""Gold: filters on the AH bot's leg exits (X1), then meta-labeling (commercial track,
exploratory; ``docs/strategies/GOLD_AHF.md`` has the rules, registered before any run).

    python -m app research gold-ahf screen                 # stages 1-2 on XAUUSD, D and V
    python -m app research gold-ahf meta                   # stage 3, only if stage 2 passed
    python -m app research gold-ahf check --export <GOLD M1 export>   # stage 4, once

Every signal is a trade (no skip while one is open, ``GOLD_AHF.md`` §2); trades are simulated by
``gold_ah.simulate_one`` with X1's leg exits.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import splits
from app.research import gold_ah as ah
from app.strategies.cli import OUT_DIR

SEED = 20261109
BOOT = 2_000
SHUFFLES = 50
D_PERIOD = (pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2018-01-01", tz="UTC"))
V_PERIOD = (pd.Timestamp("2018-01-01", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC"))
C_START = pd.Timestamp("2022-01-01", tz="UTC")
F_START = pd.Timestamp("2022-02-01", tz="UTC")
BOT_WEEKS = (pd.Timestamp("2026-10-14", tz="UTC"), pd.Timestamp("2026-11-06", tz="UTC"))
MIN_KEEP_1 = 0.20
MIN_KEEP = 0.10
MAX_CONDS = 3
MIN_LEVEL = 0.01
NY = ah.NY
X1 = ah.SETTINGS_X[0]
SCREEN = OUT_DIR / "gold_ahf_screen.md"
META = OUT_DIR / "gold_ahf_meta.md"
CHECK = OUT_DIR / "gold_ahf_check.md"
STATE = OUT_DIR / "gold_ahf_state.json"

CATEGORICAL = ["hour", "weekday", "session"]
NUMERIC = [
    "mins_left",
    "news_window",
    "vol_m1_1d",
    "vol_1d_20d",
    "atr_d_bp",
    "atr_d_pct",
    "day_used",
    "rng10_atr",
    "ret10",
    "ret60",
    "ret240",
    "ret1440",
    "ret_5d",
    "ema_gap",
    "dist_ema50",
    "htf_ema",
    "er60",
    "pos_day",
    "pos_5d",
    "prev_day_dir",
    "k5",
    "pos60",
    "pull_depth",
    "pull_bars",
    "ret3",
    "sig_body",
    "sig_range",
    "leg_atr",
    "leg_d",
    "leg_bars",
    "leg_speed",
    "rw_p",
    "sl_atr",
    "leg_try",
    "room_tp",
    "room_sl",
    "pd_pos",
    "round_dist",
    "gap_open",
    "tv_ratio",
    "tv_1d",
    "spread_rel",
    "sig_same_60",
    "sig_opp_60",
    "cost_r",
    "last20_all",
    "last20_same",
]
FEATURES = CATEGORICAL + NUMERIC
assert len(FEATURES) == 50


# --- trades ----------------------------------------------------------------------------------


def all_trades(cx: ah.Ctx, sig: pd.DataFrame) -> pd.DataFrame:
    """Every raw signal with a leg is a trade (X1's exits, no overlap skip)."""
    rows = []
    for i, d in zip(sig.i.to_numpy(), sig.d.to_numpy(), strict=True):
        i, d = int(i), int(d)
        leg = ah.leg_index(cx, i, d)
        if leg is None:
            continue
        q, hb, tries = leg
        lo_src, hi_src = (cx.lo, cx.h) if d == 1 else (cx.h, cx.lo)
        start, ext = lo_src[q], hi_src[hb]
        rr, e = d * (ext - start), cx.c[i]
        if not (d * (e - start) > 0 and d * (ext - e) > 0):
            continue
        stop, tp = ext - d * ah.SL_K * rr, start + d * ah.TP_K * rr
        r = ah.simulate_one(cx, i, d, X1, (stop, tp))
        if not r:
            continue
        r.update(q=q, hb=hb, leg_try=tries, start=start, ext=ext, stop=stop, tp=tp)
        rows.append(r)
    t = pd.DataFrame(rows)
    if len(t):
        t["ts"] = cx.ts[t.i.to_numpy()]
        t["exit_ts"] = cx.ts[np.minimum(t.exit_i.to_numpy(), len(cx.ts) - 1)]
        t["year"] = t.ts.dt.year
        ny = t.ts.dt.tz_convert(NY)
        days = (ny + pd.Timedelta(hours=7)).dt.normalize().dt.tz_localize(None)
        t["week"] = ((days - pd.Timestamp("1970-01-05")).dt.days // 7).astype(int)
    return t


def skip_mask(t: pd.DataFrame, keep: np.ndarray) -> np.ndarray:
    """X1's rule on the kept trades: skip a trade while one of the same direction is open."""
    out = np.zeros(len(t), bool)
    busy = {1: -1, -1: -1}
    order = np.argsort(t.i.to_numpy(), kind="stable")
    ii, dd, ee = t.i.to_numpy(), t.d.to_numpy(), t.exit_i.to_numpy()
    for k in order:
        if keep[k] and busy[dd[k]] < ii[k]:
            out[k] = True
            busy[dd[k]] = ee[k]
    return out


# --- features --------------------------------------------------------------------------------


def _shift(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    if n < len(a):
        out[n:] = a[: len(a) - n]
    return out


def bar_arrays(m1: pd.DataFrame, cx: ah.Ctx) -> dict:
    """Per-bar arrays the features read; every value at bar j uses bars up to j only."""
    h, lo, c, o = cx.h, cx.lo, cx.c, cx.o
    n = len(c)
    cs, hs, ls = pd.Series(c), pd.Series(h), pd.Series(lo)
    prev = _shift(c, 1)
    tr = np.nanmax(np.c_[h - lo, np.abs(h - prev), np.abs(lo - prev)], axis=1)
    trs = pd.Series(tr)
    a = {"atr": cx.atr}
    a["tr1d"] = trs.rolling(1440, min_periods=1440).mean().to_numpy()
    a["tr20d"] = trs.rolling(28800, min_periods=28800).mean().to_numpy()
    a["ema20"] = cs.ewm(span=20, adjust=False).mean().to_numpy()
    a["ema50"] = cs.ewm(span=50, adjust=False).mean().to_numpy()
    a["ema1200"] = cs.ewm(span=1200, adjust=False).mean().to_numpy()
    a["ema3000"] = cs.ewm(span=3000, adjust=False).mean().to_numpy()
    hh5, ll5 = hs.rolling(5).max().to_numpy(), ls.rolling(5).min().to_numpy()
    a["k5"] = (c - ll5) / np.where(hh5 > ll5, hh5 - ll5, np.nan)
    hh60, ll60 = hs.rolling(60).max().to_numpy(), ls.rolling(60).min().to_numpy()
    a["pos60"] = (c - ll60) / np.where(hh60 > ll60, hh60 - ll60, np.nan)
    a["rng10"] = (hs.rolling(10).max() - ls.rolling(10).min()).to_numpy()
    a["absdc60"] = pd.Series(np.abs(c - prev)).rolling(60).sum().to_numpy()
    for k in (3, 10, 60, 240, 1440):
        a[f"c{k}"] = _shift(c, k)
    if "tick_volume" in m1:
        tv = m1["tick_volume"].to_numpy(float)
        tvs = pd.Series(tv)
        a["tv"] = tv
        a["tv60"] = tvs.rolling(60).mean().to_numpy()
        a["tv10"] = tvs.rolling(10).mean().to_numpy()
        a["tv1440"] = tvs.rolling(1440).mean().to_numpy()
    else:
        a["tv"] = a["tv60"] = a["tv10"] = a["tv1440"] = np.full(n, np.nan)
    a["spread_med"] = pd.Series(cx.spread).rolling(1440, min_periods=60).median().to_numpy()

    # the trading day (17:00 to 17:00 New York) and completed-day values
    ny = cx.ts.tz_convert(NY)
    a["mins"] = np.asarray(ny.hour * 60 + ny.minute)
    a["hour"] = np.asarray(ny.hour)
    day = (ny + pd.Timedelta(hours=7)).normalize()
    key = pd.factorize(day)[0]
    a["weekday"] = np.asarray(day.day_of_week)
    g = pd.DataFrame({"k": key, "o": o, "h": h, "l": lo, "c": c}).groupby("k")
    dd = g.agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"))
    pc = dd.c.shift(1)
    dtr = np.maximum(dd.h - dd.l, np.maximum((dd.h - pc).abs(), (dd.l - pc).abs()))
    atr_d = dtr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    pct = atr_d.rolling(250, min_periods=250).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True)
    p = (dd.h + dd.l + dd.c) / 3
    prevd = pd.DataFrame(
        {
            "atr_d": atr_d.shift(1),
            "atr_d_pct": pct.shift(1),
            "pdh": dd.h.shift(1),
            "pdl": dd.l.shift(1),
            "pdc": dd.c.shift(1),
            "pdo": dd.o.shift(1),
            "h5": dd.h.rolling(5).max().shift(1),
            "l5": dd.l.rolling(5).min().shift(1),
            "c5": dd.c.shift(5),
            "pp": p.shift(1),
            "r1": (2 * p - dd.l).shift(1),
            "s1": (2 * p - dd.h).shift(1),
            "dopen": dd.o,
        }
    )
    for col in prevd:
        a[col] = prevd[col].to_numpy()[key]
    a["dhigh"] = hs.groupby(key).cummax().to_numpy()
    a["dlow"] = ls.groupby(key).cummin().to_numpy()

    # raw signal counts per direction (cumulative, for the last-60-bar counts)
    for d in (1, -1):
        cd = cx.cond[d]
        first = cd & ~np.r_[False, cd[:-1]] & ~cx.blocked & (cx.sld > 0)
        a[f"sigcum{d}"] = np.cumsum(first)
    return a


def _recent(t: pd.DataFrame, mask: np.ndarray, n: int = 20) -> np.ndarray:
    """Mean gross R of the last n trades in ``mask`` that exited before each trade's bar."""
    sub = t[mask]
    order = np.argsort(sub.exit_i.to_numpy(), kind="stable")
    ex = sub.exit_i.to_numpy()[order]
    cs = np.r_[0.0, np.cumsum(sub.gross.to_numpy()[order])]
    k = np.searchsorted(ex, t.i.to_numpy(), side="left")  # exits strictly before bar i
    out = np.full(len(t), np.nan)
    ok = k >= n
    out[ok] = (cs[k[ok]] - cs[k[ok] - n]) / n
    return out


def features(t: pd.DataFrame, a: dict, cx: ah.Ctx) -> pd.DataFrame:
    i = t.i.to_numpy()
    d = t.d.to_numpy().astype(float)
    c, o, h, lo = cx.c[i], cx.o[i], cx.h[i], cx.lo[i]
    atr = a["atr"][i]
    atr_d = a["atr_d"][i]
    mins = a["mins"][i]
    f = pd.DataFrame(index=t.index)
    f["hour"] = a["hour"][i]
    f["weekday"] = a["weekday"][i]
    f["session"] = np.select(
        [(mins >= 18 * 60) | (mins < 2 * 60), mins < 8 * 60, mins < 12 * 60], [0, 1, 2], 3
    )
    f["mins_left"] = (17 * 60 - mins) % 1440
    f["news_window"] = (
        ((mins >= 8 * 60 + 25) & (mins < 9 * 60 + 5))
        | ((mins >= 9 * 60 + 55) & (mins < 10 * 60 + 35))
    ).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        f["vol_m1_1d"] = atr / a["tr1d"][i]
        f["vol_1d_20d"] = a["tr1d"][i] / a["tr20d"][i]
        f["atr_d_bp"] = atr_d / c * 1e4
        f["atr_d_pct"] = a["atr_d_pct"][i]
        f["day_used"] = (a["dhigh"][i] - a["dlow"][i]) / atr_d
        f["rng10_atr"] = a["rng10"][i] / atr
        f["ret10"] = d * (c - a["c10"][i]) / atr
        f["ret60"] = d * (c - a["c60"][i]) / atr_d
        f["ret240"] = d * (c - a["c240"][i]) / atr_d
        f["ret1440"] = d * (c - a["c1440"][i]) / atr_d
        f["ret_5d"] = d * (c - a["c5"][i]) / atr_d
        f["ema_gap"] = d * (a["ema20"][i] - a["ema50"][i]) / atr
        f["dist_ema50"] = d * (c - a["ema50"][i]) / atr
        f["htf_ema"] = d * (a["ema1200"][i] - a["ema3000"][i]) / atr_d
        f["er60"] = d * (c - a["c60"][i]) / a["absdc60"][i]
        rng = a["dhigh"][i] - a["dlow"][i]
        pos = (c - a["dlow"][i]) / np.where(rng > 0, rng, np.nan)
        f["pos_day"] = np.where(d > 0, pos, 1 - pos)
        hi5 = np.fmax(a["h5"][i], a["dhigh"][i])
        lo5 = np.fmin(a["l5"][i], a["dlow"][i])
        pos = (c - lo5) / np.where(hi5 > lo5, hi5 - lo5, np.nan)
        f["pos_5d"] = np.where(d > 0, pos, 1 - pos)
        f["prev_day_dir"] = d * np.sign(a["pdc"][i] - a["pdo"][i])
        f["k5"] = np.where(d > 0, a["k5"][i], 1 - a["k5"][i])
        f["pos60"] = np.where(d > 0, a["pos60"][i], 1 - a["pos60"][i])
        start, ext = t.start.to_numpy(), t.ext.to_numpy()
        f["pull_depth"] = (ext - c) / (ext - start)
        f["pull_bars"] = (i - t.hb.to_numpy()).astype(float)
        f["ret3"] = d * (c - a["c3"][i]) / atr
        f["sig_body"] = np.where(h > lo, d * (c - o) / (h - lo), 0.0)
        f["sig_range"] = (h - lo) / atr
        rr = d * (ext - start)
        leg_bars = (t.hb.to_numpy() - t.q.to_numpy()).astype(float)
        f["leg_atr"] = rr / atr
        f["leg_d"] = rr / atr_d
        f["leg_bars"] = leg_bars
        f["leg_speed"] = rr / leg_bars / atr
        f["rw_p"] = t.p0.to_numpy()
        sld = d * (c - t.stop.to_numpy())
        tpd = d * (t.tp.to_numpy() - c)
        f["sl_atr"] = sld / atr
        f["leg_try"] = t.leg_try.to_numpy().astype(float)
        lv = np.c_[[a[k][i] for k in ("pdh", "pdl", "h5", "l5", "pp", "r1", "s1")]].T
        dist = d[:, None] * (lv - c[:, None])
        fwd = np.where(dist > 0, dist, np.inf).min(axis=1)
        back = np.where(dist < 0, -dist, np.inf).min(axis=1)
        allnan = np.isnan(lv).all(axis=1)
        f["room_tp"] = np.where(allnan, np.nan, np.minimum(fwd / tpd, 5.0))
        f["room_sl"] = np.where(allnan, np.nan, np.minimum(back / sld, 5.0))
        pdr = a["pdh"][i] - a["pdl"][i]
        pos = (c - a["pdl"][i]) / np.where(pdr > 0, pdr, np.nan)
        f["pd_pos"] = np.where(d > 0, pos, 1 - pos)
        f["round_dist"] = np.abs(c - np.round(c / 10) * 10) / atr
        f["gap_open"] = d * (a["dopen"][i] - a["pdc"][i]) / atr_d
        f["tv_ratio"] = a["tv"][i] / a["tv60"][i]
        f["tv_1d"] = a["tv10"][i] / a["tv1440"][i]
        f["spread_rel"] = cx.spread[i] / a["spread_med"][i]
    j1, j0 = np.maximum(i - 1, 0), np.maximum(i - 61, 0)  # signals in bars i-60 .. i-1
    buys = a["sigcum1"][j1] - a["sigcum1"][j0]
    sells = a["sigcum-1"][j1] - a["sigcum-1"][j0]
    same = np.where(d > 0, buys, sells)
    opp = np.where(d > 0, sells, buys)
    f["sig_same_60"] = same.astype(float)
    f["sig_opp_60"] = opp.astype(float)
    f["cost_r"] = t.cost.to_numpy()
    f["last20_all"] = _recent(t, np.ones(len(t), bool))
    last_b, last_s = _recent(t, t.d.to_numpy() == 1), _recent(t, t.d.to_numpy() == -1)
    f["last20_same"] = np.where(d > 0, last_b, last_s)
    f = f.replace([np.inf, -np.inf], np.nan)
    return f[FEATURES]


def build_set(m1: pd.DataFrame) -> pd.DataFrame:
    cx = ah.context(m1)
    t = all_trades(cx, ah.raw_signals(cx))
    if not len(t):
        return t
    f = features(t, bar_arrays(m1, cx), cx)
    t = t.drop(columns=[k for k in FEATURES if k in t]).reset_index(drop=True)
    return pd.concat([t, f.reset_index(drop=True)], axis=1)


# --- statistics ------------------------------------------------------------------------------


def _week_index(week: np.ndarray) -> tuple[np.ndarray, int]:
    u, inv = np.unique(week, return_inverse=True)
    return inv, len(u)


def cluster_t(y: np.ndarray, wk: np.ndarray, nw: int, mask: np.ndarray) -> tuple[float, float]:
    """Mean of y over mask and its t with a week-clustered SE (ratio estimator)."""
    n = mask.sum()
    if n < 2:
        return np.nan, np.nan
    s = np.bincount(wk[mask], weights=y[mask], minlength=nw)
    k = np.bincount(wk[mask], minlength=nw).astype(float)
    m = s.sum() / n
    used = k > 0
    w = used.sum()
    if w < 2:
        return m, np.nan
    var = ((s[used] - m * k[used]) ** 2).sum() / n**2 * w / (w - 1)
    return m, m / np.sqrt(var) if var > 0 else np.nan


def boot_p(y: np.ndarray, week: np.ndarray, seed: int = SEED, boot: int = BOOT) -> dict:
    """Weekly block bootstrap of the mean: one-sided p (share of draws <= 0) and a 95% range."""
    wk, nw = _week_index(week)
    s = np.bincount(wk, weights=y, minlength=nw)
    k = np.bincount(wk, minlength=nw).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nw, size=(boot, nw))
    means = s[idx].sum(1) / np.maximum(k[idx].sum(1), 1)
    return dict(
        mean=y.mean(),
        p=(means <= 0).mean(),
        lo=np.quantile(means, 0.025),
        hi=np.quantile(means, 0.975),
    )


# --- stage 2: the filter ---------------------------------------------------------------------


@dataclass(frozen=True)
class Cond:
    feature: str
    op: str  # "<=", ">=" or "in"
    value: float | tuple

    def mask(self, f: pd.DataFrame) -> np.ndarray:
        x = f[self.feature].to_numpy()
        with np.errstate(invalid="ignore"):
            if self.op == "<=":
                return x <= self.value
            if self.op == ">=":
                return x >= self.value
            return np.isin(x, np.asarray(self.value))

    def text(self) -> str:
        if self.op == "in":
            return f"`{self.feature}` in {{{', '.join(str(int(v)) for v in self.value)}}}"
        return f"`{self.feature}` {self.op} {self.value:.4g}"


def edges(f: pd.DataFrame) -> dict:
    """D's quintile edges per numeric feature (features only, no outcome)."""
    return {
        k: np.nanquantile(f[k].to_numpy(), [0.2, 0.4, 0.6, 0.8])
        for k in NUMERIC
        if np.isfinite(f[k].to_numpy()).sum() > 10
    }


def candidates(f: pd.DataFrame, y: np.ndarray, q: dict) -> list[Cond]:
    out = []
    for k, (q20, q40, q60, q80) in q.items():
        for op, v in (("<=", q20), ("<=", q40), ("<=", q60), (">=", q40), (">=", q60), (">=", q80)):
            out.append(Cond(k, op, float(v)))
    n = len(f)
    for k in CATEGORICAL:
        x = f[k].to_numpy()
        keep = []
        for lvl in np.unique(x[~pd.isna(x)]):
            m = x == lvl
            if m.sum() >= MIN_LEVEL * n and y[m].mean() > 0:
                keep.append(float(lvl))
        if keep:
            out.append(Cond(k, "in", tuple(keep)))
    return out


def greedy(f: pd.DataFrame, y: np.ndarray, week: np.ndarray, q: dict) -> tuple[list[Cond], float]:
    """GOLD_AHF.md §5: up to three conditions, each raising the week-clustered t of gross R."""
    wk, nw = _week_index(week)
    cands = candidates(f, y, q)
    masks = {c: c.mask(f) for c in cands}
    n = len(f)
    chosen: list[Cond] = []
    keep = np.ones(n, bool)
    best_t = -np.inf
    for step in range(MAX_CONDS):
        floor = (MIN_KEEP_1 if step == 0 else MIN_KEEP) * n
        used = {c.feature for c in chosen}
        pick, pick_t = None, best_t
        for c in cands:
            if c.feature in used:
                continue
            m = keep & masks[c]
            if m.sum() < floor:
                continue
            _, tv = cluster_t(y, wk, nw, m)
            if np.isfinite(tv) and tv > pick_t:
                pick, pick_t = c, tv
        if pick is None:
            break
        chosen.append(pick)
        keep &= masks[pick]
        best_t = pick_t
    return chosen, best_t


def apply(conds: list[Cond], f: pd.DataFrame) -> np.ndarray:
    m = np.ones(len(f), bool)
    for c in conds:
        m &= c.mask(f)
    return m


def shuffled_t(
    f: pd.DataFrame,
    y: np.ndarray,
    week: np.ndarray,
    q: dict,
    seed: int = SEED,
    runs: int = SHUFFLES,
) -> np.ndarray:
    """The greedy rerun on outcomes circularly shifted in time (10-90% of the trades), so the
    features lose their link with the outcomes while the outcomes' serial structure stays."""
    rng = np.random.default_rng(seed)
    n = len(y)
    out = []
    for _ in range(runs):
        k = int(rng.integers(int(0.1 * n), int(0.9 * n)))
        out.append(greedy(f, np.roll(y, k), week, q)[1])
    return np.asarray(out)


# --- reports ---------------------------------------------------------------------------------


def _period(t: pd.DataFrame, p: tuple) -> np.ndarray:
    return ((t.ts >= p[0]) & (t.ts < p[1])).to_numpy()


def _line(x: pd.DataFrame) -> str:
    if not len(x):
        return "| 0 | | | | | | | |"
    days = max(1, x.ts.dt.normalize().nunique())
    edge = (x.hit_tp.astype(float) - x.p0).mean()
    return (
        f"| {len(x):,} | {len(x) / days:.1f} | {x.gross.mean():+.3f} | {edge:+.1%} | "
        f"{x.cost.mean():.3f} | {x.net.mean():+.3f} | {x.net_slip.mean():+.3f} | "
        f"{x.net_2x.mean():+.3f} |"
    )


HEAD = (
    "| Set | Trades | A day | Gross R | TP − RW | Cost R | Net R | Net R slip | Net R 2x |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)


def stage1(d: pd.DataFrame, q: dict) -> list[str]:
    y = d.gross.to_numpy()
    edge = (d.hit_tp.astype(float) - d.p0).to_numpy()
    lines = [
        "## Stage 1: features on D (2012-2017), descriptive only",
        "",
        "Gross R by quintile of D (Q1 lowest); TP − RW = TP rate minus the random-walk rate; "
        "ρ = Spearman of the feature with gross R.",
        "",
        "| Feature | Q1 | Q2 | Q3 | Q4 | Q5 | TP − RW Q1 | TP − RW Q5 | ρ | Missing |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for k in NUMERIC:
        x = d[k].to_numpy()
        ok = np.isfinite(x)
        if k not in q or ok.sum() < 10:
            lines.append(f"| `{k}` | | | | | | | | | {1 - ok.mean():.0%} |")
            continue
        b = np.digitize(x, q[k])  # 0..4; ties go up
        g = [y[ok & (b == j)].mean() if (ok & (b == j)).any() else np.nan for j in range(5)]
        e1 = edge[ok & (b == 0)].mean() if (ok & (b == 0)).any() else np.nan
        e5 = edge[ok & (b == 4)].mean() if (ok & (b == 4)).any() else np.nan
        rho = pd.Series(x[ok]).rank().corr(pd.Series(y[ok]).rank())
        lines.append(
            f"| `{k}` | "
            + " | ".join(f"{v:+.3f}" for v in g)
            + f" | {e1:+.1%} | {e5:+.1%} | {rho:+.3f} | {1 - ok.mean():.0%} |"
        )
    for k in CATEGORICAL:
        lines += [
            "",
            f"**`{k}`** (gross R, trades)",
            "",
            "| Level | Trades | Gross R | TP − RW |",
            "| --- | --- | --- | --- |",
        ]
        for lvl, g in d.groupby(k):
            e = (g.hit_tp.astype(float) - g.p0).mean()
            lines.append(f"| {int(lvl)} | {len(g):,} | {g.gross.mean():+.3f} | {e:+.1%} |")
    return lines + [""]


def screen(t: pd.DataFrame) -> tuple[str, dict]:
    md, mv = _period(t, D_PERIOD), _period(t, V_PERIOD)
    d, v = t[md].reset_index(drop=True), t[mv].reset_index(drop=True)
    q = edges(d)
    y = d.gross.to_numpy()
    conds, t_d = greedy(d, y, d.week.to_numpy(), q)
    null = shuffled_t(d, y, d.week.to_numpy(), q)
    bar = float(np.nanquantile(null, 0.95))
    kd, kv = apply(conds, d), apply(conds, v)
    vb = boot_p(v.gross.to_numpy()[kv], v.week.to_numpy()[kv]) if kv.sum() > 1 else None
    yr = v[kv].groupby("year").gross.mean()
    g1 = bool(conds) and t_d > bar
    g2 = vb is not None and vb["mean"] > 0 and vb["p"] < 0.05
    g3 = int((yr > 0).sum()) >= 3
    passed = bool(g1 and g2 and g3)
    lines = [
        "# Gold AH filters: stages 1-2 (`GOLD_AHF.md`)",
        "",
        "_`python -m app research gold-ahf screen`: XAUUSD store M1, every X1 signal a trade "
        "(§2). D 2012-2017, V 2018-2021; C is not read._",
        "",
    ]
    lines += stage1(d, q)
    lines += ["## Stage 2: the filter chosen on D", ""]
    lines += [f"{j + 1}. {c.text()}" for j, c in enumerate(conds)] or ["(no condition)"]
    lines += [
        "",
        f"- t of gross R on D: {t_d:.2f}; shuffled selections (50): median "
        f"{np.nanmedian(null):.2f}, 95th percentile {bar:.2f}.",
        "",
        HEAD,
        "| D, all " + _line(d),
        "| D, filter " + _line(d[kd]),
        "| V, all " + _line(v),
        "| V, filter " + _line(v[kv]),
        "| V, filter, X1 skip " + _line(v[skip_mask(v, kv)]),
        "",
    ]
    lines += [
        "**V, filtered gross R by year:** " + ", ".join(f"{y_} {g:+.3f}" for y_, g in yr.items()),
        "",
    ]
    if vb is not None:
        lines += [
            f"**V, filtered gross R:** {vb['mean']:+.3f} (95% {vb['lo']:+.3f} to "
            f"{vb['hi']:+.3f}), one-sided p {vb['p']:.3f}.",
            "",
        ]
    lines += [
        "## Gate of stage 2 (§5)",
        "",
        "| Condition | Result |",
        "| --- | --- |",
        f"| 1. D t above the shuffled 95th percentile | {'met' if g1 else 'not met'} |",
        f"| 2. V gross R > 0, p < 0.05 | {'met' if g2 else 'not met'} |",
        f"| 3. V gross R > 0 in ≥ 3 of 4 years | {'met' if g3 else 'not met'} "
        f"({int((yr > 0).sum())}) |",
        "",
        f"**Stage 2 {'passed' if passed else 'not passed'}.**"
        + ("" if passed else " The study stops here (§5): stage 3 does not run."),
        "",
    ]
    state = dict(
        stage2=passed,
        conds=[[c.feature, c.op, c.value] for c in conds],
        t_d=t_d,
        bar=bar,
        v_net_slip=float(v[kv].net_slip.mean()) if kv.any() else None,
    )
    return "\n".join(lines) + "\n", state


def conds_from(state: dict) -> list[Cond]:
    return [Cond(f, op, tuple(v) if op == "in" else float(v)) for f, op, v in state["conds"]]


# --- stage 3: meta-labeling ------------------------------------------------------------------


class Design:
    """Train-window design: one-hot categories, median imputation + missing flags, scaling."""

    def fit(self, x: pd.DataFrame) -> Design:
        self.levels = {k: np.unique(x[k].dropna().to_numpy()) for k in CATEGORICAL}
        num = x[NUMERIC]
        self.med = num.median()
        self.flags = [k for k in NUMERIC if num[k].isna().any()]
        z = self._raw(x)
        self.mu, self.sd = z.mean(0), z.std(0)
        self.sd[self.sd == 0] = 1.0
        return self

    def _raw(self, x: pd.DataFrame) -> np.ndarray:
        parts = [x[NUMERIC].fillna(self.med).to_numpy(float)]
        parts += [x[k].isna().to_numpy(float)[:, None] for k in self.flags]
        for k, lv in self.levels.items():
            parts.append((x[k].to_numpy()[:, None] == lv[None, :]).astype(float))
        return np.hstack(parts)

    def transform(self, x: pd.DataFrame) -> np.ndarray:
        return (self._raw(x) - self.mu) / self.sd


def _platt(raw: np.ndarray, y: np.ndarray):
    from sklearn.linear_model import LogisticRegression

    z = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1 - raw, 1e-6, 1))
    m = LogisticRegression(C=1e6, max_iter=1000).fit(z[:, None], y)

    def f(r: np.ndarray) -> np.ndarray:
        zz = np.log(np.clip(r, 1e-6, 1 - 1e-6) / np.clip(1 - r, 1e-6, 1))
        return m.predict_proba(zz[:, None])[:, 1]

    return f


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, model: str) -> np.ndarray:
    """Fit on the first 75% of the train window (by time), Platt on the last 25%; p for test.
    The fit is weighted by |net R|, the calibration is not, so p estimates P(net R > 0)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss

    from app.research import meta

    train = train.sort_values("ts")
    cut = int(0.75 * len(train))
    fit, cal = train.iloc[:cut], train.iloc[cut:]
    y_fit = (fit.net > 0).to_numpy(int)
    w_fit = fit.net.abs().to_numpy()
    if model == "lr":
        des = Design().fit(fit)
        xf = des.transform(fit)
        folds = np.array_split(np.arange(len(fit)), meta.INNER_FOLDS + 1)
        best_c, best_l = meta.C_GRID[0], np.inf
        for c_ in meta.C_GRID:
            loss = 0.0
            for j in range(1, len(folds)):
                tr_, va = np.concatenate(folds[:j]), folds[j]
                m = LogisticRegression(C=c_, max_iter=2000).fit(
                    xf[tr_], y_fit[tr_], sample_weight=w_fit[tr_]
                )
                loss += log_loss(
                    y_fit[va], m.predict_proba(xf[va])[:, 1], labels=[0, 1], sample_weight=w_fit[va]
                )
            if loss < best_l:
                best_c, best_l = c_, loss
        m = LogisticRegression(C=best_c, max_iter=2000).fit(xf, y_fit, sample_weight=w_fit)

        def raw(x: pd.DataFrame) -> np.ndarray:
            return m.predict_proba(des.transform(x))[:, 1]
    else:
        import lightgbm as lgb

        def mat(x: pd.DataFrame) -> pd.DataFrame:
            z = x[FEATURES].copy()
            for k in CATEGORICAL:
                z[k] = pd.Categorical(z[k], categories=range(24))
            return z

        ds = lgb.Dataset(mat(fit), y_fit, weight=w_fit, categorical_feature=CATEGORICAL)
        b = lgb.train(meta.LGBM_PARAMS, ds, num_boost_round=meta.LGBM_ROUNDS)

        def raw(x: pd.DataFrame) -> np.ndarray:
            return b.predict(mat(x))

    cal_f = _platt(raw(cal), (cal.net > 0).to_numpy(int))
    return cal_f(raw(test))


def windows() -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    starts = pd.date_range("2018-01-01", "2021-07-01", freq="6MS", tz="UTC")
    return [(s, s + pd.DateOffset(months=6)) for s in starts]


def walk_forward(t: pd.DataFrame, model: str) -> pd.DataFrame:
    out = []
    for a, b in windows():
        train = t[(t.ts >= D_PERIOD[0]) & (t.exit_ts < a - pd.Timedelta(days=1))]
        test = t[(t.ts >= a) & (t.ts < b)]
        if len(train) < 200 or not len(test):
            continue
        p = fit_predict(train, test, model)
        m1 = train.net[train.net > 0].mean()
        m0 = train.net[train.net <= 0].mean()
        base = (train.net > 0).mean()
        r = test[["ts", "week", "year", "net", "net_slip", "gross"]].copy()
        r["p"], r["base"], r["window"] = p, base, str(a.date())
        r["accept"] = p * m1 + (1 - p) * m0 > 0
        out.append(r)
    return pd.concat(out) if out else pd.DataFrame()


def random_controls(wf: pd.DataFrame, runs: int = 20) -> np.ndarray:
    res = []
    for s in range(1, runs + 1):
        rng = np.random.default_rng(s)
        acc = []
        for _, g in wf.groupby("window"):
            k = int(g.accept.sum())
            if k:
                acc.append(g.net.to_numpy()[rng.choice(len(g), k, replace=False)])
        res.append(np.concatenate(acc).mean() if acc else np.nan)
    return np.asarray(res)


def meta_stage(t: pd.DataFrame, state: dict) -> tuple[str, dict]:
    conds = conds_from(state)
    ft = t[apply(conds, t)].reset_index(drop=True)
    v = ft[_period(ft, V_PERIOD)]
    lines = [
        "# Gold AH filters: stage 3, meta-labeling (`GOLD_AHF.md` §6)",
        "",
        "_`python -m app research gold-ahf meta`: the trades passing the stage-2 filter "
        "(" + "; ".join(c.text() for c in conds) + "); walk-forward 2018-2021._",
        "",
        f"Filtered trades on V: {len(v):,}, net R {v.net.mean():+.3f} "
        f"(slip {v.net_slip.mean():+.3f}).",
        "",
        "| Model | Accepted | A window | Net R acc. | Net R slip acc. | Gain vs filter | "
        "Random 95th | BSS | Gate |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    passed = {}
    for model in ("lr", "lgbm"):
        wf = walk_forward(ft, model)
        if not len(wf):
            lines.append(f"| {model} | 0 | | | | | | | not met |")
            passed[model] = False
            continue
        acc = wf[wf.accept]
        y = (wf.net > 0).to_numpy(float)
        brier = ((wf.p - y) ** 2).mean()
        ref = ((wf.base - y) ** 2).mean()
        bss = 1 - brier / ref
        ctrl = random_controls(wf)
        r95 = float(np.nanquantile(ctrl, 0.95))
        net_acc = acc.net.mean() if len(acc) else np.nan
        per_w = len(acc) / wf.window.nunique()
        ok = (
            len(acc) > 0
            and net_acc > 0
            and per_w >= 30
            and net_acc > wf.net.mean()
            and net_acc > r95
            and bss > 0
        )
        passed[model] = bool(ok)
        lines.append(
            f"| {model} | {len(acc):,} | {per_w:.0f} | {net_acc:+.3f} | "
            f"{acc.net_slip.mean():+.3f} | {net_acc - wf.net.mean():+.3f} | {r95:+.3f} | "
            f"{bss:+.4f} | {'met' if ok else 'not met'} |"
        )
    carry = "lr" if passed["lr"] else "lgbm" if passed["lgbm"] else None
    if carry is None and state.get("v_net_slip") is not None and state["v_net_slip"] > 0:
        carry = "filter"
    lines += ["", f"**Carried forward to stage 4: {carry or 'nothing; the study stops'}.**", ""]
    state = dict(state, stage3=passed, carry=carry)
    return "\n".join(lines) + "\n", state


# --- stage 4: the check ----------------------------------------------------------------------


def check_rule(train: pd.DataFrame, test: pd.DataFrame, state: dict) -> np.ndarray:
    conds = conds_from(state)
    keep = apply(conds, test)
    if state["carry"] in ("lr", "lgbm"):
        tr = train[apply(conds, train)]
        sub = test[keep]
        if len(sub):
            p = fit_predict(tr, sub, state["carry"])
            m1, m0 = tr.net[tr.net > 0].mean(), tr.net[tr.net <= 0].mean()
            k = np.flatnonzero(keep)
            keep[k[~(p * m1 + (1 - p) * m0 > 0)]] = False
    return keep


def check_stage(t: pd.DataFrame, fx: pd.DataFrame | None, state: dict) -> str:
    end = pd.Timestamp(splits().lockbox_start, tz="UTC")
    train = t[(t.ts >= D_PERIOD[0]) & (t.exit_ts < C_START - pd.Timedelta(days=1))]
    c = t[(t.ts >= C_START) & (t.ts < end)].reset_index(drop=True)
    kc = check_rule(train, c, state)
    lines = [
        "# Gold AH filters: stage 4, the check (`GOLD_AHF.md` §7)",
        "",
        f"_Carried forward: {state['carry']}; trained on 2012-2021. C = 2022 to "
        f"{end.date()}; F = FxPro GOLD 2022-02 on._",
        "",
        HEAD,
        "| C, all " + _line(c),
        "| C, rule " + _line(c[kc]),
        "| C, rule, X1 skip " + _line(c[skip_mask(c, kc)]),
    ]
    ok_c = kc.any() and c[kc].net_slip.mean() > 0
    ok_f = False
    if fx is not None:
        f = fx[fx.ts >= F_START].reset_index(drop=True)
        kf = check_rule(train, f, state)
        ok_f = kf.any() and f[kf].net_slip.mean() > 0
        bw = ((f.ts >= BOT_WEEKS[0]) & (f.ts < BOT_WEEKS[1])).to_numpy()
        lines += [
            "| F, all " + _line(f),
            "| F, rule " + _line(f[kf]),
            "| F, rule, bot's weeks " + _line(f[kf & bw]),
        ]
    lines += [
        "",
        "**Net R by year (rule, C):** "
        + ", ".join(f"{y} {g:+.3f}" for y, g in c[kc].groupby("year").net.mean().items()),
        "",
        f"**Decision (§7): {'shadow strategy for the demo' if ok_c and ok_f else 'dropped'}"
        f"** (C {'met' if ok_c else 'not met'}, F {'met' if ok_f else 'not met'}).",
        "",
    ]
    return "\n".join(lines) + "\n"


# --- command line ----------------------------------------------------------------------------


def _load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def _save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, default=float), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-ahf")
    ap.add_argument("command", choices=["screen", "meta", "check"])
    ap.add_argument("--export", type=Path, help="check: an FxPro GOLD M1 export (required)")
    args = ap.parse_args(argv)
    if args.command == "check" and args.export is None:
        ap.error("check needs --export (condition F, GOLD_AHF.md §7)")
    state = _load_state()
    if args.command == "screen":
        if "stage2" in state:
            ap.error(f"stage 2 already ran ({STATE.name}); it runs once")
        t = build_set(ah.load_store())
        text, state = screen(t)
        out = SCREEN
    elif args.command == "meta":
        if not state.get("stage2"):
            ap.error("stage 3 runs only after stage 2 passed (GOLD_AHF.md §5)")
        if "stage3" in state:
            ap.error("stage 3 already ran; it runs once")
        t = build_set(ah.load_store())
        text, state = meta_stage(t, state)
        out = META
    else:
        if not state.get("carry"):
            ap.error("stage 4 runs only with a rule carried forward from stage 3")
        if state.get("stage4"):
            ap.error("the check already ran; it runs once")
        t = build_set(ah.load_store())
        fx = build_set(ah.load_export(args.export))
        text = check_stage(t, fx, state)
        state = dict(state, stage4=True)
        out = CHECK
    _save_state(state)
    out.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # a Windows console is cp1252
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
