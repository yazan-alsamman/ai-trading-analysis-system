"""Strategy and cost parameters. Every value is an initial one from the spec, to be tuned on the
2012-2017 development period only and then frozen."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import pandas as pd

ENTRY_TIMEFRAME = pd.Timedelta(minutes=15)  # the spec's entry timeframe


@dataclass(frozen=True)
class StrategyParams:
    k_htf: int = 3  # swing half-width on 1h and 4h
    k_ltf: int = 2  # swing half-width on the entry bars (the CHoCH reference)
    atr_period: int = 14  # Wilder ATR on 15m
    min_sweep_atr: float = 0.1  # minimum penetration of the sweep's first bar beyond the level
    max_sweep_atr: float = 1.5  # deeper than this is a breakout, not a sweep
    choch_window: int = 8  # bars after the sweep in which the CHoCH must close
    min_fvg_atr: float = 0.1  # minimum gap size
    sl_buffer_atr: float = 0.1  # SL beyond the sweep extreme (plus the current spread)
    min_r: float = 1.5
    max_r: float = 4.0
    entry_window: int = 8  # bars an ARMED setup waits for its fill
    horizon: int = 48  # bars an ACTIVE trade is held at most, counting the fill bar
    level_max_age_days: int = 5  # trading days a liquidity level stays active
    entry: str = "proximal"  # "proximal" edge of the FVG, or "midpoint" (ablation)
    # Variant A (2026-10-19): a new extreme after the sweep extends it instead of discarding the
    # setup, while the total depth below the level stays within ``max_sweep_atr``.
    extend_sweep: bool = False
    # Variant B: Asian and London session highs and lows as extra liquidity levels.
    session_levels: bool = False
    # Entry bars in minutes (15 for the spec; 5 for attempt 4). Bar-count windows above are in entry
    # bars, so a 5m run scales them (8 -> 24, 48 -> 144) to keep the same clock time.
    entry_tf_minutes: int = 15
    # Attempt 5 (2026-10-19, Fadi's review): the FVG's third bar must be the CHoCH bar or one of
    # the N entry bars before it, so the gap belongs to the displacement that broke structure.
    # Counted in bars, not minutes. None keeps the v1 rule (any gap from the extreme to the CHoCH).
    fvg_max_bars_before_choch: int | None = None

    @property
    def entry_timeframe(self) -> pd.Timedelta:
        return pd.Timedelta(minutes=self.entry_tf_minutes)

    def as_dict(self) -> dict:
        return asdict(self)


# v1 rule set (attempt 4, "AB5"), frozen on 2026-10-19 and superseded the same day by FROZEN_V2
# after the manual review found FVGs far from the CHoCH. Kept unchanged for the record.
FROZEN_V1 = StrategyParams(
    extend_sweep=True,
    session_levels=True,
    entry_tf_minutes=5,
    choch_window=24,
    entry_window=24,
    horizon=144,
)

# v2 rule set (attempt 5, "AB5F"): v1 plus an FVG within 6 entry bars before the CHoCH (or on it).
# Frozen on 2026-10-19; superseded the same day by FROZEN_V3 after the pattern-validity review
# (14 of 20, gate failed). Kept unchanged for the record.
FROZEN_V2 = replace(FROZEN_V1, fvg_max_bars_before_choch=6)

# v3 rule set (attempt 6, "AB5F3"): v2 with one combined change from the validity review: an FVG
# of at least 0.25 ATR (displacement), a sweep of at least 0.25 ATR, and a CHoCH reference swing
# with k = 3 on the entry bars. Frozen on 2026-10-19 by Fadi's decision. Do not change these values;
# a new rule set gets a new name and a new entry in the attempts log.
FROZEN_V3 = replace(FROZEN_V2, min_fvg_atr=0.25, min_sweep_atr=0.25, k_ltf=3)

# The rule set every tool (report, review, conditions) uses by default.
CURRENT = FROZEN_V3
CURRENT_NAME = "FROZEN_V3"

RULE_SETS = {"FROZEN_V1": FROZEN_V1, "FROZEN_V2": FROZEN_V2, "FROZEN_V3": FROZEN_V3}


@dataclass(frozen=True)
class CostParams:
    """Round-trip cost in price units: the recorded spread plus the larger of ``extra_frac`` of it
    or ``extra_min`` (MT5 records the in-bar minimum spread), plus ``sl_slippage`` on SL exits."""

    extra_frac: float = 0.5
    extra_min: float = 0.10
    sl_slippage: float = 0.10

    def round_trip(self, spread: float) -> float:
        return spread + max(self.extra_frac * spread, self.extra_min)

    def as_dict(self) -> dict:
        return asdict(self)
