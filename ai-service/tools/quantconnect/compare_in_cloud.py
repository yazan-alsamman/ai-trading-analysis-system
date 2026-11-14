# QuantConnect Research notebook: GC minute order flow against FxPro's XAUUSD, inside the cloud.
#
# The free plan cannot download files the notebook writes, so FxPro's minutes come up instead:
# files uploaded to the project arrive empty in the notebook, so paste data/raw/gc_flow/fxpro_cell.py
# (the minutes packed into one cell) into a cell, run it, then run this one.
# Only a small summary is printed; no QuantConnect data leaves the cloud. Same measures as
# tools/quantconnect/compare_fxpro.py: one-minute return correlation at lags -5..+5 (positive:
# GC moves first), the GC - FxPro gap (basis) by contract and day, and the delta's correlation
# with FxPro's return in the same minute. Whether the flow predicts later moves is not looked at.
import glob
import os

import numpy as np
import pandas as pd

FX_NAME = "fxpro_xauusd_m1_2025q4.csv"
if "FX_MINUTES" in globals():  # pasted cell data/raw/gc_flow/fxpro_cell.py (uploads arrive empty)
    fx = FX_MINUTES.copy()  # noqa: F821
    print("FxPro: FX_MINUTES from the pasted cell,", len(fx), "minutes")
else:
    fx_path = next(iter(glob.glob(f"**/{FX_NAME}", recursive=True)), None)
    print("FxPro file:", fx_path)
    fx = pd.read_csv(fx_path)
    fx["ts_utc"] = pd.to_datetime(fx["ts_utc"], utc=True)
fx["mid"] = fx["close"] + fx["spread"] / 2
fx = fx.set_index("ts_utc")

files = sorted(f for f in glob.glob("gc_flow/*.csv") if not os.path.basename(f).startswith("test"))
g = pd.concat([pd.read_csv(f, parse_dates=["time"]) for f in files], ignore_index=True)
g = g.drop_duplicates("time").sort_values("time")
g["ts_utc"] = g["time"].dt.tz_localize("America/New_York", ambiguous="NaT",
                                      nonexistent="NaT").dt.tz_convert("UTC")
g = g.dropna(subset=["ts_utc"]).set_index("ts_utc")
print("GC files:", files, "minutes:", len(g))

j = g.join(fx[["close", "mid"]].rename(columns={"close": "fx_close", "mid": "fx_mid"}),
           how="inner").dropna(subset=["close", "fx_close"])
full = pd.date_range(j.index.min(), j.index.max(), freq="1min")
r = pd.DataFrame({"gc": np.log(j["close"]).reindex(full).diff(),
                  "fx": np.log(j["fx_close"]).reindex(full).diff(),
                  "delta": j["delta"].reindex(full)})
print(f"\nMinutes with both prices: {len(j):,}, {j.index.min():%Y-%m-%d} to {j.index.max():%Y-%m-%d}")
print("\nOne-minute return correlation by lag (positive lag: GC moves first)")
for k in range(-5, 6):
    print(f"  lag {k:+d} min: {r['gc'].corr(r['fx'].shift(-k)):+.3f}")
z = (r["delta"] - r["delta"].mean()) / r["delta"].std()
print(f"\nDelta (standardised) with FxPro's return in the same minute: {z.corr(r['fx']):+.3f}")
print(f"Delta with GC's own return in the same minute: {z.corr(r['gc']):+.3f}")
j["basis"] = j["mid_close"] - j["fx_mid"]
print("\nGap GC - FxPro (mid, $) by contract:")
print(j.groupby("contract")["basis"].agg(["median", "std", "count"]).round(2).to_string())
daily = j.groupby(j.index.tz_convert("America/New_York").date)["basis"].agg(["median", "std"])
print(f"\nDaily median gap from {daily['median'].min():+.2f} to {daily['median'].max():+.2f}; "
      f"largest daily SD {daily['std'].max():.2f}")
print(f"\nGC minutes: trades a minute median {g['trades'].median():.0f}, volume median "
      f"{g['volume'].median():.0f} lots, unsigned share {g['unsigned_vol'].sum() / g['volume'].sum():.1%}")
