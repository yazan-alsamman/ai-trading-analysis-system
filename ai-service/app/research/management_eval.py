"""Stage D: family C, the walk-forward management procedure against M0
(docs/strategies/PREREG.md, section 9; trials 19-21).

    python -m app research management               # every instrument in the store

**Runs only after approval, on the frozen rules** (``strategy_eval.registered``: approval date,
seeds, and every file of ``EVAL_PATHS`` as at the frozen commit).

**Entries.** Per strategy S1-S8 and instrument, the fixed entry set of M0's one-active-trade
rule on bars from 2012 loaded to 2024-07-01 (``book.fixed_entry_table``). Every bundle M0-M8
manages each entry on its own: its own exit time, exit reason and net R, with the decision swap
scenario (W1 by its own exit time, at the price of each rollover).

**Procedure,** per signal type t (scalp, intraday, swing) and each of the 13 test windows
(6 months from 2018-01-01; ``splits``): the training trades are the trades of type t with entry
before the window start whose exit under every bundle, plus the embargo (1 day), is at or before
it (``decide.training``); the chosen bundle has the highest mean net R over them, ties to the
lower index, M0 below 100 training trades (``decide.select_bundle``). The test trades are the
entries of type t in the window; one is excluded, and counted, only when its M0 or chosen-bundle
outcome is unresolved (``decide.window_trades``). delta = net R(chosen) - net R(M0).

**Test:** mean delta over all test trades of type t, 4-week blocks, p = max(p1, p2)
(``decide.paired_test``), Holm over the three types, one-sided alpha 0.05. A passed type waits for
its holdout check (improvement > 0 on holdout entries, section 9), which is not run here; otherwise
"not activated". Reported, never decided on: the selection per window, the bundle the procedure
would serve (selection at 2024-07-01), each bundle's test-window mean net R on the same entries,
overlaps and entry-set differences per bundle (section 9: diagnostics of the fixed-entry
approximation, not portfolio results).

Writes ``docs/strategies/management.md`` and the entry table to
``data/processed/stage_d_entries.parquet`` (untracked). Nothing after 2024-07-01 is loaded."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import bundles, instruments, rules, signal_specs, splits
from app.data.importer import DEFAULT_OUT as STORE
from app.management.book import entry_set_difference, fixed_entry_table, overlaps
from app.research import decide
from app.research.strategy_eval import BOOT, START_2012, SWAPS, registered
from app.strategies import frames as research_frames
from app.strategies.cli import OUT_DIR, load_swaps
from app.strategies.counts import bounds
from app.strategies.rules import Frames

TYPES = ("scalp", "intraday", "swing")
TRIAL = {"scalp": 19, "intraday": 20, "swing": 21}


def windows() -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """The 13 test windows of the walk-forward (as ``walkforward.folds``)."""
    s = splits()
    start = pd.Timestamp(s.walk_forward[0], tz="UTC")
    stop = pd.Timestamp(s.walk_forward[1], tz="UTC")
    out = []
    while start < stop:
        end = min(start + pd.DateOffset(months=s.walk_forward_test_months), stop)
        out.append((start, end))
        start = end
    return out


def entry_tables(
    frames_by_symbol: dict[str, Frames], swaps: dict, names: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The fixed entry set with every bundle's own columns, and the diagnostics per strategy,
    instrument and bundle (overlaps, entries added and dropped under the bundle's own rule)."""
    _, holdout, _ = bounds()
    rp, bs = rules(), bundles()
    bs = {n: bs[n] for n in names}
    tables, diag = [], []
    t0 = time.monotonic()
    for sym, f in sorted(frames_by_symbol.items()):
        for tf, df in f.items():
            if len(df) and df["close_utc"].max() > holdout:
                raise ValueError(f"{sym} {tf}: bars after the holdout start {holdout}")
        inst = instruments()[sym]
        for name, sp in sorted(signal_specs().items()):
            tab = fixed_entry_table(f, inst, sp, rp, bs, swaps[sym])
            tables.append(tab.assign(type=sp.type, family=sp.family))
            diff = entry_set_difference(f, inst, sp, rp, bs)
            for b in names:
                diag.append(
                    {"strategy": name, "symbol": sym, "bundle": b, "overlaps": overlaps(tab, b),
                     "added": diff[b][0], "dropped": diff[b][1]}
                )  # fmt: skip
        print(f"{sym}: entry table ready ({(time.monotonic() - t0) / 60:.1f} min)",
              file=sys.stderr, flush=True)  # fmt: skip
    return pd.concat(tables, ignore_index=True), pd.DataFrame(diag)


@dataclass
class TypeResult:
    type: str
    selection: pd.DataFrame  # per window: training trades, chosen, test trades, excluded
    test: pd.DataFrame  # entry_utc, delta, window, chosen
    p: float
    k: int
    ci: tuple[float, float]
    adjusted: float = np.nan
    result: str = ""
    served: str = ""


def procedure(
    table: pd.DataFrame, names: list[str], wins: list[tuple[pd.Timestamp, pd.Timestamp]],
    embargo_days: int, boot: int, seed: int,
) -> TypeResult | None:  # fmt: skip
    """Section 9 for one type's entries."""
    if table.empty:
        return None
    sel, tests = [], []
    for start, end in wins:
        train = decide.training(table, names, start, embargo_days)
        chosen = decide.select_bundle(table, names, start, embargo_days)
        test, excluded = decide.window_trades(table, (start, end), chosen)
        sel.append(
            {"window": start.date().isoformat(), "training": int(train.sum()), "chosen": chosen,
             "test": len(test), "excluded": excluded,
             "mean_delta": float(test["delta"].mean()) if len(test) else np.nan}
        )  # fmt: skip
        tests.append(test.assign(window=start.date().isoformat(), chosen=chosen))
    test = pd.concat(tests, ignore_index=True)
    served = decide.select_bundle(table, names, wins[-1][1], embargo_days)
    if len(test) < 2:
        return TypeResult("", pd.DataFrame(sel), test, 1.0, 0, (np.nan, np.nan), served=served)
    p, k = decide.paired_test(test["delta"].to_numpy(), test["entry_utc"], boot, seed)
    (ds,), _ = decide.bootstrap(
        [test["delta"].to_numpy()], decide.block_ids(test["entry_utc"]), boot,
        np.random.default_rng(seed),
    )  # fmt: skip
    ci = (float(np.quantile(ds, 0.025)), float(np.quantile(ds, 0.975)))
    return TypeResult("", pd.DataFrame(sel), test, p, k, ci, served=served)


def evaluate(
    table: pd.DataFrame, names: list[str], seed: int, boot: int = BOOT
) -> dict[str, TypeResult]:
    wins = windows()
    out = {}
    for t in TYPES:
        r = procedure(table[table["type"] == t], names, wins, splits().embargo_days, boot, seed)
        if r is not None:
            r.type = t
            out[t] = r
    adj = decide.holm({t: (out[t].p if t in out else 1.0) for t in TYPES})
    for t, r in out.items():
        r.adjusted = adj[t]
        r.result = (
            "passed (holdout check pending)"
            if r.k >= decide.MIN_BLOCKS and r.adjusted <= decide.ALPHA
            else "not activated"
        )
    return out


def _f(v: float) -> str:
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:+.3f}"


def _table(df: pd.DataFrame) -> list[str]:
    cell = lambda v: f"{v:+.3f}" if isinstance(v, float) else str(v)  # noqa: E731
    cols = list(df.columns)
    return [
        "| " + " | ".join(cols) + " |",
        "|" + " --- |" * len(cols),
        *["| " + " | ".join(cell(v) for v in r) + " |" for r in df.itertuples(index=False)],
    ]


def render(
    results: dict[str, TypeResult], table: pd.DataFrame, diag: pd.DataFrame, names: list[str],
    commit: str, head: str, seed: int, boot: int, run_date: str,
) -> str:  # fmt: skip
    wins = windows()
    lines = [
        "# Stage D: family C, management against M0 (trials 19-21)",
        "",
        f"_Generated by `python -m app research management` on {run_date}. Rules frozen at"
        f" `{commit}`, code `{head}`; bootstrap seed {seed}, B = {boot}. Entries: the fixed M0"
        " entry set from 2012, bars to 2024-07-01; every bundle manages each entry on its own"
        " (decision swap scenario). Test windows 2018-01 to 2024-06. Holm over the three types,"
        " one-sided alpha 0.05. A passed type is not activated yet: it waits for its holdout"
        " check (section 9)._",
        "",
        "## Decision (PREREG section 9)",
        "",
        "| Trial | Type | Test trades | Excluded | K | Mean delta (95%) | p | Holm p | Result |"
        " Bundle the procedure would serve |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for t in TYPES:
        r = results.get(t)
        if r is None:
            lines.append(f"| {TRIAL[t]} | {t} | 0 | 0 | 0 | | 1.0000 | | not tested | |")
            continue
        m = r.test["delta"].mean() if len(r.test) else np.nan
        lines.append(
            f"| {TRIAL[t]} | {t} | {len(r.test)} | {int(r.selection['excluded'].sum())} | {r.k} |"
            f" {_f(m)} ({_f(r.ci[0])} to {_f(r.ci[1])}) | {r.p:.4f} | {r.adjusted:.4f} |"
            f" {r.result} | {r.served} |"
        )
    for t in TYPES:
        r = results.get(t)
        if r is None:
            continue
        lines += ["", f"## {t}: selection per window", "", *_table(r.selection)]
    lines += [
        "",
        "## Reported, not decided on",
        "",
        "Each bundle's mean net R on the test-window entries of each type (the same entries; after"
        " the walk-forward selection these are descriptive, never used to choose anything):",
        "",
    ]
    rows = []
    for t in TYPES:
        g = table[(table["type"] == t) & (table["entry_utc"] >= wins[0][0])
                  & (table["entry_utc"] < wins[-1][1])]  # fmt: skip
        row = {"type": t, "entries": len(g)}
        for b in names:
            row[b] = float(g[decide.r_col(b)].mean()) if len(g) else np.nan
        rows.append(row)
    lines += _table(pd.DataFrame(rows))
    d = diag.groupby("bundle")[["overlaps", "added", "dropped"]].sum().reindex(names).reset_index()
    lines += [
        "",
        "Diagnostics of the fixed-entry approximation (all strategies and instruments, all years;"
        " section 9: not portfolio results, decide nothing): entries that start while an earlier"
        " one of the same strategy is still open under the bundle, and entries the bundle's own"
        " one-active rule would add or drop against M0's entry set.",
        "",
        *_table(d),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research management")
    ap.add_argument("--symbol", action="append")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    try:
        commit, head, seeds_ = registered()
    except (PermissionError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    _, holdout, _ = bounds()
    symbols = args.symbol or sorted(s for s in instruments() if (args.store / s).is_dir())
    frames = {s: research_frames.load(s, START_2012, holdout, args.store) for s in symbols}
    names = list(bundles())
    table, diag = entry_tables(frames, load_swaps(SWAPS), names)
    results = evaluate(table, names, seeds_[1], BOOT)
    run_date = pd.Timestamp.now(tz="UTC").date().isoformat()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "management.md").write_text(
        render(results, table, diag, names, commit, head, seeds_[1], BOOT, run_date),
        encoding="utf-8", newline="\n",
    )  # fmt: skip
    table.to_parquet(args.store / "stage_d_entries.parquet", index=False)
    print(f"wrote {args.out / 'management.md'}")
    return 0
