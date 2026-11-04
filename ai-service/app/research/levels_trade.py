"""Addendum 2, H_L2: the level-break trade in the MT5 Strategy Tester
(docs/strategies/ADDENDUM_2_LEVEL_BREAK.md, sections 3 and 5).

    python -m app research levels-trade export     # the trades for tools/mt5/LevelBreak.mq5
    python -m app research levels-trade compare    # after the six tester runs; once

**Trades** (section 3): every real-level touch of the H_L1 reading (``levels_confirm.touches``, the
same store, rules and seed). A stop order at the level in the direction of approach (buy stop from
below, sell stop from above), placed at the open of the touch bar and valid to its close; SL =
level -/+ D, TP = level +/- D; closed at market at the close of the 48th bar after the touch bar.
Times go to the EA on the server clock (Europe/Athens: the store has no clock correction after
2017).

An instrument may be run in parts of the period (``Part`` in the EA); the results are merged,
and the comparison is refused while any trade has no tester result.

**Decision** (section 5): x = net R in the tester ((profit + commission + fee + swap) / the money
risk of the level and SL), T1 (percentile) and T2 (t with K - 1 df) on 4-week blocks from
2018-01-01, B = 20,000, seed 20261104, p = max(p1, p2) < 0.05 one-sided, K >= 30. The Deflated
Sharpe is reported with N = 60. Writes ``docs/strategies/levels_trade.md``; refused if it exists."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import decide
from app.research import levels_confirm as lc
from app.research.meta import deflated_sharpe

SERVER_TZ = "Europe/Athens"
TRADES_FILE = "levels_trades.csv"
RESULT_GLOB = "levels_replay_*.csv"
REPORT = lc.OUT_DIR / "levels_trade.md"
N_DSR = 60
COLUMNS = ["id", "symbol", "kind", "dir", "place_server", "expire_server", "exit_server", "level",
           "sl", "tp", "d"]  # fmt: skip


def common_files() -> Path | None:
    appdata = os.environ.get("APPDATA")
    p = Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files" if appdata else None
    return p if p is not None and p.is_dir() else None


def server(ts: pd.Series) -> pd.Series:
    """UTC to the server clock, naive."""
    return pd.to_datetime(ts, utc=True).dt.tz_convert(SERVER_TZ).dt.tz_localize(None)


def trades(frames: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """The section 3 trades of every real-level touch, oldest first."""
    rng = np.random.default_rng(lc.SEED)  # as the H_L1 reading: the same touches
    out = []
    for sym in lc.INSTRUMENTS:
        fr = frames[sym]
        m = fr["5m"]
        e = lc.touches(fr, sym, lc.STEP[sym], rng)
        e = e[~e["placebo"]]
        i = e["i"].to_numpy()
        h1 = fr["1h"]
        a1 = lc.wilder(*(h1[k].to_numpy() for k in ("high", "low", "close")))
        k1 = np.searchsorted(h1["close_utc"].to_numpy(), m["ts_utc"].to_numpy()[i], "right") - 1
        d = a1[k1]
        s = np.where(e["up"].to_numpy(), 1.0, -1.0)
        lv = e["lv"].to_numpy()
        out.append(pd.DataFrame({
            "symbol": sym, "kind": e["kind"].to_numpy(), "dir": np.where(s > 0, "buy", "sell"),
            "place_utc": m["ts_utc"].to_numpy()[i], "expire_utc": m["close_utc"].to_numpy()[i],
            "exit_utc": m["close_utc"].to_numpy()[i + lc.HZ], "level": lv, "sl": lv - s * d,
            "tp": lv + s * d, "d": d, "outcome": e["outcome"].to_numpy(),
        }))  # fmt: skip
    t = pd.concat(out, ignore_index=True)
    for c in ("place_utc", "expire_utc", "exit_utc"):
        t[c] = pd.to_datetime(t[c], utc=True)
    t = t.sort_values(["place_utc", "symbol", "kind"]).reset_index(drop=True)
    t["id"] = np.arange(1, len(t) + 1)
    for c in ("place", "expire", "exit"):
        t[f"{c}_server"] = server(t[f"{c}_utc"])
    return t


def write_trades(t: pd.DataFrame, path: Path) -> None:
    out = t[COLUMNS].copy()
    for c in ("place_server", "expire_server", "exit_server"):
        out[c] = out[c].dt.strftime("%Y.%m.%d %H:%M:%S")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, float_format="%.8f", lineterminator="\r\n")


RANK = {"closed": 0, "expired": 1, "failed": 2, "open_at_end": 3, "pending_at_end": 4,
        "not_reached": 5}  # fmt: skip


def merged(files: list[Path]) -> pd.DataFrame:
    """The tester results of every run, one row per trade: a run over part of the period leaves
    the other trades not reached, so the most advanced status of each trade is kept."""
    res = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    res = res.assign(rank=res["status"].map(RANK).fillna(9))
    return res.sort_values(["id", "rank"]).drop_duplicates("id").drop(columns="rank")


def joined(t: pd.DataFrame, res: pd.DataFrame) -> pd.DataFrame:
    j = t.merge(res, on="id", how="left")
    done = j["status"] == "closed"
    money = j["risk_money"].where(j["risk_money"] > 0)
    j["x"] = ((j["profit"] + j["commission"] + j["fee"] + j["swap"]) / money).where(done)
    j["cost"] = (-(j["commission"] + j["fee"]) / money).where(done)
    return j


def h_l2(j: pd.DataFrame, boot: int = lc.B) -> dict:
    """The section 5 test on the closed trades."""
    x = j.dropna(subset=["x"])
    rng = np.random.default_rng(lc.SEED)
    (star,), k = decide.bootstrap([x["x"].to_numpy()], decide.block_ids(x["place_utc"]), boot, rng)
    mean = float(x["x"].mean())
    p1, p2 = decide.p_percentile(star), decide.p_wald(mean, star, k)
    p = max(p1, p2)
    ok = k >= decide.MIN_BLOCKS
    lo, hi = np.percentile(star, [2.5, 97.5])
    passed = ok and p < decide.ALPHA and mean > 0
    return {"n": len(x), "k": k, "mean": mean, "lo": lo, "hi": hi, "p1": p1, "p2": p2, "p": p,
            "method_ok": ok, "passed": passed,
            "dsr": deflated_sharpe(x["x"].to_numpy(), N_DSR)}  # fmt: skip


def render(j: pd.DataFrame, r: dict, run_date: str) -> str:
    x = j.dropna(subset=["x"])
    status = j["status"].fillna("missing").value_counts()
    result = ("confirmed out of sample: L-BRK enters the forward paper log as exploratory"
              if r["passed"] else "mechanism confirmed, no net edge")  # fmt: skip
    dsr = r["dsr"]
    lines = [
        "# Addendum 2: the level-break trade in the MT5 Strategy Tester (H_L2)",
        "",
        f"_Generated by `python -m app research levels-trade compare` on {run_date}, once. Trades "
        "of every real-level touch of the H_L1 reading (`levels_confirm.md`), replayed by "
        "`tools/mt5/LevelBreak.mq5` with stop orders at the level, on real ticks with the "
        "account's spread and commission. Rules: `ADDENDUM_2_LEVEL_BREAK.md` sections 3 and 5._",
        "",
        "## Decision (section 5)",
        "",
        "| Trades | Blocks K | Mean net R (95%) | p1 / p2 | p | Method condition | Result |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| {r['n']:,} | {r['k']} | {r['mean']:+.4f} ({r['lo']:+.4f} to {r['hi']:+.4f}) "
        f"| {r['p1']:.4f} / {r['p2']:.4f} | {r['p']:.4f} "
        f"| {'met' if r['method_ok'] else 'not met'} "
        f"| {'passed' if r['passed'] else 'not passed'} |",
        "",
        f"H_L1 passed (`levels_confirm.md`), so: **{result}.**",
        "",
        f"Deflated Sharpe (N = {N_DSR}): per-trade Sharpe {dsr['sharpe']:+.4f}, expected maximum "
        f"{dsr['sr0']:+.4f}, DSR {dsr['dsr']:.4f}.",
        "",
        "## Replay",
        "",
        "| Status | Trades |",
        "| --- | --- |",
        *[f"| {k} | {v:,} |" for k, v in status.items()],
        "",
        "## Reported, not decided on",
        "",
        "| Instrument | Trades | Mean net R | Commission in R | TP | SL | Time exit |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s, g in [*x.groupby("symbol", sort=False), ("All", x)]:
        mix = g["close_reason"].value_counts(normalize=True)
        lines.append(f"| {s} | {len(g):,} | {g['x'].mean():+.4f} | {g['cost'].mean():.4f} "
                     f"| {mix.get('tp', 0):.0%} | {mix.get('sl', 0):.0%} "
                     f"| {mix.get('time', 0):.0%} |")  # fmt: skip
    lines += ["", "| Level | Trades | Mean net R |", "| --- | --- | --- |"]
    lines += [f"| {k} | {len(g):,} | {g['x'].mean():+.4f} |" for k, g in x.groupby("kind")]
    lines += ["", "| Year | Trades | Mean net R |", "| --- | --- | --- |"]
    lines += [f"| {y} | {len(g):,} | {g['x'].mean():+.4f} |"
              for y, g in x.groupby(x["place_utc"].dt.year)]  # fmt: skip
    twice = (x["x"] - x["cost"]).mean()
    lines += ["", f"At twice the commission: mean net R {twice:+.4f} (the spread is not doubled)."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research levels-trade")
    ap.add_argument("step", choices=("export", "compare"))
    ap.add_argument("--store", type=Path, default=lc.STORE)
    ap.add_argument("--results", type=Path, default=None)
    args = ap.parse_args(argv)
    if not lc.REPORT.exists():
        print("refused: the H_L1 reading (levels_confirm.md) comes first", file=sys.stderr)
        return 2
    t = trades(lc.load(args.store))
    common = common_files()
    if args.step == "export":
        targets = [args.store / TRADES_FILE, *([common / TRADES_FILE] if common else [])]
        for p in targets:
            write_trades(t, p)
            print(f"wrote {p}")
        print(f"{len(t):,} trades:", t.groupby("symbol", sort=False).size().to_dict())
        return 0
    if REPORT.exists():
        print(f"refused: {REPORT.name} exists; H_L2 is judged once", file=sys.stderr)
        return 2
    folder = args.results or common
    files = sorted(folder.glob(RESULT_GLOB)) if folder else []
    res = merged(files) if files else pd.DataFrame(columns=["id", "status"])
    j = joined(t, res)
    left = j[~j["status"].isin(["closed", "expired", "failed"])]
    if len(left):
        print(f"refused: {len(left):,} trades without a tester result:",
              left.groupby("symbol").size().to_dict(), file=sys.stderr)  # fmt: skip
        return 2
    r = h_l2(j)
    REPORT.write_text(render(j, r, pd.Timestamp.now(tz="UTC").date().isoformat()),
                      encoding="utf-8", newline="\n")  # fmt: skip
    print(f"wrote {REPORT}")
    return 0
