"""Gold: the dealing range, a pullback to its 50% and an FVG entry (commercial track,
exploratory; ``docs/strategies/GOLD_DR.md`` has the rules, registered before any run).

    python -m app research gold-dr build [--version dr2]       # XAUUSD store, 2012 to 2026-01-09
    python -m app research gold-dr fxpro --export <GOLD M1 export>

The range logic runs on closed 15m bars built from M1; limit fills and exits are resolved on M1.
Costs: the FVG bar's mean recorded spread + $0.07 per oz, a round trip; $0.10 slippage on stop
exits, reported beside the net.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import splits
from app.data.aggregate import aggregate
from app.data.importer import M1
from app.research import gold_ah as ah
from app.strategies.cli import OUT_DIR

COMMISSION = 0.07
SLIP = 0.10
NY = "America/New_York"
K = 2
VALID = 8  # 15m bars a limit stays
HORIZON = 48 * 15  # M1 bars after the fill
COST_CAP = 0.10
TUNE = (2012, 2021)
CHECK_START = pd.Timestamp("2022-01-01", tz="UTC")
FX_START = pd.Timestamp("2016-02-01", tz="UTC")
REPORT = OUT_DIR / "gold_dr_xauusd.md"
FX_REPORT = OUT_DIR / "gold_dr_fxpro.md"


@dataclass(frozen=True)
class Setting:
    tp: float
    sl: str  # LOW or EQ
    m: float
    cap: float | None = None  # DR2: the range's cap in daily ATRs

    @property
    def name(self) -> str:
        c = "" if self.cap is None else f" C{self.cap:g}"
        return f"{self.tp:g}R {self.sl} M{self.m:g}{c}"


SETTINGS = [Setting(tp, sl, m) for m in (1.5, 3.0) for sl in ("LOW", "EQ") for tp in (2.0, 4.0)]
SETTINGS2 = [
    Setting(tp, sl, 1.5, c) for c in (1.0, 2.0) for sl in ("LOW", "EQ") for tp in (2.0, 4.0)
]
VERSIONS = {"dr": SETTINGS, "dr2": SETTINGS2}


# --- the range state machine on 15m ----------------------------------------------------------


def atr14(h, lo, c):
    prev = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - lo, np.abs(h - prev), np.abs(lo - prev)], axis=1)
    return pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()


def pivot_lows(lo: np.ndarray, k: int = K) -> np.ndarray:
    s = pd.Series(lo)
    w = s.rolling(2 * k + 1, center=True).min()
    return (s == w).to_numpy() & ~np.isnan(w.to_numpy())


def _prev_true(mask: np.ndarray) -> np.ndarray:
    """For each index, the last index at or before it where ``mask`` holds (-1 if none)."""
    idx = np.where(mask, np.arange(len(mask)), -1)
    return np.maximum.accumulate(idx)


def setups(
    f: pd.DataFrame, m: float, cap: float | None = None, atr_d: np.ndarray | None = None
) -> tuple[pd.DataFrame, dict]:
    """Every FVG order the rules place, for one minimum range M (and, for DR2, a cap C on the
    range in daily ATRs, ``atr_d`` being the last closed day's ATR at each 15m bar). The machine
    is written for a bullish range; a bearish one runs on mirrored prices (-high as low)."""
    h0, l0, c0 = (f[k].to_numpy(float) for k in ("high", "low", "close"))
    atr = atr14(h0, l0, c0)
    piv = pivot_lows(l0)
    piv_hi = pivot_lows(-h0)
    prev = {1: _prev_true(piv), -1: _prev_true(piv_hi)}
    val = {1: l0, -1: -h0}  # a swing low's value in each direction's coordinates
    n = len(f)
    rows = []
    stats = dict(touches=0, fvgs=0, caps=0)
    d = 0  # +1 bullish, -1 bearish, 0 none yet
    L = H = P = E = np.nan
    li = hi = pi = -1  # bar of L, of H, of P
    touched = False
    touch_bar = -1
    fvg_done = False
    for j in range(2 * K, n):
        if d == 0:
            p = j - K
            if piv[p] or piv_hi[p]:
                d = 1 if piv[p] else -1
                hh = h0[p : j + 1] if d == 1 else -l0[p : j + 1]
                L, li = val[d][p], p
                hi = p + int(np.argmax(hh))
                H = hh.max()
            continue
        hj, lj = (h0[j], l0[j]) if d == 1 else (-l0[j], -h0[j])
        if lj < L:  # the range breaks: the state turns, the old high anchors the new range
            d, L, H, li, hi = -d, -H, -lj, hi, j
            touched, fvg_done = False, False
            continue
        if not touched:
            if hj > H:
                H, hi = hj, j
            if cap is not None and H - L > cap * atr_d[j]:
                q = prev[d][min(hi, j - K)]
                if q > li:
                    L, li = val[d][q], q
                    stats["caps"] += 1
            E = (H + L) / 2
            if lj <= E and H - L >= m * atr[j]:
                touched, touch_bar, P, pi, fvg_done = True, j, lj, j, False
                stats["touches"] += 1
            continue
        if hj > H:  # the pullback is over: its low starts a new range
            L, li, H, hi, touched, fvg_done = P, pi, hj, j, False, False
            continue
        if lj < P:
            P, pi = lj, j
        if fvg_done or j - 1 <= touch_bar:
            continue
        a2 = h0[j - 2] if d == 1 else -l0[j - 2]  # bar t-2's high (mirrored)
        gap = lj - a2
        if gap > 0 and gap >= 0.1 * atr[j]:
            fvg_done = True
            stats["fvgs"] += 1
            rows.append(dict(t=j, d=d, entry=lj, P=P, E=E, H=H, atr=atr[j]))
    s = pd.DataFrame(rows)
    if len(s):  # back to real prices
        for k in ("entry", "P", "E", "H"):
            s[k] = s[k] * s["d"]
    return s, stats


# --- trades on M1 ----------------------------------------------------------------------------


def _first(mask: np.ndarray) -> int:
    if not mask.size:
        return -1
    k = int(np.argmax(mask))
    return k if mask[k] else -1


def trades(f: pd.DataFrame, m1: pd.DataFrame, s: pd.DataFrame, st: Setting) -> pd.DataFrame:
    ts = m1["ts_utc"].dt.tz_convert(None).to_numpy()
    h, lo, c = (m1[k].to_numpy(float) for k in ("high", "low", "close"))
    ny = pd.DatetimeIndex(m1["ts_utc"]).tz_convert(NY)
    key = pd.factorize((ny + pd.Timedelta(hours=7)).normalize())[0]
    last = np.r_[np.nonzero(np.diff(key))[0], len(key) - 1][key]
    close15 = pd.to_datetime(f["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
    spread15 = f["spread_mean"].to_numpy(float)
    out = []
    busy = np.datetime64("1970-01-01")
    for r in s.itertuples():
        t = r.t
        if close15[t] <= busy or t + VALID >= len(f):
            continue
        d = r.d
        sl = (r.P if st.sl == "LOW" else r.E) - d * 0.1 * r.atr
        risk = d * (r.entry - sl)
        if risk <= 0:
            continue
        cost = spread15[t] + COMMISSION
        if cost / risk > COST_CAP:
            continue
        tp = r.entry + d * st.tp * risk
        a = int(np.searchsorted(ts, close15[t]))
        b = int(np.searchsorted(ts, close15[t + VALID]))
        adv = lo[a:b] if d == 1 else -h[a:b]
        fav = h[a:b] if d == 1 else -lo[a:b]
        fill = _first(adv <= d * r.entry)
        cancel = _first(fav > d * r.H)
        if fill < 0 or (0 <= cancel < fill):
            busy = ts[a + cancel] if cancel >= 0 else ts[b - 1]
            continue
        i0 = a + fill
        i1 = min(last[i0], i0 + HORIZON, len(ts) - 1)
        adv = lo[i0 : i1 + 1] if d == 1 else -h[i0 : i1 + 1]
        fav = h[i0 + 1 : i1 + 1] if d == 1 else -lo[i0 + 1 : i1 + 1]
        x_sl = _first(adv <= d * sl)
        x_tp = _first(fav >= d * tp)
        x_tp = x_tp + 1 if x_tp >= 0 else -1
        if x_sl >= 0 and (x_tp < 0 or x_sl <= x_tp):
            ex, px, stop = i0 + x_sl, sl, True
        elif x_tp >= 0:
            ex, px, stop = i0 + x_tp, tp, False
        else:
            ex, px, stop = i1, c[i1], False
        gross = d * (px - r.entry)
        out.append(
            dict(
                ts=pd.Timestamp(ts[i0], tz="UTC"), d=d, gross=gross / risk, cost=cost / risk,
                slip=(SLIP if stop else 0.0) / risk,
                reason="sl" if stop else ("tp" if px == tp else "time"),
            )
        )  # fmt: skip
        busy = ts[ex]
    t = pd.DataFrame(out)
    if len(t):
        t["net"] = t.gross - t.cost
        t["net_slip"] = t.net - t.slip
        t["net_2x"] = t.gross - 2 * t.cost - 2 * t.slip
        t["year"] = t.ts.dt.year
    return t


# --- reports ---------------------------------------------------------------------------------


def summary(t: pd.DataFrame, lo: pd.Timestamp, hi: pd.Timestamp) -> dict:
    x = t[(t.ts >= lo) & (t.ts < hi)] if len(t) else t
    if not len(x):
        return dict(n=0)
    yr = x.groupby("year").net.mean()
    return dict(
        n=len(x), gross=x.gross.mean(), cost=x.cost.mean(), net=x.net.mean(),
        net_slip=x.net_slip.mean(), net_2x=x.net_2x.mean(), win=(x.net > 0).mean(),
        tp=(x.reason == "tp").mean(), time=(x.reason == "time").mean(),
        years_pos=(yr > 0).mean(),
    )  # fmt: skip


HEAD = (
    "| Setting | Trades | Gross R | Cost R | Net R | Net R slip | Net R 2x | Win | TP | Time "
    "| Years + |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)


def _row(name: str, s: dict) -> str:
    if not s.get("n"):
        return f"| {name} | 0 | | | | | | | | | |"
    return (
        f"| {name} | {s['n']:,} | {s['gross']:+.3f} | {s['cost']:.3f} | {s['net']:+.3f} | "
        f"{s['net_slip']:+.3f} | {s['net_2x']:+.3f} | {s['win']:.0%} | {s['tp']:.0%} | "
        f"{s['time']:.0%} | {s['years_pos']:.0%} |"
    )


def daily_atr(m1: pd.DataFrame, f: pd.DataFrame) -> np.ndarray:
    """ATR(14, D1) of the last trading day closed by each 15m bar's close."""
    d1 = aggregate(m1, "D1", M1).reset_index(drop=True)
    a = atr14(*(d1[k].to_numpy(float) for k in ("high", "low", "close")))
    dc = pd.to_datetime(d1["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
    fc = pd.to_datetime(f["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
    k = np.searchsorted(dc, fc, side="right") - 1
    return np.where(k >= 0, a[np.clip(k, 0, None)], np.nan)


def run_all(m1: pd.DataFrame, settings: list[Setting]) -> tuple[dict, dict]:
    f = aggregate(m1, "15m", M1).reset_index(drop=True)
    atr_d = daily_atr(m1, f)
    res, stats = {}, {}
    for m, cap in sorted({(st.m, st.cap or 0.0) for st in settings}):
        c = cap or None
        s, stats[(m, c)] = setups(f, m, c, atr_d)
        for st in settings:
            if st.m == m and st.cap == c:
                res[st.name] = trades(f, m1, s, st)
    return res, stats


def build(version: str = "dr") -> str:
    m1 = ah.load_store()
    res, stats = run_all(m1, VERSIONS[version])
    t0 = pd.Timestamp(f"{TUNE[0]}-01-01", tz="UTC")
    t1 = pd.Timestamp(f"{TUNE[1] + 1}-01-01", tz="UTC")
    end = pd.Timestamp(splits().lockbox_start, tz="UTC")
    tune = {k: summary(v, t0, t1) for k, v in res.items()}
    check = {k: summary(v, CHECK_START, end) for k, v in res.items()}
    ok = {k: s for k, s in tune.items()
          if s.get("n", 0) >= 300 and s["net"] > 0 and s["years_pos"] >= 0.6}  # fmt: skip
    choice = max(ok, key=lambda k: ok[k]["net"]) if ok else None
    lines = [
        f"# Gold dealing range {version.upper()}: XAUUSD (`GOLD_DR.md`)",
        "",
        f"_`python -m app research gold-dr build`: XAUUSD store M1 to {end.date()} (the lockbox "
        "is not read), 15m ranges. Net R per trade; costs and slippage as `GOLD_DR.md` §1._",
        "",
        "## Tune period, 2012-2021",
        "",
        HEAD,
        *[_row(k, s) for k, s in tune.items()],
        "",
        "## Check, 2022 to 2026-01-09",
        "",
        HEAD,
        *[_row(k, s) for k, s in check.items()],
        "",
        "## Decision (§3, §4)",
        "",
    ]
    if choice is None:
        lines.append("No setting qualifies on 2012-2021 (net R > 0, ≥ 60% of years, ≥ 300 trades): "
                     f"**{version.upper()} is dropped at condition 1.**")  # fmt: skip
    else:
        c = check[choice]
        passed = c.get("n", 0) and c["net_slip"] > 0
        lines.append(f"- Choice: **{choice}** ({tune[choice]['net']:+.3f} R on 2012-2021).")
        verdict = "met" if passed else f"**not met: {version.upper()} is dropped**"
        lines.append(
            f"- Check, net R with slippage: {c.get('net_slip', float('nan')):+.3f}: "
            f"condition 2 {verdict}."
        )
    lines += ["", "## Ranges (deciding nothing)", ""]
    for (m, c), s in stats.items():
        cc = "" if c is None else f", C {c:g} ({s['caps']:,} cap moves)"
        lines.append(f"- M {m:g}{cc}: {s['touches']:,} touches of 50%, {s['fvgs']:,} FVG orders.")
    lines += ["", "## Net R by year (no slippage)", ""]
    by = pd.DataFrame({k: v.groupby("year").net.mean() for k, v in res.items() if len(v)})
    lines += ["| Year | " + " | ".join(by.columns) + " |", "| --- |" + " --- |" * len(by.columns)]
    for y, r in by.iterrows():
        lines.append(f"| {y} | " + " | ".join(f"{v:+.3f}" for v in r.to_numpy()) + " |")
    lines += ["", "## By side, whole period (net R with slippage)", "",
              "| Setting | Buys | Sells |", "| --- | --- | --- |"]  # fmt: skip
    for k, v in res.items():
        if len(v):
            g = v.groupby("d").net_slip.mean()
            lines.append(f"| {k} | {g.get(1, np.nan):+.3f} | {g.get(-1, np.nan):+.3f} |")
    return "\n".join(lines) + "\n"


def fxpro(export: Path, version: str = "dr") -> str:
    m1 = ah.load_export(export)
    res, _ = run_all(m1, VERSIONS[version])
    lo = max(FX_START, pd.Timestamp(m1.ts_utc.iloc[0]))
    hi = pd.Timestamp(m1.ts_utc.iloc[-1]) + pd.Timedelta(minutes=1)
    lines = [
        "# Gold dealing range: FxPro GOLD (`GOLD_DR.md`)",
        "",
        f"_`python -m app research gold-dr fxpro`: `{export.name}`, {lo.date()} to "
        f"{(hi - pd.Timedelta(minutes=1)).date()}._",
        "",
        HEAD,
        *[_row(k, summary(v, lo, hi)) for k, v in res.items()],
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-dr")
    ap.add_argument("command", choices=["build", "fxpro"])
    ap.add_argument("--export", type=Path)
    ap.add_argument("--version", choices=list(VERSIONS), default="dr")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    tag = "" if args.version == "dr" else args.version.removeprefix("dr")
    if args.command == "build":
        text = build(args.version)
        out = args.out or REPORT.with_name(f"gold_dr{tag}_xauusd.md")
    else:
        if args.export is None:
            ap.error("fxpro needs --export")
        text = fxpro(args.export, args.version)
        out = args.out or FX_REPORT.with_name(f"gold_dr{tag}_fxpro.md")
    out.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
