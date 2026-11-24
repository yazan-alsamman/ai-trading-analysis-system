"""Gold: let the five's winners run past 16:45 (``docs/strategies/GOLD_HOLD.md``, registered
2026-11-10).

    python -m app research gold-hold build --export <GOLD M1>

The five's own entries and D, M8 throughout; only the end changes: BASE (as now), ALL1 (every
trade to the next day's 16:45, no horizon), WIN1 / WIN3 (a trade already at break-even at BASE's
end runs on to the 16:45 of the next / third trading day). Swap is a scenario: 3% a year of the
price for a buy, 1% for a sell, per night, three on the Wednesday rollover."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_exit as gx
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_hold_xauusd.md"  # not gold_hold.md: GOLD_HOLD.md on Windows
TUNE_END = gc.TUNE_END
SETTINGS = ("BASE", "ALL1", "WIN1", "WIN3")
DAYS = {"ALL1": 1, "WIN1": 1, "WIN3": 3}
SWAP_BUY, SWAP_SELL = 0.03, 0.01  # a year, of the price
NAMES = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")


def day_ends(cx: gl.Ctx) -> np.ndarray:
    """Per trading day: its last bar closing by 16:45 New York (-1: none)."""
    n_days = int(cx.day_idx.max()) + 1
    out = np.full(n_days, -1)
    ok = cx.day_idx >= 0
    g = pd.Series(cx.deadline[ok]).groupby(cx.day_idx[ok]).max()
    out[g.index.to_numpy()] = g.to_numpy()
    return out


def rollover_weight(cx: gl.Ctx) -> np.ndarray:
    """Per trading day: the nights its opening rollover counts (3 for Thursday's, opened
    Wednesday 17:00)."""
    close = pd.to_datetime(cx.d1["close_utc"], utc=True).dt.tz_convert(gl.NY)
    return np.where(close.dt.day_of_week.to_numpy() == 3, 3.0, 1.0)


def simulate(sig: pd.DataFrame, cx: gl.Ctx, setting: str) -> pd.DataFrame:
    o, h, lo, c = cx.o, cx.h, cx.lo, cx.c
    swl, swh = gl.swing_lows(lo), -gl.swing_lows(-h)
    ends, weight = day_ends(cx), rollover_weight(cx)
    cum = np.r_[0.0, np.cumsum(weight)]
    last = len(c) - 1
    out = []
    for name, g in sig.sort_values("i", kind="stable").groupby("strategy", sort=False):
        busy = -1
        for r in g.itertuples(index=False):
            i, base_end = int(r.i), int(r.end)
            if i <= busy:
                continue
            day = int(cx.day_idx[i])
            ext = base_end
            if setting != "BASE":
                k = day + DAYS[setting]
                ext = int(ends[k]) if 0 <= k < len(ends) and ends[k] > base_end else last
            end = ext if setting == "ALL1" else base_end
            s, e, risk = float(r.dir), float(r.entry), float(r.risk)
            cost = cx.spread[i] + gl.COMMISSION
            sl = e - s * risk
            armed, why, exit_px, j, start = False, "time", c[end], end, i + 1
            while True:
                hit = False
                for j in range(start, end + 1):
                    if lo[j] <= sl if s > 0 else h[j] >= sl:
                        gap = o[j] < sl if s > 0 else o[j] > sl
                        exit_px, why, hit = (o[j] if gap else sl), "sl", True
                        break
                    best = h[j] - e if s > 0 else e - lo[j]
                    if not armed and best >= risk:
                        armed = True
                        sl = e + s * cost if s * (e + s * cost - sl) > 0 else sl
                    if armed:
                        sw = swl[j] - 0.1 * cx.atr5[j] if s > 0 else swh[j] + 0.1 * cx.atr5[j]
                        if np.isfinite(sw) and s * (sw - sl) > 0 and s * (c[j] - sw) > 0:
                            sl = sw
                if hit:
                    break
                j = end
                if setting in ("WIN1", "WIN3") and armed and end == base_end and ext > base_end:
                    start, end = base_end + 1, ext
                    continue
                exit_px, why = c[end], "time"
                break
            busy = j
            d_end = int(cx.day_idx[j])
            nights = cum[d_end + 1] - cum[day + 1] if d_end > day else 0.0
            rate = SWAP_BUY if s > 0 else SWAP_SELL
            swap = nights * e * rate / 360.0 / risk
            out.append((name, i, j, s, risk, s * (exit_px - e) / risk, cost / risk, why,
                        swap, d_end > day))  # fmt: skip
    cols = ["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit", "swap", "overnight"]
    t = gs.finish(pd.DataFrame(out, columns=cols), cx)
    t["net"] -= t["swap"]
    t["net_slip"] -= t["swap"]
    return t


def mean(t: pd.DataFrame) -> float:
    return float(t["net_slip"].mean()) if len(t) else np.nan


HEAD = [
    "| Setting | Trades | Gross R | Cost R | Swap R | Net R with slip | Sum R | Largest drawdown R "
    "| Held overnight |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
]


def line(name: str, t: pd.DataFrame) -> str:
    p = gn.portfolio([t])
    return (f"| {name} | {len(t):,} | {t['gross'].mean():+.3f} | {t['cost'].mean():.3f} "
            f"| {t['swap'].mean():.3f} | {mean(t):+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} "
            f"| {t['overnight'].mean():.0%} |")  # fmt: skip


def block(title: str, runs: dict[str, pd.DataFrame], f) -> tuple[list[str], dict[str, float]]:
    lines, means = [f"**{title}**", "", *HEAD], {}
    for s, t in runs.items():
        sub = t[f(t)]
        means[s] = mean(sub)
        lines.append(line(s, sub))
    return [*lines, ""], means


def build(export: Path) -> str:
    cx = gl.context(gl.load())
    sig = gx.signals(cx)
    runs = {s: simulate(sig, cx, s) for s in SETTINGS}
    a_lines, a = block("XAUUSD 2012-2021", runs, lambda t: t["year"] <= TUNE_END)
    b_lines, b = block("XAUUSD 2022 to 2026-01-09", runs, lambda t: t["year"] > TUNE_END)
    best = max(("ALL1", "WIN1", "WIN3"), key=lambda s: a[s])
    fx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
    fsig = gx.signals(fx)
    when = pd.to_datetime(fx.m["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
    fsig = fsig[when[fsig["i"]] >= np.datetime64(gv.FX_START.tz_convert(None))]
    fruns = {s: simulate(fsig, fx, s) for s in SETTINGS}
    c_lines, cm = block(f"FxPro GOLD 2016-02 to the end (`{export.name}`)", fruns,
                        lambda t: t["i"] >= 0)  # fmt: skip
    d_lines, _ = block("FxPro GOLD 2026", fruns,
                       lambda t: pd.Series(pd.to_datetime(when[t["i"]]).year == 2026,
                                           index=t.index))  # fmt: skip
    beat = [a[best] > a["BASE"], b[best] > b["BASE"], cm[best] > cm["BASE"]]
    chk = runs[best][runs[best]["year"] > TUNE_END]
    base_chk = runs["BASE"][runs["BASE"]["year"] > TUNE_END]
    lines = [
        "# Gold: let the five's winners run past 16:45",
        "",
        "_`python -m app research gold-hold build`, registered in `GOLD_HOLD.md` (2026-11-10). "
        "The five's own entries and D, M8; only the end changes. Cost = the entry bar's spread + "
        "$0.07 per oz; slip $0.10 on SL exits; swap scenario 3% / 1% a year (buy / sell)._",
        "",
        *a_lines,
        *b_lines,
        *c_lines,
        *d_lines,
        f"Chosen on 2012-2021: **{best}**.",
        "",
        "The check by strategy (net R with slip and swap), BASE / chosen:",
        "",
        "| Strategy | BASE | Chosen |",
        "| --- | --- | --- |",
        *[
            f"| {n} | {mean(base_chk[base_chk['strategy'] == n]):+.3f} "
            f"| {mean(chk[chk['strategy'] == n]):+.3f} |"
            for n in NAMES
        ],
        "",
        f"**Decision (§2): {best} "
        + ("beats BASE in all three periods: shadow version" if all(beat) else "is not adopted")
        + "** (2012-2021 / check / FxPro: "
        + " / ".join("yes" if x else "no" for x in beat)
        + ").",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-hold")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
