"""The round-trip cost of the cost model (P3 task 2; docs/strategies/PREREG.md, section 3):
``spread + max(cost_extra_frac * spread, cost_extra_min)`` with the decision bar's spread. On its
own so that signal-time code (the cost filter of the signal strategies) can use it without
importing the label engine."""

from __future__ import annotations

from app.config import Instrument


def round_trip(spread: float, inst: Instrument) -> float:
    return spread + max(inst.cost_extra_frac * spread, inst.cost_extra_min)
