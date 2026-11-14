"""The path of the five's trades after entry (``docs/strategies/TRADE_PATH.md``, stage 1,
registered 2026-11-12 before any measurement).

    python -m app research trade-path

XAUUSD 2012-2021 only. Each trade's path from the bar after its entry bar to 16:45 New York, in R
(its own D) from the entry, signed in its direction; the original stop (-1 R) ends it (a bar that
reaches it adds no favourable price). Control: the mirror (the same path, opposite direction)."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from app.research import gold_lab as gl
from app.research import gold_night as gn

REPORT = gl.OUT_DIR / "trade_path_result.md"  # not trade_path.md: TRADE_PATH.md on Windows
YEARS = (2012, 2021)
LADDER = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5)
SPEED = ((0, 15), (15, 60), (60, 180), (180, 10_000))  # minutes to +1 R
GIVE = ((1.5, 0.3), (1.5, 0.5), (2.0, 0.3), (2.0, 0.5))  # (peak at least, share given back)
STALL = (60, 120)  # minutes without +1 R


def path(cx: gl.Ctx, i: int, d: float, e: float, r: float) -> dict:
    """One trade's path: per bar the favourable extreme, the close (R) and minutes since entry,
    up to the stop bar (excluded) or 16:45; and its final value (-1 at the stop, else the last
    close)."""
    end = int(cx.deadline[i])
    a = i + 1
    if end < a:
        return {}
    hh, ll, cc = cx.h[a : end + 1], cx.lo[a : end + 1], cx.c[a : end + 1]
    best = (hh - e) / r if d > 0 else (e - ll) / r
    worst = (ll - e) / r if d > 0 else (e - hh) / r
    close = d * (cc - e) / r
    hit = np.flatnonzero(worst <= -1.0)
    stop = int(hit[0]) if len(hit) else len(best)
    ts = getattr(cx, "_ts_naive", None)
    if ts is None:  # cached on the context: the conversion is slow
        ts = cx.m["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[m]")
        cx._ts_naive = ts
    mins = (ts[a : end + 1] - ts[i]).astype(int)
    return {
        "best": best[:stop],
        "close": close[:stop],
        "mins": mins[:stop],
        "final": -1.0 if len(hit) else float(close[-1]),
    }


def mirror(cx: gl.Ctx, i: int, d: float, e: float, r: float) -> dict:
    return path(cx, i, -d, e, r)


def measures(p: dict) -> dict:
    """The quantities of TRADE_PATH.md for one path."""
    if not p or not len(p["best"]):
        return {}
    best, close, mins, final = p["best"], p["close"], p["mins"], p["final"]
    peak = np.maximum.accumulate(best)
    out = {"mfe": float(peak[-1]), "final": final}
    k1 = np.flatnonzero(best >= 1.0)
    out["t1"] = float(mins[k1[0]]) if len(k1) else np.nan
    out["move_from_1"] = final - 1.0 if len(k1) else np.nan
    for m, g in GIVE:
        idx = np.flatnonzero((peak >= m) & (close <= (1 - g) * peak))
        out[f"give_{m:g}_{g:g}"] = final - close[idx[0]] if len(idx) else np.nan
    for s in STALL:
        k = np.flatnonzero(mins >= s)
        ok = len(k) and peak[k[0]] < 1.0
        out[f"stall_{s}"] = final - close[k[0]] if ok else np.nan
    return out


def table(cx: gl.Ctx, trades: pd.DataFrame, flip: bool = False) -> pd.DataFrame:
    rows = []
    for r in trades.itertuples(index=False):
        p = (mirror if flip else path)(cx, int(r.i), float(r.dir), float(r.entry), float(r.risk))
        m = measures(p)
        if m:
            rows.append({"strategy": r.strategy, "day": r.ny_day, **m})
    return pd.DataFrame(rows)


def cluster_t(x: np.ndarray, groups: np.ndarray) -> float:
    ok = np.isfinite(x)
    x, groups = x[ok], groups[ok]
    n = len(x)
    if n < 3:
        return np.nan
    mu = x.mean()
    s = pd.Series(x - mu).groupby(groups).sum().to_numpy()
    g = len(s)
    se = np.sqrt((s**2).sum() * g / max(g - 1, 1)) / n
    return float(mu / se) if se > 0 else np.nan


def z_two(p1: float, n1: int, p2: float, n2: int) -> float:
    if min(n1, n2) < 2:
        return np.nan
    p = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return float((p1 - p2) / se) if se > 0 else np.nan


def signs(t: pd.DataFrame, col: str) -> str:
    v = t.groupby("strategy")[col].mean()
    return " ".join(f"{k} {x:+.2f}" for k, x in v.items())


def build() -> str:
    cx = gl.context(gl.load())
    five = pd.concat(gn.day_strategies(cx).values(), ignore_index=True)
    five = five[five["year"].between(*YEARS)].reset_index(drop=True)
    real, mir = table(cx, five), table(cx, five, flip=True)
    lines = [
        "# The path of the five's trades after entry (stage 1)",
        "",
        f"_`python -m app research trade-path`, registered in `TRADE_PATH.md`. XAUUSD "
        f"{YEARS[0]}-{YEARS[1]}, {len(real):,} trades. R = each trade's D. Mirror = the same "
        "path in the opposite direction. Moves are from the stated moment to 16:45 or the "
        "original stop; zero under a random walk._",
        "",
        "## 1. The ladder: of the trades that reached +k R, the share that reached +(k + 0.5) R",
        "",
        "| k | Reached k | Share on | Mirror | Random walk | z vs mirror |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    cands = []
    for k in LADDER:
        a, b = real[real["mfe"] >= k], mir[mir["mfe"] >= k]
        pa = (a["mfe"] >= k + 0.5).mean() if len(a) else np.nan
        pb = (b["mfe"] >= k + 0.5).mean() if len(b) else np.nan
        z = z_two(pa, len(a), pb, len(b))
        lines.append(
            f"| {k:g} | {len(a):,} | {pa:.1%} | {pb:.1%} | {(k + 1) / (k + 1.5):.1%} | {z:+.2f} |"
        )
        if abs(z) >= 3 and abs(pa - pb) >= 0.05:
            cands.append(f"ladder k = {k:g}: {pa:.1%} against the mirror's {pb:.1%} (z {z:+.1f})")
    lines += [
        "",
        "## 2. Speed: by the minutes taken to reach +1 R",
        "",
        "| Minutes to +1 R | Trades | Reached +2 R | +3 R | Mirror +2 R | Mean move from +1 R | t "
        "| Per strategy |",
        "|" + " --- |" * 8,
    ]
    for lo_, hi_ in SPEED:
        a = real[(real["t1"] >= lo_) & (real["t1"] < hi_)]
        b = mir[(mir["t1"] >= lo_) & (mir["t1"] < hi_)]
        t_ = cluster_t(a["move_from_1"].to_numpy(), a["day"].to_numpy())
        lines.append(
            f"| {lo_}-{hi_ if hi_ < 10_000 else '...'} | {len(a):,} | {(a['mfe'] >= 2).mean():.1%} "
            f"| {(a['mfe'] >= 3).mean():.1%} | {(b['mfe'] >= 2).mean():.1%} "
            f"| {a['move_from_1'].mean():+.3f} | {t_:+.2f} | {signs(a, 'move_from_1')} |"
        )
        cands += _cand(f"speed {lo_}-{hi_} min, move from +1 R", a, "move_from_1", t_)
    lines += [
        "",
        "## 3. Give-back: the move after the price is back by g of its peak",
        "",
        "| Peak at least | Given back | Trades | Mean move after | t | Mirror | Per strategy |",
        "|" + " --- |" * 7,
    ]
    for m, g in GIVE:
        col = f"give_{m:g}_{g:g}"
        a = real[np.isfinite(real[col])]
        t_ = cluster_t(a[col].to_numpy(), a["day"].to_numpy())
        lines.append(
            f"| {m:g} R | {g:.0%} | {len(a):,} | {a[col].mean():+.3f} | {t_:+.2f} "
            f"| {mir[col].mean():+.3f} | {signs(a, col)} |"
        )
        cands += _cand(f"give-back {g:.0%} after a {m:g} R peak", a, col, t_)
    lines += [
        "",
        "## 4. Time without progress: not at +1 R after s minutes",
        "",
        "| Minutes | Trades | Mean move after | t | Mirror | Per strategy |",
        "|" + " --- |" * 6,
    ]
    for s in STALL:
        col = f"stall_{s}"
        a = real[np.isfinite(real[col])]
        t_ = cluster_t(a[col].to_numpy(), a["day"].to_numpy())
        lines.append(
            f"| {s} | {len(a):,} | {a[col].mean():+.3f} | {t_:+.2f} | {mir[col].mean():+.3f} "
            f"| {signs(a, col)} |"
        )
        cands += _cand(f"no +1 R after {s} minutes", a, col, t_)
    lines += ["", "## Candidates for stage 2 (|t| >= 3, size >= 0.05 R, same sign in 4 of 5)", ""]
    lines += [f"- {c}" for c in cands] or [
        "- **None: the path after entry shows no structure that meets the registered bar.**"
    ]
    lines += [
        "",
        f"Overall: mean final (to 16:45 or the original stop) {real['final'].mean():+.3f} R, "
        f"mirror {mir['final'].mean():+.3f} R; mean peak {real['mfe'].mean():.2f} R.",
    ]
    return "\n".join(lines) + "\n"


def _cand(name: str, a: pd.DataFrame, col: str, t_: float) -> list[str]:
    mu = a[col].mean()
    per = a.groupby("strategy")[col].mean()
    same = int((np.sign(per) == np.sign(mu)).sum())
    if np.isfinite(t_) and abs(t_) >= 3 and abs(mu) >= 0.05 and same >= 4:
        return [f"{name}: {mu:+.3f} R (t {t_:+.1f}, same sign in {same} of 5)"]
    return []


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="python -m app research trade-path").parse_args(argv)
    REPORT.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
