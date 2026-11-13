"""The live gold-levels engine against the research trades (P7 F1, ``docs/phase7/PLAN.md``).

    python -m app research gold-levels-check [--from 2025-07-01] [--to 2026-01-08]

For each New York weekday: the engine (``app.live.gold_levels.scan_day``) on frames cut as a live
request would carry them (the last 3,000 5m, 500 1h, 300 4h and 260 closed D1 bars, plus the day
in progress), at 16:55 New York; against ``gold_live.five_trades`` with ROUND on the full store.
Then the same days at 10:00 New York: every setup's path then must be the start of its path at
16:55 (nothing after ``as_of`` read)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.live import gold_levels as lv
from app.research import gold_lab as gl
from app.research import gold_live as gv

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "phase7" / "gold_levels_check.md"
KEEP = {"5m": 3000, "1h": 500, "4h": 300, "D1": 260}


def cut(fr: dict[str, pd.DataFrame], as_of: pd.Timestamp) -> dict[str, pd.DataFrame]:
    out = {}
    for tf, n in KEEP.items():
        f = fr[tf]
        out[tf] = f[f["close_utc"] <= as_of].tail(n).reset_index(drop=True)
    out["D1"] = lv.with_current_day(out["D1"], out["5m"])
    return out


def research(fr: dict[str, pd.DataFrame], start: pd.Timestamp) -> pd.DataFrame:
    _, every, _, cx = gv.five_trades(fr, start=start, with_round=True)
    every = every.copy()
    every["ny_day"] = cx.ny_day[every["i"].to_numpy()]
    every["fill_at"] = cx.m["close_utc"].to_numpy()[every["i"].to_numpy()]
    return every


def engine_trades(setups: list[lv.LevelSetup]) -> pd.DataFrame:
    rows = []
    for s in setups:
        if s.state != "CLOSED":
            continue
        fill = next(p.at for p in s.path if p.state == "ACTIVE")
        rows.append(
            {
                "strategy": s.strategy,
                "kind": s.kind,
                "fill_at": fill,
                "dir": 1.0 if s.direction == "buy" else -1.0,
                "r": s.path[-1].realized_r,
            }
        )
    return pd.DataFrame(rows, columns=["strategy", "kind", "fill_at", "dir", "r"])


def prefix_ok(early: list[lv.LevelSetup], late: list[lv.LevelSetup]) -> tuple[int, int]:
    """Setups whose path at the early time is the start of their path at the late time."""
    final = {(s.strategy, s.kind): s for s in late}
    ok = bad = 0
    for s in early:
        f = final.get((s.strategy, s.kind))
        a = [(p.state, p.at) for p in s.path]
        b = [(p.state, p.at) for p in f.path] if f else []
        if b[: len(a)] == a:
            ok += 1
        else:
            bad += 1
    return ok, bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gold-levels-check")
    ap.add_argument("--from", dest="start", default="2025-07-01")
    ap.add_argument("--to", dest="end", default="2026-01-08")
    a = ap.parse_args(argv or [])
    fr = gl.load()
    start = pd.Timestamp(a.start, tz="UTC")
    ref = research(fr, start)
    days = pd.bdate_range(a.start, a.end)
    got, n_ok, n_bad, n_days = [], 0, 0, 0
    doubles: set = set()
    for d in days:
        day = d.year * 10000 + d.month * 100 + d.day
        late = lv.scan_day(cut(fr, lv.at_ny(day, 16 * 60 + 55)), lv.at_ny(day, 16 * 60 + 55))
        if not late:
            continue
        n_days += 1
        early = lv.scan_day(cut(fr, lv.at_ny(day, 10 * 60)), lv.at_ny(day, 10 * 60))
        ok, bad = prefix_ok(early, late)
        n_ok, n_bad = n_ok + ok, n_bad + bad
        got.append(engine_trades(late).assign(ny_day=day))
        fills = {(x.strategy, p.at) for x in late for p in x.path if p.state == "ACTIVE"}
        doubles.update(
            (x.strategy, p.at)
            for x in late
            for p in x.path
            if p.state == "INVALIDATED"
            and p.reason == "strategy_busy"
            and (x.strategy, p.at) in fills
        )
    eng = pd.concat(got, ignore_index=True)
    ref = ref[
        ref["ny_day"].between(int(days[0].strftime("%Y%m%d")), int(days[-1].strftime("%Y%m%d")))
    ]
    ref = ref.assign(fill_at=pd.to_datetime(ref["fill_at"], utc=True))
    eng = eng.assign(fill_at=pd.to_datetime(eng["fill_at"], utc=True))
    j = ref[["strategy", "kind", "fill_at", "dir", "net_slip"]].merge(
        eng,
        on=["strategy", "kind", "fill_at"],
        how="outer",
        indicator=True,
        suffixes=("_ref", "_eng"),
    )
    both = j[j["_merge"] == "both"]
    diff = (both["net_slip"] - both["r"]).abs()
    key = list(zip(both["strategy"], both["fill_at"], strict=True))
    dbl = np.array([k in doubles for k in key], bool)
    unexplained = diff[~dbl]
    worst = float(unexplained.max()) if len(unexplained) else 0.0
    same_dir = int((both["dir_ref"] == both["dir_eng"]).sum())
    lines = [
        "# The live gold-levels engine against the research trades",
        "",
        f"_`python -m app research gold-levels-check --from {a.start} --to {a.end}`: {n_days} New "
        "York weekdays; the engine on request-sized frames (5m 3,000, 1h 500, 4h 300, D1 260 + "
        "the day in progress) at 16:55 New York, against `gold_live.five_trades` with ROUND on "
        "the full store._",
        "",
        "| Item | Value |",
        "| --- | --- |",
        f"| Research trades | {int((j['_merge'] != 'right_only').sum()):,} |",
        f"| Engine trades (CLOSED) | {int((j['_merge'] != 'left_only').sum()):,} |",
        f"| Matched (strategy, level, fill bar) | {len(both):,} |",
        f"| Same direction | {same_dir:,} |",
        f"| Net R difference, largest / mean | {diff.max():.6f} / {diff.mean():.6f} |",
        f"| Trades on a bar where two levels of the strategy were touched | {int(dbl.sum())} |",
        f"| Of them with a different R | {int((diff[dbl] > 1e-9).sum())} |",
        f"| Largest difference on the other trades | {worst:.6f} |",
        f"| Research only | {int((j['_merge'] == 'left_only').sum())} |",
        f"| Engine only | {int((j['_merge'] == 'right_only').sum())} |",
        f"| Paths at 10:00 that start the 16:55 path (no look-ahead) | {n_ok:,} of "
        f"{n_ok + n_bad:,} |",
        "",
        "Two levels of one strategy touched on the same bar: the EA's stop orders fill in price "
        "order, so the engine takes the level nearer the bar's open (ties: the EA's level order) "
        "and the other is `strategy_busy`. The research code (`gold_lab.simulate`) sorts these "
        "with an unstable sort, so it can take the farther level's entry while labelling the "
        "trade with the nearer one. The engine follows the EA; the research code is frozen and "
        "unchanged.",
        "",
    ]
    odd = j[j["_merge"] != "both"].sort_values("fill_at").head(30)
    if len(odd):
        lines += [
            "## Unmatched (first 30)",
            "",
            "| Side | Strategy | Level | Fill (UTC) |",
            "| --- | --- | --- | --- |",
        ]
        lines += [
            f"| {r['_merge']} | {r['strategy']} | {r['kind']} | {r['fill_at']:%Y-%m-%d %H:%M} |"
            for _, r in odd.iterrows()
        ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    ok = len(both) and worst < 1e-9
    return 0 if ok and n_bad == 0 and (j["_merge"] == "both").all() else 1
