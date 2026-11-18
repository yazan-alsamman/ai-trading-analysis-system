"""``python -m app research sentiment download|data|gates`` (``docs/sentiment/PREREG_SENTIMENT.md``
§2-§3; data work only, no model).

    python -m app research sentiment download [--prices-from PATH]  # raw files + SHA-256 check
    python -m app research sentiment data    # verify, clean, dedupe, split, prices -> processed/
    python -m app research sentiment gates   # G1-G5 -> docs/sentiment/gates.md, class weights

Every command stops if a raw file differs from its SHA-256 in ``app/config/sentiment.toml``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.research.sentiment import data as sd


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m app research sentiment",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    dl = sub.add_parser("download", help="fetch the raw files and check their SHA-256")
    dl.add_argument(
        "--prices-from",
        type=Path,
        default=None,
        help="the Dukascopy CSV made with the command in sentiment.toml",
    )
    sub.add_parser("data", help="verify, clean, dedupe, split, prices -> data/sentiment/processed")
    sub.add_parser("gates", help="G1-G5 -> docs/sentiment/gates.md")
    args = ap.parse_args(argv)
    cfg = sd.load_config()
    try:
        if args.cmd == "download":
            for key, status in sd.download(cfg, args.prices_from).items():
                print(f"{key}: {status}")
        elif args.cmd == "data":
            built = sd.build(cfg)
            sd.save(cfg, built)
            g, sp, pr = built.manifest["gold"], built.manifest["split"], built.manifest["prices"]
            print(
                f"gold: {g['rows_raw']} rows, {g['unparsable_dates']} unparsable dates, "
                f"{g['dup_exact']} exact + {g['dup_near']} near duplicates, {g['kept']} kept"
            )
            print(f"split: {sp['chosen']} {sp['counts']}")
            print(
                f"prices: {pr['bars_from_first']} bars from 2003, "
                f"{pr['ohlc_violations']} OHLC violations, {pr['gk_nonpositive']} gk_var <= 0"
            )
            print(f"wrote {cfg.processed}")
        else:
            from app.research.sentiment import gates

            gates.run(cfg)
            print(f"wrote {cfg.report} and the class weights in {cfg.path.name}")
    except sd.ChecksumError as e:
        print(f"stopped: {e}", file=sys.stderr)
        return 1
    return 0
