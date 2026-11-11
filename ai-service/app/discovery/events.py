"""Event detectors for discovery round 2 (``docs/discovery/PLAN.md`` §4, stage D2).

Every detector is a pure function of closed M1 bars (and the calendar or the drivers) up to the
event's bar: an event is (family, cell, i, sign), where ``i`` is the M1 bar whose close is the
event time t0 and ``sign`` the family's direction hypothesis. Nothing after t0 is read. The cells
here are provisional; ``PREREG_2.md`` freezes them.

- **F3, news:** a release minute r (UTC); the bar closing at r + d (d = 1, 5, 15 minutes); sign =
  the move from the close at r to the close at r + d (drift; a reversal shows as a negative
  markout). Sets: TOP3 (NFP, CPI m/m, the Fed decision) and HIGH (every high-importance USD
  release; one event per minute).
- **F2, forced flow:** the LBMA PM auction (15:00 London), the WM/Reuters fix (16:00 London),
  COMEX settlement (13:30 New York), the WM fix on the month's last trading day; sign = against
  the move over the L minutes into the window (L = 30, 60).
- **F1, unconfirmed move:** gold moves at least k x ATR(14, 1h) over w minutes; UNCONF when
  neither the dollar index fell nor the bond rose with it (sign: against gold's move), CONF when
  either moved with it by half its usual w-minute move (sign: with gold's move); 60-minute
  refractory per cell.
- **F5p, grids:** multiples of $25, $50, $100 and $75; BREAK = an M1 close across a level (sign:
  the cross), REJECT = a bar that trades through a level from the previous close and closes back
  (sign: back away); a level counts once per 60 minutes."""

from __future__ import annotations

import numpy as np
import pandas as pd

NY, LONDON = "America/New_York", "Europe/London"
COMMISSION = 0.07
TOP3 = ("Nonfarm Payrolls", "CPI m/m", "Fed Interest Rate Decision")
DELAYS = (1, 5, 15)
WINDOWS = {"PM": ("15:00", LONDON), "WM": ("16:00", LONDON), "COMEX": ("13:30", NY),
           "MONTHEND": ("16:00", LONDON)}  # fmt: skip
LOOKBACKS = (30, 60)
F1_K, F1_W, REFRACTORY = (0.5, 1.0), (15, 30), 60
# Dukascopy's dollar index has fake one-minute spikes through 2018 and its bond through 2019
# (``drivers.md``); F1 reads them only from these dates (Fadi, 2026-11-11, before any outcome).
DXY_FROM = pd.Timestamp("2019-01-01", tz="UTC")
BOND_FROM = pd.Timestamp("2020-01-01", tz="UTC")
GRIDS = (25.0, 50.0, 100.0, 75.0)
COLS = ["family", "cell", "i", "sign"]


def _frame(family: str, cell: str, i: np.ndarray, sign: np.ndarray) -> pd.DataFrame:
    ok = sign != 0
    return pd.DataFrame({"family": family, "cell": cell, "i": i[ok].astype(np.int64),
                         "sign": sign[ok].astype(np.int8)})  # fmt: skip


def close_index(ts: pd.Series, when: pd.Series) -> np.ndarray:
    """The M1 bar whose close (open + 1 minute) is exactly ``when``; -1: none."""
    t = ts.to_numpy("datetime64[ns]")
    w = pd.DatetimeIndex(when).tz_convert("UTC").tz_localize(None) - pd.Timedelta(minutes=1)
    k = np.searchsorted(t, w.to_numpy("datetime64[ns]"))
    k = np.minimum(k, len(t) - 1)
    return np.where(t[k] == w.to_numpy("datetime64[ns]"), k, -1)


# --- F3 -------------------------------------------------------------------------------------------


def f3(m1: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    usd = cal[cal["currency"] == "USD"]
    sets = {"TOP3": usd[usd["event"].isin(TOP3)], "HIGH": usd[usd["importance"] == 3]}
    c = m1["close"].to_numpy()
    out = []
    for name, ev in sets.items():
        r = pd.Series(ev["ts_utc"].drop_duplicates().sort_values().to_numpy())
        r = pd.to_datetime(r, utc=True)
        base = close_index(m1["ts_utc"], r)
        for d in DELAYS:
            k = close_index(m1["ts_utc"], r + pd.Timedelta(minutes=d))
            ok = (base >= 0) & (k >= 0)
            sign = np.sign(c[k[ok]] - c[base[ok]])
            out.append(_frame("F3", f"{name}+{d}", k[ok], sign))
    return pd.concat(out, ignore_index=True)


# --- F2 -------------------------------------------------------------------------------------------


def window_times(days: pd.Series, hhmm: str, tz: str) -> pd.Series:
    """``hhmm`` local time on each calendar day of ``days`` (dates), as UTC timestamps."""
    local = pd.to_datetime(days.astype(str) + " " + hhmm).dt.tz_localize(
        tz, ambiguous="NaT", nonexistent="NaT"
    )
    return local.dt.tz_convert("UTC").dropna()


def f2(m1: pd.DataFrame) -> pd.DataFrame:
    ts = m1["ts_utc"]
    c = m1["close"].to_numpy()
    days = pd.Series(pd.to_datetime(ts.dt.tz_convert(LONDON).dt.date.unique()))
    days = days[days.dt.day_of_week < 5]
    last = days.groupby(days.dt.to_period("M")).max()
    out = []
    for name, (hhmm, tz) in WINDOWS.items():
        dd = pd.Series(last.to_numpy()) if name == "MONTHEND" else days
        when = window_times(dd.dt.strftime("%Y-%m-%d"), hhmm, tz)
        k = close_index(ts, when)
        for lb in LOOKBACKS:
            b = close_index(ts, when - pd.Timedelta(minutes=lb))
            ok = (k >= 0) & (b >= 0)
            sign = -np.sign(c[k[ok]] - c[b[ok]])
            out.append(_frame("F2", f"{name}-{lb}", k[ok], sign))
    return pd.concat(out, ignore_index=True)


# --- F1 -------------------------------------------------------------------------------------------


def atr_1h(m1: pd.DataFrame, n: int = 14) -> np.ndarray:
    """ATR(14) of hourly bars built from M1, per M1 bar: the last hour closed by its close."""
    ts = m1["ts_utc"]
    h = m1.groupby(ts.dt.floor("1h"), sort=True).agg(
        h=("high", "max"), l=("low", "min"), c=("close", "last")
    )
    prev = h["c"].shift()
    tr = pd.concat([h["h"] - h["l"], (h["h"] - prev).abs(), (h["l"] - prev).abs()], axis=1)
    atr = tr.max(axis=1).ewm(alpha=1 / n, adjust=False).mean()
    hour_close = (h.index + pd.Timedelta(hours=1)).to_numpy("datetime64[ns]")
    bar_close = (ts + pd.Timedelta(minutes=1)).dt.tz_localize(None).to_numpy("datetime64[ns]")
    hc = pd.DatetimeIndex(hour_close).tz_localize(None).to_numpy("datetime64[ns]")
    k = np.searchsorted(hc, bar_close, side="right") - 1
    return np.where(k >= 0, atr.to_numpy()[np.maximum(k, 0)], np.nan)


def aligned(m1: pd.DataFrame, drv: pd.DataFrame, stale: int = 5) -> np.ndarray:
    """A driver's last close at or before each gold bar's open, within ``stale`` minutes."""
    g = pd.DataFrame({"ts_utc": m1["ts_utc"].dt.as_unit("ns")})
    d = drv[["ts_utc", "close"]].sort_values("ts_utc")
    d = d.assign(ts_utc=d["ts_utc"].dt.as_unit("ns"))  # the stores differ in resolution
    j = pd.merge_asof(g, d, on="ts_utc", direction="backward",
                      tolerance=pd.Timedelta(minutes=stale))  # fmt: skip
    return j["close"].to_numpy()


def minutes(ts: pd.Series) -> np.ndarray:
    """Whole minutes since the epoch, whatever the timestamps' resolution."""
    return ts.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[m]").astype("int64")


def refractory(i: np.ndarray, minutes: np.ndarray, gap: int = REFRACTORY) -> np.ndarray:
    """Keep an event only if it is at least ``gap`` minutes after the last kept one."""
    keep = np.zeros(len(i), bool)
    last = -np.inf
    for q in range(len(i)):
        if minutes[q] - last >= gap:
            keep[q] = True
            last = minutes[q]
    return keep


def f1(m1: pd.DataFrame, dxy: pd.DataFrame, bond: pd.DataFrame) -> pd.DataFrame:
    c = m1["close"].to_numpy()
    atr = atr_1h(m1)
    dxy = dxy[dxy["ts_utc"] >= DXY_FROM]
    bond = bond[bond["ts_utc"] >= BOND_FROM]
    x, b = aligned(m1, dxy), aligned(m1, bond)
    mins = minutes(m1["ts_utc"])
    out = []
    for w in F1_W:
        dg = c - np.r_[np.full(w, np.nan), c[:-w]]
        same = mins - np.r_[np.full(w, -(10**9)), mins[:-w]] == w  # w minutes apart, no gap
        dx = np.log(x) - np.log(np.r_[np.full(w, np.nan), x[:-w]])
        db = np.log(b) - np.log(np.r_[np.full(w, np.nan), b[:-w]])
        # the drivers' usual w-minute move: std over the previous 5 days of bars, known at t
        sx = pd.Series(dx).shift(1).rolling(7200, min_periods=1000).std().to_numpy()
        sb = pd.Series(db).shift(1).rolling(7200, min_periods=1000).std().to_numpy()
        for k in F1_K:
            big = same & np.isfinite(dg) & (np.abs(dg) >= k * atr)
            s = np.sign(dg)
            exp_x, exp_b = -s * dx, s * db  # > 0: moved the way that confirms gold
            conf = big & ((exp_x > 0.5 * sx) | (exp_b > 0.5 * sb))
            unconf = big & (exp_x <= 0) & (exp_b <= 0)
            for name, m, sign in (("UNCONF", unconf, -s), ("CONF", conf, s)):
                idx = np.flatnonzero(m & np.isfinite(dx) & np.isfinite(db))
                keep = refractory(idx, mins[idx])
                out.append(_frame("F1", f"{name}-k{k:g}-w{w}", idx[keep], sign[idx[keep]]))
    return pd.concat(out, ignore_index=True)


# --- F5p ------------------------------------------------------------------------------------------


def f5(m1: pd.DataFrame, offsets: dict[float, float] | None = None) -> pd.DataFrame:
    """Grid events; ``offsets`` shifts each grid (the placebo), 0 by default."""
    c, h, lo = (m1[k].to_numpy() for k in ("close", "high", "low"))
    prev = np.r_[np.nan, c[:-1]]
    mins = minutes(m1["ts_utc"])
    out = []
    for g in GRIDS:
        off = (offsets or {}).get(g, 0.0)
        lvl_up = np.floor((prev - off) / g) * g + g + off  # the first level above the last close
        lvl_dn = np.ceil((prev - off) / g) * g - g + off  # the first level below it
        for name in ("BREAK", "REJECT"):
            if name == "BREAK":
                up, dn = c >= lvl_up, c <= lvl_dn
                sign = np.where(up, 1, np.where(dn, -1, 0))
                lvl = np.where(up, lvl_up, lvl_dn)
            else:
                up = (h >= lvl_up) & (c < lvl_up)
                dn = (lo <= lvl_dn) & (c > lvl_dn)
                sign = np.where(up & ~dn, -1, np.where(dn & ~up, 1, 0))
                lvl = np.where(up, lvl_up, lvl_dn)
            idx = np.flatnonzero((sign != 0) & np.isfinite(prev))
            # a level counts once per 60 minutes
            key = pd.DataFrame({"i": idx, "lvl": np.round(lvl[idx], 3), "m": mins[idx]})
            keep = np.zeros(len(key), bool)
            for _, grp in key.groupby("lvl", sort=False):
                k_ = refractory(grp["i"].to_numpy(), grp["m"].to_numpy())
                keep[grp.index.to_numpy()[k_]] = True
            out.append(_frame("F5p", f"{name}-{g:g}", idx[keep], sign[idx[keep]]))
    return pd.concat(out, ignore_index=True).sort_values("i", kind="stable").reset_index(drop=True)


def cost_unit(m1: pd.DataFrame, i: np.ndarray) -> np.ndarray:
    """c(t0): the event bar's recorded spread + the round-trip commission, in price units."""
    return m1["spread"].to_numpy()[i] + COMMISSION
