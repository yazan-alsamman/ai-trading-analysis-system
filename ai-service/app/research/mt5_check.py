"""The cost-model check in the MT5 Strategy Tester (docs/strategies/EXTERNAL_REVIEW.md,
recommendation 2). Descriptive only: it decides nothing and is not a trial.

    python -m app research mt5-check export         # the trade sample for the tester
    python -m app research mt5-check compare        # after the six tester runs

**Sample.** Stage C's M0 trades (``data/processed/stage_c_trades.parquet``, primary book, resolved)
with entry from 2024-01-01 to 2024-07-01: the end of the primary period, where the broker keeps
real ticks. Trades that enter or exit in a week when US and EU daylight saving disagree are left
out, so the server clock is New York + 7 h for every trade (``app.data.clock``). No bar after
2024-07-01 and nothing of the holdout or lockbox is read.

**Replay.** ``tools/mt5/ReplayTrades.mq5``, one tester run per instrument, "Every tick based on
real ticks": each trade opens at market on the first tick at or after its entry time, with the
research SL and TP levels, and is closed at market at the research exit time if neither was hit.

**Compare.** Per trade, the tester's net R is (profit + commission + fee + swap) / the money risk
of the research entry and SL. On trades whose exit kind agrees (both TP, both SL, or both at the
time), the tester's cost is the research gross R minus the tester's net R before swap; it is set
against the modelled cost (round trip, plus SL slippage on SL exits). The tester fills stops at
their level, so it checks the spread and commission, not the slippage."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.data.clock import MARKET_TZ, SERVER_TO_NY_HOURS, dst_mismatch
from app.data.importer import DEFAULT_OUT as STORE
from app.strategies.cli import OUT_DIR

START = pd.Timestamp("2024-01-01", tz="UTC")
END = pd.Timestamp("2024-07-01", tz="UTC")
SERVER_TZ = "Europe/Athens"
SAMPLE_FILE = "ai_replay_trades.csv"
RESULT_GLOB = "mt5_replay_*.csv"
REPORT = OUT_DIR / "mt5_cost_check.md"
TIME_EXITS = ("timeout", "session_end", "session_end_gap")
SAMPLE_COLUMNS = ["id", "symbol", "strategy", "type", "direction", "entry_server", "exit_server",
                  "entry", "sl", "tp", "risk", "k", "reason"]  # fmt: skip


def common_files() -> Path | None:
    """The MT5 Common\\Files folder, which every terminal and tester agent can read and write."""
    appdata = os.environ.get("APPDATA")
    p = Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files" if appdata else None
    return p if p is not None and p.is_dir() else None


def server_time(ts: pd.Series) -> pd.Series:
    """UTC to the FxPro server clock (New York + 7 h), naive."""
    return ts.dt.tz_convert(MARKET_TZ).dt.tz_localize(None) + pd.Timedelta(hours=SERVER_TO_NY_HOURS)


def sample(
    book: pd.DataFrame, start: pd.Timestamp = START, end: pd.Timestamp = END
) -> pd.DataFrame:
    """The trades sent to the tester, with their levels, server times and modelled costs."""
    t = book[(book["book"] == "primary") & (book["state"] == "resolved")
             & (book["entry_utc"] >= start) & (book["entry_utc"] < end)]  # fmt: skip
    t = t[~(dst_mismatch(t["entry_utc"], SERVER_TZ) | dst_mismatch(t["exit_utc"], SERVER_TZ))]
    t = t.sort_values(["entry_utc", "symbol", "strategy"]).reset_index(drop=True)
    s = np.where(t["direction"] == "buy", 1.0, -1.0)
    gross = 2 * t["net_w0"] - t["net_2x"]  # net = gross - cost, net_2x = gross - 2 cost
    return t.assign(
        id=np.arange(1, len(t) + 1),
        sl=t["entry"] - s * t["risk"],
        tp=t["entry"] + s * t["k"] * t["risk"],
        entry_server=server_time(t["entry_utc"]),
        exit_server=server_time(t["exit_utc"]),
        gross=gross,
        cost=gross - t["net_w0"],
    )


def write_sample(s: pd.DataFrame, path: Path) -> None:
    out = s[SAMPLE_COLUMNS].copy()
    for col in ("entry_server", "exit_server"):
        out[col] = out[col].dt.strftime("%Y.%m.%d %H:%M:%S")  # MQL5 StringToTime
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, float_format="%.8f", lineterminator="\r\n")


def load_results(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob(RESULT_GLOB))
    if not files:
        raise FileNotFoundError(f"no {RESULT_GLOB} in {folder}")
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def exit_kind(reason: pd.Series) -> pd.Series:
    return reason.where(~reason.isin(TIME_EXITS), "time")


def joined(s: pd.DataFrame, res: pd.DataFrame) -> pd.DataFrame:
    """The sample with each trade's tester result (trades the tester did not replay included)."""
    j = s.merge(res, on="id", how="left")
    done = j["status"] == "closed"
    money = j["risk_money"].where(j["risk_money"] > 0)
    sign = np.where(j["direction"] == "buy", 1.0, -1.0)
    j["mt5_net"] = ((j["profit"] + j["commission"] + j["fee"] + j["swap"]) / money).where(done)
    j["mt5_before_swap"] = ((j["profit"] + j["commission"] + j["fee"]) / money).where(done)
    j["mt5_commission"] = (-(j["commission"] + j["fee"]) / money).where(done)
    j["mt5_spread"] = ((j["open_ask"] - j["open_bid"]) / j["risk"]).where(done)
    j["entry_gap"] = (sign * (j["m1_close"] - j["entry"]) / j["risk"]).where(j["m1_close"] > 0)
    j["same_exit"] = done & (exit_kind(j["reason"]) == j["close_reason"])
    j["mt5_cost"] = (j["gross"] - j["mt5_before_swap"]).where(j["same_exit"])
    return j


def _table(j: pd.DataFrame, by: str) -> list[str]:
    lines = [
        f"| {by} | Sent | Replayed | Same exit | Modelled cost | Tester cost | of which spread "
        "| of which commission | Mean x (research) | Mean net R (tester) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key, g in [*j.groupby(by), ("all", j)]:
        done, same = g[g["status"] == "closed"], g[g["same_exit"]]
        lines.append(
            f"| {key} | {len(g)} | {len(done)} | {len(same) / max(len(done), 1):.0%} "
            f"| {same['cost'].mean():.3f} | {same['mt5_cost'].mean():.3f} "
            f"| {same['mt5_spread'].mean():.3f} | {same['mt5_commission'].mean():.3f} "
            f"| {done['x'].mean():+.3f} | {done['mt5_net'].mean():+.3f} |"
        )
    return lines


def render(j: pd.DataFrame, excluded: int, run_date: str) -> str:
    status = j["status"].fillna("missing").value_counts()
    aligned = (j["entry_gap"].abs() <= 0.05).mean()
    lines = [
        "# MT5 Strategy Tester check of the cost model",
        "",
        f"_Generated by `python -m app research mt5-check compare` on {run_date}. Descriptive only:"
        " it decides nothing, changes no rule and is not a trial. Sample: Stage C's M0 trades"
        f" (primary book) with entry from {START.date()} to {END.date()}; {excluded} trades in the"
        " weeks when US and EU daylight saving disagree left out. Replayed by"
        ' `tools/mt5/ReplayTrades.mq5`, "Every tick based on real ticks"._',
        "",
        "Costs in R a trade. The modelled cost is the registered round trip, plus the SL slippage"
        " on SL exits. The tester cost is the research gross R minus the tester's net R before"
        " swap, on the trades whose exit kind agrees (both TP, both SL, or both at the time). The"
        " tester fills"
        " stops at their level, so it measures spread and commission, not slippage.",
        "",
        "## Replay",
        "",
        "| Status | Trades |",
        "| --- | --- |",
        *[f"| {k} | {v} |" for k, v in status.items()],
        "",
        f"Clock alignment: the tester's M1 close at the entry time is within 0.05 R of the research"
        f" entry price on {aligned:.0%} of the trades (a low share means a clock or data mismatch,"
        " and the comparison below is not valid).",
        "",
        "## By instrument",
        "",
        *_table(j, "symbol"),
        "",
        "## By type",
        "",
        *_table(j, "type"),
        "",
        "## By exit",
        "",
        *_table(j.assign(exit=exit_kind(j["reason"])), "exit"),
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research mt5-check")
    ap.add_argument("step", choices=("export", "compare"))
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--results", type=Path, default=None,
                    help="folder of mt5_replay_*.csv (default: MT5 Common\\Files)")  # fmt: skip
    args = ap.parse_args(argv)
    book_path = args.store / "stage_c_trades.parquet"
    if not book_path.exists():
        print(f"refused: {book_path} not found (written by `python -m app research evaluate`)",
              file=sys.stderr)  # fmt: skip
        return 2
    book = pd.read_parquet(book_path)
    s = sample(book)
    window = book[(book["book"] == "primary") & (book["state"] == "resolved")
                  & (book["entry_utc"] >= START) & (book["entry_utc"] < END)]  # fmt: skip
    excluded = len(window) - len(s)
    common = common_files()
    if args.step == "export":
        targets = [
            args.store / "mt5_check" / SAMPLE_FILE,
            *([common / SAMPLE_FILE] if common else []),
        ]
        for p in targets:
            write_sample(s, p)
            print(f"wrote {p}")
        if common is None:
            print("MT5 Common\\Files not found: copy the file there by hand", file=sys.stderr)
        print(f"{len(s)} trades ({excluded} in DST-mismatch weeks left out):")
        print(s.groupby("symbol").size().to_string())
        return 0
    folder = args.results or common
    if folder is None:
        print("refused: give --results (MT5 Common\\Files not found)", file=sys.stderr)
        return 2
    j = joined(s, load_results(folder))
    REPORT.write_text(render(j, excluded, pd.Timestamp.now(tz="UTC").date().isoformat()),
                      encoding="utf-8", newline="\n")  # fmt: skip
    print(f"wrote {REPORT}")
    return 0
