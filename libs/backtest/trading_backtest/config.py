"""Backtest configuration: costs, direction, position sizing and exits.

Sizing and exits are small pluggable pieces (:class:`Sizer`, :class:`ExitRules`) so risk
management (stops by ATR, trailing stops, risk-based sizing) can extend them later.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Direction = Literal["long_only", "long_short"]
SizingMode = Literal["fraction", "fixed"]

DIRECTIONS = ("long_only", "long_short")
SIZING_MODES = ("fraction", "fixed")


def _number(name: str, value: Any, *, low: float, high: float, low_open: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    too_low = value <= low if low_open else value < low
    if too_low or value > high:
        bracket = "(" if low_open else "["
        raise ValueError(f"{name} must be in {bracket}{low:g}, {high:g}], got {value:g}")
    return value


@dataclass(frozen=True)
class Sizer:
    """Quantity for a new position.

    ``fraction``: ``value`` (0, 1] of current equity, compounding; the quantity is chosen so
    notional plus the entry fee fits in that amount. ``fixed``: ``value`` quote currency of
    notional per trade (capped at equity: no leverage).
    """

    mode: SizingMode = "fraction"
    value: float = 1.0

    def quantity(self, equity: float, fill_price: float, fee_rate: float) -> float:
        if equity <= 0 or fill_price <= 0:
            return 0.0
        if self.mode == "fraction":
            return self.value * equity / (fill_price * (1 + fee_rate))
        notional = min(self.value, equity / (1 + fee_rate))
        return notional / fill_price


@dataclass(frozen=True)
class ExitRules:
    """``stop_loss_pct`` / ``take_profit_pct`` are percent distances from the entry fill price;
    ``max_bars_held`` closes at the open of the bar that many bars after the entry bar."""

    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_bars_held: int | None = None
    exit_on_opposite_signal: bool = True

    def levels(self, side: int, entry_price: float) -> tuple[float, float]:
        """(stop price, take-profit price) for a position; NaN when not set."""
        sl = tp = math.nan
        if self.stop_loss_pct is not None:
            sl = entry_price * (1 - side * self.stop_loss_pct / 100)
        if self.take_profit_pct is not None:
            tp = entry_price * (1 + side * self.take_profit_pct / 100)
        return sl, tp


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 10_000.0
    fee_bps: float = 10.0  # per side, of notional (Binance spot: 0.10 %)
    slippage_bps: float = 5.0  # against you on every fill
    direction: Direction = "long_only"
    sizing: Sizer = field(default_factory=Sizer)
    exits: ExitRules = field(default_factory=ExitRules)

    @property
    def fee_rate(self) -> float:
        return self.fee_bps / 10_000

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None = None) -> BacktestConfig:
        """Validate a JSON-like config (unknown keys and bad values raise ValueError) and fill in
        defaults. ``sizing`` is ``{"mode": "fraction"|"fixed", "value": x}``; ``exits`` has
        ``stop_loss_pct``, ``take_profit_pct``, ``max_bars_held``, ``exit_on_opposite_signal``."""
        data = dict(data or {})
        allowed = {"initial_capital", "fee_bps", "slippage_bps", "direction", "sizing", "exits"}
        _no_unknown("config", data, allowed)
        kwargs: dict[str, Any] = {}
        if "initial_capital" in data:
            kwargs["initial_capital"] = _number(
                "initial_capital", data["initial_capital"], low=0, high=1e12, low_open=True
            )
        for name in ("fee_bps", "slippage_bps"):
            if name in data:
                kwargs[name] = _number(name, data[name], low=0, high=1000)
        if "direction" in data:
            if data["direction"] not in DIRECTIONS:
                raise ValueError(f"direction must be one of {', '.join(DIRECTIONS)}")
            kwargs["direction"] = data["direction"]
        if "sizing" in data:
            kwargs["sizing"] = _sizer(data["sizing"])
        if "exits" in data:
            kwargs["exits"] = _exits(data["exits"])
        return cls(**kwargs)


def _no_unknown(where: str, data: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(
            f"{where}: unknown field(s) {', '.join(unknown)} "
            f"(allowed: {', '.join(sorted(allowed))})"
        )


def _sizer(data: Any) -> Sizer:
    if not isinstance(data, Mapping):
        raise ValueError("sizing must be an object like {'mode': 'fraction', 'value': 1.0}")
    _no_unknown("sizing", data, {"mode", "value"})
    mode = data.get("mode", "fraction")
    if mode not in SIZING_MODES:
        raise ValueError(f"sizing.mode must be one of {', '.join(SIZING_MODES)}")
    if mode == "fraction":
        value = _number("sizing.value", data.get("value", 1.0), low=0, high=1, low_open=True)
    else:
        if "value" not in data:
            raise ValueError("sizing.value (quote amount per trade) is required for fixed sizing")
        value = _number("sizing.value", data["value"], low=0, high=1e12, low_open=True)
    return Sizer(mode=mode, value=value)


def _exits(data: Any) -> ExitRules:
    if not isinstance(data, Mapping):
        raise ValueError("exits must be an object")
    allowed = {"stop_loss_pct", "take_profit_pct", "max_bars_held", "exit_on_opposite_signal"}
    _no_unknown("exits", data, allowed)
    kwargs: dict[str, Any] = {}
    if data.get("stop_loss_pct") is not None:
        kwargs["stop_loss_pct"] = _number(
            "exits.stop_loss_pct", data["stop_loss_pct"], low=0, high=99, low_open=True
        )
    if data.get("take_profit_pct") is not None:
        kwargs["take_profit_pct"] = _number(
            "exits.take_profit_pct", data["take_profit_pct"], low=0, high=1000, low_open=True
        )
    if data.get("max_bars_held") is not None:
        value = data["max_bars_held"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("exits.max_bars_held must be an integer >= 1")
        kwargs["max_bars_held"] = value
    if "exit_on_opposite_signal" in data:
        value = data["exit_on_opposite_signal"]
        if not isinstance(value, bool):
            raise ValueError("exits.exit_on_opposite_signal must be true or false")
        kwargs["exit_on_opposite_signal"] = value
    return ExitRules(**kwargs)
