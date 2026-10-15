"""The Strategy interface (Strategy pattern) and helpers shared by every strategy.

Signal semantics (all strategies):

* ``generate`` evaluates every **closed** bar ``t`` using bars ``<= t`` only; a signal on bar
  ``t`` is actionable at the open of bar ``t + 1``. No look-ahead, ever.
* ``signal`` is an **event** on the bar where the condition triggers (``1`` buy, ``-1`` sell,
  ``0`` nothing), not a held position. Strategies emit entries only; exits, stop-loss and
  take-profit belong to risk management.
* ``strength`` is in ``[0, 1]`` (0 when there is no signal), ``reason`` a short
  machine-readable code and ``details`` the numbers behind it (both ``None`` without a signal).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np
import pandas as pd
import trading_indicators as ti
from trading_indicators import Param

SIGNAL_COLUMNS = ("signal", "strength", "reason", "details")
BUY, SELL = 1, -1


class Strategy(ABC):
    key: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]
    category: ClassVar[str]  # "trend" | "mean_reversion" | "breakout" | "momentum"
    params: ClassVar[tuple[Param, ...]]
    inputs: ClassVar[tuple[str, ...]] = ("high", "low", "close")

    # --- parameters ------------------------------------------------------------------------

    def resolve(self, params: Mapping[str, Any] | None = None) -> dict[str, int | float]:
        """Validate ``params`` (types, ranges, cross-parameter rules) and fill in defaults."""
        params = dict(params or {})
        known = {p.name: p for p in self.params}
        unknown = sorted(set(params) - set(known))
        if unknown:
            raise ValueError(
                f"{self.key}: unknown parameter(s) {', '.join(unknown)} "
                f"(allowed: {', '.join(known) or 'none'})"
            )
        resolved: dict[str, int | float] = {}
        for name, spec in known.items():
            try:
                resolved[name] = spec.validate(params[name]) if name in params else spec.default
            except ValueError as exc:
                raise ValueError(f"{self.key}: {exc}") from None
        self.check(resolved)
        return resolved

    def check(self, params: dict[str, int | float]) -> None:  # noqa: B027 - optional hook
        """Cross-parameter rules; raise ValueError with a clear message."""

    # --- indicators and history ------------------------------------------------------------

    @abstractmethod
    def indicators(self, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        """The indicator lines to draw with this strategy, as ``{"name", "params"}``."""

    def computed_indicators(self, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Every indicator the rules read (drawn or not); used for :meth:`history`."""
        return self.indicators(params)

    def history(self, params: Mapping[str, Any] | None = None) -> int:
        """Bars needed before the first valid signal: the largest warm-up plus convergence of
        the indicators used, plus one bar to compare with the previous one."""
        p = self.resolve(params)
        needed = 0
        for ind in self.computed_indicators(p):
            spec = ti.get_indicator(ind["name"])
            needed = max(needed, spec.lookback(ind["params"]) + spec.convergence(ind["params"]))
        return needed + 1

    # --- signals ---------------------------------------------------------------------------

    def generate(self, df: pd.DataFrame, params: Mapping[str, Any] | None = None) -> pd.DataFrame:
        """Signal frame aligned to ``df.index`` (columns ``signal, strength, reason, details``)."""
        p = self.resolve(params)
        ti.core.check_frame(df, self.inputs)
        out = self._generate(df, p)
        assert list(out.columns) == list(SIGNAL_COLUMNS) and out.index.equals(df.index)
        return out

    @abstractmethod
    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame: ...

    # --- catalog ---------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        defaults = self.resolve()
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "params": [p.to_dict() for p in self.params],
            "indicators": self.indicators(defaults),
            "history": self.history(defaults),
        }


# --- helpers used by the strategies --------------------------------------------------------


def crossed_above(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """``a`` was ``<= b`` on the previous bar and is ``> b`` now (NaN anywhere -> False)."""
    prev_a, prev_b = ti.core.shift1(a), ti.core.shift1(b)
    with np.errstate(invalid="ignore"):
        return (prev_a <= prev_b) & (a > b)


def crossed_below(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    prev_a, prev_b = ti.core.shift1(a), ti.core.shift1(b)
    with np.errstate(invalid="ignore"):
        return (prev_a >= prev_b) & (a < b)


def clip01(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return float(min(1.0, max(0.0, x)))


def r(x: float, digits: int = 6) -> float | None:
    """Round a number for ``details`` (None for NaN)."""
    return None if x != x else round(float(x), digits)


def events(
    index: pd.Index,
    buy: np.ndarray,
    sell: np.ndarray,
    describe,  # (t: int, side: int) -> (strength, reason, details)
) -> pd.DataFrame:
    """Build the signal frame; ``describe`` is only called on the (few) signal bars."""
    n = len(index)
    signal = np.zeros(n, dtype=np.int8)
    signal[buy] = BUY
    signal[sell & ~buy] = SELL
    strength = np.zeros(n)
    reason = np.full(n, None, dtype=object)
    details = np.full(n, None, dtype=object)
    for t in np.flatnonzero(signal):
        s, why, info = describe(int(t), int(signal[t]))
        strength[t], reason[t], details[t] = clip01(s), why, info
    # explicit object dtype: pandas 3 would otherwise infer a string dtype for "reason" only when
    # a signal exists, so the column type would depend on the data
    return pd.DataFrame(
        {
            "signal": signal,
            "strength": strength,
            "reason": pd.Series(reason, index=index, dtype=object),
            "details": pd.Series(details, index=index, dtype=object),
        },
        index=index,
    )
