"""What COMEX gold order-flow data would cost on Databento: estimates only, nothing is bought.

    $env:DATABENTO_API_KEY = "db-..."      # PowerShell, this window only; never commit the key
    .venv/Scripts/python.exe tools/databento/cost.py

Calls only Databento's free metadata endpoints (``metadata.get_cost`` and
``metadata.get_billable_size``): no data is downloaded and nothing is charged. The research
behind the choice of vendor: ``reports/مزودو بيانات أوامر ذهب كومكس.md``."""

from __future__ import annotations

import os
import sys

DATASET = "GLBX.MDP3"  # CME Globex (CME, CBOT, NYMEX, COMEX)
GC, MGC = ("GC.c.0", "continuous"), ("MGC.c.0", "continuous")  # front month by volume roll
GC_ALL = ("GC.FUT", "parent")  # every GC contract and spread
OG_ALL = ("OG.OPT", "parent")  # gold options (symbology unconfirmed)
SAMPLE = ("2025-10-01", "2026-01-01")  # 3 months, inside the FxPro research store
YEAR = ("2025-01-01", "2026-01-01")
FIVE = ("2021-01-01", "2026-01-01")
MONTH = ("2025-12-01", "2026-01-01")

SCENARIOS = [
    ("Sample, 3 months", GC, "trades", SAMPLE),
    ("Sample, 3 months", GC, "tbbo", SAMPLE),
    ("Sample, 3 months", GC, "mbp-1", SAMPLE),
    ("Sample, 3 months", MGC, "trades", SAMPLE),
    ("Sample, 3 months", MGC, "tbbo", SAMPLE),
    ("Sample, 3 months, every GC contract", GC_ALL, "trades", SAMPLE),
    ("Depth, 1 month", GC, "mbp-10", MONTH),
    ("Depth, 1 month", GC, "mbo", MONTH),
    ("History, 5 years", GC, "trades", FIVE),
    ("History, 5 years", GC, "tbbo", FIVE),
    ("Depth, 1 year", GC, "mbp-10", YEAR),
    ("Depth, 1 year", GC, "mbo", YEAR),
    ("Options statistics (open interest), 1 year", OG_ALL, "statistics", YEAR),
]


def main() -> int:
    if not os.environ.get("DATABENTO_API_KEY", "").strip():
        print(
            "Set DATABENTO_API_KEY in this window first (PowerShell):\n"
            '    $env:DATABENTO_API_KEY = "db-..."\n'
            "Never paste the key into a file or a chat.",
            file=sys.stderr,
        )
        return 2
    import databento as db

    client = db.Historical()
    print(f"Dataset range: {client.metadata.get_dataset_range(dataset=DATASET)}\n")
    print(f"{'Scenario':45} {'Symbol':10} {'Schema':10} {'Period':25} {'GB':>9} {'USD':>10}")
    total = 0.0
    for name, (symbol, stype), schema, (start, end) in SCENARIOS:
        kw = dict(
            dataset=DATASET, symbols=[symbol], stype_in=stype, schema=schema, start=start, end=end
        )
        try:
            gb = client.metadata.get_billable_size(**kw) / 1e9
            usd = client.metadata.get_cost(**kw)
        except Exception as e:  # an unknown symbol or schema: report it and go on
            print(f"{name:45} {symbol:10} {schema:10} {start}..{end}  error: {e}")
            continue
        if name.startswith("Sample, 3 months") and "every" not in name:
            total += usd
        print(f"{name:45} {symbol:10} {schema:10} {start}..{end} {gb:9.3f} {usd:10.2f}")
    print(
        f"\nThe 3-month sample (GC and MGC trades, tbbo, GC mbp-1): about ${total:,.2f} "
        "against the $125 credit of a new account."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
