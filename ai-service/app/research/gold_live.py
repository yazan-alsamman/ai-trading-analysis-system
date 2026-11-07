"""Gold v1 live: check ``tools/mt5/GoldLive.mq5`` against Python (``docs/strategies/GOLD_V1.md``).

    python -m app research gold-live check [--log gold_live_log.csv] [--reference exam|fxpro]
    python -m app research gold-live fxpro --export <Common>/Files/history/GOLDFX_M1_*.csv

``fxpro`` builds v1 on FxPro's own GOLD bars, the feed the demo trades (the research used another
feed, XAUUSD): the reference for ``check --reference fxpro`` and v1's result by year there.

The EA computes the signals itself. Run in the Strategy Tester over the exam period (2026-01-12 to
2026-10-21, real ticks, ``FixedLots = 1``), its log must give the trades Python gives for those
days (``gold_exam_trades.csv`` and ``.parquet``, written by ``gold-exam run``):

- **Signals.** The EA's fills against Python's trades, matched on strategy and signal bar
  (server time). Each one on only one side is listed, with the EA's reason for a touch it did not
  trade.
- **Prices.** For the matched trades: direction, level and distance D.
- **Results.** Gross R from the EA's exit price against Python's gross R, and the EA's net R from
  its deals.

Writes ``gold_live_check.md``."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl

REPORT = gl.OUT_DIR / "gold_live_check.md"
CONTRACT = 100.0  # oz a lot


COLUMNS = ["time_server", "event", "strategy", "kind", "dir", "bar_server", "level", "entry", "sl",
           "risk", "lots", "ticket", "price", "note"]  # fmt: skip
NUMERIC = ["dir", "level", "entry", "sl", "risk", "lots", "ticket", "price"]


def read_log(path) -> pd.DataFrame:
    """The rows of the last run (from the last START); the note is the rest of the line, so a
    comma in it does not shift the columns."""
    text = path.read() if hasattr(path, "read") else Path(path).read_text(encoding="utf-8")
    rows = [ln.split(",", len(COLUMNS) - 1) for ln in text.splitlines()[1:] if ln.strip()]
    df = pd.DataFrame([r + [""] * (len(COLUMNS) - len(r)) for r in rows], columns=COLUMNS)
    starts = df.index[df["event"] == "START"]
    if len(starts):
        df = df.loc[starts[-1] :].reset_index(drop=True)
    df[NUMERIC] = df[NUMERIC].apply(pd.to_numeric, errors="coerce")
    df["ticket"] = df["ticket"].fillna(0).astype("int64")
    return df


def python_trades(reference: str = "exam") -> pd.DataFrame:
    """Python's trades with their signal bar on the server clock: the exam's (the research XAUUSD
    feed) or v1 on FxPro's GOLD feed (``fxpro``)."""
    parquet, csv = (ge.TRADES, ge.TRADE_FILE) if reference == "exam" else (FX_TRADES, FX_FILE)
    t = pd.read_parquet(parquet)
    f = pd.read_csv(gl.STORE / csv)[["id", "place_server"]]
    t = t.merge(f, on="id")
    return t.rename(columns={"place_server": "bar_server"})


def within_log(py: pd.DataFrame, log: pd.DataFrame) -> pd.DataFrame:
    """Python's trades inside the period the log covers (its first to last bar)."""
    bars = log.loc[log["bar_server"] != "", "bar_server"]
    return py[(py["bar_server"] >= bars.min()) & (py["bar_server"] <= bars.max())]


# --- v1 on FxPro's GOLD feed ---------------------------------------------------------------------

FX_TRADES = gl.STORE / "gold_fxpro_trades.parquet"
FX_FILE = "gold_fxpro_trades.csv"
FX_REPORT = gl.OUT_DIR / "gold_fxpro.md"
# FxPro's GOLD history is daily bars to 2015-09-10, hourly bars to 2016-01-08 15:00, M1 from
# 2016-01-08 15:16, with the spread recorded as 0 to 2016-01-18 15:48 (server time). v1 reads the
# lines from the first full day with M1 bars and spreads, and trades from 2016-02-01, when its
# 5-day levels and ATR(14, 4h) have filled.
FX_FIRST_DAY = b"2016.01.19"
FX_START = pd.Timestamp("2016-02-01", tz="UTC")


def fx_lines(export: Path):
    """The export's header and its lines from ``FX_FIRST_DAY`` (server date) on."""
    with open(export, "rb") as f:
        yield next(f)
        for ln in f:
            if ln[:10] >= FX_FIRST_DAY:
                yield ln


def fxpro(export: Path) -> str:
    """v1 (the exam's code and settings) on an FxPro GOLD M1 export (MT5 "Export Bars" or
    ``ExportHistory`` with ``GOLD_name = GOLD``): the trades for the check and the result by
    year."""
    fr = ge.frames_from_lines(fx_lines(export))  # a parse of GOLD's own feed, not a lockbox read
    zero = int((fr["5m"]["spread_max"] == 0).sum())  # 5-minute bars with no spread recorded
    t, events, cx = ge.exam_trades(fr, start=FX_START)
    t.to_parquet(FX_TRADES, index=False)
    gc.trade_file(t, events, cx, gl.STORE / FX_FILE)
    placed = pd.to_datetime(cx.m["ts_utc"].to_numpy()[t["i"]], utc=True)
    exam = t[placed >= ge.EXAM_START]

    def row(name: str, g: pd.DataFrame) -> str:
        se = g["net"].std(ddof=1) / np.sqrt(max(len(g), 2))
        return (f"| {name} | {len(g):,} | {g['net'].mean():+.3f} ({se:.3f}) "
                f"| {g['net_slip'].mean():+.3f} |")  # fmt: skip

    lines = [
        "# Gold v1 on FxPro's GOLD feed (Python)",
        "",
        f"_`python -m app research gold-live fxpro`: `{export.name}`, the exam's code and settings "
        "(`GOLD_V1.md`), FxPro's recorded spread + $0.07 per oz. The research used another feed "
        "(XAUUSD); 2016 to 2026-01-09 was seen there, so this is a check of the feed, not a test._",
        "",
        f"_Bars from {FX_FIRST_DAY.decode()} (server date; earlier GOLD history is daily or hourly "
        f"bars, or has no spread), trades from {FX_START.date()}. "
        f"{zero:,} of {len(fr['5m']):,} five-minute bars have no spread recorded._",
        "",
        "| Set | Trades | Net R (SE) | Net with slip |",
        "| --- | --- | --- | --- |",
        row("All", t),
        *[row(k, g) for k, g in t.groupby("strategy")],
        row("Exam period (2026-01-12 on)", exam),
        "",
        "| Year | Trades | Net R (SE) | Net with slip |",
        "| --- | --- | --- | --- |",
        *[row(str(y), g) for y, g in t.groupby("year")],
    ]
    return "\n".join(lines) + "\n"


def check(log: pd.DataFrame, py: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """One row per trade on either side, and the counts."""
    fills = log[log["event"] == "FILL"].copy()
    exits = log[log["event"] == "EXIT"].drop_duplicates("ticket", keep="last")
    deals = log[log["event"] == "DEAL"].groupby("ticket")["price"].sum()
    fills = fills.rename(columns={"kind": "ea_kind"})
    fills["exit_price"] = fills["ticket"].map(exits.set_index("ticket")["price"])
    fills["exit_why"] = fills["ticket"].map(exits.set_index("ticket")["note"])
    fills["ea_gross"] = fills["dir"] * (fills["exit_price"] - fills["entry"]) / fills["risk"]
    money = fills["risk"] * fills["lots"] * CONTRACT
    fills["ea_net"] = fills["ticket"].map(deals) / money
    k = ["strategy", "bar_server"]
    j = py.merge(fills, on=k, how="outer", suffixes=("_py", "_ea"), indicator=True)
    touches = (
        log[log["event"] == "TOUCH"].groupby(k)["note"].agg(lambda s: "; ".join(sorted(set(s))))
    )
    j["ea_reason"] = [
        touches.get((s, b), "") for s, b in zip(j["strategy"], j["bar_server"], strict=True)
    ]
    both = j[j["_merge"] == "both"]
    py_dir = both["dir_py"]
    ea_dir = both["dir_ea"]
    counts = {
        "python": int((j["_merge"] != "right_only").sum()),
        "ea": int((j["_merge"] != "left_only").sum()),
        "matched": len(both),
        "dir_agree": int((np.sign(py_dir) == np.sign(ea_dir)).sum()),
        "level_diff_max": float((both["level_py"] - both["level_ea"]).abs().max())
        if len(both)
        else np.nan,
        "risk_ratio_median": float((both["risk_ea"] / both["risk_py"]).median())
        if len(both)
        else np.nan,
        "risk_off_1pct": int(((both["risk_ea"] / both["risk_py"] - 1).abs() > 0.01).sum()),
        "gross_py": float(both["gross"].mean()) if len(both) else np.nan,
        "gross_ea": float(both["ea_gross"].mean()) if len(both) else np.nan,
        "net_ea_all": float(j["ea_net"].mean()),
        "net_py_all": float(j["net"].mean()),
    }
    return j, counts


def render(j: pd.DataFrame, n: dict, reference: str = "exam") -> str:
    source = (
        "the Python trades of `gold-exam run` (the research XAUUSD feed)"
        if reference == "exam"
        else "v1 in Python on FxPro's GOLD feed (`gold-live fxpro`)"
    )
    only_py = j[j["_merge"] == "left_only"]
    only_ea = j[j["_merge"] == "right_only"]
    lines = [
        "# Gold v1 live EA against Python",
        "",
        f"_`tools/mt5/GoldLive.mq5` in the Strategy Tester over the exam period against {source} "
        "(`GOLD_V1.md`). Matched on strategy and signal bar._",
        "",
        "| Item | Value |",
        "| --- | --- |",
        f"| Python trades | {n['python']} |",
        f"| EA trades | {n['ea']} |",
        f"| Matched | {n['matched']} |",
        f"| Same direction | {n['dir_agree']} |",
        f"| Largest level difference | {n['level_diff_max']:.2f} |",
        f"| D, EA / Python (median) | {n['risk_ratio_median']:.4f} |",
        f"| D off by more than 1% | {n['risk_off_1pct']} |",
        f"| Gross R, matched: Python / EA | {n['gross_py']:+.3f} / {n['gross_ea']:+.3f} |",
        f"| Net R, all: Python / EA | {n['net_py_all']:+.3f} / {n['net_ea_all']:+.3f} |",
        "",
        f"## Python only ({len(only_py)})",
        "",
        "| Strategy | Signal bar (server) | EA's reason |",
        "| --- | --- | --- |",
        *[
            f"| {r.strategy} | {r.bar_server} | {r.ea_reason or '-'} |"
            for r in only_py.itertuples()
        ],
        "",
        f"## EA only ({len(only_ea)})",
        "",
        "| Strategy | Signal bar (server) | Kind | Fill |",
        "| --- | --- | --- | --- |",
        *[
            f"| {r.strategy} | {r.bar_server} | {r.ea_kind} | {r.note} |"
            for r in only_ea.itertuples()
        ],
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-live")
    ap.add_argument("step", choices=("check", "fxpro"))
    ap.add_argument("--log", default="gold_live_log.csv", help="in <Common>/Files")
    ap.add_argument("--reference", choices=("exam", "fxpro"), default="exam",
                    help="check: the exam's trades or v1 on FxPro's GOLD feed")  # fmt: skip
    ap.add_argument("--export", type=Path, help="fxpro: the GOLDFX_M1_*.csv export")
    args = ap.parse_args(argv)
    if args.step == "fxpro":
        FX_REPORT.write_text(fxpro(args.export), encoding="utf-8", newline="\n")
        print(f"wrote {FX_REPORT}")
        return 0
    log = read_log(gc.common_files() / args.log)
    j, n = check(log, within_log(python_trades(args.reference), log))
    REPORT.write_text(render(j, n, args.reference), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}: {n}")
    return 0
