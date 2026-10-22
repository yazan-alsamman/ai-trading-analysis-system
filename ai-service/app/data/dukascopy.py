"""Dukascopy M1 sample for the P1 cross-check (bid candles, UTC).

    python -m app dukascopy download              # the sample below, every instrument in the store
    python -m app dukascopy download --symbol XAUUSD

The sample was fixed before any file was looked at: for every year of each instrument's FxPro
history up to 2025, the first full Monday-Friday week of February, May, August and November, plus
the two days of the longest FxPro holes (2024-07-02 and 2025-07-02). No date on or after the
lockbox start is ever requested.

Files come from Dukascopy's public datafeed, one per day:
``https://datafeed.dukascopy.com/datafeed/<SYMBOL>/<YYYY>/<MM-1>/<DD>/BID_candles_min_1.bi5``,
LZMA-compressed records of 24 bytes (big-endian): seconds since 00:00 UTC, open, close, low, high
(integers, price × ``PRICE_SCALE``) and volume (float). They are cached as downloaded under
``data/dukascopy/<SYMBOL>/`` (untracked) and only decoded with the standard library."""

from __future__ import annotations

import argparse
import lzma
import struct
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import instruments, splits
from app.data.importer import DEFAULT_OUT as STORE

CACHE = Path(__file__).resolve().parents[2] / "data" / "dukascopy"
URL = "https://datafeed.dukascopy.com/datafeed/{symbol}/{y}/{m:02d}/{d:02d}/BID_candles_min_1.bi5"
PRICE_SCALE = {"XAUUSD": 1e3, "USDJPY": 1e3}  # others 1e5
SAMPLE_MONTHS = (2, 5, 8, 11)
EXTRA_DAYS = (date(2024, 7, 2), date(2025, 7, 2))
LAST_YEAR = 2025
REQUESTS_PER_SECOND = 4
RECORD = struct.Struct(">5if")


class LockboxError(RuntimeError):
    """A request would fetch data from the lockbox period."""


def first_full_week(year: int, month: int) -> list[date]:
    d = date(year, month, 1)
    while d.weekday() != 0:  # Monday
        d += timedelta(days=1)
    return [d + timedelta(days=k) for k in range(5)]


def sample_days(first_year: int) -> list[date]:
    days = [
        d
        for y in range(first_year, LAST_YEAR + 1)
        for m in SAMPLE_MONTHS
        for d in first_full_week(y, m)
    ]
    days += [d for d in EXTRA_DAYS if d.year >= first_year]
    return sorted(set(days))


def url(symbol: str, day: date) -> str:
    if day >= splits().lockbox_start:
        raise LockboxError(f"{day} is in the lockbox period; it is never downloaded")
    return URL.format(symbol=symbol, y=day.year, m=day.month - 1, d=day.day)


def decode(raw: bytes, symbol: str, day: date) -> pd.DataFrame:
    """One day's M1 bid bars (UTC open time) from a .bi5 file; empty for a day without data."""
    cols = ["ts_utc", "open", "high", "low", "close", "volume"]
    if not raw:
        return pd.DataFrame({c: [] for c in cols})
    data = lzma.decompress(raw)
    if len(data) % RECORD.size:
        raise ValueError(f"{symbol} {day}: {len(data)} bytes is not a whole number of records")
    rec = np.array(list(RECORD.iter_unpack(data)), dtype="float64").reshape(-1, 6)
    scale = PRICE_SCALE.get(symbol, 1e5)
    start = pd.Timestamp(day, tz="UTC")
    return pd.DataFrame(
        {
            "ts_utc": (start + pd.to_timedelta(rec[:, 0], unit="s")).as_unit("ns"),
            "open": rec[:, 1] / scale,
            "close": rec[:, 2] / scale,
            "low": rec[:, 3] / scale,
            "high": rec[:, 4] / scale,
            "volume": rec[:, 5],
        }
    )[cols]


def _get(address: str, attempts: int = 4) -> bytes:
    req = urllib.request.Request(address, headers={"User-Agent": "ai-service-research/1"})
    for k in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b""
            if k == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if k == attempts - 1:
                raise
        time.sleep(2 * (k + 1))
    return b""


def path(symbol: str, day: date, cache: Path = CACHE) -> Path:
    return cache / symbol / f"{day.isoformat()}.bi5"


def download(symbol: str, days: list[date], cache: Path = CACHE) -> dict:
    fetched = cached = 0
    for day in days:
        target = path(symbol, day, cache)
        if target.exists():
            cached += 1
            continue
        raw = _get(url(symbol, day))
        decode(raw, symbol, day)  # refuse a file that does not decode before keeping it
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(raw)
        tmp.replace(target)
        fetched += 1
        time.sleep(1 / REQUESTS_PER_SECOND)
    return {"days": len(days), "fetched": fetched, "cached": cached}


def load(symbol: str, days: list[date], cache: Path = CACHE) -> pd.DataFrame:
    frames = [
        decode(path(symbol, d, cache).read_bytes(), symbol, d)
        for d in days
        if path(symbol, d, cache).exists()
    ]
    return pd.concat(frames, ignore_index=True) if frames else decode(b"", symbol, days[0])


def store_first_year(symbol: str, store: Path = STORE) -> int:
    ts = pd.read_parquet(store / symbol / "m1.parquet", columns=["ts_utc"])["ts_utc"]
    return int(ts.iloc[0].year)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)
    d = sub.add_parser("download", help="fetch the cross-check sample")
    d.add_argument("--symbol", action="append")
    d.add_argument("--store", type=Path, default=STORE)
    d.add_argument("--cache", type=Path, default=CACHE)
    c = sub.add_parser("compare", help="FxPro vs Dukascopy report")
    c.add_argument("--symbol", action="append")
    c.add_argument("--store", type=Path, default=STORE)
    c.add_argument("--cache", type=Path, default=CACHE)
    args = ap.parse_args(argv)
    symbols = args.symbol or sorted(
        p.parent.name for p in args.store.glob("*/import.json") if p.parent.name in instruments()
    )
    if args.command == "download":
        for symbol in symbols:
            r = download(symbol, sample_days(store_first_year(symbol, args.store)), args.cache)
            print(f"{symbol}: {r}", flush=True)
        return 0
    from app.data.crosscheck import main as compare

    return compare(symbols, args.store, args.cache)


if __name__ == "__main__":
    sys.exit(main())
