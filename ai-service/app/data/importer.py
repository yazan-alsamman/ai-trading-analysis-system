"""Import FxPro MT5 history into the research store (Parquet, UTC, closed bars only).

    python -m app import --raw-dir "PATH/TO/history"                # every M1 export found
    python -m app import --raw-dir PATH --symbol XAUUSD --out data/processed

For each instrument: the M1 bars and the 5m, 15m, 1h, 4h and D1 bars built from them, written to
``<out>/<SYMBOL>/<timeframe>.parquet``, plus ``import.json`` with the input (the bytes read before
the lockbox and their SHA-256), the parse counts and a content hash per frame. The store is
research data and is not tracked by git; re-running on the same input rewrites the same values.
Every export is read through ``HistoryExport``, so nothing on or after the lockbox start is read.
Periods stamped on a clock a whole number of hours off ``Europe/Athens`` are detected from the
weekly open and corrected (``app.data.clock``); the segments go into ``import.json``."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import instruments, splits
from app.data import clock
from app.data.aggregate import TIMEFRAMES, aggregate
from app.data.exports import name_fields
from app.data.mt5 import parse_export
from app.data.raw import HistoryExport

IMPORT_VERSION = 2  # 2: clock correction
M1 = pd.Timedelta(minutes=1)
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "data" / "processed"


def content_hash(df: pd.DataFrame) -> str:
    """SHA-256 of a frame's column names, dtypes and values, independent of the file format."""
    h = hashlib.sha256()
    for col in df.columns:
        s = df[col]
        h.update(f"{col}:{s.dtype}\n".encode())
        if isinstance(s.dtype, pd.DatetimeTZDtype):
            h.update(s.dt.as_unit("ns").astype("int64").to_numpy().tobytes())
        else:
            mask = s.isna().to_numpy()
            values = s.astype("float64").to_numpy(na_value=np.nan)
            h.update(np.where(mask, 0.0, values).astype("<f8").tobytes())
            h.update(np.packbits(mask).tobytes())
    return h.hexdigest()


def find_exports(raw_dir: Path) -> dict[str, Path]:
    """The M1 export of each configured instrument in ``raw_dir``, by its MT5 file name."""
    found: dict[str, Path] = {}
    for p in sorted(raw_dir.glob("*.csv")):
        f = name_fields(p.name)
        if f.get("timeframe") == "M1" and f["symbol"] in instruments():
            if f["symbol"] in found:
                raise ValueError(f"two M1 exports of {f['symbol']} in {raw_dir}")
            found[f["symbol"]] = p
    return found


def _write(path: Path, write) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    write(tmp)
    os.replace(tmp, path)


def import_symbol(symbol: str, export_path: Path, out_dir: Path = DEFAULT_OUT) -> dict:
    s = splits()
    export = HistoryExport(export_path)
    parsed = parse_export(export.raw_lines(), instruments()[symbol], M1, s.server_tz)
    if parsed.bars.empty:
        raise ValueError(f"{export_path.name} has no valid bars before the lockbox")
    segments = clock.detect(parsed.bars["ts_utc"], instruments()[symbol], s.server_tz)
    m1 = clock.apply(parsed.bars, segments)
    segments = clock.check_mismatch_weeks(m1, segments, s.server_tz)
    m1 = clock.apply_mismatch_weeks(m1, segments, s.server_tz)
    frames = {"m1": m1} | {tf: aggregate(m1, tf, M1) for tf in TIMEFRAMES}

    record = {
        "import_version": IMPORT_VERSION,
        "symbol": symbol,
        "input": {
            "file": export_path.name,
            "bytes_read": export.bytes_read,
            "sha256_of_bytes_read": export.sha256,
            "lockbox_start": s.lockbox_start.isoformat(),
            "stopped_at_lockbox": export.stopped_at_cutoff,
        },
        "server_tz": s.server_tz,
        "parse": parsed.stats,
        "clock_segments": segments,
        "range_utc": [m1["ts_utc"].iloc[0].isoformat(), m1["ts_utc"].iloc[-1].isoformat()],
        "frames": {
            tf: {"rows": len(df), "content_sha256": content_hash(df)} for tf, df in frames.items()
        },
        "versions": {lib: version(lib) for lib in ("pandas", "pyarrow")},
    }
    for tf, df in frames.items():
        _write(
            out_dir / symbol / f"{tf}.parquet",
            lambda p, df=df: df.to_parquet(p, index=False, engine="pyarrow", compression="zstd"),
        )
    text = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    _write(out_dir / symbol / "import.json", lambda p: p.write_text(text, encoding="utf-8"))
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--raw-dir", type=Path, required=True, help="folder of MT5 M1 history exports")
    ap.add_argument("--symbol", action="append", help="default: every configured symbol found")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    found = find_exports(args.raw_dir)
    symbols = args.symbol or sorted(found)
    missing = [sym for sym in symbols if sym not in found]
    if missing or not symbols:
        print(f"no M1 export for {missing or 'any symbol'} in {args.raw_dir}", file=sys.stderr)
        return 1
    for symbol in symbols:
        r = import_symbol(symbol, found[symbol], args.out)
        p = r["parse"]
        print(
            f"{symbol}: {p['rows_kept']:,} M1 bars kept, {p['rows_rejected']} rejected "
            f"{p['rejected_by_reason']}, {r['range_utc'][0]} -> {r['range_utc'][1]}, "
            f"stopped at lockbox: {r['input']['stopped_at_lockbox']}"
        )
    return 0
