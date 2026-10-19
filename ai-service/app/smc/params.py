"""Strategy and cost parameters. Every value is an initial one from the spec, to be tuned on the
2012-2017 development period only and then frozen."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

ENTRY_TIMEFRAME = pd.Timedelta(minutes=15)


@dataclass(frozen=True)
class StrategyParams:
    k_htf: int = 3  # swing half-width on 1h and 4h
    k_ltf: int = 2  # swing half-width on 15m
    atr_period: int = 14  # Wilder ATR on 15m
    min_sweep_atr: float = 0.1  # minimum penetration beyond the level
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

    def as_dict(self) -> dict:
        return asdict(self)


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
