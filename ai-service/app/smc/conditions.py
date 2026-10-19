"""Automated check of the five written conditions for every planned setup.

    python -m app.smc.conditions        # docs/phase2/conditions.{md,json}

The engine decides; this module re-derives each condition from the raw bars and the setup's recorded
bar indices, without reusing the engine's decision code, and reports any setup that breaks one. It
measures whether the implementation matches the written definition (spec, Strategy rules 1-8 with
the v2 FVG amendment). Whether the pattern is a sound trading pattern is the human review's job."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.smc.engine import Setup, run
from app.smc.params import FROZEN_V2, CostParams, StrategyParams
from app.smc.primitives import atr
from app.smc.report import DATA_DIR, DEV_END, OUT_DIR

CONDITIONS = ("level", "sweep", "choch", "fvg", "plan")
TOL = 1e-6


def _frame(bars: pd.DataFrame, direction: str) -> tuple[np.ndarray, ...]:
    """OHLC in a frame where every setup is a buy (sells negated), plus the spread."""
    o, h, lo, c = (bars[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    if direction == "sell":
        o, h, lo, c = -o, -lo, -h, -c
    return o, h, lo, c


_CACHE: dict[tuple[int, str], tuple[np.ndarray, ...]] = {}


def _arrays(bars: pd.DataFrame, direction: str, period: int) -> tuple[np.ndarray, ...]:
    key = (id(bars), direction)
    if key not in _CACHE:
        _, h, lo, c = _frame(bars, direction)
        _CACHE[key] = (h, lo, c, atr(h, lo, c, period))
    return _CACHE[key]


def check(s: Setup, bars: pd.DataFrame, p: StrategyParams) -> dict[str, bool | str]:
    """Each written condition for one setup, re-derived from the bars. Values are True, or a short
    reason it fails."""
    sign = 1.0 if s.direction == "buy" else -1.0
    h, lo, c, atr_all = _arrays(bars, s.direction, p.atr_period)
    spread = bars["spread"].fillna(0.0).to_numpy(float)
    a = atr_all[s.sweep_idx]
    ts = bars["ts_utc"]
    level = sign * s.level.price
    extreme = sign * s.extreme
    out: dict[str, bool | str] = {}

    # 1. Level: available before the sweep and untouched between then and the sweep's first bar.
    avail = int(ts.searchsorted(s.level.available_at))
    first = next((i for i in range(avail, s.sweep_idx + 1) if lo[i] < level), None)
    if avail > s.sweep_idx:
        out["level"] = "level not yet available at the sweep"
    elif first is None or first < s.sweep_idx - 1:
        out["level"] = "level traded through before the sweep"
    else:
        out["level"] = True

    # 2. Sweep: first bar trades through by 0.1-1.5 ATR, the sweep bar closes back, and the extreme
    #    stays within 1.5 ATR of the level.
    depth_first = level - lo[first] if first is not None else np.nan
    depth = level - extreme
    a_first = atr_all[first] if first is not None else np.nan  # ATR known at that bar's close
    if not (p.min_sweep_atr * a_first - TOL <= depth_first <= p.max_sweep_atr * a_first + TOL):
        out["sweep"] = f"first-bar depth {depth_first:.2f} outside 0.1-1.5 ATR"
    elif c[s.sweep_idx] <= level:
        out["sweep"] = "sweep bar did not close back"
    elif depth > p.max_sweep_atr * a + TOL:
        out["sweep"] = f"extreme {depth:.2f} beyond 1.5 ATR"
    elif (
        abs(
            min(lo[s.sweep_idx - 1 if first < s.sweep_idx else s.sweep_idx : s.choch_idx + 1])
            - extreme
        )
        > TOL
    ):
        out["sweep"] = "recorded extreme is not the lowest low before the CHoCH"
    else:
        out["sweep"] = True

    # 3. CHoCH: within the window, closes beyond a confirmed swing that formed before the extreme.
    k = p.k_ltf
    r = s.ref_idx
    is_swing = all(h[r] > h[r - d] and h[r] > h[r + d] for d in range(1, k + 1))
    if s.choch_idx - s.sweep_idx > p.choch_window:
        out["choch"] = "CHoCH outside the window"
    elif not is_swing or r >= s.extreme_idx or r + k > s.choch_idx:
        out["choch"] = "reference is not a confirmed swing before the extreme"
    elif c[s.choch_idx] <= h[r]:
        out["choch"] = "CHoCH bar did not close beyond the reference"
    else:
        out["choch"] = True

    # 4. FVG: a real gap of at least 0.1 ATR, inside the move, within N bars before the CHoCH.
    i = s.fvg_idx
    gap = lo[i] - h[i - 2]
    window = p.fvg_max_bars_before_choch
    if i - 2 < s.extreme_idx or i > s.choch_idx:
        out["fvg"] = "gap outside the move from the extreme to the CHoCH"
    elif gap < p.min_fvg_atr * a - TOL:
        out["fvg"] = f"gap {gap:.2f} below the minimum {p.min_fvg_atr * a:.2f}"
    elif window is not None and s.choch_idx - i > window:
        out["fvg"] = f"gap {s.choch_idx - i} bars before the CHoCH (max {window})"
    else:
        out["fvg"] = True

    # 5. Plan: entry at the near edge, SL beyond the extreme, TP 1.5-4R above the entry.
    entry, sl, tp = sign * s.entry, sign * s.sl, sign * s.tp
    risk = entry - sl
    want_sl = extreme - p.sl_buffer_atr * a - spread[s.choch_idx]
    rr = (tp - entry) / risk if risk > 0 else np.nan
    if abs(entry - lo[i]) > TOL:
        out["plan"] = "entry is not the FVG's near edge"
    elif abs(sl - want_sl) > 1e-4:
        out["plan"] = "SL is not extreme - buffer - spread"
    elif not (p.min_r - TOL <= rr <= p.max_r + TOL):
        out["plan"] = f"R {rr:.2f} outside 1.5-4"
    else:
        out["plan"] = True
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    p = FROZEN_V2
    bars, h1, h4 = (
        pd.read_parquet(DATA_DIR / f"{t}.parquet") for t in (f"{p.entry_tf_minutes}m", "1h", "4h")
    )
    bars = bars[bars["ts_utc"] < DEV_END].reset_index(drop=True)
    planned = [s for s in run(bars, h1, h4, p, CostParams()) if s.tp is not None and s.r_multiple]
    rows = []
    for s in planned:
        res = check(s, bars, p)
        rows.append({"setup_id": s.setup_id, "direction": s.direction, **res})
    df = pd.DataFrame(rows)
    summary = {
        "rule_set": "FROZEN_V2",
        "period": "2012-2017 (development)",
        "setups_checked": len(df),
        "pass_rate": {c: float((df[c] == True).mean()) for c in CONDITIONS},  # noqa: E712
        "all_pass": int((df[list(CONDITIONS)] == True).all(axis=1).sum()),  # noqa: E712
        "failures": [
            {"setup_id": r["setup_id"], "condition": c, "reason": r[c]}
            for _, r in df.iterrows()
            for c in CONDITIONS
            if r[c] is not True
        ],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "conditions.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Phase 2 — automated condition check (frozen v2 rules, 2012–2017)",
        "",
        "_Generated by `python -m app.smc.conditions`. Each written condition is re-derived "
        "from the raw 5m bars for every setup that reached a full trade plan._",
        "",
        f"Setups checked: **{summary['setups_checked']}**. "
        f"All five conditions pass: **{summary['all_pass']}**.",
        "",
        "| Condition | Pass rate |",
        "| --- | --- |",
    ]
    lines += [f"| {c} | {100 * summary['pass_rate'][c]:.1f}% |" for c in CONDITIONS]
    if summary["failures"]:
        lines += ["", "## Failures", "", "| Setup | Condition | Reason |", "| --- | --- | --- |"]
        lines += [
            f"| {f['setup_id']} | {f['condition']} | {f['reason']} |" for f in summary["failures"]
        ]
    (args.out / "conditions.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{summary['all_pass']} of {summary['setups_checked']} pass all five conditions")


if __name__ == "__main__":
    main()
