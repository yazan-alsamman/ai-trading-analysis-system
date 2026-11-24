"""The single holdout reading (docs/strategies/PREREG.md, sections 9 and 10; Addendum 1).

    python -m app research holdout                  # once; refused if it was read before

**Read once.** Refused when ``docs/strategies/holdout.md`` exists, while the reports of Stages C and
D (``evaluation.md``, ``management.md``) are not committed unchanged, while Stage E is not closed
in ``PREREG.md``, and under the Stage C guard (approval, seeds, rule files as at the frozen
commit). Bars are loaded to the lockbox start (2026-01-10); the lockbox is never read. The
commit holding the reports is recorded in the report.

**What is checked** (nothing else is computed on the holdout):

1. **Families A and B:** no strategy passed, so there is no holdout check (section 10).
2. **Family C, scalp** (trial 19, passed): the bundle the procedure serves is the selection at
   2024-07-01 (training trades known by then, as in Stage D). On the scalp entries of M0's fixed
   entry set with entry in the holdout, mean (net R of that bundle - net R of M0) > 0 is
   "consistent on the holdout": activated; otherwise not activated. Intraday and swing were not
   activated, so they get no check.
3. **Addendum 1, S1 + M8** (trial 26): on S1's entries in the holdout, mean net R under M8 > 0
   **and** mean (M8 - M0) > 0 is "consistent on the holdout"; otherwise "not consistent". Reported
   as well, never decided on: S1 under M8's own one-active-trade book, per instrument, per month,
   before costs, at twice the costs, and under W0 and W3.

Net R everywhere: registered costs, SL slippage, the decision swap scenario (W1). Unresolved
outcomes at the lockbox start are excluded and counted."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import bundles, instruments, rules, signal_specs, splits
from app.data.importer import DEFAULT_OUT as STORE
from app.management.book import fixed_entry_table, manager, one_active
from app.research import decide
from app.research.strategy_eval import START_2012, SWAPS, registered
from app.strategies import frames as research_frames
from app.strategies import swap
from app.strategies.cli import OUT_DIR, PREREG, ROOT, load_swaps
from app.strategies.counts import bounds
from app.strategies.rules import Frames, candidates

REPORT = OUT_DIR / "holdout.md"
STAGE_REPORTS = ("docs/strategies/evaluation.md", "docs/strategies/management.md")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def preconditions(report: Path = REPORT, prereg: Path = PREREG) -> tuple[str, str, str]:
    """(frozen commit, HEAD, commit of the stage reports), or an error that refuses the reading."""
    if report.exists():
        raise PermissionError(f"the holdout was read already ({report.name}); it is read once")
    commit, head, _ = registered()
    if "| Stage E (family D, AI) | closed" not in prereg.read_text(encoding="utf-8"):
        raise PermissionError("the holdout is read after Stage E is run or closed (section 10)")
    for path in STAGE_REPORTS:
        tracked = _git("ls-files", "--error-unmatch", path).returncode == 0
        clean = _git("diff", "--quiet", "HEAD", "--", path).returncode == 0
        if not (tracked and clean):
            raise PermissionError(f"{path} must be committed and unchanged before the holdout")
    reports = _git("log", "-1", "--format=%H", "--", *STAGE_REPORTS).stdout.strip()
    return commit, head, reports


def entry_table(frames_by_symbol: dict[str, Frames], swaps: dict, names: list[str]) -> pd.DataFrame:
    """M0's fixed entry set of every strategy on bars to the lockbox start, every bundle's own
    columns (as Stage D, on a longer load)."""
    _, _, lockbox = bounds()
    rp, bs = rules(), bundles()
    bs = {n: bs[n] for n in names}
    parts = []
    for sym, f in sorted(frames_by_symbol.items()):
        for tf, df in f.items():
            if len(df) and df["close_utc"].max() > lockbox:
                raise ValueError(f"{sym} {tf}: bars after the lockbox start {lockbox}")
        inst = instruments()[sym]
        for _, sp in sorted(signal_specs().items()):
            tab = fixed_entry_table(f, inst, sp, rp, bs, swaps[sym])
            parts.append(tab.assign(type=sp.type, family=sp.family))
        print(f"{sym}: entry table ready", file=sys.stderr, flush=True)
    return pd.concat(parts, ignore_index=True)


def in_holdout(table: pd.DataFrame) -> pd.DataFrame:
    _, holdout, lockbox = bounds()
    return table[(table["entry_utc"] >= holdout) & (table["entry_utc"] < lockbox)]


def scalp_check(table: pd.DataFrame, names: list[str]) -> dict:
    """Family C, scalp: the served bundle against M0 on the holdout scalp entries."""
    _, holdout, lockbox = bounds()
    scalp = table[table["type"] == "scalp"]
    served = decide.select_bundle(scalp, names, holdout, splits().embargo_days)
    test, excluded = decide.window_trades(scalp, (holdout, lockbox), served)
    mean = float(test["delta"].mean()) if len(test) else np.nan
    ok = len(test) > 0 and mean > 0
    return {"served": served, "n": len(test), "excluded": excluded, "mean_delta": mean,
            "blocks": len(np.unique(decide.block_ids(test["entry_utc"]))) if len(test) else 0,
            "result": "consistent on the holdout: activated" if ok
            else "not consistent on the holdout: not activated"}  # fmt: skip


def addendum_check(table: pd.DataFrame) -> dict:
    """Addendum 1: S1 under M8, and M8 against M0, on S1's holdout entries."""
    s1 = in_holdout(table[table["strategy"] == "S1"])
    m8, m0 = s1[decide.r_col("M8")], s1[decide.r_col("M0")]
    ok = m8.notna() & m0.notna()
    g = s1[ok]
    mean, delta = float(m8[ok].mean()), float((m8 - m0)[ok].mean())
    consistent = bool(ok.any() and mean > 0 and delta > 0)
    return {"n": int(ok.sum()), "excluded": int((~ok).sum()), "mean_m8": mean, "mean_m0":
            float(m0[ok].mean()), "mean_delta": delta,
            "blocks": len(np.unique(decide.block_ids(g["entry_utc"]))) if len(g) else 0,
            "result": ("" if consistent else "not ") + "consistent on the holdout",
            "trades": g}  # fmt: skip


def addendum_details(frames_by_symbol: dict[str, Frames], swaps: dict) -> dict:
    """Reported for Addendum 1, never decided on: S1 under M8 on the holdout entries before costs,
    at twice the costs, under W0, W1 and W3, and under M8's own one-active-trade book."""
    _, holdout, lockbox = bounds()
    rp, bs = rules(), bundles()
    sp = signal_specs()["S1"]
    rows, own = [], []
    for sym, f in sorted(frames_by_symbol.items()):
        inst, e = instruments()[sym], f[sp.frame]
        close, price_at = e["close_utc"], swap.close_before(e)
        cands = candidates(f, inst, sp)
        run8 = manager(f, inst, sp, rp, bs["M8"])
        fixed = [
            c for c, o in one_active(cands, manager(f, inst, sp, rp, bs["M0"])) if o is not None
        ]
        for c in fixed:
            t = close.iloc[c.idx]
            if not holdout <= t < lockbox:
                continue
            o = run8(c)
            if o.state != "CLOSED":
                continue
            x = pd.Timestamp(o.exit_ns, tz="UTC")
            w1 = swap.swap_r(swaps[sym], c.direction, t, x, c.risk, c.entry, price_at)
            w3 = swap.stress_r(swaps[sym], t, x, c.risk, c.entry)
            rows.append({"symbol": sym, "month": t.strftime("%Y-%m"), "gross": o.gross_r,
                         "w0": o.net_r(), "w1": o.net_r() + w1, "w3": o.net_r() + w3,
                         "x2": o.net_r(2) + w1})  # fmt: skip
        for c, o in one_active(cands, run8):
            t = close.iloc[c.idx]
            if o is not None and o.state == "CLOSED" and holdout <= t < lockbox:
                x = pd.Timestamp(o.exit_ns, tz="UTC")
                own.append(o.net_r() + swap.swap_r(swaps[sym], c.direction, t, x, c.risk,
                                                   c.entry, price_at))  # fmt: skip
    d = pd.DataFrame(rows)
    return {"detail": d, "own_n": len(own), "own_mean": float(np.mean(own)) if own else np.nan}


def _f(v: float) -> str:
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:+.3f}"


def render(scalp: dict, add: dict, det: dict, commit: str, head: str, reports: str,
           run_date: str) -> str:  # fmt: skip
    d = det["detail"]
    lines = [
        "# The holdout reading (2024-07-01 to 2026-01-10, read once)",
        "",
        f"_Generated by `python -m app research holdout` on {run_date}. Rules frozen at"
        f" `{commit}`, code `{head}`; the reports of Stages C and D were committed at `{reports}`"
        " before this reading. Bars loaded to the lockbox start; the lockbox was not read. About 20"
        " four-week blocks: below the method condition, so no test and no interval decide"
        " anything (`PREREG.md` section 10). A consistent result is not a statistical"
        " confirmation._",
        "",
        "## Decisions",
        "",
        "| Check | Registered rule | Holdout | Result |",
        "| --- | --- | --- | --- |",
        "| Families A and B (trials 11-18) | holdout check for a passed strategy | no strategy"
        " passed | no check; every status stays as in Stage C |",
        f"| Family C, scalp (trial 19, passed) | mean (served bundle - M0) > 0 | served"
        f" {scalp['served']}; n {scalp['n']} (excluded {scalp['excluded']}), {scalp['blocks']}"
        f" blocks; mean delta {_f(scalp['mean_delta'])} | **{scalp['result']}** |",
        "| Family C, intraday and swing (trials 20-21) | - | not activated in Stage D | no check |",
        f"| Addendum 1, S1 + M8 (trial 26) | mean net R (M8) > 0 and mean (M8 - M0) > 0 | n"
        f" {add['n']} (excluded {add['excluded']}), {add['blocks']} blocks;"
        f" M8 {_f(add['mean_m8'])},"
        f" M0 {_f(add['mean_m0'])}, delta {_f(add['mean_delta'])} | **{add['result']}** |",
        "",
        "S1 stays unvalidated whatever this shows (Addendum 1, section 3); its registered test is"
        " the forward paper log (section 6).",
        "",
        "## Addendum 1: reported, not decided on",
        "",
        "| Quantity | Value |",
        "| --- | --- |",
        f"| S1 + M8 before costs (gross) | {_f(d['gross'].mean()) if len(d) else ''} |",
        f"| S1 + M8 net under W0 / W1 (decision) / W3 | {_f(d['w0'].mean()) if len(d) else ''} /"
        f" {_f(d['w1'].mean()) if len(d) else ''} / {_f(d['w3'].mean()) if len(d) else ''} |",
        f"| S1 + M8 at twice the costs | {_f(d['x2'].mean()) if len(d) else ''} |",
        f"| S1 under M8's own one-active-trade book | n {det['own_n']},"
        f" mean {_f(det['own_mean'])} |",
        "",
    ]
    if len(d):
        lines += ["Per instrument:", "", "| Instrument | n | Mean net R |", "| --- | --- | --- |"]
        for k, q in d.groupby("symbol"):
            lines.append(f"| {k} | {len(q)} | {_f(q['w1'].mean())} |")
        lines += ["", "Per month:", "", "| Month | n | Mean net R |", "| --- | --- | --- |"]
        for k, q in d.groupby("month"):
            lines.append(f"| {k} | {len(q)} | {_f(q['w1'].mean())} |")
    return "\n".join([*lines, ""])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research holdout")
    ap.add_argument("--store", type=Path, default=STORE)
    args = ap.parse_args(argv)
    try:
        commit, head, reports = preconditions()
    except (PermissionError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    _, _, lockbox = bounds()
    symbols = sorted(s for s in instruments() if (args.store / s).is_dir())
    frames = {s: research_frames.load(s, START_2012, lockbox, args.store) for s in symbols}
    swaps = load_swaps(SWAPS)
    names = list(bundles())
    table = entry_table(frames, swaps, names)
    scalp, add = scalp_check(table, names), addendum_check(table)
    det = addendum_details(frames, swaps)
    run_date = pd.Timestamp.now(tz="UTC").date().isoformat()
    REPORT.write_text(render(scalp, add, det, commit, head, reports, run_date), encoding="utf-8",
                      newline="\n")  # fmt: skip
    print(f"wrote {REPORT}")
    return 0
