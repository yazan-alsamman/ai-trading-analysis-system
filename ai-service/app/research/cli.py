"""``python -m app research <command> ...``: the research commands. baselines, walkforward,
versions, meta: L1 (P3, P4). post-counts, evaluate, management, holdout: the signal strategies
(docs/strategies/PREREG.md). mt5-check: the cost model in the MT5 Strategy Tester (descriptive).
levels-confirm: Addendum 2, the level-break reading on the confirmation instruments (once).
levels-trade: Addendum 2, the level-break trade in the MT5 Strategy Tester (H_L2, once)."""

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
    if argv and argv[0] == "holdout":
        from app.research.holdout import main as holdout

        return holdout(argv[1:])
    if argv and argv[0] == "levels-confirm":
        from app.research.levels_confirm import main as levels_confirm

        return levels_confirm(argv[1:])
    if argv and argv[0] == "levels-trade":
        from app.research.levels_trade import main as levels_trade

        return levels_trade(argv[1:])
    if argv and argv[0] == "mt5-check":
        from app.research.mt5_check import main as mt5_check

        return mt5_check(argv[1:])
    if argv and argv[0] == "baselines":
        from app.research.baselines import main as baselines

        return baselines(argv)
    print(__doc__, file=sys.stderr)
    return 2
