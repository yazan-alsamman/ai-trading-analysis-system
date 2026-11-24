"""Heikin-Ashi flips on 4h, on the five FX pairs (``docs/strategies/HA4H_FX.md``, registered
2026-11-12 before any outcome on these markets).

    python -m app research ha-fx [--export <GOLD M1>]

``gold_ha`` H24 rules on 4h bars (stop and reverse at the real next open, flat over the weekend),
FX costs (recorded spread + 0.00007 x price), swap scenarios of 0, 0.5 and 1 pip a night (three on
Wednesday rollovers). The decision: the pooled pairs at 0.5 pip."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_exam as ge
from app.research import gold_ha as ha
from app.research import gold_lab as gl
from app.research import gold_live as gv

REPORT = gl.OUT_DIR / "ha4h_fx_result.md"
PAIRS = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "AUDUSD": 0.0001, "USDCAD": 0.0001}
FX_COMMISSION = 7e-5
SWAPS = (0.0, 0.5, 1.0)  # pips a night
DECIDE = 0.5
GOLD_SWAPS = (0.0, 0.10, 0.20)  # $ an ounce a night
WARM = pd.Timedelta(days=30)
LOCKBOX = pd.Timestamp("2026-01-10", tz="UTC")


def nights(t: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    """17:00 New York rollovers held by each trade (a Wednesday one counts three)."""
    t_in = frame["ts_utc"].to_numpy()[t["k"]]
    t_out = np.where(
        t["why"] == "cut", frame["close_utc"].to_numpy()[t["x"]], frame["ts_utc"].to_numpy()[t["x"]]
    )
    a = pd.to_datetime(t_in, utc=True).tz_convert(gl.NY) - pd.Timedelta(hours=17)
    b = pd.to_datetime(t_out, utc=True).tz_convert(gl.NY) - pd.Timedelta(hours=17)
    out = np.zeros(len(t))
    for q, (x, y) in enumerate(zip(a.normalize(), b.normalize(), strict=True)):
        days = pd.date_range(x + pd.Timedelta(days=1), y, freq="D") if y > x else []
        out[q] = sum(3 if d.day_of_week == 2 else 1 for d in days)
    return out


def run(frame: pd.DataFrame, commission, pip: float, swaps, start: pd.Timestamp) -> pd.DataFrame:
    t = ha.trades(frame, "H24", commission=commission)
    t = t[pd.to_datetime(t["t_open"], utc=True) >= start].reset_index(drop=True)
    n = nights(t, frame)
    t["nights"] = n
    for s in swaps:
        t[f"net_{s:g}"] = t["gross"] - t["cost"] - n * s * pip / t["risk"]
    d = swaps[1] if len(swaps) > 1 else swaps[0]
    t["net"] = t[f"net_{d:g}"]  # the deciding scenario (``gold_ha.t_vs_e0`` reads "net")
    t["net2"] = t["net"] - t["cost"]
    return t


def row(name: str, t: pd.DataFrame, swaps, days: int) -> str:
    yr = t.groupby("year")["net"].mean()
    return (
        f"| {name} | {len(t):,} | {len(t) / max(days, 1):.2f} | {t['gross'].mean():+.3f} "
        f"| {t['cost'].mean():.3f} | {t['nights'].mean():.2f} | "
        + " | ".join(f"{t[f'net_{s:g}'].mean():+.3f}" for s in swaps)
        + f" | {t['net2'].mean():+.3f} | {(yr > 0).mean():.0%} | {ha.t_vs_e0(t):+.2f} |"
    )


def build(export: Path | None) -> str:
    head = (
        "| Pair | Trades | A day | Gross R | Cost R | Nights held | Net, swap 0 | 0.5 pip "
        "| 1 pip | At 2x cost (0.5) | Years + (0.5) | t vs E0 (0.5) |"
    )
    lines = [
        "# Heikin-Ashi flips on 4h, the five FX pairs",
        "",
        "_`python -m app research ha-fx`, registered in `HA4H_FX.md` (2026-11-12) before the "
        "run. R = ATR(14, 4h); cost = spread + 0.00007 x price; swap per rollover held._",
        "",
        head,
        "|" + " --- |" * 12,
    ]
    every, by_pair = [], {}
    for sym, pip in PAIRS.items():
        fr = gl.load(sym)
        f4 = fr["4h"]
        f4 = f4[f4["ts_utc"] < LOCKBOX].reset_index(drop=True)
        start = f4["ts_utc"].iloc[0] + WARM
        t = run(f4, FX_COMMISSION * f4["close"].to_numpy(), pip, SWAPS, start)
        days = f4[f4["ts_utc"] >= start]["close_utc"].dt.tz_convert(gl.NY).dt.date.nunique()
        lines.append(row(sym, t, SWAPS, days))
        by_pair[sym] = t
        every.append(t.assign(pair=sym))
    pool = pd.concat(every, ignore_index=True)
    lines.append(
        row("**All five**", pool, SWAPS, max(1, days)).replace(f"| {len(pool) / days:.2f}", "| -")
    )
    tp = ha.t_vs_e0(pool)
    m, m2 = pool["net"].mean(), pool["net2"].mean()
    prim = m > 0 and m2 > 0 and tp >= 3
    pos = sum(by_pair[s]["net"].mean() > 0 for s in PAIRS)
    lines += [
        "",
        f"**Primary (pooled, 0.5 pip):** mean {m:+.3f} R, at 2x cost {m2:+.3f}, t vs E0 "
        f"{tp:+.2f}: {'passes' if prim else 'fails'}. Pairs with net > 0: {pos} of 5. "
        f"**The rule {'generalises' if prim and pos >= 3 else 'does not generalise'}.**",
        "",
    ]
    if export is not None:
        fx = ge.frames_from_lines(gv.fx_lines(export))["4h"]
        t = run(fx, gl.COMMISSION, 1.0, GOLD_SWAPS, gv.FX_START)
        days = fx[fx["ts_utc"] >= gv.FX_START]["close_utc"].dt.tz_convert(gl.NY).dt.date.nunique()
        lines += [
            "Reported, deciding nothing: gold on FxPro 2016-02 to 2026-11-05 (4h, swap $0, "
            "0.10, 0.20 an ounce a night; gold was seen).",
            "",
            head.replace("0.5 pip", "$0.10").replace("1 pip", "$0.20").replace("(0.5)", "($0.10)"),
            "|" + " --- |" * 12,
            row("GOLD (FxPro)", t, GOLD_SWAPS, days),
        ]
    years = sorted(pool["year"].unique())
    lines += [
        "",
        "By year, net R at 0.5 pip:",
        "",
        "| Pair | " + " | ".join(map(str, years)) + " |",
        "|" + " --- |" * (1 + len(years)),
    ]
    for sym, t in by_pair.items():
        v = t.groupby("year")["net"].mean()
        lines.append(f"| {sym} | " + " | ".join(f"{v.get(y, np.nan):+.3f}" for y in years) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research ha-fx")
    ap.add_argument("--export", type=Path, help="FxPro GOLD M1 export (the gold row)")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
