"""Import MT5 M5 history into the research store and write its data-quality report.

    python -m app.data.importer                      # every <SYMBOL>_M5_mt5.csv in ../data/raw
    python -m app.data.importer --symbol XAUUSD --raw-dir /path/to/raw

Outputs (research side only; ai-service stays stateless in production):

* ``data/processed/<SYMBOL>/{5m,15m,1h,4h}.parquet`` - untracked research store;
* ``docs/data_quality/<SYMBOL>_M5.{md,json}`` - the committed report.

Re-running on the same input rewrites byte-identical outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

from app.data.aggregate import TIMEFRAMES, aggregate
from app.data.mt5 import read_mt5_export
from app.data.quality import build_report, render_markdown
from app.data.schema import INSTRUMENTS, content_hash, file_sha256
from app.data.sessions import SERVER_TZ

SERVICE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = SERVICE_DIR.parent / "data" / "raw"
DEFAULT_OUT_DIR = SERVICE_DIR / "data" / "processed"
DEFAULT_REPORT_DIR = SERVICE_DIR / "docs" / "data_quality"


def _atomic_write(path: Path, write) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    write(tmp)
    os.replace(tmp, path)


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    _atomic_write(
        path, lambda p: df.to_parquet(p, index=False, engine="pyarrow", compression="zstd")
    )


def _write_text(text: str, path: Path) -> None:
    _atomic_write(path, lambda p: p.write_text(text, encoding="utf-8", newline="\n"))


def import_symbol(
    symbol: str,
    raw_file: Path,
    out_dir: Path = DEFAULT_OUT_DIR,
    report_dir: Path = DEFAULT_REPORT_DIR,
    server_tz: str = SERVER_TZ,
    last_bar_closed: bool = False,
) -> dict:
    instrument = INSTRUMENTS[symbol]
    parsed = read_mt5_export(
        raw_file, instrument, server_tz=server_tz, last_bar_closed=last_bar_closed
    )
    m5 = parsed.bars
    if m5.empty:
        raise ValueError(f"{raw_file} has no valid bars")

    frames = {"5m": m5}
    for tf, freq in TIMEFRAMES.items():
        frames[tf] = aggregate(m5, freq, instrument.session)

    hashes = {tf: content_hash(df) for tf, df in frames.items()}
    input_info = {
        "file": raw_file.name,
        "bytes": raw_file.stat().st_size,
        "sha256": file_sha256(raw_file),
    }
    report = build_report(
        m5,
        {tf: df for tf, df in frames.items() if tf != "5m"},
        parsed.stats,
        parsed.rejected,
        instrument,
        input_info,
        hashes,
        server_tz,
    )

    for tf, df in frames.items():
        _write_parquet(df, out_dir / symbol / f"{tf}.parquet")
    stem = report_dir / f"{symbol}_M5"
    _write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", stem.with_suffix(".json"))
    _write_text(render_markdown(report), stem.with_suffix(".md"))
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--symbol", action="append", choices=sorted(INSTRUMENTS), help="default: every export found"
    )
    ap.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = ap.parse_args(argv)

    symbols = args.symbol or [
        s for s in sorted(INSTRUMENTS) if (args.raw_dir / f"{s}_M5_mt5.csv").exists()
    ]
    if not symbols:
        print(f"no <SYMBOL>_M5_mt5.csv exports in {args.raw_dir}", file=sys.stderr)
        return 1
    for symbol in symbols:
        r = import_symbol(
            symbol, args.raw_dir / f"{symbol}_M5_mt5.csv", args.out_dir, args.report_dir
        )
        p, g = r["parse"], r["gaps"]
        print(
            f"{symbol}: {p['rows_kept']:,} bars kept, {p['rows_rejected']} rejected "
            f"{p['rejected_by_reason']}, "
            f"{g['total_gaps']['mid_session']:,} mid-session gaps, "
            f"{r['timezone']['bars_inside_closed_hours']} bars in closed hours; "
            f"report {args.report_dir / (symbol + '_M5.md')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
