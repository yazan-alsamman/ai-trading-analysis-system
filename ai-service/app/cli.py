"""Command line for the offline (research) side of ai-service.

    python -m app config                 # print the resolved configuration
    python -m app lockbox seal|verify    # seal or check the 2026 lockbox
    python -m app import --raw-dir PATH  # MT5 history -> research store (Parquet)
    python -m app quality                # data-quality report of the store
    python -m app dukascopy download|compare  # P1 cross-check sample and report
    python -m app smc detect --symbol XAUUSD    # P2 patterns, development period
    python -m app setups build|label --rules V5-S  # P3 setups and labels, development period
    python -m app setups count --rules V5-S        # P3 sample counts (no performance)
    python -m app research baselines               # P3 E0 vs E1, development period

Each command is a module with ``main(argv) -> int``; it is imported only when called, so the
service itself never loads research code."""

from __future__ import annotations

import importlib
import sys

COMMANDS = {
    "config": "app.config",
    "lockbox": "app.lockbox",
    "import": "app.data.importer",
    "quality": "app.data.quality",
    "dukascopy": "app.data.dukascopy",
    "smc": "app.smc.detector",
    "setups": "app.setups.builder",
    "research": "app.research.baselines",
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    return importlib.import_module(COMMANDS[argv[0]]).main(argv[1:])
