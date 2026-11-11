"""``python -m app discovery <command> ...``: discovery round 2 (``docs/discovery/PLAN.md``).
calendar: import and check the MT5 economic calendar (stage D1)."""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if argv and argv[0] == "calendar":
        from app.discovery.calendar import main as calendar

        return calendar(argv[1:])
    if argv and argv[0] == "count":
        from app.discovery.count import main as count

        return count(argv[1:])
    if argv and argv[0] == "drivers":
        from app.discovery.drivers import main as drivers

        return drivers(argv[1:])
    print(__doc__, file=sys.stderr)
    return 2
