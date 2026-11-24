"""Markouts, controls and gates for discovery round 2 (``docs/discovery/PREREG_2.md`` §4-7).

- **Markout:** m(h) = sign x (mid(t0 + h) - mid(t0)), mid = close + spread / 2, using the first M1
  bar closing at or after t0 + h and within 5 minutes after it (else missing). z(h) = m(h) / c(t0),
  c = the bar's spread + $0.07.
- **E0:** 20 random M1 bars per event from the same year, New York hour and ATR(14, 1h) quintile
  (within the year), Monday to Friday, not within 60 minutes of an event of the same cell; each
  takes the event's sign and its own cost.
- **Placebos:** F3 the same New York minute on the 5 nearest trading days without a high-importance
  USD release within 60 minutes; F2 the window moved 2 hours earlier and later (MONTHEND: the 5
  trading days before the month's last); F1 the drivers moved by +/- 7 days; F5p 20 random grid
  offsets in (0.1, 0.9) of the step.
- **Tests:** 4-week calendar blocks, a block bootstrap (B = 20,000) of the difference in means."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.discovery import events as ev

H = (1, 5, 15, 30, 60, 120, 240)
LATE = 5  # minutes a markout bar may close after t0 + h
E0_DRAWS, E0_GAP = 20, 60
SEED_E0, SEED_PLACEBO, SEED_BOOT = 20261112, 20261113, 20261114
B = 20_000
BLOCK_MIN = 28 * 1440
PLACEBO_DAYS, RELEASE_GAP = 5, 60
MAX_PLACEBO_GAP = 30  # calendar days from the release day
SHIFT_HOURS = 2
DRIVER_SHIFT = pd.Timedelta(days=7)
GRID_DRAWS = 20


# --- bars and markouts ----------------------------------------------------------------------------


@dataclass
class Bars:
    mins: np.ndarray  # minute of each bar's open
    close_min: np.ndarray
    mid: np.ndarray
    cost: np.ndarray
    atr: np.ndarray
    year: np.ndarray
    key: np.ndarray  # year, New York hour, ATR quintile; -1: not eligible for E0


def bars(m1: pd.DataFrame) -> Bars:
    mins = ev.minutes(m1["ts_utc"])
    c, spread = m1["close"].to_numpy(), m1["spread"].to_numpy()
    atr = ev.atr_1h(m1)
    year = m1["ts_utc"].dt.year.to_numpy()
    ny = m1["ts_utc"].dt.tz_convert(ev.NY)
    pct = pd.Series(atr).groupby(year).rank(pct=True).to_numpy()
    q = np.where(np.isfinite(pct), np.minimum((pct * 5).astype("float"), 4.999), np.nan)
    ok = np.isfinite(q) & (ny.dt.day_of_week.to_numpy() < 5)
    key = np.where(ok, year * 1000 + ny.dt.hour.to_numpy() * 10 + np.nan_to_num(q).astype(int), -1)
    return Bars(mins, mins + 1, c + spread / 2, spread + ev.COMMISSION, atr, year, key)


def markout_bar(bx: Bars, i: np.ndarray, h: int) -> np.ndarray:
    """The bar whose close ends the h-minute markout from bar i; -1: none within LATE minutes."""
    target = bx.close_min[i] + h
    j = np.minimum(np.searchsorted(bx.close_min, target, "left"), len(bx.mid) - 1)
    late = bx.close_min[j] - target
    return np.where((late >= 0) & (late <= LATE), j, -1) if len(i) else np.array([], int)


def z_markout(bx: Bars, i: np.ndarray, sign: np.ndarray, h: int) -> np.ndarray:
    """z(h) of events (bar i, sign); NaN where the markout bar is missing."""
    j = markout_bar(bx, i, h)
    ok = j >= 0
    z = np.full(len(i), np.nan)
    z[ok] = sign[ok] * (bx.mid[j[ok]] - bx.mid[i[ok]]) / bx.cost[i[ok]]
    return z


def atr_markout(bx: Bars, i: np.ndarray, sign: np.ndarray, h: int) -> np.ndarray:
    j = markout_bar(bx, i, h)
    ok = j >= 0
    out = np.full(len(i), np.nan)
    out[ok] = sign[ok] * (bx.mid[j[ok]] - bx.mid[i[ok]]) / bx.atr[i[ok]]
    return out


# --- E0 -------------------------------------------------------------------------------------------


def e0_draws(bx: Bars, i: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """E0_DRAWS matched bars per event (-1 where its stratum is empty)."""
    em = np.sort(bx.mins[i])
    k = np.searchsorted(em, bx.mins)
    near = np.full(len(bx.mins), np.inf)
    for kk in (k - 1, k):
        ok = (kk >= 0) & (kk < len(em))
        near[ok] = np.minimum(near[ok], np.abs(bx.mins[ok] - em[kk[ok]]))
    pool = np.flatnonzero((bx.key >= 0) & (near > E0_GAP))
    pool = pool[np.argsort(bx.key[pool], kind="stable")]
    pk = bx.key[pool]
    ek = bx.key[i]
    lo, hi = np.searchsorted(pk, ek, "left"), np.searchsorted(pk, ek, "right")
    n = hi - lo
    u = rng.random((len(i), E0_DRAWS))
    pos = lo[:, None] + np.floor(u * np.maximum(n, 1)[:, None]).astype(int)
    out = np.where((n > 0)[:, None] & (ek >= 0)[:, None], pool[np.minimum(pos, len(pool) - 1)], -1)
    return out


def e0_z(bx: Bars, draws: np.ndarray, sign: np.ndarray, h: int) -> np.ndarray:
    """Per event: the mean z(h) of its matched bars, taking the event's sign."""
    flat = draws.ravel()
    s = np.repeat(sign, draws.shape[1]).astype(float)
    z = np.full(len(flat), np.nan)
    ok = flat >= 0
    z[ok] = z_markout(bx, flat[ok], s[ok], h)
    z = z.reshape(draws.shape)
    n = np.isfinite(z).sum(axis=1)
    s = np.where(np.isfinite(z), z, 0.0).sum(axis=1)
    return np.where(n > 0, s / np.maximum(n, 1), np.nan)


# --- placebos -------------------------------------------------------------------------------------


def _hhmm(h: int, m: int) -> str:
    return f"{h % 24:02d}:{m:02d}"


def f2_placebo(m1: pd.DataFrame) -> pd.DataFrame:
    """F2's rule with the window moved 2 hours earlier and later (pooled); MONTHEND: 16:00 London
    on the 5 trading days before the month's last."""
    ts = m1["ts_utc"]
    c = m1["close"].to_numpy()
    days = pd.Series(pd.to_datetime(ts.dt.tz_convert(ev.LONDON).dt.date.unique()))
    days = days[days.dt.day_of_week < 5].reset_index(drop=True)
    month = days.dt.to_period("M")
    rank = days.groupby(month).rank(ascending=False, method="first").to_numpy()
    passed = month.isin(ev.month_ends(days).index).to_numpy()  # as F2: complete months only
    before_last = days[(rank >= 2) & (rank <= 1 + PLACEBO_DAYS) & passed]
    out = []
    for name, (hhmm, tz) in ev.WINDOWS.items():
        hh, mm = (int(x) for x in hhmm.split(":"))
        if name == "MONTHEND":
            plans = [(before_last, hhmm)]
        else:
            plans = [(days, _hhmm(hh + s, mm)) for s in (-SHIFT_HOURS, SHIFT_HOURS)]
        for lb in ev.LOOKBACKS:
            idx, sg = [], []
            for dd, t in plans:
                when = ev.window_times(dd.dt.strftime("%Y-%m-%d"), t, tz)
                k = ev.close_index(ts, when)
                b = ev.close_index(ts, when - pd.Timedelta(minutes=lb))
                ok = (k >= 0) & (b >= 0)
                idx.append(k[ok])
                sg.append(-np.sign(c[k[ok]] - c[b[ok]]))
            out.append(ev._frame("F2", f"{name}-{lb}", np.concatenate(idx), np.concatenate(sg)))
    return pd.concat(out, ignore_index=True)


def f3_placebo(m1: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """F3's rule at the release's New York clock minute on the 5 nearest trading days with no
    high-importance USD release within 60 minutes."""
    usd = cal[cal["currency"] == "USD"]
    every = np.sort(
        usd.loc[usd["importance"] == 3, "ts_utc"]
        .dt.tz_convert("UTC")
        .dt.tz_localize(None)
        .to_numpy("datetime64[m]")
        .astype("int64")
    )
    sets = {"TOP3": usd[usd["event"].isin(ev.TOP3)], "HIGH": usd[usd["importance"] == 3]}
    ny_dates = m1["ts_utc"].dt.tz_convert(ev.NY).dt.normalize().dt.tz_localize(None)
    tdays = np.unique(ny_dates[ny_dates.dt.day_of_week < 5].to_numpy("datetime64[D]"))
    c = m1["close"].to_numpy()
    out = []
    for name, evs in sets.items():
        r = pd.to_datetime(
            pd.Series(evs["ts_utc"].drop_duplicates().sort_values().to_numpy()), utc=True
        )
        loc = r.dt.tz_convert(ev.NY)
        when = []
        for q in range(len(r)):
            d0 = np.datetime64(loc.iloc[q].date(), "D")
            if not len(tdays) or d0 < tdays[0] or d0 > tdays[-1]:
                continue  # a release outside the data has no placebo days in it
            p = int(np.searchsorted(tdays, d0))
            hhmm = loc.iloc[q].strftime("%H:%M")
            got, step = 0, 1
            while got < PLACEBO_DAYS and step < 60:
                for cand in (p - step, p + step):
                    if got >= PLACEBO_DAYS or not 0 <= cand < len(tdays) or tdays[cand] == d0:
                        continue
                    if abs((tdays[cand] - d0).astype(int)) > MAX_PLACEBO_GAP:
                        continue
                    t = pd.Timestamp(f"{tdays[cand]} {hhmm}").tz_localize(
                        ev.NY, ambiguous="NaT", nonexistent="NaT"
                    )
                    if t is pd.NaT:
                        continue
                    tm = int(
                        t.tz_convert("UTC")
                        .tz_localize(None)
                        .to_datetime64()
                        .astype("datetime64[m]")
                        .astype("int64")
                    )
                    j = np.searchsorted(every, tm)
                    near = (
                        min(abs(every[jj] - tm) for jj in (j - 1, j) if 0 <= jj < len(every))
                        if len(every)
                        else np.inf
                    )
                    if near > RELEASE_GAP:
                        when.append(t.tz_convert("UTC"))
                        got += 1
                step += 1
        w = pd.Series(pd.DatetimeIndex(when).unique())  # two releases can share a placebo minute
        base = ev.close_index(m1["ts_utc"], w)
        for d in ev.DELAYS:
            k = ev.close_index(m1["ts_utc"], w + pd.Timedelta(minutes=d))
            ok = (base >= 0) & (k >= 0)
            out.append(ev._frame("F3", f"{name}+{d}", k[ok], np.sign(c[k[ok]] - c[base[ok]])))
    return pd.concat(out, ignore_index=True)


def f1_placebo(m1: pd.DataFrame, dxy: pd.DataFrame, bond: pd.DataFrame) -> pd.DataFrame:
    """F1's rule with both drivers moved by +7 and -7 days (pooled)."""
    dxy = dxy[dxy["ts_utc"] >= ev.DXY_FROM]
    bond = bond[bond["ts_utc"] >= ev.BOND_FROM]
    parts = []
    for s in (DRIVER_SHIFT, -DRIVER_SHIFT):
        parts.append(
            ev.f1(m1, dxy.assign(ts_utc=dxy["ts_utc"] + s), bond.assign(ts_utc=bond["ts_utc"] + s))
        )
    return pd.concat(parts, ignore_index=True)


def f5_placebo(m1: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """F5p's rule on grids moved by GRID_DRAWS random offsets in (0.1, 0.9) of the step."""
    parts = []
    for _ in range(GRID_DRAWS):
        off = {g: float(rng.uniform(0.1, 0.9)) * g for g in ev.GRIDS}
        parts.append(ev.f5(m1, off))
    return pd.concat(parts, ignore_index=True)


# --- statistics -----------------------------------------------------------------------------------


def block_ids(mins: np.ndarray, start_min: int) -> np.ndarray:
    return (mins - start_min) // BLOCK_MIN


def resamples(n_blocks: int, seed: int = SEED_BOOT, b: int = B) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, n_blocks, size=(b, n_blocks))


def boot_t(
    idx: np.ndarray,
    blk_a: np.ndarray,
    a: np.ndarray,
    blk_b: np.ndarray | None = None,
    b: np.ndarray | None = None,
) -> tuple[float, float]:
    """(observed difference, t) of mean(a) - mean(b) (b absent: mean(a)) under a joint block
    bootstrap with resampled block indices ``idx`` (B x blocks)."""
    nb = idx.shape[1]

    def sums(blk, x):
        ok = np.isfinite(x) & (blk >= 0) & (blk < nb)
        s = np.bincount(blk[ok], x[ok], minlength=nb)
        n = np.bincount(blk[ok], minlength=nb).astype(float)
        return s, n

    sa, na = sums(blk_a, a)
    if na.sum() < 2:
        return np.nan, np.nan
    obs = sa.sum() / na.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        star = sa[idx].sum(1) / na[idx].sum(1)
        if b is not None:
            sb, nbb = sums(blk_b, b)
            if nbb.sum() < 2:
                return np.nan, np.nan
            obs -= sb.sum() / nbb.sum()
            star = star - sb[idx].sum(1) / nbb[idx].sum(1)
    se = np.nanstd(star, ddof=1)
    return float(obs), float(obs / se) if se > 0 else np.nan


def p_two_sided(t: np.ndarray) -> np.ndarray:
    from scipy.stats import norm

    return 2 * norm.sf(np.abs(t))


def benjamini_hochberg(p: np.ndarray, q: float = 0.10) -> np.ndarray:
    """True where the hypothesis is rejected at FDR q (NaN p: not rejected)."""
    p = np.where(np.isfinite(p), p, 1.0)
    m = len(p)
    order = np.argsort(p)
    ok = p[order] <= q * np.arange(1, m + 1) / m
    out = np.zeros(m, bool)
    if ok.any():
        out[order[: np.flatnonzero(ok).max() + 1]] = True
    return out


def holm(p: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    p = np.where(np.isfinite(p), p, 1.0)
    m = len(p)
    out = np.zeros(m, bool)
    for r, k in enumerate(np.argsort(p)):
        if p[k] > alpha / (m - r):
            break
        out[k] = True
    return out


def stable(years: np.ndarray, d: np.ndarray, two_years: bool = False) -> bool:
    """No calendar year carries more than half of the summed excess (two years: the same sign)."""
    ok = np.isfinite(d)
    s = pd.Series(d[ok]).groupby(years[ok]).sum()
    total = s.sum()
    if total == 0 or len(s) == 0:
        return False
    if two_years:
        return bool((np.sign(s) == np.sign(total)).all() and len(s) >= 2)
    return bool((s / total).max() <= 0.5)
