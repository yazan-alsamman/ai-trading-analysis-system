"""Backtest configuration: costs, direction, position sizing (:class:`Sizer`), exits
(:class:`ExitRules`: stop, trailing stop, targets, time exit) and account guards.

JSON (``BacktestConfig.from_dict``; unknown fields are errors, messages carry the path)::

    {"initial_capital": 10000, "fee_bps": 10, "slippage_bps": 5, "direction": "long_only",
     "sizing": {...}, "stop": {...}, "trailing": {...}, "take_profit": {...}, "guards": {...},
     "check_entry_bar": true,
     "exits": {"max_bars_held": null, "exit_on_opposite_signal": true}}

The risk parts are described in ``trading_backtest.risk``. The Y11 fields
``exits.stop_loss_pct`` and ``exits.take_profit_pct`` are still accepted as aliases of
``stop: {"type": "percent"}`` and ``take_profit: {"type": "percent"}``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field, ValidationError, model_validator

from trading_backtest import risk as rk
from trading_backtest.risk import Guards, StopRule, TargetRule, TrailingRule

Direction = Literal["long_only", "long_short"]
SizingMode = Literal["fraction", "fixed", "risk", "volatility"]

DIRECTIONS = ("long_only", "long_short")
SIZING_MODES = ("fraction", "fixed", "risk", "volatility")
CAP_TOLERANCE = 1e-12  # the cap only applies beyond float noise (Y11 results stay bit-identical)


@dataclass(frozen=True)
class Sizer:
    """Quantity for a new position (see docs/risk-management.md for the formulas).

    ``fraction``: ``value`` (0, 1] of current equity, compounding; notional plus the entry fee
    fits in that amount. ``fixed``: ``value`` quote currency of notional (capped at equity).
    ``risk``: ``risk_pct`` % of equity lost (fees included) if the stop is hit.
    ``volatility``: one ATR(``length``) move = ``target_pct`` % of equity.
    Every mode is capped at ``max_position_pct`` % of equity (100 = no leverage); a notional
    below ``min_notional`` is not traded (``size_below_min``).
    """

    mode: SizingMode = "fraction"
    value: float = 1.0
    risk_pct: float = 1.0
    target_pct: float = 1.0
    length: int = 14
    max_position_pct: float = 100.0
    min_notional: float = 10.0

    def quantity(self, equity: float, fill_price: float, fee_rate: float) -> float:
        """Y11 API: the quantity of a fraction/fixed position (0 when it cannot be sized)."""
        qty, reason = self.size(equity, fill_price, fee_rate)
        return 0.0 if reason else qty

    def size(
        self,
        equity: float,
        entry: float,
        fee_rate: float,
        stop: float | None = None,
        atr: float | None = None,
    ) -> tuple[float, str | None]:
        """(quantity, invalid reason or None)."""
        if equity <= 0 or entry <= 0:
            return 0.0, "no_equity"
        if self.mode == "fraction":
            qty = self.value * equity / (entry * (1 + fee_rate))
        elif self.mode == "fixed":
            notional = min(self.value, equity / (1 + fee_rate))
            qty = notional / entry
        elif self.mode == "risk":
            if stop is None:
                return 0.0, "stop_unavailable"
            per_unit = abs(entry - stop) + (entry + stop) * fee_rate
            qty = self.risk_pct / 100 * equity / per_unit
        else:
            if atr is None or not atr > 0:
                return 0.0, "atr_unavailable"
            qty = self.target_pct / 100 * equity / atr
        cap = self.max_position_pct / 100 * equity / (entry * (1 + fee_rate))
        if qty > cap * (1 + CAP_TOLERANCE):
            qty = cap
        if qty * entry < self.min_notional or qty <= 0:
            return qty, "size_below_min"
        return qty, None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"mode": self.mode}
        if self.mode in ("fraction", "fixed"):
            out["value"] = self.value
        elif self.mode == "risk":
            out["risk_pct"] = self.risk_pct
        else:
            out.update(target_pct=self.target_pct, length=self.length)
        out.update(max_position_pct=self.max_position_pct, min_notional=self.min_notional)
        return out


def sizer_from(model: Any) -> Sizer:
    common = {
        "max_position_pct": float(model.max_position_pct),
        "min_notional": float(model.min_notional),
    }
    if isinstance(model, rk.FractionSizing):
        return Sizer("fraction", value=float(model.value), **common)
    if isinstance(model, rk.FixedSizing):
        return Sizer("fixed", value=float(model.value), **common)
    if isinstance(model, rk.RiskSizing):
        return Sizer("risk", risk_pct=float(model.risk_pct), **common)
    return Sizer("volatility", target_pct=float(model.target_pct), length=model.length, **common)


@dataclass(frozen=True)
class ExitRules:
    """How a position ends: ``stop`` (initial stop), ``trailing`` (moves it in your favour),
    ``take_profit`` (one or several targets), ``max_bars_held`` (closes at the open that many
    bars after the entry bar) and the opposite signal. ``check_entry_bar``: stops and targets
    are checked on the entry bar too (after the fill at its open)."""

    stop: StopRule | None = None
    trailing: TrailingRule | None = None
    take_profit: TargetRule | None = None
    max_bars_held: int | None = None
    exit_on_opposite_signal: bool = True
    check_entry_bar: bool = True

    @property
    def stop_loss_pct(self) -> float | None:  # Y11 name
        return self.stop.value if self.stop and self.stop.type == "percent" else None

    @property
    def take_profit_pct(self) -> float | None:  # Y11 name
        t = self.take_profit
        if t and t.type == "percent" and len(t.levels) == 1 and t.levels[0][1] == 1.0:
            return t.levels[0][0]
        return None


class _Exits(rk._M):
    stop_loss_pct: float | None = Field(default=None, gt=0, le=99, allow_inf_nan=False)
    take_profit_pct: float | None = Field(default=None, gt=0, le=1000, allow_inf_nan=False)
    max_bars_held: int | None = Field(default=None, ge=1, strict=True)
    exit_on_opposite_signal: bool = Field(default=True, strict=True)


class BacktestConfigIn(rk._M):
    """JSON input of :class:`BacktestConfig` (validation and JSON Schema)."""

    initial_capital: float = Field(default=10_000.0, gt=0, le=1e12, allow_inf_nan=False)
    fee_bps: float = Field(default=10.0, ge=0, le=1000, allow_inf_nan=False)
    slippage_bps: float = Field(default=5.0, ge=0, le=1000, allow_inf_nan=False)
    direction: Direction = "long_only"
    sizing: rk.SizingIn = rk.FractionSizing()
    stop: rk.StopIn | None = None
    trailing: rk.TrailingIn | None = None
    take_profit: rk.TakeProfitIn | None = None
    guards: rk.GuardsIn | None = None
    check_entry_bar: bool = Field(default=True, strict=True)
    exits: _Exits = _Exits()

    @model_validator(mode="after")
    def _aliases(self) -> BacktestConfigIn:
        if self.exits.stop_loss_pct is not None and self.stop is not None:
            raise ValueError("give either stop or exits.stop_loss_pct, not both")
        if self.exits.take_profit_pct is not None and self.take_profit is not None:
            raise ValueError("give either take_profit or exits.take_profit_pct, not both")
        return self


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 10_000.0
    fee_bps: float = 10.0  # per side, of notional (Binance spot: 0.10 %)
    slippage_bps: float = 5.0  # against you on every fill
    direction: Direction = "long_only"
    sizing: Sizer = field(default_factory=Sizer)
    exits: ExitRules = field(default_factory=ExitRules)
    guards: Guards = field(default_factory=Guards)

    @property
    def fee_rate(self) -> float:
        return self.fee_bps / 10_000

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000

    def to_dict(self) -> dict[str, Any]:
        """Normalised JSON (``from_dict(to_dict())`` gives the same config)."""
        e = self.exits
        return {
            "initial_capital": self.initial_capital,
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "direction": self.direction,
            "sizing": self.sizing.to_dict(),
            "stop": e.stop.to_dict() if e.stop else None,
            "trailing": e.trailing.to_dict() if e.trailing else None,
            "take_profit": e.take_profit.to_dict() if e.take_profit else None,
            "guards": self.guards.to_dict(),
            "check_entry_bar": e.check_entry_bar,
            "exits": {
                "max_bars_held": e.max_bars_held,
                "exit_on_opposite_signal": e.exit_on_opposite_signal,
            },
        }

    def risk_dict(self) -> dict[str, Any]:
        """The risk part (a risk config / profile)."""
        d = self.to_dict()
        keys = ("stop", "trailing", "take_profit", "sizing", "guards", "fee_bps")
        return {k: d[k] for k in keys}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None = None) -> BacktestConfig:
        """Validate a JSON-like config and fill in defaults. Raises :class:`ConfigError` (a
        ``ValueError``) whose message starts with the path, e.g. ``stop.multiplier: ...``."""
        try:
            model = BacktestConfigIn.model_validate(dict(data or {}))
        except ValidationError as exc:
            raise rk.pydantic_errors(exc) from None
        stop, take_profit = model.stop, model.take_profit
        if model.exits.stop_loss_pct is not None:
            stop = rk.PercentStop(type="percent", value=model.exits.stop_loss_pct)
        if model.exits.take_profit_pct is not None:
            take_profit = rk.PercentTarget(type="percent", value=model.exits.take_profit_pct)
        checked = model.model_copy(update={"stop": stop, "take_profit": take_profit})
        errors = rk.stop_requirements(checked)
        if errors:
            raise rk.ConfigError(errors)
        return cls(
            initial_capital=float(model.initial_capital),
            fee_bps=float(model.fee_bps),
            slippage_bps=float(model.slippage_bps),
            direction=model.direction,
            sizing=sizer_from(model.sizing),
            exits=ExitRules(
                stop=rk.stop_rule(stop),
                trailing=rk.trailing_rule(model.trailing),
                take_profit=rk.target_rule(take_profit),
                max_bars_held=model.exits.max_bars_held,
                exit_on_opposite_signal=model.exits.exit_on_opposite_signal,
                check_entry_bar=model.check_entry_bar,
            ),
            guards=rk.guards_rule(model.guards),
        )

    @classmethod
    def from_risk(cls, risk: Mapping[str, Any] | None, **overrides: Any) -> BacktestConfig:
        """A config from a risk config (profile): its stop/trailing/take_profit/sizing/guards
        and ``fee_bps``; ``overrides`` set other fields (initial_capital, ...)."""
        normalised = rk.validate_risk_config(risk)
        return cls.from_dict({**normalised, "slippage_bps": 0.0, **overrides})
