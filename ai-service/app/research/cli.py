"""``python -m app research <command> ...``: the research commands. baselines, walkforward,
versions, meta: L1 (P3, P4). post-counts, evaluate, management, holdout: the signal strategies
(docs/strategies/PREREG.md). mt5-check: the cost model in the MT5 Strategy Tester (descriptive).
levels-confirm: Addendum 2, the level-break reading on the confirmation instruments (once).
levels-trade: Addendum 2, the level-break trade in the MT5 Strategy Tester (H_L2, once).
gold-lab, gold-combo: the commercial gold track (exploratory).
gold-exam: the gold track's lockbox exam (once). gold-live: the v1 live EA against Python."""

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
    if argv and argv[0] == "gold-combo":
        from app.research.gold_combo import main as gold_combo

        return gold_combo(argv[1:])
    if argv and argv[0] == "gold-exam":
        from app.research.gold_exam import main as gold_exam

        return gold_exam(argv[1:])
    if argv and argv[0] == "gold-live":
        from app.research.gold_live import main as gold_live

        return gold_live(argv[1:])
    if argv and argv[0] == "gold-vp":
        from app.research.gold_vp import main as gold_vp

        return gold_vp(argv[1:])
    if argv and argv[0] == "gold-swing":
        from app.research.gold_swing import main as gold_swing

        return gold_swing(argv[1:])
    if argv and argv[0] == "gold-regime":
        from app.research.gold_regime import main as gold_regime

        return gold_regime(argv[1:])
    if argv and argv[0] == "gold-orb":
        from app.research.gold_orb import main as gold_orb

        return gold_orb(argv[1:])
    if argv and argv[0] == "gold-pullback":
        from app.research.gold_pullback import main as gold_pullback

        return gold_pullback(argv[1:])
    if argv and argv[0] == "gold-retrace":
        from app.research.gold_retrace import main as gold_retrace

        return gold_retrace(argv[1:])
    if argv and argv[0] == "gold-night":
        from app.research.gold_night import main as gold_night

        return gold_night(argv[1:])
    if argv and argv[0] == "gold-shadow":
        from app.research.gold_shadow import main as gold_shadow

        return gold_shadow(argv[1:])
    if argv and argv[0] == "gold-dr":
        from app.research.gold_dr import main as gold_dr

        return gold_dr(argv[1:])
    if argv and argv[0] == "gold-ah":
        from app.research.gold_ah import main as gold_ah

        return gold_ah(argv[1:])
    if argv and argv[0] == "gold-lab":
        from app.research.gold_lab import main as gold_lab

        return gold_lab(argv[1:])
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
