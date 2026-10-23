"""``python -m app research <baselines|walkforward|versions> ...``: the research commands."""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if argv and argv[0] == "walkforward":
        from app.research.walkforward import main as walkforward

        return walkforward(argv[1:])
    if argv and argv[0] == "versions":
        from app.research.versions import main as versions

        return versions(argv[1:])
    if argv and argv[0] == "baselines":
        from app.research.baselines import main as baselines

        return baselines(argv)
    print(__doc__, file=sys.stderr)
    return 2
