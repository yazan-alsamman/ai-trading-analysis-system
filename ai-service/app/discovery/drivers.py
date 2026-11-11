"""Cross-asset drivers for discovery round 2 (``docs/discovery/PLAN.md``, stage D1).

    python -m app discovery drivers download     # Dukascopy M1: the dollar index and a US bond
    python -m app discovery drivers store        # decode, write the parquet stores, coverage
    python -m app discovery drivers silver --export <XAGUSD M1 csv>   # silver, a feature only

- ``DOLLARIDXUSD`` (the dollar index) and ``USTBONDTRUSD`` (a US Treasury bond CFD; its price
  moves against long yields): every weekday 2018-01-01 to 2026-01-09 from Dukascopy's public
  datafeed (``app.data.dukascopy``, cached under ``data/dukascopy/``). No day on or after the
  lockbox start is requested.
- Silver (``XAGUSD``): FxPro's M1 export, from 2016-01-19 (the first full day with M1 bars and a
  spread), server time converted with Europe/Athens, to 2026-01-09.

Writes ``data/processed/drivers/<SYMBOL>.parquet`` (ts_utc, open, high, low, close) and
``docs/discovery/drivers.md`` (coverage only: no outcome is computed)."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from app.data import dukascopy as dk

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed" / "drivers"
REPORT = ROOT / "docs" / "discovery" / "drivers.md"
DUKAS = ("DOLLARIDXUSD", "USTBONDTRUSD")
FIRST, LAST = date(2018, 1, 1), date(2026, 1, 9)
LOCKBOX = date(2026, 1, 10)
SILVER_FIRST = "2016.01.19"
FAKE_TICKS = 5000  # as gold_live.summary_bar


def weekdays(a: date = FIRST, b: date = LAST) -> list[date]:
    if b >= LOCKBOX:
        raise dk.LockboxError(f"{b} is on or after the lockbox start {LOCKBOX}")
    out, d = [], a
    while d <= b:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


WAITS = (10, 30, 60, 120, 300)  # seconds before each retry when the feed refuses (HTTP 503 ...)


def gentle_download(symbol: str, days: list[date], per_second: float = 1.0) -> dict:
    """Like ``dukascopy.download``, slower, with long back-offs; a day that keeps failing is
    skipped and listed (run again later to fill it), so one refusal does not stop the run."""
    import time

    fetched = cached = 0
    failed: list[date] = []
    for n, day in enumerate(days, 1):
        target = dk.path(symbol, day)
        if target.exists():
            cached += 1
        else:
            raw = None
            for wait in (*WAITS, None):
                try:
                    raw = dk._get(dk.url(symbol, day))
                    break
                except OSError as err:
                    if wait is None:
                        print(f"{symbol} {day}: giving up ({err})", flush=True)
                        break
                    print(f"{symbol} {day}: {err}; waiting {wait} s", flush=True)
                    time.sleep(wait)
            if raw is None:
                failed.append(day)
                continue
            dk.decode(raw, symbol, day)  # refuse a file that does not decode before keeping it
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".tmp")
            tmp.write_bytes(raw)
            tmp.replace(target)
            fetched += 1
            time.sleep(1 / per_second)
        if n % 50 == 0 or n == len(days):
            print(dk._bar(symbol, n, len(days)), flush=True)
    return {"days": len(days), "fetched": fetched, "cached": cached, "failed": len(failed)}


def store_dukas(symbol: str) -> pd.DataFrame:
    m = dk.load(symbol, weekdays())
    # a minute that did not trade repeats the last price with zero volume: keep traded minutes
    m = m[m["volume"] > 0].reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    m[["ts_utc", "open", "high", "low", "close"]].to_parquet(OUT / f"{symbol}.parquet", index=False)
    return m


def store_silver(export: Path) -> pd.DataFrame:
    rows = pd.read_csv(export, sep="\t")
    rows.columns = [c.strip("<>").lower() for c in rows.columns]
    rows = rows[rows["date"] >= SILVER_FIRST]
    # the export's summary bars (gold_live.summary_bar): real volume 0, tick volume above 5,000
    rows = rows[~((rows["vol"] == 0) & (rows["tickvol"] > FAKE_TICKS))]
    srv = pd.to_datetime(rows["date"] + " " + rows["time"], format="%Y.%m.%d %H:%M:%S")
    ts = srv.dt.tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="NaT").dt.tz_convert(
        "UTC"
    )
    m = pd.DataFrame({"ts_utc": ts, "open": rows["open"], "high": rows["high"],
                      "low": rows["low"], "close": rows["close"]}).dropna()  # fmt: skip
    m = m[m["ts_utc"] < pd.Timestamp(LOCKBOX, tz="UTC")].reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    m.to_parquet(OUT / "XAGUSD.parquet", index=False)
    return m


def coverage() -> str:
    lines = [
        "# Discovery drivers: coverage (stage D1)",
        "",
        "_`python -m app discovery drivers store`. Minutes with a traded M1 bar, by year. No "
        "outcome is computed._",
        "",
        "| Driver | First minute | Last minute | " + " | ".join(str(y) for y in range(2016, 2026))
        + " |",
        "| --- | --- | --- |" + " --- |" * 10,
    ]  # fmt: skip
    for sym in ("XAGUSD", *DUKAS):
        p = OUT / f"{sym}.parquet"
        if not p.exists():
            continue
        ts = pd.read_parquet(p, columns=["ts_utc"])["ts_utc"]
        per = ts.dt.year.value_counts()
        cells = [f"{per.get(y, 0):,}" for y in range(2016, 2026)]
        lines.append(f"| {sym} | {ts.min():%Y-%m-%d %H:%M} | {ts.max():%Y-%m-%d %H:%M} | "
                     + " | ".join(cells) + " |")  # fmt: skip
    lines += [
        "",
        "For scale: a full week of a market open about 23 hours a day has about 6,900 minutes, a "
        "year about 355,000.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app discovery drivers")
    ap.add_argument("step", choices=("download", "store", "silver"))
    ap.add_argument("--export", type=Path, help="silver: the XAGUSD M1 export")
    ap.add_argument("--symbol", choices=DUKAS, help="download: one series only")
    ap.add_argument("--reverse", action="store_true", help="download: latest day first")
    args = ap.parse_args(argv)
    if args.step == "download":
        days = weekdays()[::-1] if args.reverse else weekdays()
        for sym in [args.symbol] if args.symbol else DUKAS:
            print(sym, gentle_download(sym, days), flush=True)
    elif args.step == "silver":
        m = store_silver(args.export)
        print(f"XAGUSD: {len(m):,} minutes")
    else:
        for sym in DUKAS:
            print(sym, f"{len(store_dukas(sym)):,} traded minutes")
    REPORT.write_text(coverage(), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
