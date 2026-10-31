"""``python -m app research <baselines|walkforward|versions|meta|post-counts|evaluate|management>
...``: the research commands (post-counts, evaluate and management: the signal strategies,
docs/strategies/PREREG.md)."""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if argv and argv[0] == "meta":
        from app.research.meta import main as meta

        return meta(argv[1:])
    if argv and argv[0] == "walkforward":
        from app.research.walkforward import main as walkforward

        return walkforward(argv[1:])
    if argv and argv[0] == "versions":
        from app.research.versions import main as versions

        return versions(argv[1:])
    if argv and argv[0] == "post-counts":
        from app.research.post_counts import main as post_counts

        return post_counts(argv[1:])
    if argv and argv[0] == "evaluate":
        from app.research.strategy_eval import main as evaluate

        return evaluate(argv[1:])
    if argv and argv[0] == "management":
        from app.research.management_eval import main as management

        return management(argv[1:])
    if argv and argv[0] == "baselines":
        from app.research.baselines import main as baselines

        return baselines(argv)
    print(__doc__, file=sys.stderr)
    return 2
