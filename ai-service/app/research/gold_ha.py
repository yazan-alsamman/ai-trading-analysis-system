"""Gold: Heikin-Ashi colour flips (``docs/strategies/GOLD_HA.md``, registered 2026-11-12).

    python -m app research gold-ha build --export <GOLD M1>

A closed HA candle whose colour differs from the previous one is a flip: green buys, red sells,
at the next real bar's open; the next flip exits (at the real open after it) and reverses. H24:
always in the market but flat over the weekend (Friday 16:45 New York); DAY: flat every day at
16:45 New York until the 18:00 reopen. R = ATR(14) of the frame at the signal bar."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.discovery import markout as mk
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn

REPORT = gl.OUT_DIR / "gold_ha_result.md"  # not gold_ha.md: GOLD_HA.md on Windows
TUNE_END = 2021
CUT, REOPEN = 16 * 60 + 45, 18 * 60  # New York minutes
E0_RUNS, E0_SEED = 50, 20261117
CELLS = ("H24", "DAY")
OTHER_FRAMES = ("1h", "4h", "D1")


def heikin_ashi(o, h, lo, c) -> tuple[np.ndarray, np.ndarray]:
    """HA open and close: close = (O + H + L + C) / 4, open = mean of the previous HA open and
    close (the first: (O + C) / 2)."""
    hc = (o + h + lo + c) / 4
    ho = np.empty(len(c))
    if len(c):
        ho[0] = (o[0] + c[0]) / 2
    for t in range(1, len(c)):
        ho[t] = (ho[t - 1] + hc[t - 1]) / 2
    return ho, hc


def flips(ho: np.ndarray, hc: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The colour carried forward over dojis (+1 green, -1 red, 0 before the first), and the bars
    where it changes."""
    col = pd.Series(np.sign(hc - ho)).replace(0, np.nan).ffill().fillna(0).to_numpy()
    flip = np.r_[False, (col[1:] != col[:-1]) & (col[:-1] != 0)]
    return col, flip


def clock(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per bar: New York minute of its open and of its close, and weekday of its close."""
    o = frame["ts_utc"].dt.tz_convert(gl.NY)
    c = frame["close_utc"].dt.tz_convert(gl.NY)
    return (
        (o.dt.hour * 60 + o.dt.minute).to_numpy(),
        (c.dt.hour * 60 + c.dt.minute).to_numpy(),
        c.dt.day_of_week.to_numpy(),
    )


def cut_bars(frame: pd.DataFrame, cell: str) -> tuple[np.ndarray, np.ndarray]:
    """The forced-exit bars (the last bar closing by 16:45 New York on its date: every weekday for
    DAY, Fridays for H24) and the bars no trade may open on (between that cut and the reopen)."""
    omin, cmin, cdow = clock(frame)
    date = frame["close_utc"].dt.tz_convert(gl.NY).dt.date.to_numpy()
    by = cmin <= CUT
    ok = by & ((cdow == 4) if cell == "H24" else (cdow < 5))
    idx = np.arange(len(frame))
    last = pd.Series(np.where(ok, idx, -1)).groupby(date).transform("max").to_numpy()
    cut = (last == idx) & ok
    blocked = (omin >= CUT) & (omin < REOPEN) & ((cdow == 4) if cell == "H24" else (cdow < 5))
    return cut, blocked


def trades(frame: pd.DataFrame, cell: str, fill: str = "real", commission=None) -> pd.DataFrame:
    """Every trade of a cell. ``fill = "ha"``: entries and exits at HA prices (the artefact)."""
    o, h, lo, c = (frame[k].to_numpy() for k in ("open", "high", "low", "close"))
    spread = frame["spread_mean"].to_numpy()
    ho, hc = heikin_ashi(o, h, lo, c)
    col, flip = flips(ho, hc)
    cut, blocked = cut_bars(frame, cell)
    atr = gl.wilder(h, lo, c)
    px_open = o if fill == "real" else ho  # the next bar's open (real, or HA)
    px_close = c if fill == "real" else hc
    rows = []
    pos, k0, sig, d, e = 0, -1, -1, 0.0, 0.0
    n = len(c)
    for t in range(n - 1):
        if pos and cut[t]:
            rows.append((sig, k0, t, d, e, px_close[t], "cut"))
            pos = 0
        if flip[t]:
            if pos:
                rows.append((sig, k0, t + 1, d, e, px_open[t + 1], "flip"))
                pos = 0
            if not blocked[t + 1] and not cut[t] and np.isfinite(atr[t]) and atr[t] > 0:
                pos, k0, sig, d, e = 1, t + 1, t, col[t], px_open[t + 1]
    out = pd.DataFrame(rows, columns=["i", "k", "x", "dir", "entry", "exit_px", "why"])
    out["risk"] = atr[out["i"]]
    out["gross"] = out["dir"] * (out["exit_px"] - out["entry"]) / out["risk"]
    comm = gl.COMMISSION if commission is None else commission  # FX: an array by bar
    comm_k = comm[out["k"]] if np.ndim(comm) else comm
    out["cost"] = (spread[out["k"]] + comm_k) / out["risk"]
    out["net"] = out["gross"] - out["cost"]
    out["net2"] = out["gross"] - 2 * out["cost"]
    out["year"] = frame["close_utc"].dt.year.to_numpy()[out["i"]]
    out["t_open"] = frame["ts_utc"].to_numpy()[out["k"]]
    return out


def e0_excess(t: pd.DataFrame) -> np.ndarray:
    """Per trade: net R minus its mean over E0_RUNS random sides."""
    rng = np.random.default_rng(E0_SEED)
    s = np.where(rng.random((E0_RUNS, len(t))) < 0.5, 1.0, -1.0)
    rand = (s * t["gross"].to_numpy()).mean(axis=0) - t["cost"].to_numpy()
    return t["net"].to_numpy() - rand


def t_vs_e0(t: pd.DataFrame) -> float:
    m = pd.to_datetime(t["t_open"], utc=True).dt.tz_convert(None).to_numpy("datetime64[m]")
    start = np.datetime64("2012-01-01T00:00", "m")
    blk = ((m - start).astype("int64") // mk.BLOCK_MIN).astype(int)
    blk = blk - blk.min()
    _, tt = mk.boot_t(mk.resamples(int(blk.max()) + 1), blk, e0_excess(t))
    return tt


def summary(t: pd.DataFrame, days: int) -> dict:
    yr = t.groupby("year")["net"].mean()
    return {
        "trades": len(t),
        "per_day": len(t) / max(days, 1),
        "gross": t["gross"].mean(),
        "cost": t["cost"].mean(),
        "net": t["net"].mean(),
        "net2": t["net2"].mean(),
        "years_pos": (yr > 0).mean() if len(yr) else np.nan,
        "hold_h": ((t["x"] - t["k"]).mean()),
    }


def trading_days(frame: pd.DataFrame, a: int, b: int) -> int:
    y = frame["close_utc"].dt.year
    d = frame["close_utc"].dt.tz_convert(gl.NY).dt.date
    return int(d[(y >= a) & (y <= b)].nunique())


def with_tday(t: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    d1 = cx.d1["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
    when = pd.to_datetime(t["t_open"], utc=True).dt.tz_convert(None).to_numpy("datetime64[ns]")
    return t.assign(tday=np.searchsorted(d1, when, "right") - 1)


def build(export: Path) -> str:
    fr = gl.load()
    f15 = fr["15m"]
    lines = [
        "# Gold: Heikin-Ashi colour flips on 15m, XAUUSD and FxPro",
        "",
        "_`python -m app research gold-ha build`, registered in `GOLD_HA.md` (2026-11-12). "
        "Entry and exit at the real next open; R = ATR(14, 15m); cost = spread + $0.07; no "
        "swap charged._",
        "",
    ]
    head = [
        "| Cell | Period | Trades | A day | Gross R | Cost R | Net R | At 2x | Years + "
        "| Bars held | t vs E0 |",
        "|" + " --- |" * 11,
    ]
    lines += head
    res = {}
    for cell in CELLS:
        t = trades(f15, cell)
        res[cell] = t
        for name, (a, b) in (("2012-2021", (2012, TUNE_END)), ("2022 to 2026-01-09", (2022, 2026))):
            g = t[(t["year"] >= a) & (t["year"] <= b)]
            s = summary(g, trading_days(f15, a, b))
            lines.append(
                f"| {cell} | {name} | {s['trades']:,} | {s['per_day']:.1f} "
                f"| {s['gross']:+.3f} | {s['cost']:.3f} | {s['net']:+.3f} "
                f"| {s['net2']:+.3f} | {s['years_pos']:.0%} | {s['hold_h']:.1f} "
                f"| {t_vs_e0(g):+.2f} |"
            )
    tune = {c: res[c][res[c]["year"] <= TUNE_END] for c in CELLS}
    ts = {c: t_vs_e0(tune[c]) for c in CELLS}
    p = np.array([1 - _phi(ts[c]) for c in CELLS])
    holm = mk.holm(p, 0.05)
    ok1 = {
        c: (
            tune[c]["net"].mean() > 0
            and summary(tune[c], 1)["years_pos"] >= 0.6
            and tune[c]["net2"].mean() > 0
            and ts[c] >= 3
            and holm[q]
        )
        for q, c in enumerate(CELLS)
    }
    best = max(CELLS, key=lambda c: tune[c]["net"].mean())
    lines += [
        "",
        f"Condition 1 (2012-2021): H24 {'met' if ok1['H24'] else 'not met'}, DAY "
        f"{'met' if ok1['DAY'] else 'not met'}; the better cell by net R: {best}.",
        "",
    ]
    fx_fr = ge.frames_from_lines(gv.fx_lines(export))
    fx15 = fx_fr["15m"]
    start = gv.FX_START
    ft = trades(fx15, best)
    ft = ft[pd.to_datetime(ft["t_open"], utc=True) >= start]
    chk = res[best][res[best]["year"] > TUNE_END]
    fcx = gl.context(fx_fr)
    since = pd.to_datetime(fcx.m["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
    day = {
        k: v[since[v["i"]] >= np.datetime64(start.tz_convert(None))]
        for k, v in gn.day_strategies(fcx).items()
    }
    corr = gn.correlations(with_tday(ft, fcx), day)
    conds = [
        any(ok1.values()),
        chk["net"].mean() > 0,
        ft["net"].mean() > 0,
        all(v < 0.2 for v in corr.values()),
    ]
    lines += [
        f"**{best}:** check {chk['net'].mean():+.3f} R ({len(chk):,} trades); FxPro "
        f"{ft['net'].mean():+.3f} ({len(ft):,}, gross {ft['gross'].mean():+.3f}); daily "
        "correlation with the five "
        + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
        + f". Conditions 1-4: {'/'.join('yes' if x else 'no' for x in conds)}. "
        f"**{'passes' if all(conds) else 'dropped'}.**",
        "",
    ]
    lines += [
        "## Reported, not a trial: fills at HA prices (the artefact)",
        "",
        "The same trades of each cell, entered and exited at HA prices instead of real ones:",
        "",
        "| Cell | Period | Net R at real prices | Net R at HA prices |",
        "| --- | --- | --- | --- |",
    ]
    for cell in CELLS:
        ha = trades(f15, cell, fill="ha")
        for name, (a, b) in (("2012-2021", (2012, TUNE_END)), ("2022 to 2026-01-09", (2022, 2026))):
            r = res[cell][(res[cell]["year"] >= a) & (res[cell]["year"] <= b)]["net"].mean()
            h_ = ha[(ha["year"] >= a) & (ha["year"] <= b)]["net"].mean()
            lines.append(f"| {cell} | {name} | {r:+.3f} | {h_:+.3f} |")
    lines += [
        "",
        "## Reported, deciding nothing: other frames (H24, real fills)",
        "",
        "| Frame | Period | Trades | A day | Gross R | Cost R | Net R | t vs E0 |",
        "|" + " --- |" * 8,
    ]
    for tf in OTHER_FRAMES:
        t = trades(fr[tf], "H24")
        for name, (a, b) in (("2012-2021", (2012, TUNE_END)), ("2022 to 2026-01-09", (2022, 2026))):
            g = t[(t["year"] >= a) & (t["year"] <= b)]
            s = summary(g, trading_days(f15, a, b))
            lines.append(
                f"| {tf} | {name} | {s['trades']:,} | {s['per_day']:.2f} "
                f"| {s['gross']:+.3f} | {s['cost']:.3f} | {s['net']:+.3f} "
                f"| {t_vs_e0(g):+.2f} |"
            )
    yrs = sorted(res["H24"]["year"].unique())
    lines += [
        "",
        "By year, net R (15m):",
        "",
        "| Cell | " + " | ".join(map(str, yrs)) + " |",
        "|" + " --- |" * (1 + len(yrs)),
    ]
    for cell in CELLS:
        v = res[cell].groupby("year")["net"].mean()
        lines.append(f"| {cell} | " + " | ".join(f"{v.get(y, np.nan):+.3f}" for y in yrs) + " |")
    return "\n".join(lines) + "\n"


def _phi(x: float) -> float:
    from scipy.stats import norm

    return float(norm.cdf(x)) if np.isfinite(x) else 0.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-ha")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
