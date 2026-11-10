"""Gold demo: the live account's trades against Python on the same days (``GOLD_V1.md``, the demo).

    python -m app research gold-demo check --report <ReportHistory-*.html> --export <GOLD M1 csv>
        [--start 2026-11-10]

The EA runs on a MetaTrader VPS, so its log file stays there. This check reads what the account
itself records instead:

- ``--report``: the account history report (MT5: History tab, right click, Report, HTML). Its
  Positions, Orders and Deals tables give each trade's strategy (the order comment the EA writes,
  "LVL4H PDL"), side, level (the stop order's price), first SL, lots, fill, exit and money.
- ``--export``: a fresh FxPro GOLD M1 export (``ExportHistory`` or "Export Bars") starting at
  least three weeks before ``--start``, so the 5-day levels and the ATRs have filled. Python runs
  the five strategies on it exactly as ``gold-live fxpro`` does.

Matched on strategy and signal bar (the 5-minute bar of the fill, server time). Reports: matches,
level and distance D, gross R both sides, the demo's net R from its own money, the entry
slippage, and where each strategy stands against the demo's stop rules (100 trades, then every
50, mean net R below -0.10). Writes ``gold_demo_check.md``."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv

REPORT = gl.OUT_DIR / "gold_demo_check.md"
STRATEGIES = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")
SERVER_TZ = "Europe/Athens"
STOP_AT, STOP_EVERY, STOP_LINE = 100, 50, -0.10
WARM = pd.Timedelta(days=21)


# --- the account history report (MT5 HTML, UTF-16) -------------------------------------------


class _Cells(HTMLParser):
    """Every table row as a list of (text, hidden) cells."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, bool]]] = []
        self._row: list[tuple[str, bool]] | None = None
        self._cell: list[str] | None = None
        self._hidden = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell, self._hidden = [], "hidden" in (dict(attrs).get("class") or "")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append((" ".join("".join(self._cell).split()), self._hidden))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _decode(raw: bytes) -> str:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8", errors="replace")


def report_tables(text: str) -> dict[str, pd.DataFrame]:
    """The Positions, Orders and Deals tables (all text). Hidden cells are dropped, except that a
    hidden cell in a data row without one in its header (the Positions comment) becomes Comment."""
    p = _Cells()
    p.feed(text)
    out: dict[str, pd.DataFrame] = {}
    rows, k = p.rows, 0
    while k < len(rows):
        texts = [c for c, _ in rows[k] if c]
        if len(texts) == 1 and texts[0] in ("Positions", "Orders", "Deals") and k + 1 < len(rows):
            name = texts[0]
            head, seen = [], {}
            for c, hid in rows[k + 1]:
                if hid:
                    continue
                n = seen.get(c, 0)
                seen[c] = n + 1
                head.append(c if n == 0 else f"{c}_{n + 1}")
            data = []
            k += 2
            while k < len(rows) and any(c for c, _ in rows[k]):
                cells = rows[k]
                shown = [c for c, hid in cells if not hid]
                extra = " ".join(c for c, hid in cells if hid and c)
                if len(shown) >= len(head):
                    rec = dict(zip(head, shown[: len(head)], strict=True))
                    if "Comment" not in rec:
                        rec["Comment"] = extra
                    data.append(rec)
                k += 1
            out[name] = pd.DataFrame(data)
            continue
        k += 1
    return out


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(" ", "").str.replace(" ", ""), errors="coerce")


def demo_trades(tables: dict[str, pd.DataFrame], symbol: str = "GOLD") -> pd.DataFrame:
    """One row per closed EA position: strategy, kind, dir, bar_server, level (the stop order's
    price; NaN for a market entry), fill, first SL, D, lots, exit price and time, exit (sl / ea),
    net money, gross R (from the level, as Python) and net R (money over D x lots x 100)."""
    pos, orders, deals = tables["Positions"], tables["Orders"], tables.get("Deals")
    pos = pos[pos["Symbol"] == symbol].copy()
    first = pos["Comment"].str.split().str[0]
    pos = pos[first.isin(STRATEGIES)].copy()
    if pos.empty:
        return pd.DataFrame()
    o = orders.set_index("Order")
    pos["strategy"] = pos["Comment"].str.split().str[0]
    pos["kind"] = pos["Comment"].str.split().str[1:].str.join(" ")
    pos["dir"] = np.where(pos["Type"].str.lower().str.startswith("buy"), 1, -1)
    pos["lots"] = _num(pos["Volume"])
    pos["fill"] = _num(pos["Price"])
    pos["exit_price"] = _num(pos["Price_2"])
    pos["exit_server"] = pos["Time_2"]
    oprice = _num(pos["Position"].map(o["Price"]))
    pos["level"] = oprice  # "market" parses as NaN
    pos["sl0"] = _num(pos["Position"].map(o["S / L"]))
    e = pos["level"].fillna(pos["fill"])
    pos["risk"] = pos["dir"] * (e - pos["sl0"])
    pos["money"] = _num(pos["Profit"]) + _num(pos["Commission"]) + _num(pos["Swap"])
    pos["gross"] = pos["dir"] * (pos["exit_price"] - e) / pos["risk"]
    pos["net"] = pos["money"] / (pos["risk"] * pos["lots"] * gv.CONTRACT)
    pos["slip"] = pos["dir"] * (pos["fill"] - e)  # $ worse than the level (stop entries)
    ts = pd.to_datetime(pos["Time"], format="%Y.%m.%d %H:%M:%S")
    pos["opened"] = ts
    pos["bar_server"] = ts.dt.floor("5min").dt.strftime("%Y.%m.%d %H:%M:%S")
    pos["exit"] = "ea"
    if deals is not None and len(deals):
        outs = deals[deals["Direction"].str.lower() == "out"]
        sl = outs["Comment"].str.lower().str.lstrip("[").str.startswith("sl")
        hit = set(zip(outs.loc[sl, "Time"], _num(outs.loc[sl, "Price"]).round(2), strict=True))
        key = zip(pos["Time_2"], pos["exit_price"].round(2), strict=True)
        pos["exit"] = ["sl" if k in hit else "ea" for k in key]
    cols = ["strategy", "kind", "dir", "bar_server", "opened", "level", "fill", "sl0", "risk",
            "lots", "exit_price", "exit_server", "exit", "money", "gross", "net",
            "slip"]  # fmt: skip
    return pos[cols].sort_values("opened", kind="stable").reset_index(drop=True)


# --- Python on the same days --------------------------------------------------------------------


def python_trades(export: Path, start: pd.Timestamp) -> tuple[pd.DataFrame, pd.Timestamp]:
    """The five strategies on the export, placed from ``start``; and the server time up to which
    both sides are complete (the start of the export's last server day)."""
    fr = ge.frames_from_lines(gv.fx_lines(export))
    _, every, _, cx = gv.five_trades(fr, start=start)
    u = pd.to_datetime(cx.m["ts_utc"].to_numpy()[every["i"]], utc=True)
    every["bar_server"] = u.tz_convert(SERVER_TZ).tz_localize(None).strftime("%Y.%m.%d %H:%M:%S")
    first = pd.Timestamp(cx.m["ts_utc"].iloc[0]).tz_convert(SERVER_TZ).tz_localize(None)
    if first > start.tz_convert(SERVER_TZ).tz_localize(None) - WARM:
        raise SystemExit(f"the export starts {first}: it must start 3 weeks before {start.date()}")
    last = pd.Timestamp(cx.m["ts_utc"].iloc[-1]).tz_convert(SERVER_TZ).tz_localize(None)
    return every, last.normalize()


# --- the check ----------------------------------------------------------------------------------


def match(py: pd.DataFrame, demo: pd.DataFrame) -> pd.DataFrame:
    k = ["strategy", "bar_server"]
    keep = ["strategy", "bar_server", "dir", "level", "risk", "gross", "net", "net_slip", "exit"]
    return py[keep].merge(demo, on=k, how="outer", suffixes=("_py", "_demo"), indicator=True)


def stop_status(demo: pd.DataFrame) -> list[tuple[str, int, float, str]]:
    """Per strategy and for all: trades, mean net R and the stop rules' reading."""
    out = []
    for name, g in [*((s, demo[demo["strategy"] == s]) for s in STRATEGIES), ("All", demo)]:
        n, m = len(g), float(g["net"].mean()) if len(g) else np.nan
        if n < STOP_AT:
            state = f"first check at {STOP_AT} ({STOP_AT - n} to go)"
        else:
            last = STOP_AT + (n - STOP_AT) // STOP_EVERY * STOP_EVERY
            at = float(g["net"].iloc[:last].mean())
            state = (f"checked at {last}: {at:+.3f} -> "
                     + ("**below -0.10: stop**" if at < STOP_LINE else "keep"))  # fmt: skip
        out.append((name, n, m, state))
    return out


def render(j: pd.DataFrame, demo: pd.DataFrame, meta: dict) -> str:
    both = j[j["_merge"] == "both"]
    only_py, only_demo = j[j["_merge"] == "left_only"], j[j["_merge"] == "right_only"]

    def mean(s: pd.Series) -> str:
        return f"{s.mean():+.3f}" if len(s) else "-"

    level_diff = (both["level_py"] - both["level_demo"]).abs().max()
    d_ratio = (both["risk_demo"] / both["risk_py"]).median()

    lines = [
        "# Gold demo against Python",
        "",
        f"_`python -m app research gold-demo check`: `{meta['report']}` against the five "
        f"strategies in Python on `{meta['export']}` (FxPro GOLD). Trades placed {meta['start']} "
        f"to {meta['end']} (server time). Matched on strategy and the 5-minute bar of the fill._",
        "",
        "| Item | Value |",
        "| --- | --- |",
        f"| Python trades | {(j['_merge'] != 'right_only').sum()} |",
        f"| Demo trades | {(j['_merge'] != 'left_only').sum()} |",
        f"| Matched | {len(both)} |",
        f"| Same direction | {int((both['dir_py'] == both['dir_demo']).sum())} |",
        f"| Largest level difference ($) | {level_diff:.2f} |",
        f"| D, demo / Python (median) | {d_ratio:.4f} |",
        f"| Gross R, matched: Python / demo | {mean(both['gross_py'])} / "
        f"{mean(both['gross_demo'])} |",
        f"| Net R, all: Python / demo | {mean(j['net_py'].dropna())} / "
        f"{mean(j['net_demo'].dropna())} |",
        f"| Entry slippage, stop fills ($, mean / worst) | {demo['slip'].mean():+.2f} / "
        f"{demo['slip'].max():+.2f} |",
        "",
        "| Strategy | Python | Demo | Matched | Gross R matched, Python / demo "
        "| Net R, Python / demo |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in STRATEGIES:
        g = j[j["strategy"] == s]
        b = g[g["_merge"] == "both"]
        lines.append(
            f"| {s} | {(g['_merge'] != 'right_only').sum()} | {(g['_merge'] != 'left_only').sum()} "
            f"| {len(b)} | {mean(b['gross_py'])} / {mean(b['gross_demo'])} "
            f"| {mean(g['net_py'].dropna())} / {mean(g['net_demo'].dropna())} |"
        )
    lines += [
        "",
        "## The stop rules (`GOLD_V1.md`): demo trades, mean net R",
        "",
        "| Strategy | Demo trades | Mean net R | Reading |",
        "| --- | --- | --- | --- |",
        *[
            f"| {n} | {c} | {m:+.3f} | {st} |" if c else f"| {n} | 0 | - | {st} |"
            for n, c, m, st in stop_status(demo)
        ],
        "",
        f"## Python only ({len(only_py)})",
        "",
        "| Strategy | Signal bar (server) | Dir | Level |",
        "| --- | --- | --- | --- |",
        *[
            f"| {r.strategy} | {r.bar_server} | {int(r.dir_py):+d} | {r.level_py:.2f} |"
            for r in only_py.itertuples()
        ],
        "",
        f"## Demo only ({len(only_demo)})",
        "",
        "| Strategy | Signal bar (server) | Kind | Dir | Fill | Net R |",
        "| --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.strategy} | {r.bar_server} | {r.kind} | {int(r.dir_demo):+d} | {r.fill:.2f} "
            f"| {r.net_demo:+.3f} |"
            for r in only_demo.itertuples()
        ],
        "",
        "## Every demo trade",
        "",
        "| Opened (server) | Strategy | Kind | Dir | Level | Fill | D | Lots | Exit | Gross R "
        "| Net R | Money |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.opened:%Y.%m.%d %H:%M:%S} | {r.strategy} | {r.kind} | {int(r.dir):+d} "
            f"| {r.level:.2f} | {r.fill:.2f} | {r.risk:.2f} | {r.lots:.2f} | {r.exit} "
            f"| {r.gross:+.3f} | {r.net:+.3f} | {r.money:+.2f} |"
            for r in demo.itertuples()
        ],
    ]
    return "\n".join(lines) + "\n"


def check(report: Path, export: Path, start: pd.Timestamp) -> str:
    demo = demo_trades(report_tables(_decode(report.read_bytes())))
    py, end = python_trades(export, start)
    s0 = start.tz_convert(SERVER_TZ).tz_localize(None)
    if len(demo):
        demo = demo[(demo["opened"] >= s0) & (demo["opened"] < end)].reset_index(drop=True)
    py = py[pd.to_datetime(py["bar_server"], format="%Y.%m.%d %H:%M:%S") < end]
    j = match(py, demo if len(demo) else pd.DataFrame(columns=["strategy", "bar_server"]))
    meta = {"report": report.name, "export": export.name, "start": f"{s0:%Y-%m-%d %H:%M}",
            "end": f"{end:%Y-%m-%d %H:%M}"}  # fmt: skip
    return render(j, demo, meta)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-demo")
    ap.add_argument("step", choices=("check",))
    ap.add_argument("--report", type=Path, required=True, help="MT5 history report (HTML)")
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    ap.add_argument("--start", default="2026-11-10", help="first demo day (UTC date)")
    args = ap.parse_args(argv)
    text = check(args.report, args.export, pd.Timestamp(args.start, tz="UTC"))
    REPORT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
