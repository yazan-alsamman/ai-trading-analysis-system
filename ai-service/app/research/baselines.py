"""P3 task 4: E0 (random entries) against E1 (rules only), development period (H1).

    python -m app research baselines                   # E1 = L1, E1s = V5-S, every instrument
    python -m app research baselines --horizon 96      # a trial horizon (docs/phase3/TRIALS.md)

Writes ``docs/phase3/baselines.md`` and ``data/processed/p3_baselines_{e1,e0}.parquet``
(one row per trade, untracked).

**E1** is the adopted rule set (L1) traded by the rules alone: every labelled (``CLOSED``)
setup of the development period, pooled over the instruments that have development data.
**E1s** is the strict rule set (V5-S), reported the same way.

**E0** answers "is it the pattern, or only the trade mechanics?". For each E1 trade it opens a
random trade that keeps everything except the pattern (Fadi, 2026-10-22, matched design):

* the same instrument, year and New York hour, on a random bar of the same entry frame (closed
  hours already removed), far enough from the end for the full horizon;
* a random direction (a fair coin);
* the same risk in ATR units (the E1 risk over its sweep ATR, times the ATR of the random bar);
  market entry at the bar's close, SL that far away;
* the same TP rule (``builder.target``: nearest opposite active level with R in [1.5, 4], else
  rejected) with the level book as it stood after that bar; a rejected draw is redrawn;
* the same labels and costs (``labels.resolve``, the bar's spread).

E0 is drawn ``REPS`` times. Reported: the E0 mean of each replication (its spread is the range
of a random strategy with these mechanics), the one-sided p-value of the E1 mean against them,
and the paired difference E1 - E0 (each E1 trade minus the mean of its own random trades) with a
weekly block bootstrap 95% interval (trades in the same week, on any instrument, resampled
together). Seeds are fixed here before any run. Performance of the development period only."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Strategy, instruments, strategy
from app.data.importer import DEFAULT_OUT as STORE
from app.data.sessions import MARKET_TZ
from app.setups.builder import OUT_DIR, target
from app.setups.labels import Bars, label_all, resolve
from app.smc.detector import development_frames, levels_for
from app.smc.primitives import LevelBook, atr

SEED = 20261023  # fixed on 2026-10-22, before the first run
REPS = 200
BOOT = 2000
MAX_DRAWS = 50  # redraws per random trade before giving up (counted in the report)


@dataclass
class Market:
    """What a random entry needs from one instrument's entry frame."""

    entry: pd.DataFrame
    atr: np.ndarray
    spread: np.ndarray
    close: np.ndarray
    snapshot: dict[int, dict[str, tuple]]  # active levels after each candidate bar
    pool: dict[tuple[int, int], np.ndarray]  # (year, New York hour) -> candidate bars
    bars: dict[str, Bars]


def market(frames: dict[str, pd.DataFrame], p: Strategy) -> Market:
    entry = frames[p.entry_timeframe]
    h, lo, c = (entry[k].to_numpy(float) for k in ("high", "low", "close"))
    a = atr(h, lo, c, p.atr_period)
    col = f"spread_{p.spread_stat}"
    spread = entry[col].fillna(0.0).to_numpy(float) if col in entry else np.zeros(len(entry))
    n = len(entry)
    ok = ~np.isnan(a) & (np.arange(n) + p.horizon_bars < n)
    ny = pd.DatetimeIndex(entry["ts_utc"]).tz_convert(MARKET_TZ)
    keys = pd.DataFrame({"year": entry["ts_utc"].dt.year, "hour": ny.hour, "j": np.arange(n)})
    keys = keys[ok]
    pool = {k: g["j"].to_numpy() for k, g in keys.groupby(["year", "hour"])}
    book = LevelBook(entry, levels_for(frames, p), p.max_age_days)
    snapshot = {}
    for j in range(n):
        book.step(j)
        if ok[j]:
            snapshot[j] = {s: tuple(v) for s, v in book.active.items()}
    return Market(
        entry, a, spread, c, snapshot, pool, {d: Bars.of(entry, d) for d in ("buy", "sell")}
    )


def random_trade(
    m: Market, year: int, hour: int, risk_atr: float, rng: np.random.Generator, p, inst
) -> dict | None:
    cands = m.pool.get((year, hour))
    if cands is None:
        return None
    for _ in range(MAX_DRAWS):
        j = int(cands[rng.integers(len(cands))])
        direction = "buy" if rng.random() < 0.5 else "sell"
        sign = 1.0 if direction == "buy" else -1.0
        entry = float(m.close[j])
        risk = risk_atr * float(m.atr[j])
        opposite = m.snapshot[j]["high" if sign > 0 else "low"]
        pl = target(direction, entry, entry - sign * risk, risk, list(opposite), p)
        if pl.state != "ARMED":
            continue
        lab = resolve(m.bars[direction], j, pl, float(m.spread[j]), p, inst)
        if lab.state != "CLOSED":
            continue
        return {
            "decision_idx": j,
            "direction": direction,
            "y": lab.y,
            "gross_r": lab.gross_r,
            "net_r": lab.net_r,
            "net_r_2x": lab.net_r_2x,
        }
    return None


def e0(m: Market, e1: pd.DataFrame, symbol: str, p: Strategy, rng, reps: int) -> pd.DataFrame:
    inst = instruments()[symbol]
    hours = pd.DatetimeIndex(e1["decision_utc"]).tz_convert(MARKET_TZ).hour
    rows = []
    for rep in range(reps):
        for (_, t), hour in zip(e1.iterrows(), hours, strict=True):
            r = random_trade(m, int(t["year"]), int(hour), t["risk"] / t["atr"], rng, p, inst)
            if r is not None:
                rows.append({"rep": rep, "setup_id": t["setup_id"], "symbol": symbol, **r})
    return pd.DataFrame(rows)


def week_of(ts: pd.Series) -> np.ndarray:
    return pd.DatetimeIndex(ts).tz_convert(MARKET_TZ).tz_localize(None).to_period("W").astype(str)


def block_ci(values: np.ndarray, weeks: np.ndarray, rng, boot: int = BOOT) -> tuple[float, float]:
    """95% interval of the mean by a weekly block bootstrap (whole weeks resampled)."""
    df = pd.DataFrame({"v": values, "w": weeks}).groupby("w")["v"].agg(["sum", "count"])
    s, c = df["sum"].to_numpy(), df["count"].to_numpy()
    idx = rng.integers(0, len(df), size=(boot, len(df)))
    means = s[idx].sum(axis=1) / c[idx].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def summary(df: pd.DataFrame, rng) -> dict:
    lo, hi = block_ci(df["net_r"].to_numpy(float), week_of(df["decision_utc"]), rng)
    return {
        "trades": len(df),
        "tp": df["y"].mean(),
        "gross": df["gross_r"].mean(),
        "net": df["net_r"].mean(),
        "net_2x": df["net_r_2x"].mean(),
        "ci": (lo, hi),
    }


def compare(e1: pd.DataFrame, e0_df: pd.DataFrame, rng) -> dict:
    """E1 against its own random trades."""
    rep_means = e0_df.groupby("rep")["net_r"].mean().to_numpy()
    own = e0_df.groupby(["symbol", "setup_id"])["net_r"].mean()
    paired = e1.join(own.rename("e0"), on=["symbol", "setup_id"]).dropna(subset=["e0"])
    diff = (paired["net_r"] - paired["e0"]).to_numpy(float)
    lo, hi = block_ci(diff, week_of(paired["decision_utc"]), rng)
    e1_mean = e1["net_r"].mean()
    return {
        "e0_mean": float(rep_means.mean()),
        "e0_range": tuple(np.percentile(rep_means, [2.5, 97.5])),
        "e0_tp": float(e0_df["y"].mean()),
        "p": (1 + int((rep_means >= e1_mean).sum())) / (1 + len(rep_means)),
        "diff": float(diff.mean()),
        "diff_ci": (lo, hi),
    }


def _r(x: float) -> str:
    return f"{x:+.3f}"


def _row(name: str, s: dict) -> str:
    lo, hi = s["ci"]
    return (
        f"| {name} | {s['trades']} | {s['tp']:.1%} | {_r(s['gross'])} | {_r(s['net'])} |"
        f" {_r(lo)} to {_r(hi)} | {_r(s['net_2x'])} |"
    )


HEAD = [
    "| Set | Trades | TP | Mean R gross | Mean R net | Net 95% (weekly block) | Net at 2x costs |",
    "| --- | --- | --- | --- | --- | --- | --- |",
]


def render(
    e1: pd.DataFrame, e0_df: pd.DataFrame, e1s: pd.DataFrame, rng, missing: int, horizon: int
) -> str:
    c = compare(e1, e0_df, rng)
    xau = e1[e1["symbol"] == "XAUUSD"]
    cx = compare(xau, e0_df[e0_df["symbol"] == "XAUUSD"], rng)
    lines = [
        "# P3: E0 (random entries) against E1 (rules only)",
        "",
        "_Generated by `python -m app research baselines`; design in `app/research/baselines.py`."
        f" Development period (2012-2017) only. Seed {SEED}, {REPS} E0 replications, {BOOT}"
        f" bootstrap resamples. Horizon {horizon} bars. R is per trade after costs (net) unless"
        " marked gross._",
        "",
        "## E1 against E0 (H1)",
        "",
        "| | All instruments | XAUUSD |",
        "| --- | --- | --- |",
        f"| E1 mean net R | {_r(e1['net_r'].mean())} | {_r(xau['net_r'].mean())} |",
        f"| E0 mean net R (mean of {REPS} replications) | {_r(c['e0_mean'])} |"
        f" {_r(cx['e0_mean'])} |",
        f"| E0 replications, 95% range | {_r(c['e0_range'][0])} to {_r(c['e0_range'][1])} |"
        f" {_r(cx['e0_range'][0])} to {_r(cx['e0_range'][1])} |",
        f"| E1 - E0, paired | {_r(c['diff'])} | {_r(cx['diff'])} |",
        f"| E1 - E0, 95% (weekly block) | {_r(c['diff_ci'][0])} to {_r(c['diff_ci'][1])} |"
        f" {_r(cx['diff_ci'][0])} to {_r(cx['diff_ci'][1])} |",
        f"| One-sided p (E0 replications >= E1) | {c['p']:.3f} | {cx['p']:.3f} |",
        f"| TP rate E1 / E0 | {e1['y'].mean():.1%} / {c['e0_tp']:.1%} |"
        f" {xau['y'].mean():.1%} / {cx['e0_tp']:.1%} |",
        "",
        "## Rules only",
        "",
        *HEAD,
        _row("E1 (L1), all", summary(e1, rng)),
        *[_row(f"E1 (L1), {s}", summary(g, rng)) for s, g in e1.groupby("symbol")],
        _row(
            "E1 without same-bar sweep and CHoCH",
            summary(e1[e1["bars_sweep_to_choch"] > 0], rng),
        ),
        _row("E1s (V5-S), all", summary(e1s, rng)),
        *[_row(f"E1s (V5-S), {s}", summary(g, rng)) for s, g in e1s.groupby("symbol")],
        "",
        "E1 by outcome (TP, SL, or the close of the horizon bar):",
        "",
        "| Outcome | Trades | Share | Mean R net |",
        "| --- | --- | --- | --- |",
        *[
            f"| {k} | {len(g)} | {len(g) / len(e1):.0%} | {_r(g['net_r'].mean())} |"
            for k, g in e1.groupby("reason")
        ],
        "",
        "E1 per year (net R):",
        "",
        "| Year | Trades | Mean R net | Total R net |",
        "| --- | --- | --- | --- |",
        *[
            f"| {y} | {len(g)} | {_r(g['net_r'].mean())} | {g['net_r'].sum():+.1f} |"
            for y, g in e1.groupby("year")
        ],
        "",
        f"E0 trades: {len(e0_df)} ({missing} E1 trades had no acceptable random draw in"
        f" {MAX_DRAWS} tries and are left out of the paired difference).",
        "",
    ]
    return "\n".join(lines)


def labelled(symbol: str, p: Strategy, store: Path) -> tuple[dict, pd.DataFrame]:
    frames = development_frames(symbol, store, p)
    if frames[p.entry_timeframe].empty:
        return frames, pd.DataFrame()
    df = label_all(frames, symbol, p)
    if df.empty:
        return frames, df
    df = df[df["state"] == "CLOSED"].reset_index(drop=True)
    df.insert(0, "symbol", symbol)
    return frames, df


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research baselines")
    ap.add_argument("command", choices=["baselines"])
    ap.add_argument("--rules", default="L1")
    ap.add_argument("--strict", default="V5-S")
    ap.add_argument("--symbol", action="append")
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--horizon", type=int, help="horizon in entry bars (default: strategy.toml)")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    p, ps = strategy(args.rules), strategy(args.strict)
    if args.horizon:
        p, ps = replace(p, horizon_bars=args.horizon), replace(ps, horizon_bars=args.horizon)
    tag = "" if args.horizon is None else f"_h{args.horizon}"
    symbols = args.symbol or sorted(
        x.parent.name for x in args.store.glob("*/import.json") if x.parent.name in instruments()
    )
    rng = np.random.default_rng(SEED)
    e1s_parts, e1_parts, e0_parts = [], [], []
    for s in symbols:
        frames, e1 = labelled(s, p, args.store)
        if e1.empty:
            print(f"{s}: no development data or setups", file=sys.stderr)
            continue
        e1_parts.append(e1)
        e0_parts.append(e0(market(frames, p), e1, s, p, rng, args.reps))
        e1s_parts.append(labelled(s, ps, args.store)[1])
        print(f"{s}: E1 {len(e1)} trades", file=sys.stderr)
    if not e1_parts:
        print("no trades", file=sys.stderr)
        return 1
    e1, e0_df = pd.concat(e1_parts, ignore_index=True), pd.concat(e0_parts, ignore_index=True)
    e1s = pd.concat(e1s_parts, ignore_index=True)
    drawn = pd.MultiIndex.from_frame(e0_df[["symbol", "setup_id"]])
    missing = int((~pd.MultiIndex.from_frame(e1[["symbol", "setup_id"]]).isin(drawn)).sum())
    e1.to_parquet(args.store / f"p3_baselines_e1{tag}.parquet", index=False)
    e0_df.to_parquet(args.store / f"p3_baselines_e0{tag}.parquet", index=False)
    args.out.mkdir(parents=True, exist_ok=True)
    report = render(e1, e0_df, e1s, rng, missing, p.horizon_bars)
    (args.out / f"baselines{tag}.md").write_text(report, encoding="utf-8", newline="\n")
    print(report)
    return 0
