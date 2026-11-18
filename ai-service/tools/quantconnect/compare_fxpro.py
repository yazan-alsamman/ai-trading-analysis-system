"""COMEX gold (GC) minute order flow against FxPro's XAUUSD: do they move together?

    .venv/Scripts/python.exe tools/quantconnect/compare_fxpro.py [--dir data/raw/gc_flow]

Reads the monthly CSVs of ``gc_flow_minutes.py`` (downloaded from QuantConnect's Object Store)
and the research store's XAUUSD M1 (FxPro, to 2026-01-09). Measures only how the two prices move
together: one-minute return correlation at lags -5..+5 minutes (positive lag: GC moves first), the
GC - FxPro price gap (basis) by day and by contract, and how the order-flow delta moves with
FxPro's return **in the same minute**. Whether the flow predicts later FxPro moves is a separate,
registered question; this script does not look at it."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
M1 = ROOT / "data" / "processed" / "XAUUSD" / "m1.parquet"
REPORT = ROOT / "docs" / "discovery" / "gc_fxpro_sync.md"
LAGS = range(-5, 6)


def load_gc(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.csv"))
    if not files:
        raise SystemExit(f"no CSV in {folder}: download gc_flow/*.csv from QuantConnect first")
    g = pd.concat([pd.read_csv(f, parse_dates=["time"]) for f in files], ignore_index=True)
    g = g.drop_duplicates("time").sort_values("time")
    g["ts_utc"] = (
        g["time"]
        .dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
        .dt.tz_convert("UTC")
    )
    return g.dropna(subset=["ts_utc"]).set_index("ts_utc")


def load_fx(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    m = pd.read_parquet(M1, filters=[("ts_utc", ">=", start), ("ts_utc", "<=", end)])
    m["mid"] = m["close"] + m["spread"] / 2
    return m.set_index("ts_utc")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "data" / "raw" / "gc_flow")
    a = ap.parse_args(argv)
    g = load_gc(a.dir)
    fx = load_fx(g.index.min(), g.index.max())
    j = g.join(
        fx[["close", "mid"]].rename(columns={"close": "fx_close", "mid": "fx_mid"}), how="inner"
    )
    j = j.dropna(subset=["close", "fx_close"])
    full = pd.date_range(j.index.min(), j.index.max(), freq="1min")
    r = pd.DataFrame(
        {
            "gc": np.log(j["close"]).reindex(full).diff(),
            "fx": np.log(j["fx_close"]).reindex(full).diff(),
            "delta": j["delta"].reindex(full),
        }
    )
    lead = {k: r["gc"].corr(r["fx"].shift(-k)) for k in LAGS}
    j["basis"] = j["mid_close"] - j["fx_mid"]
    j["day"] = j.index.tz_convert("America/New_York").date
    daily = j.groupby("day")["basis"].agg(["median", "std", "count"])
    by_c = j.groupby("contract")["basis"].agg(["median", "std", "count"])
    z = (r["delta"] - r["delta"].mean()) / r["delta"].std()
    same = z.corr(r["fx"])
    lines = [
        "# GC order flow against FxPro XAUUSD: do they move together?",
        "",
        f"_`tools/quantconnect/compare_fxpro.py`: {len(j):,} minutes with both prices, "
        f"{j.index.min():%Y-%m-%d} to {j.index.max():%Y-%m-%d}. Descriptive only._",
        "",
        "## One-minute return correlation by lag (positive: GC moves first)",
        "",
        "| Lag (minutes) | " + " | ".join(str(k) for k in LAGS) + " |",
        "|" + " --- |" * (len(LAGS) + 1),
        "| Correlation | " + " | ".join(f"{lead[k]:+.3f}" for k in LAGS) + " |",
        "",
        f"Order-flow delta (standardised) with FxPro's return in the same minute: {same:+.3f}.",
        "",
        "## The gap GC - FxPro (mid, $)",
        "",
        "| Contract | Median | SD | Minutes |",
        "| --- | --- | --- | --- |",
        *[
            f"| {c} | {x['median']:+.2f} | {x['std']:.2f} | {int(x['count']):,} |"
            for c, x in by_c.iterrows()
        ],
        "",
        f"Daily median gap: from {daily['median'].min():+.2f} to {daily['median'].max():+.2f}; "
        f"the largest daily SD {daily['std'].max():.2f}.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
