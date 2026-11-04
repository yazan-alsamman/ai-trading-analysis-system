"""Gold lab: the commercial track (Fadi, 2026-11-04). Exploratory, not part of the registered
research: XAUUSD only, scalp and intraday, every bar from 2012 to the lockbox start may be used for
development (holdout included), and the lockbox (2026-01-10 onward) stays sealed for one final
exam of the finished combination.

    python -m app research gold-lab screen      # every candidate strategy, M0 and M8

**Signals.** The frozen S1, S4, S6 (and S6 reversed) and S7 entry rules (``app.strategies``), and
new rules written here (``NEW``). Every trade is simulated on the 5m bars: entry at the close of
the signal bar (or at the level for a stop entry), SL and TP checked bar by bar (a bar reaching
both counts as the SL), forced exit at the session end (16:45 New York) or the horizon, one active
trade per strategy.

**Management.** M0: fixed SL and TP. M8 (activated for scalps by Stage D and the holdout): at +1 R
the SL moves to entry + the round-trip cost, then trails to the last confirmed 5m swing low (high
for sells; k = 2) - 0.1 x ATR(14, 5m); no TP; the same exits.

**Costs** (measured in MT5, ``mt5_cost_check.md``): the recorded spread of the signal bar (it
matched the tester on gold) + $0.07 per oz commission, per round trip. Reported with and without
an extra $0.10 slippage on stop exits.

**Screen.** Per strategy: trades a day, gross R, cost R, net R, the share of years with net R > 0,
and net R in 2012-2018 and 2019-2026. A candidate survives with net R > 0, at least 60% of years
positive and both halves positive."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import instruments, signal_specs
from app.data.importer import DEFAULT_OUT as STORE
from app.strategies import frames as F
from app.strategies.cli import OUT_DIR
from app.strategies.rules import candidates

SYM = "XAUUSD"
WARM = pd.Timestamp("2011-09-01", tz="UTC")  # gold before 2011-08 is on a shifted clock
START = pd.Timestamp("2012-01-01", tz="UTC")
LOCKBOX = pd.Timestamp("2026-01-10", tz="UTC")
COMMISSION = 0.07  # $ per oz, round trip (FxPro Raw, $3.5 per lot per side)
SL_SLIP = 0.10
NY = "America/New_York"
REPORT = OUT_DIR / "gold_lab_screen.md"


# --- data and helpers ------------------------------------------------------------------------


def load(sym: str = SYM) -> dict[str, pd.DataFrame]:
    return F.load(sym, WARM, LOCKBOX)


def wilder(h, lo, c, n=14) -> np.ndarray:
    prev = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - lo, np.abs(h - prev), np.abs(lo - prev)], axis=1)
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def on_5m(m: pd.DataFrame, frame: pd.DataFrame, values: np.ndarray) -> np.ndarray:
    """A higher-frame series as known at each 5m bar's close (the last bar closed by then)."""
    k = np.searchsorted(frame["close_utc"].to_numpy(), m["close_utc"].to_numpy(), "right") - 1
    return np.where(k >= 0, values[np.maximum(k, 0)], np.nan)


@dataclass
class Ctx:
    """The 5m bars and the series every rule needs."""

    m: pd.DataFrame
    o: np.ndarray
    h: np.ndarray
    lo: np.ndarray
    c: np.ndarray
    spread: np.ndarray
    atr5: np.ndarray
    atr1h: np.ndarray
    atr4h: np.ndarray
    atrd: np.ndarray
    ny_min: np.ndarray  # minutes since New York midnight at the bar open
    ny_day: np.ndarray  # New York date (int) of the bar open
    weekday: np.ndarray
    deadline: np.ndarray  # index of the last 5m bar closing by 16:45 New York that day
    day_idx: np.ndarray  # D1 bar of each 5m bar (17:00 New York days)
    d1: pd.DataFrame


def context(fr: dict[str, pd.DataFrame]) -> Ctx:
    m = fr["5m"]
    o, h, lo, c = (m[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = {tf: wilder(*(fr[tf][k].to_numpy() for k in ("high", "low", "close"))) for tf in ("1h", "4h", "D1")}
    ny = m["ts_utc"].dt.tz_convert(NY)
    ny_min = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
    ny_day = (ny.dt.year * 10000 + ny.dt.month * 100 + ny.dt.day).to_numpy()
    close_ny = m["close_utc"].dt.tz_convert(NY)
    cmin = (close_ny.dt.hour * 60 + close_ny.dt.minute).to_numpy()
    same_day = (close_ny.dt.normalize() == ny.dt.normalize()).to_numpy()  # not the 23:55 bar
    ok_end = (cmin <= 16 * 60 + 45) & same_day
    # last bar of each New York day closing by 16:45
    idx = np.arange(len(m))
    last = pd.Series(np.where(ok_end, idx, -1)).groupby(ny_day).transform("max").to_numpy()
    d1 = fr["D1"]
    day_idx = np.searchsorted(d1["ts_utc"].to_numpy(), m["ts_utc"].to_numpy(), "right") - 1
    return Ctx(m, o, h, lo, c, m["spread_mean"].to_numpy(), wilder(h, lo, c),
               on_5m(m, fr["1h"], a["1h"]), on_5m(m, fr["4h"], a["4h"]), on_5m(m, d1, a["D1"]),
               ny_min, ny_day, ny.dt.day_of_week.to_numpy(), last, day_idx, d1)  # fmt: skip


# --- signals ---------------------------------------------------------------------------------
# A signal: the 5m bar index of the entry (its close, or the touch bar for a stop entry), the
# direction (+1 / -1), the entry price, the risk (price), the TP in R (NaN: none), the last bar
# index the trade may live to.

COLS = ["strategy", "i", "dir", "entry", "risk", "tp_r", "end"]


def _frame(rows: dict, name: str) -> pd.DataFrame:
    d = pd.DataFrame(rows)
    d.insert(0, "strategy", name)
    return d[COLS]


def frozen(fr: dict[str, pd.DataFrame], cx: Ctx) -> list[pd.DataFrame]:
    """S1, S4, S6, S7 armed candidates, and S6 reversed, mapped to the 5m bars."""
    inst = instruments()[SYM]
    out = []
    m_close = cx.m["close_utc"].to_numpy()
    for name in ("S1", "S4", "S6", "S7"):
        spec = signal_specs()[name]
        e = fr[spec.frame]
        cs = [c for c in candidates(fr, inst, spec) if c.state == "ARMED"]
        close = e["close_utc"].to_numpy()[[c.idx for c in cs]]
        i = np.searchsorted(m_close, close)
        ok = (i < len(m_close)) & (m_close[np.minimum(i, len(m_close) - 1)] == close)
        step = int(pd.Timedelta(spec.frame).total_seconds() // 300)
        rows = {
            "i": i, "dir": np.array([c.sign for c in cs]), "entry": np.array([c.entry for c in cs]),
            "risk": np.array([c.risk for c in cs]),
            "tp_r": np.array([c.r_multiple if c.r_multiple else np.nan for c in cs]),
            "end": np.minimum(i + spec.horizon_bars * step, cx.deadline[np.minimum(i, len(m_close) - 1)]),
        }  # fmt: skip
        d = _frame(rows, name)[ok]
        out.append(d)
        if name == "S6":
            out.append(d.assign(strategy="S6R", dir=-d["dir"]))
    return out


def _liquid(cx: Ctx) -> np.ndarray:
    return (cx.weekday < 5) & (cx.ny_min >= 120) & (cx.ny_min < 16 * 60)


def _simple(cx: Ctx, name: str, sel: np.ndarray, d: np.ndarray, risk: np.ndarray, tp_r: float,
            horizon: int) -> pd.DataFrame:  # fmt: skip
    i = np.flatnonzero(sel & np.isfinite(risk) & (risk > 0))
    return _frame({"i": i, "dir": d[i], "entry": cx.c[i], "risk": risk[i], "tp_r": tp_r,
                   "end": np.minimum(i + horizon, cx.deadline[i])}, name)  # fmt: skip


def ny_momentum(cx: Ctx) -> pd.DataFrame:
    """6: at the 10:25 bar's close (10:30 New York), the move since 09:30; >= 1 x ATR(1h): go
    with it, risk 1 x ATR(1h), TP 1.5 R, to 12:00."""
    at = cx.ny_min == 10 * 60 + 25
    ref = pd.Series(np.where(cx.ny_min == 9 * 60 + 25, cx.c, np.nan)).groupby(cx.ny_day).transform("max").to_numpy()
    mv = cx.c - ref
    sel = at & (np.abs(mv) >= cx.atr1h) & (cx.weekday < 5)
    return _simple(cx, "NYMOM", sel, np.sign(mv), cx.atr1h, 1.5, 18)


def news_830(cx: Ctx) -> pd.DataFrame:
    """7 (proxy without a calendar): the 08:30-08:45 New York move; >= 0.75 x ATR(1h): go with it
    at 08:45, risk 1 x ATR(1h), TP 1.5 R, 2 h."""
    at = cx.ny_min == 8 * 60 + 40
    ref = pd.Series(np.where(cx.ny_min == 8 * 60 + 30, cx.o, np.nan)).groupby(cx.ny_day).transform("max").to_numpy()
    mv = cx.c - ref
    sel = at & (np.abs(mv) >= 0.75 * cx.atr1h) & (cx.weekday < 5)
    return _simple(cx, "NEWS830", sel, np.sign(mv), cx.atr1h, 1.5, 24)


def extreme_bar(cx: Ctx) -> pd.DataFrame:
    """8: a 5m bar with range >= 3 x ATR(14, 5m), not at 08:30, 10:00 or 14:00 New York: fade it
    at its close; SL beyond its extreme + 0.25 ATR, TP 1 R, 1 h."""
    rng_ = cx.h - cx.lo
    prev_atr = np.r_[np.nan, cx.atr5[:-1]]
    news = np.isin(cx.ny_min, [8 * 60 + 30, 10 * 60, 14 * 60])
    up = cx.c > cx.o
    sel = _liquid(cx) & (rng_ >= 3 * prev_atr) & ~news
    d = np.where(up, -1.0, 1.0)
    sl = np.where(up, cx.h + 0.25 * cx.atr5, cx.lo - 0.25 * cx.atr5)
    return _simple(cx, "EXTREME", sel, d, np.abs(sl - cx.c), 1.0, 12)


def ema_cross(cx: Ctx, reverse: bool = False) -> pd.DataFrame:
    """12 (17 reversed): EMA 9 / 21 cross on 5m; SL 1.5 x ATR(5m), TP 1.5 R, 2 h."""
    s = pd.Series(cx.c)
    f, slow = s.ewm(span=9, adjust=False).mean().to_numpy(), s.ewm(span=21, adjust=False).mean().to_numpy()
    diff = np.sign(f - slow)
    cross = (diff != np.r_[0, diff[:-1]]) & (np.r_[0, diff[:-1]] != 0)
    d = diff * (-1 if reverse else 1)
    return _simple(cx, "EMAX_R" if reverse else "EMAX", _liquid(cx) & cross, d, 1.5 * cx.atr5, 1.5, 24)


def rsi2(cx: Ctx, fr: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """11: RSI(2) on 15m below 10 above EMA(200, 15m): buy; above 90 below it: sell; SL 1.5 x
    ATR(15m), TP 1 R, 2 h."""
    q = fr["15m"]
    c = q["close"]
    delta = c.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn)).to_numpy()
    ema = c.ewm(span=200, adjust=False).mean().to_numpy()
    a15 = wilder(q["high"].to_numpy(), q["low"].to_numpy(), c.to_numpy())
    d = np.where((rsi < 10) & (c.to_numpy() > ema), 1.0, np.where((rsi > 90) & (c.to_numpy() < ema), -1.0, 0.0))
    # 15m signals at their close, on the 5m bar closing at the same time
    m_close = cx.m["close_utc"].to_numpy()
    j = np.searchsorted(m_close, q["close_utc"].to_numpy())
    ok = (j < len(m_close)) & (m_close[np.minimum(j, len(m_close) - 1)] == q["close_utc"].to_numpy()) & (d != 0)
    sel = np.zeros(len(cx.c), bool)
    dd, rr = np.zeros(len(cx.c)), np.full(len(cx.c), np.nan)
    sel[j[ok]] = True
    dd[j[ok]], rr[j[ok]] = d[ok], 1.5 * a15[ok]
    return _simple(cx, "RSI2", sel & _liquid(cx), dd, rr, 1.0, 24)


def _level_trades(cx: Ctx, name: str, levels: dict[str, np.ndarray], dist: np.ndarray,
                  horizon: int) -> pd.DataFrame:  # fmt: skip
    """A stop entry with the break at the first touch of the day of each level (the Addendum 2
    mechanism): entry at the level (or the bar open when it gapped through), SL / TP at D."""
    prev = np.r_[np.nan, cx.c[:-1]]
    ok = _liquid(cx) & np.isfinite(dist) & (dist > 0)
    out = []
    for lv_day in levels.values():
        lv = lv_day[np.maximum(cx.day_idx, 0)]
        up = (prev < lv) & (cx.h >= lv)
        dn = (prev > lv) & (cx.lo <= lv)
        idx = np.flatnonzero(ok & (up | dn) & np.isfinite(lv))
        first = pd.Series(idx).groupby(cx.day_idx[idx]).min().to_numpy()
        d = np.where(up[first], 1.0, -1.0)
        entry = np.where(d > 0, np.maximum(lv[first], cx.o[first]), np.minimum(lv[first], cx.o[first]))
        out.append(pd.DataFrame({"i": first, "dir": d, "entry": entry, "risk": dist[first], "tp_r": 1.0,
                                 "end": np.minimum(first + horizon, cx.deadline[first])}))  # fmt: skip
    return _frame(pd.concat(out, ignore_index=True).to_dict("list"), name)


def levels_4h(cx: Ctx) -> pd.DataFrame:
    """10: the level break of Addendum 2 with D = ATR(14, 4h) to the session end."""
    dh, dl = cx.d1["high"].to_numpy(), cx.d1["low"].to_numpy()
    lv = {"PDH": np.r_[np.nan, dh[:-1]], "PDL": np.r_[np.nan, dl[:-1]],
          "5DH": pd.Series(dh).rolling(5).max().shift(1).to_numpy(),
          "5DL": pd.Series(dl).rolling(5).min().shift(1).to_numpy()}  # fmt: skip
    return _level_trades(cx, "LVL4H", lv, cx.atr4h, 200)


def pivots(cx: Ctx) -> pd.DataFrame:
    """13: classic daily pivots R1 / S1, the break at the first touch, D = ATR(14, 1h), 4 h."""
    h, lo, c = (cx.d1[k].to_numpy() for k in ("high", "low", "close"))
    p = (h + lo + c) / 3
    lv = {"R1": np.r_[np.nan, (2 * p - lo)[:-1]], "S1": np.r_[np.nan, (2 * p - h)[:-1]]}
    return _level_trades(cx, "PIVOT", lv, cx.atr1h, 48)


def reopen_gap(cx: Ctx) -> pd.DataFrame:
    """16: the daily reopen (18:00 New York): a gap of >= 0.5 x ATR(1h) from the 17:00 close is
    faded at the first bar's close; TP at the gap's fill (R from the risk), SL one gap beyond,
    2 h (no session end)."""
    first = (cx.ny_min == 18 * 60) & (cx.weekday != 5)
    i = np.flatnonzero(first)
    i = i[i > 0]
    gap = cx.o[i] - cx.c[i - 1]
    keep = np.abs(gap) >= 0.5 * cx.atr1h[i]
    i, gap = i[keep], gap[keep]
    d = -np.sign(gap)
    tp_dist = np.abs(cx.c[i] - cx.c[i - 1])
    risk = np.abs(gap)
    ok = (tp_dist > 0) & (risk > 0)
    i, d, risk, tp_dist = i[ok], d[ok], risk[ok], tp_dist[ok]
    return pd.DataFrame({"strategy": "GAP", "i": i, "dir": d, "entry": cx.c[i], "risk": risk,
                         "tp_r": tp_dist / risk, "end": np.minimum(i + 24, len(cx.c) - 1)})  # fmt: skip


def dollar_lead(cx: Ctx, other: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """18: the dollar's 15-minute move (EURUSD down and USDJPY up) >= 2 standard deviations while
    gold moved < 0.3 x ATR(5m): trade gold against the dollar; SL 1.5 x ATR(5m), TP 1 R, 1 h."""
    t = cx.m["close_utc"]
    z = []
    for sym, sign in (("EURUSD", -1.0), ("USDJPY", 1.0)):
        b = other[sym]["5m"].set_index("close_utc")["close"]
        r = np.log(b).diff(3)
        zz = (r / r.rolling(2000, min_periods=500).std()).reindex(t).to_numpy()
        z.append(sign * zz)
    usd = np.nanmean(np.c_[z[0], z[1]], axis=1)
    gold_mv = np.abs(cx.c - np.r_[np.full(3, np.nan), cx.c[:-3]])
    sel = _liquid(cx) & (np.abs(usd) >= 2) & (gold_mv < 0.3 * cx.atr5) & np.all(np.isfinite(np.c_[z[0], z[1]]), axis=1)
    return _simple(cx, "USDLEAD", sel, -np.sign(usd), 1.5 * cx.atr5, 1.0, 12)


def spread_spike(cx: Ctx) -> pd.DataFrame:
    """19: the bar's mean spread >= 3 x its median of the last day: fade the last 3 bars' move;
    SL 1.5 x ATR(5m), TP 1 R, 1 h."""
    med = pd.Series(cx.spread).rolling(288, min_periods=100).median().shift(1).to_numpy()
    mv = cx.c - np.r_[np.full(3, np.nan), cx.c[:-3]]
    sel = _liquid(cx) & (cx.spread >= 3 * med) & (np.abs(mv) > 0)
    return _simple(cx, "SPREAD", sel, -np.sign(mv), 1.5 * cx.atr5, 1.0, 12)


BREAKOUTS = ("S1", "S4", "NYMOM", "NEWS830", "LVL4H", "PIVOT")


def big_day(cx: Ctx, sig: pd.DataFrame) -> pd.DataFrame:
    """22: breakout signals kept only after a day whose range was >= 1.5 x ATR(14, D1)."""
    rng_ = (cx.d1["high"] - cx.d1["low"]).to_numpy()
    ad = wilder(*(cx.d1[k].to_numpy() for k in ("high", "low", "close")))
    big = np.r_[False, (rng_ >= 1.5 * np.r_[np.nan, ad[:-1]])[:-1]]
    keep = big[np.maximum(cx.day_idx[sig["i"].to_numpy()], 0)]
    return sig[keep].assign(strategy=sig["strategy"] + "+BIG")


def all_signals(fr, cx: Ctx, other) -> pd.DataFrame:
    parts = frozen(fr, cx) + [ny_momentum(cx), news_830(cx), extreme_bar(cx), ema_cross(cx),
                              ema_cross(cx, reverse=True), rsi2(cx, fr), levels_4h(cx), pivots(cx),
                              reopen_gap(cx), dollar_lead(cx, other), spread_spike(cx)]  # fmt: skip
    s = pd.concat(parts, ignore_index=True)
    s = pd.concat([s, big_day(cx, s[s["strategy"].isin(BREAKOUTS)])], ignore_index=True)
    s = s[(s["i"] > 5) & (s["end"] > s["i"]) & (s["end"] < len(cx.c) - 1) & (s["risk"] > 0)]
    t = cx.m["close_utc"].to_numpy()[s["i"].to_numpy()]
    return s[pd.to_datetime(t, utc=True) >= START].reset_index(drop=True)


# --- simulation ------------------------------------------------------------------------------


def swing_lows(lo: np.ndarray, k: int = 2) -> np.ndarray:
    """At bar j: the low of the last swing low confirmed by j (low[j-k] below the k bars on each
    side), NaN before the first."""
    w = np.lib.stride_tricks.sliding_window_view(lo, 2 * k + 1)
    is_sw = w[:, k] == w.min(axis=1)
    val = np.full(len(lo), np.nan)
    val[2 * k:] = np.where(is_sw, w[:, k], np.nan)
    return pd.Series(val).ffill().to_numpy()


def simulate(sig: pd.DataFrame, cx: Ctx, bundle: str, events: list | None = None) -> pd.DataFrame:
    """Gross R and exit of every signal under M0 or M8, one active trade per strategy. ``events``
    collects each M8 SL move: (strategy, entry bar, first bar it is in force, new SL)."""
    h, lo, c = cx.h, cx.lo, cx.c
    swl, swh = swing_lows(lo), -swing_lows(-h)
    out = []
    for name, g in sig.sort_values("i").groupby("strategy", sort=False):
        busy = -1
        for r in g.itertuples(index=False):
            i, end = int(r.i), int(r.end)
            if i <= busy:
                continue
            s, e, risk = float(r.dir), float(r.entry), float(r.risk)
            cost = cx.spread[i] + COMMISSION
            sl = e - s * risk
            tp = e + s * risk * r.tp_r if (bundle == "M0" and np.isfinite(r.tp_r)) else np.nan
            armed = False
            exit_px, why, j = c[end], "time", end
            for j in range(i + 1, end + 1):
                hit_sl = lo[j] <= sl if s > 0 else h[j] >= sl
                hit_tp = np.isfinite(tp) and (h[j] >= tp if s > 0 else lo[j] <= tp)
                if hit_sl:
                    exit_px, why = sl, "sl"
                    break
                if hit_tp:
                    exit_px, why = tp, "tp"
                    break
                if bundle == "M8":
                    best = h[j] - e if s > 0 else e - lo[j]
                    old = sl
                    if not armed and best >= risk:
                        armed = True
                        sl = e + s * cost if s * (e + s * cost - sl) > 0 else sl
                    if armed:
                        sw = swl[j] - 0.1 * cx.atr5[j] if s > 0 else swh[j] + 0.1 * cx.atr5[j]
                        if np.isfinite(sw) and s * (sw - sl) > 0 and s * (c[j] - sw) > 0:
                            sl = sw
                    if events is not None and sl != old:
                        events.append((name, i, j + 1, sl))
            else:
                j = end
            busy = j
            out.append((name, i, j, s, risk, s * (exit_px - e) / risk, cost / risk, why))
    return pd.DataFrame(out, columns=["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit"])


# --- screen ----------------------------------------------------------------------------------


def screen(trades: pd.DataFrame, cx: Ctx) -> pd.DataFrame:
    t = trades.assign(year=pd.to_datetime(cx.m["close_utc"].to_numpy()[trades["i"]], utc=True).year)
    t["net"] = t["gross"] - t["cost"]
    t["net_slip"] = t["net"] - np.where(t["exit"] == "sl", SL_SLIP / t["risk"], 0.0)
    days = len(np.unique(cx.ny_day[(cx.m["close_utc"] >= START).to_numpy()]))
    rows = []
    for (name, b), g in t.groupby(["strategy", "bundle"]):
        yr = g.groupby("year")["net"].mean()
        rows.append({
            "strategy": name, "bundle": b, "trades": len(g), "per_day": len(g) / days,
            "gross": g["gross"].mean(), "cost": g["cost"].mean(), "net": g["net"].mean(),
            "net_slip": g["net_slip"].mean(), "years_pos": (yr > 0).mean(),
            "net_2012_18": g.loc[g["year"] <= 2018, "net"].mean(),
            "net_2019_26": g.loc[g["year"] >= 2019, "net"].mean(),
            "se": g["net"].std(ddof=1) / np.sqrt(len(g)),
        })  # fmt: skip
    s = pd.DataFrame(rows)
    s["survives"] = (s["net"] > 0) & (s["years_pos"] >= 0.6) & (s["net_2012_18"] > 0) & (s["net_2019_26"] > 0)
    return s.sort_values("net", ascending=False).reset_index(drop=True)


def render(s: pd.DataFrame) -> str:
    lines = [
        "# Gold lab: screen of the candidate strategies (commercial track, exploratory)",
        "",
        "_XAUUSD 5m bars 2012-01 to 2026-01-09 (holdout included; lockbox not read). Gross R from "
        "bid bars; cost = recorded spread + $0.07 per oz commission (MT5-measured); net_slip adds "
        "$0.10 on stop exits. Survives: net > 0, >= 60% of years positive, both halves positive. "
        "Seen data: every number here is optimistic._",
        "",
        "| Strategy | Bundle | Trades | A day | Gross | Cost | Net (SE) | Net, SL slip | Years + | "
        "2012-18 | 2019-26 | Survives |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in s.itertuples():
        lines.append(f"| {r.strategy} | {r.bundle} | {r.trades:,} | {r.per_day:.2f} | {r.gross:+.3f} "
                     f"| {r.cost:.3f} | {r.net:+.3f} ({r.se:.3f}) | {r.net_slip:+.3f} | {r.years_pos:.0%} "
                     f"| {r.net_2012_18:+.3f} | {r.net_2019_26:+.3f} | {'yes' if r.survives else ''} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-lab")
    ap.add_argument("step", choices=("screen",))
    args = ap.parse_args(argv)
    fr = load()
    cx = context(fr)
    other = {s: F.load(s, WARM, LOCKBOX) for s in ("EURUSD", "USDJPY")}
    sig = all_signals(fr, cx, other)
    print(f"{len(sig):,} signals:", sig.groupby("strategy").size().to_dict(), file=sys.stderr)
    trades = pd.concat([simulate(sig, cx, b).assign(bundle=b) for b in ("M0", "M8")], ignore_index=True)
    trades.to_parquet(STORE / "gold_lab_trades.parquet", index=False)
    s = screen(trades, cx)
    REPORT.write_text(render(s), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
