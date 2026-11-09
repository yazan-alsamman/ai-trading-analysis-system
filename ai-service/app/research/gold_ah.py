"""Gold: the "AH" bot's 1-minute trend pullback, cloned (AHB) and varied (commercial track,
exploratory; ``docs/strategies/GOLD_AH.md`` has the rules, registered before any run).

    python -m app research gold-ah build                       # XAUUSD store, 2012 to 2026-01-09
    python -m app research gold-ah fxpro --export <GOLD M1 export> [--bot-report <MT5 report>]

Every trade is simulated on M1 bid bars. Costs: the signal bar's recorded spread + $0.07 per oz per
leg, a round trip; $0.10 slippage on every stop exit (SL and break-even), reported beside the net.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import instruments, splits
from app.data import clock
from app.data.importer import DEFAULT_OUT as STORE
from app.data.importer import M1
from app.data.mt5 import parse_export
from app.strategies.cli import OUT_DIR

SYM = "XAUUSD"
START = pd.Timestamp("2011-12-01", tz="UTC")  # one month of warm-up before 2012
TUNE = (2012, 2021)
CHECK_START = pd.Timestamp("2022-01-01", tz="UTC")
FX_START = pd.Timestamp("2016-02-01", tz="UTC")
FX_FIRST_DAY = b"2016.01.19"
COMMISSION = 0.07
SLIP = 0.10
NY = "America/New_York"
HORIZON = 360
REPORT = OUT_DIR / "gold_ah_xauusd.md"
FX_REPORT = OUT_DIR / "gold_ah_fxpro.md"


@dataclass(frozen=True)
class Setting:
    name: str
    solo: bool = False  # V1: skip while any signal is open
    trend4h: bool = False  # V2
    deep: bool = False  # V3
    min_sl: bool = False  # V4
    tp1: float = 0.4
    tp_moved: float = 0.7
    e2: bool = True


SETTINGS = [
    Setting("AHB"),
    Setting("V1", solo=True),
    Setting("V2", trend4h=True),
    Setting("V3", deep=True),
    Setting("V4", min_sl=True),
    Setting("V5", tp1=0.8, tp_moved=1.4),
    Setting("V6", e2=False),
    Setting("ALL", solo=True, trend4h=True, deep=True, min_sl=True, tp1=0.8, e2=False),
]


# --- data ------------------------------------------------------------------------------------


def load_store() -> pd.DataFrame:
    lockbox = pd.Timestamp(splits().lockbox_start, tz="UTC")
    m1 = pd.read_parquet(
        STORE / SYM / "m1.parquet", filters=[("ts_utc", ">=", START), ("ts_utc", "<", lockbox)]
    )
    return m1.reset_index(drop=True)


def load_export(export: Path) -> pd.DataFrame:
    s = splits()
    inst = instruments()[SYM]

    def lines():
        with open(export, "rb") as f:
            yield next(f)
            for ln in f:
                if ln[:10] >= FX_FIRST_DAY:
                    yield ln

    parsed = parse_export(lines(), inst, M1, s.server_tz)
    segments = clock.detect(parsed.bars, inst, s.server_tz)
    m1 = clock.apply(parsed.bars, segments)
    segments = clock.check_mismatch_weeks(m1, segments, s.server_tz)
    m1 = clock.apply_mismatch_weeks(m1, segments, s.server_tz)
    return m1.reset_index(drop=True)


# --- indicators and signals ------------------------------------------------------------------


@dataclass
class Ctx:
    ts: pd.DatetimeIndex
    o: np.ndarray
    h: np.ndarray
    lo: np.ndarray
    c: np.ndarray
    spread: np.ndarray
    end: np.ndarray  # index of the last bar before the next 17:00 New York
    blocked: np.ndarray  # no new signal (16:50 to 18:05 New York)
    cond: dict  # direction -> condition array
    extra: dict  # (direction, name) -> filter array
    sld: np.ndarray
    atr: np.ndarray


def context(m1: pd.DataFrame) -> Ctx:
    ts = pd.DatetimeIndex(m1["ts_utc"])
    o, h, lo, c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    spread = m1["spread"].to_numpy(float)
    cs = pd.Series(c)
    ema20 = cs.ewm(span=20, adjust=False).mean().to_numpy()
    ema50 = cs.ewm(span=50, adjust=False).mean().to_numpy()
    hs, ls = pd.Series(h), pd.Series(lo)
    hh5, ll5 = hs.rolling(5).max().to_numpy(), ls.rolling(5).min().to_numpy()
    k5 = (c - ll5) / np.where(hh5 > ll5, hh5 - ll5, np.nan)
    rng10 = (hs.rolling(10).max() - ls.rolling(10).min()).to_numpy()
    hh60, ll60 = hs.rolling(60).max().to_numpy(), ls.rolling(60).min().to_numpy()
    pos60 = (c - ll60) / np.where(hh60 > ll60, hh60 - ll60, np.nan)
    prev = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - lo, np.abs(h - prev), np.abs(lo - prev)], axis=1)
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    c10 = np.r_[np.full(10, np.nan), c[:-10]]
    c240 = np.r_[np.full(240, np.nan), c[:-240]]
    ny = ts.tz_convert(NY)
    mins = ny.hour * 60 + ny.minute
    blocked = np.asarray((mins >= 16 * 60 + 50) | (mins < 18 * 60 + 5) & (mins >= 17 * 60))
    day = (ny + pd.Timedelta(hours=7)).normalize()  # trading day: 17:00 to 17:00 New York
    key = pd.factorize(day)[0]
    last = np.r_[np.nonzero(np.diff(key))[0], len(key) - 1]
    end = last[key]
    with np.errstate(invalid="ignore"):
        cond = {
            1: (c > c10) & (ema20 > ema50) & (c > ema50) & (k5 <= 0.4),
            -1: (c < c10) & (ema20 < ema50) & (c < ema50) & (k5 >= 0.6),
        }
        extra = {
            (1, "trend4h"): c > c240,
            (-1, "trend4h"): c < c240,
            (1, "deep"): pos60 <= 0.64,
            (-1, "deep"): pos60 >= 0.36,
        }
    return Ctx(ts, o, h, lo, c, spread, end, blocked, cond, extra, 1.7 * rng10, atr)


def raw_signals(cx: Ctx) -> pd.DataFrame:
    out = []
    for d in (1, -1):
        cd = cx.cond[d]
        first = cd & ~np.r_[False, cd[:-1]]
        idx = np.nonzero(first & ~cx.blocked & (cx.sld > 0))[0]
        out.append(pd.DataFrame({"i": idx, "d": d}))
    return pd.concat(out).sort_values(["i", "d"]).reset_index(drop=True)


# --- simulation ------------------------------------------------------------------------------


def _first(mask: np.ndarray) -> int:
    if not mask.size:
        return -1
    k = np.argmax(mask)
    return int(k) if mask[k] else -1


def simulate_one(cx: Ctx, i: int, d: int, st: Setting) -> dict:
    """One signal. Prices are signed so a buy and a sell share the code."""
    e = cx.c[i]
    sld = cx.sld[i]
    off = 0.18 * sld
    stop = e - d * sld
    lim = e - d * off
    tp1 = e + d * st.tp1 * sld
    tpm = e + d * st.tp_moved * sld
    j1 = min(cx.end[i], i + HORIZON)
    if j1 <= i:
        return {}
    h = cx.h[i + 1 : j1 + 1]
    lo = cx.lo[i + 1 : j1 + 1]
    adv = lo if d == 1 else h  # adverse extreme
    fav = h if d == 1 else lo  # favourable extreme

    def le(x, lvl):  # x reaches lvl adversely
        return (x <= lvl) if d == 1 else (x >= lvl)

    def ge(x, lvl):  # x reaches lvl favourably
        return (x >= lvl) if d == 1 else (x <= lvl)

    n = len(h)
    legs = []  # (units, entry, exit, on_stop, exit_bar)
    t_sl = _first(le(adv, stop))
    t_tp = _first(ge(fav, tp1))
    t_fill = _first(le(adv, lim)) if st.e2 else -1
    big = n + 1
    a_sl = t_sl if t_sl >= 0 else big
    a_tp = t_tp if t_tp >= 0 else big
    a_fill = t_fill if t_fill >= 0 else big
    if a_fill <= min(a_sl, a_tp) and a_fill < big:
        f = a_fill
        if a_sl == f:  # fill first, then the SL in the same bar
            legs += [(1, e, stop, True, f), (2, lim, stop, True, f)]
        else:
            b_sl = _first(le(adv[f + 1 :], stop))
            b_tp = _first(ge(fav[f + 1 :], tp1))
            b_sl = f + 1 + b_sl if b_sl >= 0 else big
            b_tp = f + 1 + b_tp if b_tp >= 0 else big
            if b_sl <= b_tp and b_sl < big:
                legs += [(1, e, stop, True, b_sl), (2, lim, stop, True, b_sl)]
            elif b_tp < big:
                legs.append((2, lim, tp1, False, b_tp))
                if ge(fav[b_tp], tpm):
                    legs.append((1, e, tpm, False, b_tp))
                else:
                    g = b_tp + 1
                    c_be = _first(le(adv[g:], e))
                    c_tp = _first(ge(fav[g:], tpm))
                    c_be = g + c_be if c_be >= 0 else big
                    c_tp = g + c_tp if c_tp >= 0 else big
                    if c_be <= c_tp and c_be < big:
                        legs.append((1, e, e, True, c_be))
                    elif c_tp < big:
                        legs.append((1, e, tpm, False, c_tp))
                    else:
                        legs.append((1, e, cx.c[j1], False, n - 1))
            else:
                legs += [(1, e, cx.c[j1], False, n - 1), (2, lim, cx.c[j1], False, n - 1)]
    elif a_sl <= a_tp and a_sl < big:
        legs.append((1, e, stop, True, a_sl))
    elif a_tp < big:
        legs.append((1, e, tp1, False, a_tp))
    else:
        legs.append((1, e, cx.c[j1], False, n - 1))
    cost = cx.spread[i] + COMMISSION
    gross = sum(u * d * (x - en) for u, en, x, _, _ in legs)
    costs = sum(u * cost for u, *_ in legs)
    slip = sum(u * SLIP for u, _, _, s, _ in legs if s)
    risk = sld + (2 * (sld - off) if st.e2 else 0.0)
    last_bar = i + 1 + max(b for *_, b in legs)
    return dict(i=i, d=d, gross=gross / risk, cost=costs / risk, slip=slip / risk,
                net=(gross - costs) / risk, net_slip=(gross - costs - slip) / risk,
                net_2x=(gross - 2 * costs - 2 * slip) / risk, exit_i=last_bar,
                e2_filled=any(u == 2 for u, *_ in legs))  # fmt: skip


def run(cx: Ctx, sig: pd.DataFrame, st: Setting) -> pd.DataFrame:
    rows = []
    busy = {1: -1, -1: -1}
    for i, d in zip(sig.i.to_numpy(), sig.d.to_numpy(), strict=True):
        if st.trend4h and not cx.extra[(d, "trend4h")][i]:
            continue
        if st.deep and not cx.extra[(d, "deep")][i]:
            continue
        if st.min_sl and not cx.sld[i] >= 4.7 * cx.atr[i]:
            continue
        if (max(busy.values()) if st.solo else busy[d]) >= i:
            continue
        r = simulate_one(cx, int(i), int(d), st)
        if not r:
            continue
        busy[d] = r["exit_i"]
        rows.append(r)
    t = pd.DataFrame(rows)
    if len(t):
        t["ts"] = cx.ts[t.i.to_numpy()]
        t["year"] = t.ts.dt.year
    return t


# --- reports ---------------------------------------------------------------------------------


def summary(t: pd.DataFrame, lo: pd.Timestamp, hi: pd.Timestamp) -> dict:
    x = t[(t.ts >= lo) & (t.ts < hi)]
    if not len(x):
        return dict(n=0)
    yr = x.groupby("year").net.mean()
    days = max(1, x.ts.dt.normalize().nunique())
    return dict(
        n=len(x), a_day=len(x) / days, gross=x.gross.mean(), cost=x.cost.mean(),
        net=x.net.mean(), net_slip=x.net_slip.mean(), net_2x=x.net_2x.mean(),
        win=(x.net > 0).mean(), years_pos=(yr > 0).mean(), e2=x.e2_filled.mean(),
    )  # fmt: skip


def _fmt(s: dict) -> str:
    if not s.get("n"):
        return "| 0 | | | | | | | |"
    return (
        f"| {s['n']:,} | {s['a_day']:.1f} | {s['gross']:+.3f} | {s['cost']:.3f} | "
        f"{s['net']:+.3f} | {s['net_slip']:+.3f} | {s['net_2x']:+.3f} | {s['win']:.0%} |"
    )


HEAD = (
    "| Setting | Trades | A day | Gross R | Cost R | Net R | Net R slip | Net R 2x | Win |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)


def build() -> str:
    m1 = load_store()
    cx = context(m1)
    sig = raw_signals(cx)
    t0 = pd.Timestamp(f"{TUNE[0]}-01-01", tz="UTC")
    t1 = pd.Timestamp(f"{TUNE[1] + 1}-01-01", tz="UTC")
    end = pd.Timestamp(splits().lockbox_start, tz="UTC")
    lines = [
        "# Gold AH clone: XAUUSD (`GOLD_AH.md`)",
        "",
        f"_`python -m app research gold-ah build`: XAUUSD store M1, {t0.date()} to {end.date()} "
        "(the lockbox is not read). Net R per signal; costs and slippage as `GOLD_AH.md` §1._",
        "",
    ]
    tune, check, decide = [], [], []
    trades = {}
    for st in SETTINGS:
        t = run(cx, sig, st)
        trades[st.name] = t
        a, b = summary(t, t0, t1), summary(t, CHECK_START, end)
        tune.append(f"| {st.name} " + _fmt(a))
        check.append(f"| {st.name} " + _fmt(b))
        c1 = bool(a.get("n")) and a["net"] > 0 and a["years_pos"] >= 0.6
        c2 = bool(b.get("n")) and b["net_slip"] > 0
        yp = f"{a['years_pos']:.0%}" if a.get("n") else ""
        third = "pending" if c1 and c2 else "not needed"
        decide.append(
            f"| {st.name} | {'met' if c1 else 'not met'} ({yp} of years +) | "
            f"{'met' if c2 else 'not met'} | {third} |"
        )
    lines += ["## Tune period, 2012-2021", "", HEAD, *tune, "",
              "## Check, 2022 to 2026-01-09", "", HEAD, *check, "",
              "## Decision (§4)", "", "| Setting | 1. 2012-2021 | 2. Check | 3. FxPro |",
              "| --- | --- | --- | --- |", *decide, ""]  # fmt: skip
    lines += ["## Net R by year (no slippage)", ""]
    by = pd.DataFrame({k: v.groupby("year").net.mean() for k, v in trades.items() if len(v)})
    lines += ["| Year | " + " | ".join(by.columns) + " |", "| --- |" + " --- |" * len(by.columns)]
    for y, r in by.iterrows():
        lines.append(f"| {y} | " + " | ".join(f"{v:+.3f}" for v in r.to_numpy()) + " |")
    lines += ["", "## By side, whole period (net R with slippage)", ""]
    lines += ["| Setting | Buys | Sells |", "| --- | --- | --- |"]
    for k, v in trades.items():
        if len(v):
            g = v.groupby("d").net_slip.mean()
            lines.append(f"| {k} | {g.get(1, np.nan):+.3f} | {g.get(-1, np.nan):+.3f} |")
    return "\n".join(lines) + "\n"


def bot_entries(report: Path) -> pd.DataFrame:
    raw = report.read_bytes()
    txt = raw.decode("utf-16") if raw[:2] == b"\xff\xfe" else raw.decode("utf-8", "ignore")
    pat = re.compile(
        r"<td[^>]*>(\d{4}\.\d\d\.\d\d \d\d:\d\d:\d\d)</td>\s*(?:<td[^>]*>[^<]*</td>\s*){2}"
        r"<td[^>]*>(buy|sell)</td>\s*<td[^>]*>(AH_S\d_E1)</td>"
    )
    rows = [(pd.Timestamp(t), s) for t, s, _ in pat.findall(txt)]
    df = pd.DataFrame(rows, columns=["server", "side"]).drop_duplicates()
    df["ts"] = df.server.dt.tz_localize(splits().server_tz).dt.tz_convert("UTC")
    df["d"] = np.where(df.side == "buy", 1, -1)
    return df


def fxpro(export: Path, report: Path | None) -> str:
    m1 = load_export(export)
    cx = context(m1)
    sig = raw_signals(cx)
    lo, hi = max(FX_START, cx.ts[0]), cx.ts[-1] + pd.Timedelta(minutes=1)
    y26 = pd.Timestamp("2026-01-12", tz="UTC")
    lines = [
        "# Gold AH clone: FxPro GOLD (`GOLD_AH.md`)",
        "",
        f"_`python -m app research gold-ah fxpro`: `{export.name}`, {lo.date()} to "
        f"{(hi - pd.Timedelta(minutes=1)).date()}; FxPro's recorded spread + $0.07 per oz._",
        "",
        "## Condition 3: the whole export", "", HEAD,
    ]  # fmt: skip
    trades = {}
    for st in SETTINGS:
        t = run(cx, sig, st)
        trades[st.name] = t
        lines.append(f"| {st.name} " + _fmt(summary(t, lo, hi)))
    lines += ["", "## 2026-01-12 on (reported by itself)", "", HEAD]
    for k, t in trades.items():
        lines.append(f"| {k} " + _fmt(summary(t, max(lo, y26), hi)))
    if report is not None:
        be = bot_entries(report)
        be = be[(be.ts >= cx.ts[0]) & (be.ts < hi)]
        t = trades["AHB"]
        # AHB signal bar i closes at ts[i] + 1 min, the bot's E1 opens at that close
        sigs = pd.DataFrame({"ts": cx.ts[sig.i.to_numpy()] + pd.Timedelta(minutes=1), "d": sig.d})
        hit = 0
        for _, r in be.iterrows():
            m = sigs[(sigs.d == r.d) & ((sigs.ts - r.ts).abs() <= pd.Timedelta(minutes=2))]
            hit += len(m) > 0
        p = (t.ts >= be.ts.min() - pd.Timedelta(minutes=1)) & (t.ts <= be.ts.max())
        n_raw = int(((sigs.ts >= be.ts.min()) & (sigs.ts <= be.ts.max())).sum())
        share = hit / max(1, len(be))
        lines += [
            "", "## The bot's period (deciding nothing)", "",
            f"- The bot's E1 entries in the export: {len(be)}.",
            f"- AHB raw signals within 2 minutes, same direction: {hit} ({share:.0%}).",
            f"- AHB raw signals over the same period: {n_raw}.",
            f"- AHB traded {int(p.sum())} of them: net R {t[p].net.mean():+.3f}, "
            f"with slippage {t[p].net_slip.mean():+.3f}.",
        ]  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-ah")
    ap.add_argument("command", choices=["build", "fxpro"])
    ap.add_argument("--export", type=Path, help="fxpro: an FxPro GOLD M1 export")
    ap.add_argument("--bot-report", type=Path, help="fxpro: the bot's MT5 trade report")
    ap.add_argument("--out", type=Path, help="report path (default under docs/strategies)")
    args = ap.parse_args(argv)
    if args.command == "build":
        text, out = build(), args.out or REPORT
    else:
        if args.export is None:
            ap.error("fxpro needs --export")
        text, out = fxpro(args.export, args.bot_report), args.out or FX_REPORT
    out.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
