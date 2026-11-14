"""The economic calendar for family F3 (``docs/discovery/PLAN.md``, stage D1).

    python -m app discovery calendar --file <Common>/Files/calendar_history.csv

Reads the export of ``tools/mt5/ExportCalendar.mq5`` (cp1252 text). MT5 gives every calendar
time at the server's offset at export time, so the export's ``time_utc`` column is the true UTC
and ``time_server`` is not used. Writes ``data/processed/calendar.parquet`` and
``docs/discovery/calendar_check.md``: the New York times of the main US releases, and the NFP
dates against the BLS rule (``gold_shadow.nfp_days``). No market data is read."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "data" / "processed" / "calendar.parquet"
REPORT = ROOT / "docs" / "discovery" / "calendar_check.md"
NY = "America/New_York"
CHECK = {  # event: expected New York time
    "Nonfarm Payrolls": "08:30",
    "CPI m/m": "08:30",
    "Core CPI m/m": "08:30",
    "GDP q/q": "08:30",
    "Retail Sales m/m": "08:30",
    "Core PCE Price Index m/m": "08:30",
    "Initial Jobless Claims": "08:30",
    "ISM Manufacturing PMI": "10:00",
    "Fed Interest Rate Decision": "14:00",
}


def read(path: Path) -> pd.DataFrame:
    c = pd.read_csv(path, encoding="cp1252")
    out = pd.DataFrame({
        "ts_utc": pd.to_datetime(c["time_utc"], format="%Y.%m.%d %H:%M:%S").dt.tz_localize("UTC"),
        "currency": c["currency"], "country": c["country"], "event": c["event"],
        "importance": c["importance"].astype(int), "impact": c["impact"].astype(int),
        "actual": c["actual"], "forecast": c["forecast"], "previous": c["previous"],
        "revised": c["revised"], "event_id": c["event_id"], "value_id": c["value_id"],
    })  # fmt: skip
    out["surprise"] = out["actual"] - out["forecast"]
    return out.sort_values("ts_utc", kind="stable").reset_index(drop=True)


def check(c: pd.DataFrame) -> str:
    from app.research import gold_shadow as gs

    usd = c[c["currency"] == "USD"]
    ny = usd["ts_utc"].dt.tz_convert(NY)
    lines = [
        "# The economic calendar: checks (stage D1)",
        "",
        f"_`python -m app discovery calendar`: {len(c):,} releases, "
        f"{c['ts_utc'].min():%Y-%m-%d} to {c['ts_utc'].max():%Y-%m-%d}, "
        + ", ".join(f"{k} {v:,}" for k, v in c["currency"].value_counts().items())
        + ". Importance 3 (high): "
        + f"{(c['importance'] == 3).sum():,}. No market data read._",
        "",
        "## 1. New York times of the main US releases (from `time_utc`)",
        "",
        "| Event | Releases | Expected | At the expected time | Other times |",
        "| --- | --- | --- | --- | --- |",
    ]
    for ev, want in CHECK.items():
        m = (usd["event"] == ev).to_numpy()
        hm = ny[m].dt.strftime("%H:%M")
        other = hm[hm != want].value_counts().head(4)
        rest = ", ".join(f"{k} ({v})" for k, v in other.items()) or "-"
        lines.append(f"| {ev} | {m.sum():,} | {want} | {(hm == want).mean():.1%} | {rest} |")
    nfp = usd[usd["event"] == "Nonfarm Payrolls"]
    cal = set(nfp["ts_utc"].dt.tz_convert(NY).dt.strftime("%Y%m%d").astype(int))
    last = max(cal)
    rule = {d for d in gs.nfp_days(min(cal) // 10000, last // 10000) if d <= last}
    lines += [
        "",
        "## 2. NFP dates: the calendar against the BLS rule",
        "",
        f"Calendar {len(cal)}, rule {len(rule)}, both {len(cal & rule)}.",
        "",
        "| Calendar only | Rule only |",
        "| --- | --- |",
    ]
    a, b = sorted(cal - rule), sorted(rule - cal)
    for i in range(max(len(a), len(b))):
        lines.append(f"| {a[i] if i < len(a) else ''} | {b[i] if i < len(b) else ''} |")
    lines += [
        "",
        "The rule ignores holiday moves and shutdowns (`gold_shadow.nfp_days`); the calendar holds "
        "the actual dates (for example the 2013 shutdown: 2013-10-22 and 2013-11-08), so F3 uses "
        "the calendar.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app discovery calendar")
    ap.add_argument("--file", type=Path, required=True, help="calendar_history.csv")
    args = ap.parse_args(argv)
    c = read(args.file)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    c.to_parquet(STORE, index=False)
    REPORT.write_text(check(c), encoding="utf-8", newline="\n")
    print(f"wrote {STORE} ({len(c):,} releases) and {REPORT}")
    return 0
