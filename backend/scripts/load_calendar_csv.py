"""Load economic-calendar history from a CSV (B6, docs/economic-calendar.md).

    python scripts/load_calendar_csv.py --file ff_2007_2024.csv --tz America/New_York --dry-run
    python scripts/load_calendar_csv.py --file ff_2007_2024.csv --tz America/New_York
    python scripts/load_calendar_csv.py --file x.csv --tz UTC --map title=Name,date=Start

The dataset (e.g. the Kaggle ForexFactory export) is downloaded by hand and never committed.
Columns are found by their usual names (Date/Time/Currency/Impact/Event/Actual/Forecast/
Previous, or similar); ``--map field=Column,...`` names them otherwise. The times are in
``--tz`` unless the file carries offsets; a file without either fails (never guessed).
``--dry-run`` prints the detected columns, 5 parsed rows and the counts, and writes nothing.
A second run inserts nothing (the versions are unique). It uses DATABASE_URL (the .env).

On the server (no shell) the same import is ``POST /api/v1/admin/calendar/import``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.calendar.csv_import import (  # noqa: E402
    SOURCES,
    CsvFormatError,
    ImportOptions,
    import_rows,
    parse_mapping,
    reader,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", required=True, type=Path, help="the CSV file")
    parser.add_argument("--source", default=SOURCES[0], choices=SOURCES)
    parser.add_argument("--tz", help="timezone of the CSV times, e.g. America/New_York or UTC")
    parser.add_argument(
        "--from",
        dest="since",
        type=date.fromisoformat,
        default=date(2018, 1, 1),
        help="skip events before this day (default 2018-01-01)",
    )
    parser.add_argument("--map", dest="mapping", help="field=Column,... (title, date, time, ...)")
    parser.add_argument("--date-format", help="strptime format of the date column")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> dict:
    options = ImportOptions(
        source=args.source,
        tz=args.tz,
        since=args.since,
        mapping=parse_mapping(args.mapping),
        date_format=args.date_format,
        dry_run=args.dry_run,
    )
    with args.file.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
        if args.dry_run:
            summary = await import_rows(None, reader(handle), options)
        else:
            from app.db.session import SessionLocal, engine

            try:
                async with SessionLocal() as session:
                    summary = await import_rows(
                        session, reader(handle), options, batch_size=args.batch_size
                    )
            finally:
                await engine.dispose()
    return summary.as_dict()


def print_summary(result: dict) -> None:
    print("columns:", ", ".join(f"{k}={v}" for k, v in result["columns"].items()))
    print(f"parsed rows (first {len(result['sample'])}):")
    for row in result["sample"]:
        when = row["scheduled_at"] or f"{row['date']} ({row['time_label']})"
        values = " ".join(f"{k}={row[k]}" for k in ("actual", "forecast", "previous") if row[k])
        print(f"  {when}  {row['currency']:<4} {row['impact']:<7} {row['title']}  {values}")
    print("rows read:", result["rows_read"])
    print("skipped:", json.dumps(result["skipped"]) if result["skipped"] else "none")
    for example in result["skipped_examples"]:
        print("  ", example)
    print("date range:", result["first_date"], "to", result["last_date"])
    print("events per impact:", json.dumps(result["events_per_impact"]))
    print("versions:", result["versions"])
    if result["dry_run"]:
        print("dry run: nothing written")
    else:
        print("inserted:", result["inserted"], "unchanged:", result["unchanged"])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.file.is_file():
        print(f"error: no such file: {args.file}", file=sys.stderr)
        return 2
    try:
        result = asyncio.run(run(args))
    except CsvFormatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
