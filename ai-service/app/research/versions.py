"""Before / after: L1 against L1-M, each with its matched random entries (trial 6).

    python -m app research versions        # docs/phase4/L1-M.md

Both versions run on the same frames (2012-01-01 to the end of the walk-forward period,
2024-07-01; the secondary holdout and the lockbox are not loaded) and are reported for the
development period (decisions before 2018) and the walk-forward period (2018 to 2024-06)
separately. E1 is the strategy; E0 its matched random entries (``baselines``: same instrument,
year, New York hour, risk in ATR, TP rule and costs; seed and replications fixed there). For
L1-M, each random trade is managed by ``managed.manage`` with the instrument's real signal stream,
so it is closed by a real opposite signal and extended by a real same-direction one, like E1.
Swap is not modelled: rollovers are reported. Outputs: the report and
``data/processed/p4_versions_{e1,e0}.parquet`` (untracked)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import instruments, splits, strategy
from app.data.importer import DEFAULT_OUT as STORE
from app.data.sessions import MARKET_TZ
from app.research.baselines import (
    MAX_DRAWS,
    REPS,
    SEED,
    Market,
    block_ci,
    compare,
    e0,
    market,
    week_of,
)
from app.setups.builder import build, target
from app.setups.counts import history_frames
from app.setups.labels import label_all, round_trip
from app.setups.managed import manage, signal_sides, trades
from app.smc.detector import detect

OUT = Path(__file__).resolve().parents[2] / "docs" / "phase4"
SYMBOLS = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD")
GOOD_R = 0.25  # the pre-registered binary threshold (sensitivity only)
COST_MULTIPLES = (0, 1, 2, 3)


def l1_trades(frames: dict, symbol: str, p) -> pd.DataFrame:
    df = label_all(frames, symbol, p)
    df = df[df["state"] == "CLOSED"].reset_index(drop=True)
    inst = instruments()[symbol]
    df.insert(0, "symbol", symbol)
    df["cost_r"] = [round_trip(s, inst) / r for s, r in zip(df["spread"], df["risk"], strict=True)]
    df["slip_r"] = (df["gross_r"] - df["net_r"] - df["cost_r"]).clip(lower=0).round(6)
    return df


def random_managed(
    m: Market, side: np.ndarray, year: int, hour: int, risk_atr: float, rng, p, inst
) -> dict | None:
    """``baselines.random_trade`` with the L1-M management instead of the fixed horizon."""
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
        r = manage(m.bars[direction], j, pl, side, float(m.spread[j]), p, inst)
        if r.state != "CLOSED":
            continue
        return {
            "decision_idx": j,
            "direction": direction,
            "reason": r.reason,
            "y": int(r.reason == "tp"),
            "gross_r": r.gross_r,
            "net_r": r.net_r(),
            "net_r_2x": r.net_r(2),
        }
    return None


def e0_managed(m: Market, side, e1: pd.DataFrame, symbol: str, p, rng, reps: int) -> pd.DataFrame:
    inst = instruments()[symbol]
    hours = pd.DatetimeIndex(e1["decision_utc"]).tz_convert(MARKET_TZ).hour
    rows = []
    for rep in range(reps):
        for (_, t), hour in zip(e1.iterrows(), hours, strict=True):
            r = random_managed(
                m, side, int(t["year"]), int(hour), t["risk"] / t["atr"], rng, p, inst
            )
            if r is not None:
                rows.append({"rep": rep, "setup_id": t["setup_id"], "symbol": symbol, **r})
    return pd.DataFrame(rows)


def drawdown(df: pd.DataFrame) -> float:
    eq = df.sort_values("exit_utc")["net_r"].cumsum().to_numpy()
    return float((np.maximum.accumulate(np.r_[0.0, eq]) - np.r_[0.0, eq]).max())


def _r(x: float) -> str:
    return f"{x:+.3f}"


def headline(name: str, df: pd.DataFrame, rng, e1: bool) -> str:
    lo, hi = block_ci(df["net_r"].to_numpy(float), week_of(df["decision_utc"]), rng)
    held = f"{df['bars_held'].median():.0f}" if "bars_held" in df else "-"
    dd = f"{drawdown(df):.1f}" if e1 else "-"
    return (
        f"| {name} | {len(df)} | {_r(df['net_r'].mean())} | {_r(lo)} to {_r(hi)} |"
        f" {df['net_r'].sum():+.1f} | {dd} | {held} | {df['y'].mean():.1%} |"
        f" {(df['net_r'] > 0).mean():.1%} | {(df['net_r'] >= GOOD_R).mean():.1%} |"
    )


def section(title: str, e1: dict, e0_: dict, rng) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Set | Trades | Mean net R | 95% (weekly block) | Total R | Max drawdown R |"
        " Median bars held | TP | Net R > 0 | Net R >= +0.25R |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for v in e1:
        lines.append(headline(f"{v} E1", e1[v], rng, True))
        lines.append(headline(f"{v} E0 (all replications)", _timed(e0_[v], e1[v]), rng, False))
    lines += [
        "",
        "| Version | E1 - E0 (paired) | 95% (weekly block) | One-sided p |",
        "| --- | --- | --- | --- |",
    ]
    for v in e1:
        c = compare(e1[v], e0_[v], rng)
        lines.append(
            f"| {v} | {_r(c['diff'])} | {_r(c['diff_ci'][0])} to {_r(c['diff_ci'][1])} |"
            f" {c['p']:.3f} |"
        )
    lines += [
        "",
        "Exit reasons (E1):",
        "",
        "| Version | " + " | ".join(REASONS) + " |",
        "|" + " --- |" * (len(REASONS) + 1),
    ]
    for v, df in e1.items():
        share = df["reason"].value_counts(normalize=True)
        lines.append(f"| {v} | " + " | ".join(f"{share.get(k, 0):.0%}" for k in REASONS) + " |")
    lines += [
        "",
        "Mean net R of E1 by exit reason:",
        "",
        "| Version | " + " | ".join(REASONS) + " |",
        "|" + " --- |" * (len(REASONS) + 1),
    ]
    for v, df in e1.items():
        mean = df.groupby("reason")["net_r"].mean()
        lines.append(
            f"| {v} | " + " | ".join(_r(mean[k]) if k in mean else "-" for k in REASONS) + " |"
        )
    lines += [
        "",
        "Cost sensitivity (E1 mean net R; 0x = gross):",
        "",
        "| Version | " + " | ".join(f"{k}x" for k in COST_MULTIPLES) + " |",
        "|" + " --- |" * (len(COST_MULTIPLES) + 1),
    ]
    for v, df in e1.items():
        vals = [(df["gross_r"] - k * (df["cost_r"] + df["slip_r"])).mean() for k in COST_MULTIPLES]
        lines.append(f"| {v} | " + " | ".join(_r(x) for x in vals) + " |")
    lines.append("")
    return lines


REASONS = ["tp", "sl", "opposite", "timeout", "max_hold"]


def _timed(e0_df: pd.DataFrame, e1_df: pd.DataFrame) -> pd.DataFrame:
    """E0 rows with the decision time of the E1 trade they are matched to (for the weeks)."""
    t = e1_df.set_index(["symbol", "setup_id"])["decision_utc"]
    return e0_df.join(t, on=["symbol", "setup_id"])


def breakdown(df: pd.DataFrame, by: str) -> list[str]:
    lines = [f"| {by.capitalize()} | Trades | Mean net R | Total R |", "| --- | --- | --- | --- |"]
    for k, g in df.groupby(by):
        lines.append(f"| {k} | {len(g)} | {_r(g['net_r'].mean())} | {g['net_r'].sum():+.1f} |")
    return lines


def render(e1: dict, e0_: dict, rng) -> str:
    wf0 = pd.Timestamp(splits().walk_forward[0], tz="UTC")
    periods = {
        "Development period (2012-2017)": lambda d: d["decision_utc"] < wf0,
        "Walk-forward period (2018 to 2024-06)": lambda d: d["decision_utc"] >= wf0,
    }
    lines = [
        "# P4: L1 against L1-M (signal-based position management), before and after",
        "",
        "_Generated by `python -m app research versions`; rules in"
        " `docs/MARKET_STRUCTURE_DEFINITIONS.md` (L1-M), registered before this run (trial 6 in"
        f" `docs/phase3/TRIALS.md`). Seed {SEED}, {REPS} E0 replications. Net R includes the"
        " round-trip cost and SL slippage; swap is not modelled. Secondary holdout and lockbox"
        " not loaded._",
        "",
    ]
    for title, sel in periods.items():
        e1p = {v: df[sel(df)] for v, df in e1.items()}
        keys = {v: pd.MultiIndex.from_frame(e1p[v][["symbol", "setup_id"]]) for v in e1p}
        e0p = {
            v: df[pd.MultiIndex.from_frame(df[["symbol", "setup_id"]]).isin(keys[v])]
            for v, df in e0_.items()
        }
        lines += section(title, e1p, e0p, rng)
    lm = e1["L1-M"]
    lines += [
        "## L1-M details (both periods)",
        "",
        f"Trades extended by a same-direction signal: {(lm['extensions'] > 0).sum()} of {len(lm)}"
        f" ({lm['extensions'].sum()} extensions); closed by an opposite signal:"
        f" {(lm['reason'] == 'opposite').sum()}. Rollovers (17:00 New York day ends) per trade:"
        f" mean {lm['rollovers'].mean():.2f}, median {lm['rollovers'].median():.0f}; trades held"
        f" over at least one: {(lm['rollovers'] > 0).mean():.0%} (swap not charged).",
        "",
        "By instrument (L1-M E1):",
        "",
        *breakdown(lm, "symbol"),
        "",
        "By year (L1-M E1):",
        "",
        *breakdown(lm, "year"),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research versions")
    ap.add_argument("--before", default="L1")
    ap.add_argument("--after", default="L1-M")
    ap.add_argument("--symbol", action="append")
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    pb, pa = strategy(args.before), strategy(args.after)
    end = pd.Timestamp(splits().walk_forward[1], tz="UTC")
    rng = np.random.default_rng(SEED)
    e1 = {args.before: [], args.after: []}
    e0_ = {args.before: [], args.after: []}
    for s in args.symbol or list(SYMBOLS):
        frames = history_frames(s, pa, args.store, end)
        if frames[pa.entry_timeframe].empty:
            continue
        before = l1_trades(frames, s, pb)
        after = trades(frames, s, pa)
        after = after[after["state"] == "CLOSED"].reset_index(drop=True)
        m = market(frames, pa)
        side = signal_sides(len(frames[pa.entry_timeframe]), build(frames, detect(frames, pa), pa))
        e1[args.before].append(before)
        e1[args.after].append(after)
        e0_[args.before].append(e0(m, before, s, pb, rng, args.reps))
        e0_[args.after].append(e0_managed(m, side, after, s, pa, rng, args.reps))
        print(
            f"{s}: {args.before} {len(before)}, {args.after} {len(after)} trades", file=sys.stderr
        )
    e1 = {v: pd.concat(x, ignore_index=True) for v, x in e1.items()}
    e0_ = {v: pd.concat(x, ignore_index=True) for v, x in e0_.items()}
    for name, d in (("e1", e1), ("e0", e0_)):
        pd.concat([df.assign(version=v) for v, df in d.items()], ignore_index=True).to_parquet(
            args.store / f"p4_versions_{name}.parquet", index=False
        )
    args.out.mkdir(parents=True, exist_ok=True)
    report = render(e1, e0_, rng)
    (args.out / f"{args.after}.md").write_text(report, encoding="utf-8", newline="\n")
    print(report)
    return 0
