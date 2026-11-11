"""Gold: a fixed target and an early lock for the five level breaks (``docs/strategies/
GOLD_EXIT.md``, registered 2026-11-10; Fadi's idea).

    python -m app research gold-exit build      # XAUUSD 2012 to 2026-01-09

The entries are the five demo strategies' own; only the exit changes: SL = TP = k x ATR(14, D1),
the SL locked at break-even (BE) or a quarter of the target (Q) at half the target, then
optionally M8's trail. The baseline is the current M8 exit."""

from __future__ import annotations

import argparse
import itertools

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_exit_xauusd.md"  # not gold_exit.md: GOLD_EXIT.md on Windows
TUNE_END = gc.TUNE_END
KS, LOCKS, TRAILS = (0.3, 0.4, 0.5), ("BE", "Q"), (True, False)
NAMES = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")


def signals(cx: gl.Ctx) -> pd.DataFrame:
    """The five strategies' entries, as the EA places them."""
    lvl = gc.levels(cx, "LVL4H", gc.day_levels(cx), ge.LVL_MULT * cx.atr4h,
                    gc.WINDOWS[ge.LVL_WINDOW], ge.LVL_HORIZON, ge.LVL_CAP)  # fmt: skip
    piv = gc.levels(cx, "PIVOT", gc.pivot_levels(cx), cx.atr1h, gc.WINDOWS[ge.PIV_WINDOW],
                    ge.PIV_HORIZON, None)  # fmt: skip
    sh = [
        gc.levels(cx, k, lv, ge.LVL_MULT * cx.atr4h, gc.WINDOWS[ge.LVL_WINDOW], ge.LVL_HORIZON,
                  ge.LVL_CAP)
        for k, lv in gs.shadow_levels(cx).items()
    ]  # fmt: skip
    return pd.concat([lvl, piv, *sh], ignore_index=True)


def simulate(sig: pd.DataFrame, cx: gl.Ctx, k: float, lock: str, trail: bool) -> pd.DataFrame:
    """SL = TP = k x ATR(D1) from the entry; at +S/2 the SL locks (BE or Q), then the trail."""
    o, h, lo, c = cx.o, cx.h, cx.lo, cx.c
    swl, swh = gl.swing_lows(lo), -gl.swing_lows(-h)
    out = []
    for name, g in sig.sort_values("i", kind="stable").groupby("strategy", sort=False):
        busy = -1
        for r in g.itertuples(index=False):
            i, end = int(r.i), int(r.end)
            size = k * cx.atrd[i]
            if i <= busy or not np.isfinite(size) or size <= 0:
                continue
            s, e = float(r.dir), float(r.entry)
            cost = cx.spread[i] + gl.COMMISSION
            sl, tp = e - s * size, e + s * size
            locked = False
            exit_px, why, j = c[end], "time", end
            for j in range(i + 1, end + 1):
                if lo[j] <= sl if s > 0 else h[j] >= sl:
                    gap = o[j] < sl if s > 0 else o[j] > sl
                    exit_px, why = (o[j] if gap else sl), "sl"
                    break
                if h[j] >= tp if s > 0 else lo[j] <= tp:
                    gap = o[j] > tp if s > 0 else o[j] < tp
                    exit_px, why = (o[j] if gap else tp), "tp"
                    break
                best = h[j] - e if s > 0 else e - lo[j]
                if not locked and best >= size / 2:
                    locked = True
                    to = e + s * (cost if lock == "BE" else size / 4)
                    sl = to if s * (to - sl) > 0 else sl
                if locked and trail:
                    sw = swl[j] - 0.1 * cx.atr5[j] if s > 0 else swh[j] + 0.1 * cx.atr5[j]
                    if np.isfinite(sw) and s * (sw - sl) > 0 and s * (c[j] - sw) > 0:
                        sl = sw
            else:
                j = end
            busy = j
            out.append((name, i, j, s, size, s * (exit_px - e) / size, cost / size, why, locked))
    cols = ["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit", "locked"]
    return gs.finish(pd.DataFrame(out, columns=cols), cx)


def baseline(sig: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    """The current exits: SL D, no target, M8."""
    return gs.finish(gl.simulate(sig, cx, "M8"), cx)


def mean_slip(t: pd.DataFrame) -> float:
    return float(t["net_slip"].mean()) if len(t) else np.nan


def tune(sig: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    rows = []
    for k, lock, trail in itertools.product(KS, LOCKS, TRAILS):
        t = simulate(sig, cx, k, lock, trail)
        a, b = t[t["year"] <= TUNE_END], t[t["year"] > TUNE_END]
        rows.append({"k": k, "lock": lock, "trail": "yes" if trail else "no",
                     "tune_n": len(a), "tune": mean_slip(a), "tune_gross": a["gross"].mean(),
                     "tune_cost": a["cost"].mean(),
                     "tune_years": (a.groupby("year")["net_slip"].mean() > 0).mean(),
                     "check_n": len(b), "check": mean_slip(b), "check_gross": b["gross"].mean(),
                     "tp": (t["exit"] == "tp").mean()})  # fmt: skip
    return pd.DataFrame(rows).sort_values("tune", ascending=False).reset_index(drop=True)


def _line(name: str, t: pd.DataFrame) -> str:
    p = gn.portfolio([t]) if len(t) else {"dd": np.nan, "sum": np.nan}
    ex = t["exit"].value_counts(normalize=True)
    return (f"| {name} | {len(t):,} | {t['gross'].mean():+.3f} | {t['cost'].mean():.3f} "
            f"| {mean_slip(t):+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} | {ex.get('tp', 0):.0%} "
            f"| {ex.get('sl', 0):.0%} | {ex.get('time', 0):.0%} |")  # fmt: skip


HEAD = [
    "| Set | Trades | Gross R | Cost R | Net R with slip | Sum R | Largest drawdown R | TP | SL "
    "| Time |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
]


def build() -> str:
    cx = gl.context(gl.load())
    sig = signals(cx)
    base = baseline(sig, cx)
    g = tune(sig, cx)
    best = g.iloc[0]
    chosen = simulate(sig, cx, float(best["k"]), str(best["lock"]), best["trail"] == "yes")
    cb, bb = chosen[chosen["year"] > TUNE_END], base[base["year"] > TUNE_END]
    adopt = mean_slip(cb) > 0 and mean_slip(cb) > mean_slip(bb)
    lines = [
        "# Gold: a fixed target and an early lock for the five level breaks, XAUUSD",
        "",
        "_`python -m app research gold-exit build`, registered in `GOLD_EXIT.md` (2026-11-10). "
        "XAUUSD 5m bars 2012-01 to 2026-01-09; the five strategies' own entries; cost = the "
        "entry bar's spread + $0.07 per oz; slip adds $0.10 on SL exits. Seen data._",
        "",
        "## 1. The 12 settings (the five together, net R with slip, by 2012-2021)",
        "",
        "| k | Lock | Trail | Tune trades | Tune net | Tune gross | Tune cost | Tune years + "
        "| Check trades | Check net | Check gross | TP share |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.k:g} | {r.lock} | {r.trail} | {r.tune_n:,} | {r.tune:+.3f} "
            f"| {r.tune_gross:+.3f} | {r.tune_cost:.3f} | {r.tune_years:.0%} | {r.check_n:,} "
            f"| {r.check:+.3f} | {r.check_gross:+.3f} | {r.tp:.0%} |"
            for r in g.itertuples()
        ],
        "",
        f"Chosen: k {best['k']:g}, lock {best['lock']}, trail {best['trail']}.",
        "",
        "## 2. Chosen against the baseline (current M8 exits)",
        "",
        *HEAD,
    ]
    for lab, f in (("2012-2021", lambda t: t["year"] <= TUNE_END),
                   ("check 2022 to 2026-01-09", lambda t: t["year"] > TUNE_END)):  # fmt: skip
        lines += [
            _line(f"Baseline, {lab}", base[f(base)]),
            _line(f"Chosen, {lab}", chosen[f(chosen)]),
        ]
    lines += ["", "By strategy, the check:", "", *HEAD]
    for s in NAMES:
        lines += [_line(f"{s} baseline", bb[bb["strategy"] == s]),
                  _line(f"{s} chosen", cb[cb["strategy"] == s])]  # fmt: skip
    lines += ["", "| Year | Baseline net R with slip | Chosen |", "| --- | --- | --- |"]
    for y in sorted(set(base["year"])):
        lines.append(f"| {y} | {mean_slip(base[base['year'] == y]):+.3f} "
                     f"| {mean_slip(chosen[chosen['year'] == y]):+.3f} |")  # fmt: skip
    lines += ["", f"**Decision (§3): {'adopt as a shadow exit' if adopt else 'not adopted'}.**"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-exit")
    ap.add_argument("step", choices=("build",))
    ap.parse_args(argv)
    REPORT.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
