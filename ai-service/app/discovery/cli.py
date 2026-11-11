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
    if argv and argv[0] == "lead":
        from app.discovery.lead import main as lead

        return lead(argv[1:])
    if argv and argv[0] == "inject":
        from app.discovery.inject import main as inject

        return inject(argv[1:])
    if argv and argv[0] in ("map", "confirm"):
        from app.discovery.map import main as run

        return run(argv[1:], step=argv[0])
    print(__doc__, file=sys.stderr)
    return 2
