"""Rules-only report for the Sweep -> CHoCH -> FVG strategy.

    python -m app.smc.report                                      # docs/phase2/rules_only.*
    python -m app.smc.report --variant A --set extend_sweep=true  # docs/phase2/variant_A.*

Every setup also goes to an untracked CSV next to the research store.

Performance (win rate, R) is computed on the development period only (2012-2017). For the
walk-forward period only setup counts are reported, so it stays unseen for tuning. The lockbox
(2024-07 onward) is never loaded."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.smc.engine import Setup, run
from app.smc.params import CostParams, StrategyParams

SERVICE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = SERVICE_DIR / "data" / "processed" / "XAUUSD"
OUT_DIR = SERVICE_DIR / "docs" / "phase2"

DEV_END = pd.Timestamp("2018-01-01", tz="UTC")
LOCKBOX_START = pd.Timestamp("2024-07-01", tz="UTC")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def bootstrap_mean(x: np.ndarray, n_boot: int = 10_000, seed: int = 0) -> tuple[float, float]:
    if len(x) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    return (float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)))


def setups_frame(setups: list[Setup], ts: pd.Series) -> pd.DataFrame:
    def at(i):
        return None if i is None else ts.iloc[i]

    rows = []
    for s in setups:
        rows.append(
            {
                "setup_id": s.setup_id,
                "direction": s.direction,
                "state": s.state,
                "reason": s.reason,
                "level_source": s.level.source,
                "level_price": s.level.price,
                "sweep_ts": at(s.sweep_idx),
                "extreme": s.extreme,
                "choch_ts": at(s.choch_idx),
                "fvg_low": s.fvg_low,
                "fvg_high": s.fvg_high,
                "entry": s.entry,
                "sl": s.sl,
                "tp": s.tp,
                "tp_source": s.tp_source,
                "r_multiple": s.r_multiple,
                "spread": s.spread,
                "atr": s.atr,
                "fill_ts": at(s.fill_idx),
                "exit_ts": at(s.exit_idx),
                "outcome": s.outcome,
                "realized_r": s.realized_r,
                "net_r": s.net_r,
            }
        )
    return pd.DataFrame(rows)


def performance(df: pd.DataFrame) -> dict:
    closed = df[df["state"] == "CLOSED"]
    n = len(closed)
    wins = int((closed["outcome"] == "tp").sum())
    net = closed["net_r"].to_numpy(float)
    gross = closed["realized_r"].to_numpy(float)
    breakeven = (1 / (1 + closed["r_multiple"])).mean() if n else float("nan")
    return {
        "trades": n,
        "wins": wins,
        "win_rate": wins / n if n else float("nan"),
        "win_rate_ci95": wilson(wins, n),
        "breakeven_win_rate_before_costs": float(breakeven),
        "mean_r_multiple": float(closed["r_multiple"].mean()) if n else float("nan"),
        "mean_gross_r": float(gross.mean()) if n else float("nan"),
        "mean_net_r": float(net.mean()) if n else float("nan"),
        "mean_net_r_ci95": bootstrap_mean(net),
        "total_net_r": float(net.sum()),
        "outcomes": closed["outcome"].value_counts().to_dict(),
    }


def build(params: StrategyParams, costs: CostParams) -> tuple[pd.DataFrame, dict]:
    m15, h1, h4 = (pd.read_parquet(DATA_DIR / f"{tf}.parquet") for tf in ("15m", "1h", "4h"))
    m15 = m15[m15["ts_utc"] < LOCKBOX_START].reset_index(drop=True)
    setups = run(m15, h1, h4, params, costs)
    df = setups_frame(setups, m15["ts_utc"])
    df["year"] = df["sweep_ts"].dt.year
    df["period"] = np.where(df["sweep_ts"] < DEV_END, "development", "walk_forward")

    dev = df[df["period"] == "development"]
    years = sorted(df["year"].unique())
    counts_by_year = {
        int(y): {
            "setups": int((df["year"] == y).sum()),
            "armed": int(((df["year"] == y) & df["entry"].notna() & df["tp"].notna()).sum()),
            "closed": int(((df["year"] == y) & (df["state"] == "CLOSED")).sum()),
        }
        for y in years
    }
    summary = {
        "params": params.as_dict(),
        "costs": costs.as_dict(),
        "data_end": str(LOCKBOX_START),
        "states_all_periods": df["state"].value_counts().to_dict(),
        "end_reasons_all_periods": df["reason"].value_counts().to_dict(),
        "counts_by_year": counts_by_year,
        "closed_trades_pre_lockbox": int((df["state"] == "CLOSED").sum()),
        "development": {
            "all": performance(dev),
            "buy": performance(dev[dev["direction"] == "buy"]),
            "sell": performance(dev[dev["direction"] == "sell"]),
            "by_year": {int(y): performance(g) for y, g in dev.groupby("year")},
            "by_level_source": {k: performance(g) for k, g in dev.groupby("level_source")},
        },
    }
    return df, summary


def _fmt(x, digits=2):
    if isinstance(x, float) and np.isnan(x):
        return "n/a"
    return f"{x:.{digits}f}"


def _pct(x):
    return f"{_fmt(100 * x, 1)}%"


def render(summary: dict) -> str:
    d = summary["development"]
    a = d["all"]
    variant = summary.get("variant", "baseline")
    lines = [
        f"# Phase 2 — rules-only results (Sweep → CHoCH → FVG), variant {variant}",
        "",
        "_Generated by `python -m app.smc.report`. Performance is on the development period "
        "(2012–2017) only. The walk-forward period shows counts only, and the lockbox "
        "(2024-07 onward) is not loaded._",
        "",
        "## Development period, all setups that traded",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Closed trades | {a['trades']} |",
        f"| Win rate | {_pct(a['win_rate'])} "
        f"(95% CI {_pct(a['win_rate_ci95'][0])}–{_pct(a['win_rate_ci95'][1])}) |",
        f"| Break-even win rate before costs | {_pct(a['breakeven_win_rate_before_costs'])} |",
        f"| Mean R multiple of the target | {_fmt(a['mean_r_multiple'])} |",
        f"| Mean gross R per trade | {_fmt(a['mean_gross_r'], 3)} |",
        f"| Mean net R per trade | {_fmt(a['mean_net_r'], 3)} "
        f"(95% CI {_fmt(a['mean_net_r_ci95'][0], 3)} to {_fmt(a['mean_net_r_ci95'][1], 3)}) |",
        f"| Total net R | {_fmt(a['total_net_r'], 1)} |",
        f"| Outcomes | {a['outcomes']} |",
        "",
        "## Development period by direction, year and level source",
        "",
        "| Slice | Trades | Win rate | Mean net R |",
        "| --- | --- | --- | --- |",
    ]
    slices = [("buy", d["buy"]), ("sell", d["sell"])]
    slices += [(str(y), p) for y, p in d["by_year"].items()]
    slices += [(f"level {k}", p) for k, p in d["by_level_source"].items()]
    for name, p in slices:
        lines.append(
            f"| {name} | {p['trades']} | {_pct(p['win_rate'])} | {_fmt(p['mean_net_r'], 3)} |"
        )
    lines += [
        "",
        "## Setup counts by year (all periods before the lockbox)",
        "",
        "| Year | Setups detected | Reached entry/SL/TP | Closed trades |",
        "| --- | --- | --- | --- |",
    ]
    for y, c in summary["counts_by_year"].items():
        lines.append(f"| {y} | {c['setups']} | {c['armed']} | {c['closed']} |")
    lines += [
        "",
        f"Closed trades before the lockbox: **{summary['closed_trades_pre_lockbox']}**.",
        "",
        "## Why setups ended without a trade (all periods)",
        "",
        "| Reason | Count |",
        "| --- | --- |",
    ]
    for r, c in summary["end_reasons_all_periods"].items():
        lines.append(f"| {r} | {c} |")
    lines += ["", "## Parameters", "", "```json", json.dumps(summary["params"], indent=2), "```"]
    return "\n".join(lines) + "\n"


def _overrides(pairs: list[str]) -> dict:
    """Parse ``key=value`` pairs into typed ``StrategyParams`` fields."""
    defaults = StrategyParams()
    out = {}
    for pair in pairs:
        key, _, raw = pair.partition("=")
        if not hasattr(defaults, key):
            raise SystemExit(f"unknown parameter: {key}")
        default = getattr(defaults, key)
        if isinstance(default, bool):
            out[key] = raw.lower() in ("1", "true", "yes")
        else:
            out[key] = type(default)(raw)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--variant", default="baseline", help="name used in the output file names")
    ap.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE", help="override a parameter"
    )
    args = ap.parse_args(argv)
    params = StrategyParams(**_overrides(args.set))
    df, summary = build(params, CostParams())
    summary["variant"] = args.variant
    stem = "rules_only" if args.variant == "baseline" else f"variant_{args.variant}"
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_DIR / f"phase2_setups_{args.variant}.csv", index=False)
    text = json.dumps(summary, indent=2, default=str) + "\n"
    (args.out / f"{stem}.json").write_text(text, encoding="utf-8")
    (args.out / f"{stem}.md").write_text(render(summary), encoding="utf-8")
    print(f"wrote {args.out / stem}")


if __name__ == "__main__":
    main()
