"""Labelled dataset for Phase 3: one row per closed setup of the frozen rules.

    python -m app.ml.dataset  # data/processed/XAUUSD/phase3_dataset.parquet, docs/phase3/dataset.md

The label is 1 when TP was hit before SL within the horizon after the fill, 0 for SL or a timeout
(the engine already counts an ambiguous bar as SL). Unfilled setups have no label.

Every feature is measured at the close of the CHoCH bar, the moment the setup is confirmed, from
bars that had closed by then, and is scale-free (ATR units, ratios or flags), because gold's price
level more than doubled over the data. Features are written for the trade's direction: a positive
trend means the higher timeframe moves the trade's way. The report summarises features and labels
on the development period only; walk-forward rows are counted, not described."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.data.sessions import MARKET_TZ, trading_day
from app.smc.engine import Setup, run
from app.smc.params import CURRENT, CURRENT_NAME, CostParams, StrategyParams
from app.smc.primitives import atr
from app.smc.report import DATA_DIR, DEV_END, LOCKBOX_START, SERVICE_DIR

OUT_DIR = SERVICE_DIR / "docs" / "phase3"
DATASET = DATA_DIR / "phase3_dataset.parquet"

ATR_MEDIAN_BARS = 20 * 276  # about 20 trading days of 5m bars
SPREAD_MEDIAN_DAYS = 20
HTF_EMA = 50

FEATURES = [
    # setup geometry
    "r_multiple",
    "risk_atr",
    "fvg_atr",
    "sweep_depth_atr",
    "choch_disp_atr",
    "entry_dist_atr",
    "bars_sweep_to_choch",
    "fvg_bars_before_choch",
    # market context
    "trend_1h",
    "trend_4h",
    "atr_ratio_20d",
    "pd_room_atr",
    "pd_back_atr",
    "session_asia",
    "session_london",
    "session_ny",
    "level_htf",
    "level_pd",
    "is_buy",
    # cost
    "spread_rel",
    "cost_r",
]


class Context:
    """Per-bar arrays the features read, each using only bars up to and including that bar."""

    def __init__(self, bars: pd.DataFrame, h1: pd.DataFrame, h4: pd.DataFrame, p: StrategyParams):
        self.ts = bars["ts_utc"].reset_index(drop=True)
        self.tf = pd.Timedelta(minutes=p.entry_tf_minutes)
        h, lo, c = (bars[k].to_numpy(float) for k in ("high", "low", "close"))
        self.close = c
        self.spread = bars["spread"].fillna(0.0).to_numpy(float)
        self.atr = atr(h, lo, c, p.atr_period)
        self.atr_median = (
            pd.Series(self.atr).rolling(ATR_MEDIAN_BARS, min_periods=ATR_MEDIAN_BARS // 4).median()
        ).to_numpy()
        ny = self.ts.dt.tz_convert(MARKET_TZ)
        self.ny_minutes = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
        # Typical spread at this time of day: the median of the previous days' bars at that time.
        same_time = pd.Series(self.spread).groupby(self.ny_minutes)
        self.spread_median = same_time.transform(
            lambda s: s.rolling(SPREAD_MEDIAN_DAYS, min_periods=5).median().shift(1)
        ).to_numpy()
        # The previous trading day's high and low, complete before the current day's first bar.
        day = trading_day(self.ts)
        daily = (
            pd.DataFrame({"day": day, "h": h, "lo": lo})
            .groupby("day")
            .agg(high=("h", "max"), low=("lo", "min"))
        )
        prev = daily.shift(1)
        self.pdh = prev["high"].reindex(day).to_numpy()
        self.pdl = prev["low"].reindex(day).to_numpy()
        self.htf = {
            "1h": _htf_trend(h1, pd.Timedelta(hours=1), p),
            "4h": _htf_trend(h4, pd.Timedelta(hours=4), p),
        }

    def trend(self, name: str, decision_ts: pd.Timestamp) -> float:
        """(close - EMA) / ATR of the last higher-timeframe bar closed by ``decision_ts``."""
        close_ts, value = self.htf[name]
        k = int(np.searchsorted(close_ts, decision_ts.to_datetime64(), side="right")) - 1
        return float(value[k]) if k >= 0 else float("nan")


def _htf_trend(
    frame: pd.DataFrame, tf: pd.Timedelta, p: StrategyParams
) -> tuple[np.ndarray, np.ndarray]:
    h, lo, c = (frame[k].to_numpy(float) for k in ("high", "low", "close"))
    ema = pd.Series(c).ewm(span=HTF_EMA, adjust=False).mean().to_numpy()
    value = (c - ema) / atr(h, lo, c, p.atr_period)
    close_ts = (frame["ts_utc"] + tf).to_numpy(dtype="datetime64[ns]")
    return close_ts, value


def features(s: Setup, ctx: Context, costs: CostParams) -> dict[str, float]:
    """The feature row of one setup that reached a trade plan."""
    sign = 1.0 if s.direction == "buy" else -1.0
    j = s.choch_idx
    a = ctx.atr[j]
    close = ctx.close[j]
    decision = ctx.ts.iloc[j] + ctx.tf
    risk = abs(s.entry - s.sl)
    pd_target, pd_back = (ctx.pdh[j], ctx.pdl[j]) if sign > 0 else (ctx.pdl[j], ctx.pdh[j])
    minutes = ctx.ny_minutes[j]
    return {
        "r_multiple": s.r_multiple,
        "risk_atr": risk / a,
        "fvg_atr": (s.fvg_high - s.fvg_low) / a,
        "sweep_depth_atr": abs(s.level.price - s.extreme) / a,
        "choch_disp_atr": sign * (close - s.ref_price) / a,
        "entry_dist_atr": sign * (close - s.entry) / a,
        "bars_sweep_to_choch": j - s.sweep_idx,
        "fvg_bars_before_choch": j - s.fvg_idx,
        "trend_1h": sign * ctx.trend("1h", decision),
        "trend_4h": sign * ctx.trend("4h", decision),
        "atr_ratio_20d": a / ctx.atr_median[j],
        "pd_room_atr": sign * (pd_target - close) / a,
        "pd_back_atr": sign * (close - pd_back) / a,
        # New York sessions by the CHoCH bar's open: Asia 18:00-02:00, London 02:00-08:00,
        # New York 08:00-17:00.
        "session_asia": float(minutes >= 18 * 60 or minutes < 2 * 60),
        "session_london": float(2 * 60 <= minutes < 8 * 60),
        "session_ny": float(8 * 60 <= minutes < 17 * 60),
        "level_htf": float(s.level.source in ("1h", "4h")),
        "level_pd": float(s.level.source == "pd"),
        "is_buy": float(sign > 0),
        "spread_rel": ctx.spread[j] / ctx.spread_median[j] if ctx.spread_median[j] > 0 else np.nan,
        "cost_r": costs.round_trip(s.spread) / risk,
    }


def build(
    bars: pd.DataFrame,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
    params: StrategyParams = CURRENT,
    costs: CostParams | None = None,
) -> pd.DataFrame:
    """Rows for every CLOSED setup in ``bars``: meta columns, the label ``y`` and ``FEATURES``."""
    costs = costs or CostParams()
    bars = bars.reset_index(drop=True)
    setups = [s for s in run(bars, h1, h4, params, costs) if s.state == "CLOSED"]
    ctx = Context(bars, h1, h4, params)
    rows = []
    for s in setups:
        decision = ctx.ts.iloc[s.choch_idx] + ctx.tf
        rows.append(
            {
                "setup_id": s.setup_id,
                "direction": s.direction,
                "decision_ts": decision,
                "exit_ts": ctx.ts.iloc[s.exit_idx] + ctx.tf,
                "y": int(s.outcome == "tp"),
                "outcome": s.outcome,
                "realized_r": s.realized_r,
                "net_r": s.net_r,
                **features(s, ctx, costs),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["year"] = df["decision_ts"].dt.year
    df["period"] = np.where(df["decision_ts"] < DEV_END, "development", "walk_forward")
    return df.sort_values("decision_ts").reset_index(drop=True)


def render(df: pd.DataFrame) -> str:
    dev = df[df["period"] == "development"]
    counts = df.groupby("year").size()
    lines = [
        f"# Phase 3 — labelled dataset ({CURRENT_NAME})",
        "",
        "_Generated by `python -m app.ml.dataset`. One row per closed setup before the lockbox. "
        "Features and labels are described on the development period (2012–2017) only; "
        "walk-forward rows are counted, not described._",
        "",
        f"Rows: **{len(df)}** ({len(dev)} development, {len(df) - len(dev)} walk-forward).",
        "",
        "| Year | Rows |",
        "| --- | --- |",
        *[f"| {y} | {n} |" for y, n in counts.items()],
        "",
        f"Development label rate (TP before SL): {dev['y'].mean():.1%}.",
        "",
        "## Features on the development period",
        "",
        "| Feature | Missing | Mean | 10% | Median | 90% |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for f in FEATURES:
        x = dev[f]
        q = x.quantile([0.1, 0.5, 0.9])
        lines.append(
            f"| {f} | {int(x.isna().sum())} | {x.mean():.3f} | {q[0.1]:.3f} | {q[0.5]:.3f} | "
            f"{q[0.9]:.3f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    tf = f"{CURRENT.entry_tf_minutes}m"
    bars, h1, h4 = (pd.read_parquet(DATA_DIR / f"{t}.parquet") for t in (tf, "1h", "4h"))
    bars = bars[bars["ts_utc"] < LOCKBOX_START]
    df = build(bars, h1, h4)
    df.to_parquet(DATASET, index=False)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "dataset.md").write_text(render(df), encoding="utf-8")
    print(f"wrote {len(df)} rows to {DATASET}")


if __name__ == "__main__":
    main()
