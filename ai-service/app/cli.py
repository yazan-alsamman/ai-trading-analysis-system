"""Command line for the offline (research) side of ai-service.

    python -m app config                 # print the resolved configuration
    python -m app lockbox seal|verify    # seal or check the 2026 lockbox
    python -m app import --raw-dir PATH  # MT5 history -> research store (Parquet)
    python -m app quality                # data-quality report of the store

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
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    return importlib.import_module(COMMANDS[argv[0]]).main(argv[1:])
