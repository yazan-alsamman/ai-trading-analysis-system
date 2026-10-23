"""Setup features (L4, P4 task 1) and the walk-forward dataset.

    python -m app features build        # L1 setups, six instruments, 2012-01-01 to 2024-06-30

Writes ``data/processed/p4_dataset_<rules>.parquet`` (one row per labelled setup: identity,
features, label ``y`` and realised R; untracked) and ``docs/phase4/dataset_<rules>.md`` (counts
and feature coverage only: outcomes of the walk-forward period are read only by the walk-forward
protocol, never summarised here).

Every feature is known at the close of the decision (CHoCH) bar: entry-frame values at that bar
and earlier, higher-timeframe values from bars that closed by then. All are scale-free (ATR
units, ratios, positions, percentiles), because gold went from about $1,600 to $4,500.
"Aligned" features are signed by the trade direction: positive means in favour of the trade.

Families (design §9.1):

* **Setup geometry**: ``r_multiple``, ``risk_atr``, ``depth_atr``, ``levels_taken``, ``src_4h``,
  ``src_pd`` (1h is the base), ``tgt_4h``, ``tgt_pd``, ``has_fvg``, ``fvg_size_atr`` (0 without),
  ``bars_sweep_to_choch``, ``displacement_atr`` (sweep extreme to the decision close),
  ``choch_margin_atr`` (decision close beyond the broken swing).
* **Context**: ``trend_1h``, ``trend_4h``, ``trend_d1`` (aligned close minus EMA 20 of that frame,
  in its ATR); ``pd_pos`` (aligned position in the previous day's range: 1 = at the favourable
  end, a discount for a buy); ``asia_range_atr``, ``asia_pos`` (today's 20:00-00:00 New York
  range; missing until it closes).
* **Time**: ``hour_sin``, ``hour_cos`` (New York time of day), ``dow``, ``london_kz``
  (02:00-05:00 NY), ``ny_kz`` (07:00-10:00 NY).
* **Cost**: ``spread_r`` (decision spread over the risk), ``spread_atr``, ``spread_vs_hour``
  (over the median spread of the same New York hour in the 20 trading days before).
* **Volatility**: ``atr_pct`` (entry ATR percentile in the last 20 trading days),
  ``d1_atr_pct`` (D1 ATR percentile in the last 250 days).
* **Instrument**: ``direction_buy``, ``usd_long`` (the trade is long USD), ``sym_<SYMBOL>``.
* **Trade size** (Fadi, 2026-10-23): ``tp_usd_min_lot``, the profit in USD at the TP on the
  smallest lot (0.01), converted at the decision close for a non-USD quote. The one feature in
  dollars, on purpose: Fadi treats a target under about $3-4 at 0.01 lot as not worth a trade.

Not yet: news timing (needs the historical calendar, open with Yazan), the encoder embedding
(L5, P5), regime probabilities (L6, P5), cross-asset inputs (an ablation)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Strategy, instruments, splits, strategy
from app.data.aggregate import trading_day
from app.data.importer import DEFAULT_OUT as STORE
from app.data.sessions import MARKET_TZ
from app.setups.counts import history_frames
from app.setups.labels import label_all
from app.smc.primitives import atr

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "phase4"
EMA_SPAN = 20
SPREAD_DAYS = 20
ATR_PCT_BARS = 20 * 96  # about 20 trading days of 15-minute bars
D1_PCT_DAYS = 250
MIN_LOT = 0.01
ASIA = (20, 24)  # New York hours, the evening part of the trading day
SYMBOLS = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD")
ID_COLS = [
    "symbol",
    "setup_id",
    "decision_utc",
    "year",
    "direction",
    "entry",
    "tp",
    "risk",
    "spread",
]
TARGETS = ["y", "net_r", "net_r_2x", "gross_r", "reason", "exit_utc"]


def _last_closed(frame: pd.DataFrame, t: np.ndarray) -> np.ndarray:
    """Index of the last ``frame`` bar closed by each time in ``t`` (-1 if none)."""
    return np.searchsorted(frame["close_utc"].to_numpy(), t, side="right") - 1


def _trend(frame: pd.DataFrame, t: np.ndarray, period: int) -> np.ndarray:
    """(close - EMA) / ATR of the last bar of ``frame`` closed by each ``t``."""
    c = frame["close"].to_numpy(float)
    if len(c) == 0:
        return np.full(len(t), np.nan)
    ema = pd.Series(c).ewm(span=EMA_SPAN, adjust=False).mean().to_numpy()
    a = atr(frame["high"].to_numpy(float), frame["low"].to_numpy(float), c, period)
    i = _last_closed(frame, t)
    out = np.full(len(t), np.nan)
    ok = i >= 0
    out[ok] = (c[i[ok]] - ema[i[ok]]) / a[i[ok]]
    return out


def _rolling_pct(x: np.ndarray, window: int) -> np.ndarray:
    """Percentile (0-1) of each value among the last ``window`` values, itself included."""
    return pd.Series(x).rolling(window, min_periods=window // 4).rank(pct=True).to_numpy()


def _spread_vs_hour(entry: pd.DataFrame, ny: pd.DatetimeIndex) -> np.ndarray:
    """Spread over the median of the same New York hour in the previous ``SPREAD_DAYS`` days."""
    s = entry["spread_mean"] if "spread_mean" in entry else pd.Series(np.nan, index=entry.index)
    day = pd.Series(trading_day(entry["ts_utc"]).to_numpy(), index=entry.index)
    hourly = pd.DataFrame({"s": s.to_numpy(float), "day": day, "hour": ny.hour}, index=entry.index)
    out = np.full(len(entry), np.nan)
    for _, g in hourly.groupby("hour"):
        per_day = g.groupby("day")["s"].median()
        ref = per_day.rolling(SPREAD_DAYS, min_periods=5).median().shift(1)  # days before only
        ref = ref.where(ref > 0)  # a zero recorded spread gives no reference (EURUSD 2021-2023)
        out[g.index.to_numpy()] = g["s"].to_numpy() / g["day"].map(ref).to_numpy()
    return out


def _asia(entry: pd.DataFrame, ny: pd.DatetimeIndex) -> pd.DataFrame:
    """High, low and close time of each trading day's Asia window."""
    day = trading_day(entry["ts_utc"])
    m = (ny.hour >= ASIA[0]) & (ny.hour < ASIA[1])
    g = entry[m].assign(day=day[m].to_numpy()).groupby("day")
    return g.agg(hi=("high", "max"), lo=("low", "min"), end=("close_utc", "max"))


def features(frames: dict[str, pd.DataFrame], setups: pd.DataFrame, symbol: str, p) -> pd.DataFrame:
    """One row of features per setup (``label_all`` rows), from data known at its decision."""
    entry = frames[p.entry_timeframe]
    n = len(setups)
    if n == 0:
        return pd.DataFrame(index=setups.index)
    d = setups["decision_idx"].to_numpy(int)
    t = entry["close_utc"].to_numpy()[d]
    sign = np.where(setups["direction"].to_numpy() == "buy", 1.0, -1.0)
    close = entry["close"].to_numpy(float)[d]
    a = setups["atr"].to_numpy(float)
    risk = setups["risk"].to_numpy(float)
    spread = setups["spread"].to_numpy(float)
    ny_all = pd.DatetimeIndex(entry["ts_utc"]).tz_convert(MARKET_TZ)
    ny = pd.DatetimeIndex(pd.to_datetime(t)).tz_convert(MARKET_TZ)
    f = pd.DataFrame(index=setups.index)

    f["r_multiple"] = setups["r_multiple"].to_numpy(float)
    f["risk_atr"] = risk / a
    f["depth_atr"] = setups["depth_atr"].to_numpy(float)
    f["levels_taken"] = setups["levels_taken"].to_numpy(float)
    f["src_4h"] = (setups["level_source"] == "4h").to_numpy(float)
    f["src_pd"] = (setups["level_source"] == "pd").to_numpy(float)
    f["tgt_4h"] = (setups["target_source"] == "4h").to_numpy(float)
    f["tgt_pd"] = (setups["target_source"] == "pd").to_numpy(float)
    fvg = setups["fvg_size_atr"].to_numpy(float)
    f["has_fvg"] = (~np.isnan(fvg)).astype(float)
    f["fvg_size_atr"] = np.nan_to_num(fvg, nan=0.0)
    f["bars_sweep_to_choch"] = setups["bars_sweep_to_choch"].to_numpy(float)
    f["displacement_atr"] = sign * (close - setups["extreme"].to_numpy(float)) / a
    f["choch_margin_atr"] = sign * (close - setups["choch_ref_price"].to_numpy(float)) / a

    for tf, name in (("1h", "trend_1h"), ("4h", "trend_4h"), ("D1", "trend_d1")):
        f[name] = sign * _trend(frames[tf], t, p.atr_period)
    d1 = frames["D1"]
    i = _last_closed(d1, t)
    pos = np.full(n, np.nan)
    if len(d1):
        hi, lo = d1["high"].to_numpy(float), d1["low"].to_numpy(float)
        ok = i >= 0
        rng_ = hi[i[ok]] - lo[i[ok]]
        raw = (close[ok] - lo[i[ok]]) / np.where(rng_ > 0, rng_, np.nan)
        pos[ok] = np.where(sign[ok] > 0, 1 - raw, raw)
    f["pd_pos"] = pos
    asia = _asia(entry, ny_all)
    day = trading_day(entry["ts_utc"]).iloc[d].reset_index(drop=True)
    a_hi = day.map(asia["hi"]).to_numpy(float)
    a_lo = day.map(asia["lo"]).to_numpy(float)
    a_end = day.map(asia["end"])
    done = (a_end.notna() & (a_end <= pd.Series(t))).to_numpy()
    width = a_hi - a_lo
    f["asia_range_atr"] = np.where(done, width / a, np.nan)
    raw = (close - a_lo) / np.where(width > 0, width, np.nan)
    f["asia_pos"] = np.where(done, np.where(sign > 0, 1 - raw, raw), np.nan)

    minutes = ny.hour * 60 + ny.minute
    f["hour_sin"] = np.sin(2 * np.pi * minutes / 1440)
    f["hour_cos"] = np.cos(2 * np.pi * minutes / 1440)
    f["dow"] = ny.dayofweek.to_numpy(float)
    f["london_kz"] = ((ny.hour >= 2) & (ny.hour < 5)).astype(float)
    f["ny_kz"] = ((ny.hour >= 7) & (ny.hour < 10)).astype(float)

    f["spread_r"] = spread / risk
    f["spread_atr"] = spread / a
    f["spread_vs_hour"] = _spread_vs_hour(entry, ny_all)[d]

    ea = atr(
        entry["high"].to_numpy(float),
        entry["low"].to_numpy(float),
        entry["close"].to_numpy(float),
        p.atr_period,
    )
    f["atr_pct"] = _rolling_pct(ea, ATR_PCT_BARS)[d]
    d1_pct = np.full(n, np.nan)
    if len(d1):
        da = atr(
            d1["high"].to_numpy(float),
            d1["low"].to_numpy(float),
            d1["close"].to_numpy(float),
            p.atr_period,
        )
        pct = _rolling_pct(da, D1_PCT_DAYS)
        ok = i >= 0
        d1_pct[ok] = pct[i[ok]]
    f["d1_atr_pct"] = d1_pct

    inst = instruments()[symbol]
    usd = np.abs(setups["tp"].to_numpy(float) - setups["entry"].to_numpy(float))
    usd = usd * inst.contract_size * MIN_LOT
    f["tp_usd_min_lot"] = usd if inst.quote_currency == "USD" else usd / close

    f["direction_buy"] = (sign > 0).astype(float)
    usd_base = symbol.startswith("USD")
    f["usd_long"] = ((sign > 0) == usd_base).astype(float)
    for s in SYMBOLS:
        f[f"sym_{s}"] = float(s == symbol)
    return f


FEATURES = [
    "r_multiple", "risk_atr", "depth_atr", "levels_taken", "src_4h", "src_pd", "tgt_4h",
    "tgt_pd", "has_fvg", "fvg_size_atr", "bars_sweep_to_choch", "displacement_atr",
    "choch_margin_atr", "trend_1h", "trend_4h", "trend_d1", "pd_pos", "asia_range_atr",
    "asia_pos", "hour_sin", "hour_cos", "dow", "london_kz", "ny_kz", "spread_r", "spread_atr",
    "spread_vs_hour", "atr_pct", "d1_atr_pct", "tp_usd_min_lot", "direction_buy", "usd_long",
    *[f"sym_{s}" for s in SYMBOLS],
]  # fmt: skip


def dataset(symbol: str, p: Strategy, end: pd.Timestamp, store: Path = STORE) -> pd.DataFrame:
    """Labelled setups of one instrument with their features, 2012 to ``end``."""
    frames = history_frames(symbol, p, store, end)
    if frames[p.entry_timeframe].empty:
        return pd.DataFrame()
    df = label_all(frames, symbol, p)
    if df.empty:
        return df
    df = df[df["state"] == "CLOSED"].reset_index(drop=True)
    df.insert(0, "symbol", symbol)
    f = features(frames, df, symbol, p)
    return pd.concat([df[ID_COLS + TARGETS], f[FEATURES]], axis=1)


def render(df: pd.DataFrame, p: Strategy, end: pd.Timestamp) -> str:
    counts = df.pivot_table(index="year", columns="symbol", values="setup_id", aggfunc="count")
    counts = counts.fillna(0).astype(int)
    counts["all"] = counts.sum(axis=1)
    cov = df[FEATURES].notna().mean()
    lines = [
        f"# P4: setup dataset ({p.rule_set})",
        "",
        "_Generated by `python -m app features build`; features in"
        " `app/features/setup_features.py`. Counts and coverage only: outcomes of the"
        " walk-forward period are read by the walk-forward protocol alone._",
        "",
        f"Labelled setups, 2012-01-01 to {end:%Y-%m-%d} (exclusive): **{len(df)}**,"
        f" {len(FEATURES)} features.",
        "",
        "| Year | " + " | ".join(counts.columns) + " |",
        "|" + " --- |" * (len(counts.columns) + 1),
        *[f"| {y} | " + " | ".join(str(v) for v in r) + " |" for y, r in counts.iterrows()],
        "",
        "Features with missing values (share present):",
        "",
        "| Feature | Present |",
        "| --- | --- |",
        *[f"| {k} | {v:.1%} |" for k, v in cov.items() if v < 1],
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m app features build")
    ap.add_argument("command", choices=["build"])
    ap.add_argument("--rules", default="L1")
    ap.add_argument("--symbol", action="append")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    p = strategy(args.rules)
    end = pd.Timestamp(splits().walk_forward[1], tz="UTC")
    parts = []
    for s in args.symbol or [x for x in SYMBOLS if x in instruments()]:
        part = dataset(s, p, end, args.store)
        print(f"{s}: {len(part)} labelled setups", file=sys.stderr)
        if len(part):
            parts.append(part)
    if not parts:
        print("no setups", file=sys.stderr)
        return 1
    df = pd.concat(parts, ignore_index=True).sort_values(["decision_utc", "symbol"])
    df = df.reset_index(drop=True)
    df.to_parquet(args.store / f"p4_dataset_{p.rule_set}.parquet", index=False)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"dataset_{p.rule_set}.md").write_text(
        render(df, p, end), encoding="utf-8", newline="\n"
    )
    print(f"{len(df)} labelled setups, {len(FEATURES)} features")
    return 0
