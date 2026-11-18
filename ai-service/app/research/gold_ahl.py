"""Gold: X1 signals with large legs and low cost, explored on 2012-2017 only (commercial track,
exploratory, decides nothing; Fadi 2026-11-09 after `GOLD_AHF.md`).

    python -m app research gold-ahl explore      # XAUUSD store M1, bars before 2018 only

Two questions, before any rule is written:

1. **Drift.** After the signal, does price move in the trade's direction by more than the cost?
   Signed close-to-close move at fixed horizons, in units of the leg R, with the cost beside it.
   Under no drift, no exit can make gross R positive.
2. **Exit grid.** Gross and net R (in SL units) of fixed TP / SL distances from the entry, in leg-R
   units, beside X1's own exits.

Bars from 2018 on are never loaded, so the validation and check periods stay unread.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from app.research import gold_ah as ah
from app.research import gold_ahf as ahf
from app.strategies.cli import OUT_DIR

D_END = pd.Timestamp("2018-01-01", tz="UTC")
HORIZONS = (5, 15, 30, 60, 120, 240, 360)
TP_A = (0.25, 0.5, 1.0, 1.5, 2.0)  # TP = entry + a x R (leg R)
SL_B = (0.25, 0.5, 1.0, 2.0)  # SL = entry - b x R
REPORT = OUT_DIR / "gold_ahl_explore.md"


def load_d() -> pd.DataFrame:
    m1 = ah.load_store()
    return m1[m1.ts_utc < D_END].reset_index(drop=True)


def bases(t: pd.DataFrame) -> dict[str, np.ndarray]:
    """ALL, BIG (top 20% of leg_d), BIG+CHEAP (BIG with cost_r at or below BIG's median)."""
    d = ((t.ts >= ahf.D_PERIOD[0]) & (t.ts < ahf.D_PERIOD[1])).to_numpy()
    q80 = np.nanquantile(t.leg_d.to_numpy()[d], 0.8)
    big = d & (t.leg_d.to_numpy() >= q80)
    med = np.nanmedian(t.cost_r.to_numpy()[big])
    cheap = big & (t.cost_r.to_numpy() <= med)
    return {"ALL": d, "BIG": big, "BIG+CHEAP": cheap, "_q80": q80, "_med": med}


def drift(cx: ah.Ctx, t: pd.DataFrame) -> pd.DataFrame:
    """Signed move at each horizon (capped at the day's last bar), in leg-R units."""
    i = t.i.to_numpy()
    d = t.d.to_numpy()
    rr = d * (t.ext.to_numpy() - t.start.to_numpy())
    out = {}
    for h in HORIZONS:
        j = np.minimum(i + h, cx.end[i])
        out[h] = d * (cx.c[j] - cx.c[i]) / rr
    return pd.DataFrame(out, index=t.index)


def grid(cx: ah.Ctx, t: pd.DataFrame) -> pd.DataFrame:
    """Gross and net R (SL units) for each fixed TP / SL pair, one row per trade and cell."""
    rows = []
    for k, (i, d, s, e) in enumerate(
        zip(t.i.to_numpy(), t.d.to_numpy(), t.start.to_numpy(), t.ext.to_numpy(), strict=True)
    ):
        rr = d * (e - s)
        c = cx.c[i]
        for a in TP_A:
            for b in SL_B:
                r = ah.simulate_one(cx, int(i), int(d), ahf.X1, (c - d * b * rr, c + d * a * rr))
                if r:
                    rows.append((k, a, b, r["gross"], r["net"], r["net_slip"], r["cost"]))
    return pd.DataFrame(rows, columns=["k", "a", "b", "gross", "net", "net_slip", "cost"])


def _ct(y: np.ndarray, week: np.ndarray) -> str:
    wk, nw = ahf._week_index(week)
    m, tv = ahf.cluster_t(y, wk, nw, np.ones(len(y), bool))
    return f"{m:+.3f} ({tv:+.1f})"


def explore() -> str:
    m1 = load_d()
    cx = ah.context(m1)
    t = ahf.all_trades(cx, ah.raw_signals(cx))
    f = ahf.features(t, ahf.bar_arrays(m1, cx), cx)
    t = pd.concat([t.drop(columns=[k for k in ahf.FEATURES if k in t]), f], axis=1)
    b = bases(t)
    dr = drift(cx, t)
    cost_leg = (cx.spread[t.i.to_numpy()] + ah.COMMISSION) / (
        t.d.to_numpy() * (t.ext.to_numpy() - t.start.to_numpy())
    )
    lines = [
        "# Gold X1 with large legs and low cost: exploration on 2012-2017 (`gold_ahl.py`)",
        "",
        "_Exploratory, decides nothing. XAUUSD store M1, bars before 2018 only (2018 on not "
        "loaded). Every X1 signal a trade (`GOLD_AHF.md` §2)._",
        "",
        f"- BIG: `leg_d` ≥ {b['_q80']:.3f} (top 20% on 2012-2017, the leg ≥ that share of "
        f"ATR(14, D1)). BIG+CHEAP: BIG with `cost_r` ≤ {b['_med']:.4f} (BIG's median).",
        "",
        "## 1. Signed move after the signal, in leg R (mean, t with week-clustered SE)",
        "",
        "| Base | Trades | Cost (leg R) | " + " | ".join(f"{h} min" for h in HORIZONS) + " |",
        "| --- | --- | --- |" + " --- |" * len(HORIZONS),
    ]
    for name in ("ALL", "BIG", "BIG+CHEAP"):
        m = b[name]
        wk = t.week.to_numpy()[m]
        cells = [_ct(dr[h].to_numpy()[m], wk) for h in HORIZONS]
        lines.append(
            f"| {name} | {m.sum():,} | {np.nanmean(cost_leg[m]):.3f} | " + " | ".join(cells) + " |"
        )
    lines += [
        "",
        "By side (BIG+CHEAP):",
        "",
        "| Side | Trades | " + " | ".join(f"{h} min" for h in HORIZONS) + " |",
        "| --- | --- |" + " --- |" * len(HORIZONS),
    ]
    m = b["BIG+CHEAP"]
    for side, nm in ((1, "buys"), (-1, "sells")):
        s = m & (t.d.to_numpy() == side)
        wk = t.week.to_numpy()[s]
        lines.append(
            f"| {nm} | {s.sum():,} | "
            + " | ".join(_ct(dr[h].to_numpy()[s], wk) for h in HORIZONS)
            + " |"
        )

    sub = t[m].reset_index(drop=True)
    g = grid(cx, sub)
    g["week"] = sub.week.to_numpy()[g.k.to_numpy()]
    lines += [
        "",
        "## 2. Exit grid on BIG+CHEAP: TP = entry + a × R, SL = entry − b × R (leg R)",
        "",
        "Gross R in SL units (t), then net R. Under a random walk every cell's gross is about 0.",
        "",
        "| a \\ b | " + " | ".join(f"b {x}" for x in SL_B) + " |",
        "| --- |" + " --- |" * len(SL_B),
    ]
    for a in TP_A:
        cells = []
        for bb in SL_B:
            c = g[(g.a == a) & (g.b == bb)]
            cells.append(f"{_ct(c.gross.to_numpy(), c.week.to_numpy())} / {c.net.mean():+.3f}")
        lines.append(f"| a {a} | " + " | ".join(cells) + " |")
    x1 = sub
    lines += [
        "",
        "X1's own exits on the same trades: gross "
        + _ct(x1.gross.to_numpy(), x1.week.to_numpy())
        + f", cost {x1.cost.mean():.3f}, net {x1.net.mean():+.3f}, net slip "
        f"{x1.net_slip.mean():+.3f}.",
        "",
        "## 3. BIG+CHEAP by year (X1 exits, gross / net)",
        "",
        "| Year | Trades | Gross R | Net R |",
        "| --- | --- | --- | --- |",
    ]
    for y, gg in sub.groupby("year"):
        lines.append(f"| {y} | {len(gg):,} | {gg.gross.mean():+.3f} | {gg.net.mean():+.3f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-ahl")
    ap.add_argument("command", choices=["explore"])
    ap.parse_args(argv)
    text = explore()
    REPORT.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
