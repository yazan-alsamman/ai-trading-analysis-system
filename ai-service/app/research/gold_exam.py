"""The gold lockbox exam (``docs/strategies/GOLD_LOCKBOX_EXAM.md``, registered 2026-11-05).

    python -m app research gold-exam run LOCKBOX_DIR --open-lockbox   # once
    python -m app research gold-exam compare                          # after the MT5 run

``run`` is the only code path that reads past the lockbox start, and it reads one file: the XAUUSD
M1 export of the sealed lockbox, after its size and SHA-256 match the manifest. It refuses without
``--open-lockbox``, with uncommitted changes under ``app/`` or ``tools/``, or once
``gold_exam_log.json`` exists; the log is written before the file is read. It builds the frozen
combination (LVL4H with the tuned settings of ``gold_combo.md``, PIVOT, M8, no AI filter) on the
store's bars with the lockbox bars appended, and writes the trades placed in the lockbox to the
trade file of ``tools/mt5/GoldCombo.mq5``. It prints counts only.

``compare`` reads the tester's replay (``Part = exam``) and the tester log's tick source, and
writes ``gold_exam.md`` with the decision of section 4."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import instruments, splits
from app.data import clock
from app.data.aggregate import aggregate
from app.data.importer import M1
from app.data.mt5 import parse_export
from app.lockbox import sha256_file
from app.research import gold_combo as gc
from app.research import gold_lab as gl
from app.strategies import frames as F

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "lockbox" / "MANIFEST-2026-10-21.json"
FILE = "XAUUSD_M1_202601120101_202610202356.csv"
LOG = gl.OUT_DIR / "gold_exam_log.json"
REPORT = gl.OUT_DIR / "gold_exam.md"
TRADES = gl.STORE / "gold_exam_trades.parquet"
TRADE_FILE = "gold_exam_trades.csv"
REPLAY = "gold_combo_replay_exam.csv"
EXAM_START = pd.Timestamp("2026-01-12", tz="UTC")
# Frozen by gold_combo.md (tuned on 2012-2021) and the registration, section 1.
LVL_MULT, LVL_WINDOW, LVL_CAP, LVL_HORIZON = 0.75, "02-16", 0.05, 200
PIV_WINDOW, PIV_HORIZON = "02-16", 48
PASS, FAIL = 0.0, -0.10


class ExamError(RuntimeError):
    """The exam may not run (again)."""


# --- run -------------------------------------------------------------------------------------


def checked_file(
    lockbox_dir: Path, manifest: Path = MANIFEST, name: str = FILE
) -> tuple[Path, str]:
    """The lockbox file and its SHA-256, after both match the sealed manifest."""
    sealed = {f["path"]: f for f in json.loads(manifest.read_text(encoding="utf-8"))["files"]}
    if name not in sealed:
        raise ExamError(f"{name} is not in {manifest.name}")
    path = Path(lockbox_dir) / name
    digest = sha256_file(path)
    if (path.stat().st_size, digest) != (sealed[name]["bytes"], sealed[name]["sha256"]):
        raise ExamError(f"{name} does not match the sealed manifest")
    return path, digest


def lockbox_frames(path: Path) -> dict[str, pd.DataFrame]:
    """The file's bars, parsed and clock-checked as the importer does, as research frames."""
    s = splits()
    inst = instruments()[gl.SYM]
    with open(path, "rb") as f:
        parsed = parse_export(f, inst, M1, s.server_tz)
    segments = clock.detect(parsed.bars, inst, s.server_tz)
    m1 = clock.apply(parsed.bars, segments)
    segments = clock.check_mismatch_weeks(m1, segments, s.server_tz)
    m1 = clock.apply_mismatch_weeks(m1, segments, s.server_tz)
    return {tf: aggregate(m1, tf, M1) for tf in F.FRAMES}


def joined(store: dict[str, pd.DataFrame], lock: dict[str, pd.DataFrame],
           start: pd.Timestamp | None = None) -> dict[str, pd.DataFrame]:  # fmt: skip
    """The store's frames with the lockbox bars that open on or after ``start`` (by default the
    lockbox start)."""
    start = pd.Timestamp(splits().lockbox_start, tz="UTC") if start is None else start
    out = {}
    for tf, df in store.items():
        new = lock[tf][lock[tf]["ts_utc"] >= start]
        both = pd.concat([df, new.astype(df.dtypes.to_dict())], ignore_index=True)
        if not both["ts_utc"].is_monotonic_increasing or both["ts_utc"].duplicated().any():
            raise ExamError(f"{tf}: the lockbox bars do not follow the store's")
        out[tf] = both
    return out


def exam_trades(fr: dict[str, pd.DataFrame],
                start: pd.Timestamp = EXAM_START) -> tuple[pd.DataFrame, list, gl.Ctx]:  # fmt: skip
    """The frozen combination's M8 trades placed on or after ``start``."""
    cx = gl.context(fr)
    events: list = []
    lvl = gc.levels(cx, "LVL4H", gc.day_levels(cx), LVL_MULT * cx.atr4h, gc.WINDOWS[LVL_WINDOW],
                    LVL_HORIZON, LVL_CAP)  # fmt: skip
    piv = gc.levels(cx, "PIVOT", gc.pivot_levels(cx), cx.atr1h, gc.WINDOWS[PIV_WINDOW],
                    PIV_HORIZON, None)  # fmt: skip
    t = pd.concat([gc.run(lvl, cx, events), gc.run(piv, cx, events)], ignore_index=True)
    placed = pd.to_datetime(cx.m["ts_utc"].to_numpy()[t["i"]], utc=True)
    t = t[placed >= start].sort_values(["i", "strategy"], kind="stable").reset_index(drop=True)
    return t.assign(id=np.arange(1, len(t) + 1), take=True), events, cx


def code_state() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()  # fmt: skip

    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": git("status", "--porcelain", "app", "tools"),
    }


def run(lockbox_dir: Path, open_lockbox: bool) -> dict:
    if not open_lockbox:
        raise ExamError("the exam reads the lockbox: pass --open-lockbox")
    if LOG.exists():
        raise ExamError(f"{LOG.name} exists: the exam has run, and it runs once")
    code = code_state()
    if code["dirty"]:
        raise ExamError(
            f"commit the code first; uncommitted under app/ or tools/:\n{code['dirty']}"
        )
    path, digest = checked_file(lockbox_dir)
    log = {
        "registration": "docs/strategies/GOLD_LOCKBOX_EXAM.md",
        "commit": code["commit"],
        "file": FILE,
        "sha256": digest,
        "opened_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "frozen": {
            "LVL4H": [LVL_MULT, LVL_WINDOW, LVL_CAP, LVL_HORIZON],
            "PIVOT": [PIV_WINDOW, PIV_HORIZON],
            "management": "M8",
            "ai_filter": False,
        },
    }
    LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8", newline="\n")
    fr = joined(gl.load(), lockbox_frames(path))
    t, events, cx = exam_trades(fr)
    t.to_parquet(TRADES, index=False)
    common = gc.common_files()
    for target in [gl.STORE / TRADE_FILE, *([common / TRADE_FILE] if common else [])]:
        gc.trade_file(t, events, cx, target)
    last = fr["5m"]["close_utc"].iloc[-1]
    log |= {"last_bar_utc": last.isoformat(), "trades": t["strategy"].value_counts().to_dict()}
    LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8", newline="\n")
    return log


# --- compare ---------------------------------------------------------------------------------


def decide(mean: float) -> str:
    return "Pass" if mean > PASS else "Fail" if mean < FAIL else "Not confirmed"


TICK_LINE = re.compile(r"real ticks|tick generation")


def tick_source(tester: Path) -> list[str]:
    """The tick-source lines of the last tester run with ``Part=exam`` in the agents' logs."""
    runs: list[tuple[str, list[str]]] = []
    for f in sorted(tester.glob("*/Agent-*/logs/*.log")):
        text = f.read_bytes().decode("utf-16-le", "replace").splitlines()
        cur: list[str] | None = None
        for line in text:
            if "testing of" in line and "GoldCombo" in line:
                cur = [line]
                runs.append((f.name, cur))
            elif cur is not None:
                cur.append(line)
    exam = [(name, lines) for name, lines in runs if any("Part=exam" in x for x in lines)]
    if not exam:
        return []
    return [x.split("\t")[-1].strip() for x in exam[-1][1] if TICK_LINE.search(x)]


def real_ticks(lines: list[str]) -> bool:
    """No generated ticks, and real ticks from before the exam start."""
    if not lines or any("no real ticks" in x or "tick generation" in x for x in lines):
        return False
    for x in lines:
        m = re.search(r"real ticks begin from (\d{4}\.\d{2}\.\d{2})", x)
        if m and pd.Timestamp(m.group(1).replace(".", "-"), tz="UTC") > EXAM_START:
            return False
    return True


def compare(folder: Path, tester: Path) -> str:
    t = pd.read_parquet(TRADES)
    res = pd.read_csv(folder / REPLAY).drop(columns="strategy")
    j = t.merge(res, on="id", how="left")
    done = j["status"] == "closed"
    money = j["risk_money"].where(j["risk_money"] > 0)
    j["mt5"] = ((j["profit"] + j["commission"] + j["fee"] + j["swap"]) / money).where(done)
    c = j[done]
    ticks = tick_source(tester)
    real = real_ticks(ticks)
    mean = c["mt5"].mean()
    se = c["mt5"].std(ddof=1) / np.sqrt(max(len(c), 2))
    cum = c.sort_values("close_time")["mt5"].cumsum()
    status = j["status"].fillna("missing").value_counts().to_dict()
    lines = [
        "# Gold lockbox exam: result",
        "",
        "_Registration: `GOLD_LOCKBOX_EXAM.md`. Read once: `gold_exam_log.json`. MT5 net R = "
        "(profit + commission + fee + swap) / the money risk of the level and SL._",
        "",
        "## Tick source",
        "",
        *([f"- `{x}`" for x in ticks] or ["- no tester run with `Part=exam` found"]),
        "- **Real ticks for the whole exam**"
        if real
        else "- **NOT real ticks: the run does not count (section 3, step 4)**",
        "",
        "## Decision (section 4)",
        "",
        "| Trades closed | MT5 mean net R (SE) | Pass above | Fail below | Result |",
        "| --- | --- | --- | --- | --- |",
        f"| {len(c):,} | {mean:+.3f} ({se:.3f}) | {PASS:+.2f} | {FAIL:+.2f} "
        f"| **{decide(mean) if real else 'Not counted'}** |",
        "",
        f"Statuses: {status}.",
        "",
        "## Reported only",
        "",
        "| Set | Trades | MT5 net R | Python net R | Python net with slip |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {name} | {len(g):,} | {g['mt5'].mean():+.3f} | {g['net'].mean():+.3f} "
            f"| {g['net_slip'].mean():+.3f} |"
            for name, g in [("Combination", c), *c.groupby("strategy")]
        ],  # fmt: skip
        "",
        f"- Total {cum.iloc[-1]:+.1f} R; the largest drawdown {(cum - cum.cummax()).min():.1f} R."
        if len(cum)
        else "- No closed trade.",
        f"- Cost a trade in MT5 (Python gross - MT5 net): {(c['gross'] - c['mt5']).mean():.3f} R; "
        f"the Python cost model: {c['cost'].mean():.3f} R.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-exam")
    sub = ap.add_subparsers(dest="step", required=True)
    r = sub.add_parser("run")
    r.add_argument("lockbox_dir", type=Path)
    r.add_argument("--open-lockbox", action="store_true")
    sub.add_parser("compare")
    args = ap.parse_args(argv)
    try:
        if args.step == "run":
            log = run(args.lockbox_dir, args.open_lockbox)
            print(
                f"exam trades {log['trades']}; last bar {log['last_bar_utc']}; wrote {TRADE_FILE}"
            )
            return 0
        tester = Path(os.environ["APPDATA"]) / "MetaQuotes" / "Tester"
        REPORT.write_text(compare(gc.common_files(), tester), encoding="utf-8", newline="\n")
        print(f"wrote {REPORT}")
        return 0
    except ExamError as e:
        print(e, file=sys.stderr)
        return 2
