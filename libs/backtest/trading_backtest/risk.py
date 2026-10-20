"""Risk management: stops, trailing stops, targets (with partial exits), position sizing,
account guards, and the trade plan shared by the backtest engine and live signals.

The JSON shape of a risk config (``RiskConfigIn``, also the risk part of a backtest config)::

    {
      "stop":        {"type": "percent", "value": 2}
                   | {"type": "atr", "length": 14, "multiplier": 2.0}
                   | {"type": "swing", "lookback": 10, "buffer_pct": 0.1}   | null,
      "trailing":    {"type": "percent", "value": 3, "activation_r": 1, "breakeven_r": 1}
                   | {"type": "atr", "length": 14, "multiplier": 3}
                   | {"breakeven_r": 1}                                      | null,
      "take_profit": {"type": "percent", "value": 4}
                   | {"type": "r_multiple", "value": 2}
                   | {"type": "r_multiple",
                      "levels": [{"r": 1, "close_pct": 50}, {"r": 2, "close_pct": 50}]}
                   | null,
      "sizing":      {"mode": "fraction", "value": 1.0} | {"mode": "fixed", "value": 1000}
                   | {"mode": "risk", "risk_pct": 1.0}
                   | {"mode": "volatility", "target_pct": 1.0, "length": 14}
                     (+ "max_position_pct": 100, "min_notional": 10 in every mode),
      "guards":      {"max_daily_loss_pct": 3, "max_drawdown_pct": 10, "cooldown_bars": 5,
                      "max_consecutive_losses": 3}
    }

Formulas and the order of operations are in docs/risk-management.md.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, Literal, Union

import numpy as np
import pandas as pd
import trading_indicators as ti
from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    ValidationError,
    model_validator,
)

from trading_backtest.sizing import ContractSpec, round_lots

if TYPE_CHECKING:
    from trading_backtest.config import BacktestConfig

LONG, SHORT = 1, -1
MAX_TARGETS = 5
INVALID_REASONS = (
    "stop_unavailable",  # ATR / swing not computable yet (warm-up)
    "stop_wrong_side",  # the stop is not below (long) / above (short) the entry
    "atr_unavailable",  # volatility sizing without an ATR value
    "no_equity",
    "size_below_min",
)


# --- errors ----------------------------------------------------------------------------------


def _path(loc: Sequence[str | int]) -> str:
    out = ""
    for part in loc:
        if isinstance(part, int):
            out += f"[{part}]"
        elif isinstance(part, str) and part.startswith("<"):
            continue  # union tag added by Pydantic
        else:
            out += f".{part}" if out else str(part)
    return out


class ConfigError(ValueError):
    """Invalid config. ``errors`` = ``[{"path", "loc", "message"}]`` (``path`` like
    ``stop.multiplier``); ``str()`` = ``"path: message; ..."``."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(
            "; ".join(f"{e['path']}: {e['message']}" if e["path"] else e["message"] for e in errors)
        )


def issue(loc: Sequence[str | int], message: str) -> dict[str, Any]:
    return {
        "path": _path(loc),
        "loc": [p for p in loc if not (isinstance(p, str) and p.startswith("<"))],
        "message": message,
    }


def pydantic_errors(exc: ValidationError, prefix: Sequence[str | int] = ()) -> ConfigError:
    out = []
    for e in exc.errors(include_url=False):
        message = e["msg"].removeprefix("Value error, ")
        if e["type"] == "extra_forbidden":
            message = "unknown field"
        out.append(issue((*prefix, *e["loc"]), message))
    return ConfigError(out)


# --- input models (validation + JSON Schema) ---------------------------------------------------


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Pct = Annotated[float, Field(gt=0, le=99, allow_inf_nan=False)]
Length = Annotated[int, Field(ge=1, le=500, strict=True)]
Multiplier = Annotated[float, Field(gt=0, le=50, allow_inf_nan=False)]
RValue = Annotated[float, Field(gt=0, le=100, allow_inf_nan=False)]
ClosePct = Annotated[float, Field(gt=0, le=100, allow_inf_nan=False)]


def _tag(key: str, default: str | None = None):
    def get(v: Any) -> str | None:
        value = v.get(key, default) if isinstance(v, dict) else getattr(v, key, default)
        return f"<{value}>" if isinstance(value, str) else None

    return get


class PercentStop(_M):
    """``value`` % from the entry."""

    type: Literal["percent"]
    value: Pct


class AtrStop(_M):
    """``multiplier`` x ATR(``length``) of the signal bar from the entry."""

    type: Literal["atr"]
    length: Length = 14
    multiplier: Multiplier = 2.0


class SwingStop(_M):
    """Below the lowest low (long) / above the highest high (short) of the last ``lookback``
    closed bars, ``buffer_pct`` % further away."""

    type: Literal["swing"]
    lookback: Length = 10
    buffer_pct: float = Field(default=0.0, ge=0, le=50, allow_inf_nan=False)


StopIn = Annotated[
    Union[  # noqa: UP007
        Annotated[PercentStop, Tag("<percent>")],
        Annotated[AtrStop, Tag("<atr>")],
        Annotated[SwingStop, Tag("<swing>")],
    ],
    Discriminator(
        _tag("type"),
        custom_error_type="stop_type",
        custom_error_message="stop needs 'type': 'percent', 'atr' or 'swing'",
    ),
]

ActivationR = Annotated[
    RValue | None, Field(default=None, description="trail only after price moved this many R")
]
BreakevenR = Annotated[
    RValue | None, Field(default=None, description="stop to entry + costs after this many R")
]


class PercentTrailing(_M):
    """Stop ``value`` % below the highest high (long) / above the lowest low since entry."""

    type: Literal["percent"]
    value: Pct
    activation_r: ActivationR = None
    breakeven_r: BreakevenR = None


class AtrTrailing(_M):
    """Chandelier: ``multiplier`` x ATR(``length``) from the highest high / lowest low since
    entry (ATR of the bar whose close updates the stop)."""

    type: Literal["atr"]
    length: Length = 14
    multiplier: Multiplier = 3.0
    activation_r: ActivationR = None
    breakeven_r: BreakevenR = None


class BreakevenOnly(_M):
    """Only move the stop to entry + costs after ``breakeven_r`` R."""

    type: Literal["breakeven"] = "breakeven"
    breakeven_r: RValue


TrailingIn = Annotated[
    Union[  # noqa: UP007
        Annotated[PercentTrailing, Tag("<percent>")],
        Annotated[AtrTrailing, Tag("<atr>")],
        Annotated[BreakevenOnly, Tag("<breakeven>")],
    ],
    Discriminator(
        _tag("type", "breakeven"),
        custom_error_type="trailing_type",
        custom_error_message="trailing needs 'type': 'percent' or 'atr' (or only breakeven_r)",
    ),
]


class PercentLevel(_M):
    pct: float = Field(gt=0, le=1000, allow_inf_nan=False)
    close_pct: ClosePct


class RLevel(_M):
    r: RValue
    close_pct: ClosePct


def _check_levels(levels: Sequence[Any], key: str) -> None:
    values = [getattr(lv, key) for lv in levels]
    if any(b <= a for a, b in zip(values, values[1:], strict=False)):
        raise ValueError(f"levels must be in ascending {key}")
    if sum(lv.close_pct for lv in levels) > 100 + 1e-9:
        raise ValueError("the close_pct of all levels must add up to at most 100")


class PercentTarget(_M):
    """``value`` % from the entry, or several ``levels`` closing part of the position each."""

    type: Literal["percent"]
    value: float | None = Field(default=None, gt=0, le=1000, allow_inf_nan=False)
    levels: list[PercentLevel] | None = Field(default=None, min_length=1, max_length=MAX_TARGETS)

    @model_validator(mode="after")
    def _one(self) -> PercentTarget:
        if (self.value is None) == (self.levels is None):
            raise ValueError("give either value or levels")
        if self.levels:
            _check_levels(self.levels, "pct")
        return self


class RTarget(_M):
    """``value`` R from the entry (R = entry - initial stop), or several ``levels``."""

    type: Literal["r_multiple"]
    value: RValue | None = None
    levels: list[RLevel] | None = Field(default=None, min_length=1, max_length=MAX_TARGETS)

    @model_validator(mode="after")
    def _one(self) -> RTarget:
        if (self.value is None) == (self.levels is None):
            raise ValueError("give either value or levels")
        if self.levels:
            _check_levels(self.levels, "r")
        return self


TakeProfitIn = Annotated[
    Union[  # noqa: UP007
        Annotated[PercentTarget, Tag("<percent>")],
        Annotated[RTarget, Tag("<r_multiple>")],
    ],
    Discriminator(
        _tag("type"),
        custom_error_type="take_profit_type",
        custom_error_message="take_profit needs 'type': 'percent' or 'r_multiple'",
    ),
]

MaxPosition = Annotated[
    float,
    Field(default=100.0, gt=0, le=1000, allow_inf_nan=False, description="% of equity, 100 = 1x"),
]
MinNotional = Annotated[
    float, Field(default=10.0, ge=0, le=1e9, allow_inf_nan=False, description="quote currency")
]


class FractionSizing(_M):
    """``value`` (0, 1] of current equity."""

    mode: Literal["fraction"] = "fraction"
    value: float = Field(default=1.0, gt=0, le=1, allow_inf_nan=False)
    max_position_pct: MaxPosition = 100.0
    min_notional: MinNotional = 10.0


class FixedSizing(_M):
    """``value`` quote currency of notional per trade."""

    mode: Literal["fixed"]
    value: float | None = Field(default=None, gt=0, le=1e12, allow_inf_nan=False)
    max_position_pct: MaxPosition = 100.0
    min_notional: MinNotional = 10.0

    @model_validator(mode="after")
    def _value(self) -> FixedSizing:
        if self.value is None:
            raise ValueError("value (quote amount per trade) is required for fixed sizing")
        return self


class RiskSizing(_M):
    """Lose ``risk_pct`` % of equity (fees included) if the stop is hit. Needs a stop."""

    mode: Literal["risk"]
    risk_pct: float = Field(default=1.0, gt=0, le=100, allow_inf_nan=False)
    max_position_pct: MaxPosition = 100.0
    min_notional: MinNotional = 10.0


class VolatilitySizing(_M):
    """A move of one ATR(``length``) = ``target_pct`` % of equity."""

    mode: Literal["volatility"]
    target_pct: float = Field(default=1.0, gt=0, le=100, allow_inf_nan=False)
    length: Length = 14
    max_position_pct: MaxPosition = 100.0
    min_notional: MinNotional = 10.0


SizingIn = Annotated[
    Union[  # noqa: UP007
        Annotated[FractionSizing, Tag("<fraction>")],
        Annotated[FixedSizing, Tag("<fixed>")],
        Annotated[RiskSizing, Tag("<risk>")],
        Annotated[VolatilitySizing, Tag("<volatility>")],
    ],
    Discriminator(
        _tag("mode", "fraction"),
        custom_error_type="sizing_mode",
        custom_error_message="sizing.mode must be one of fraction, fixed, risk, volatility",
    ),
]


class GuardsIn(_M):
    max_daily_loss_pct: float | None = Field(default=None, gt=0, le=100, allow_inf_nan=False)
    max_drawdown_pct: float | None = Field(default=None, gt=0, le=100, allow_inf_nan=False)
    cooldown_bars: int | None = Field(default=None, ge=0, le=100_000, strict=True)
    max_consecutive_losses: int | None = Field(default=None, ge=1, le=1000, strict=True)

    @model_validator(mode="after")
    def _pause(self) -> GuardsIn:
        if self.max_consecutive_losses is not None and not self.cooldown_bars:
            raise ValueError("max_consecutive_losses needs cooldown_bars >= 1 (the pause)")
        return self


class RiskConfigIn(_M):
    """A user's risk rules (risk profile, per-activation override, or the risk part of a
    backtest config). ``fee_bps`` is only used for trade plans (live signals, calculator)."""

    stop: StopIn | None = None
    trailing: TrailingIn | None = None
    take_profit: TakeProfitIn | None = None
    sizing: SizingIn = FractionSizing()
    guards: GuardsIn | None = None
    fee_bps: float = Field(default=10.0, ge=0, le=1000, allow_inf_nan=False)


def stop_requirements(model: Any) -> list[dict[str, Any]]:
    """Rules that need a stop (R is the distance entry - initial stop)."""
    errors = []
    if model.stop is None:
        if isinstance(model.take_profit, RTarget):
            errors.append(issue(("take_profit", "type"), "r_multiple targets need a stop"))
        if isinstance(model.sizing, RiskSizing):
            errors.append(issue(("sizing", "mode"), "risk sizing needs a stop"))
        trailing = model.trailing
        if trailing is not None:
            for name in ("activation_r", "breakeven_r"):
                if getattr(trailing, name, None) is not None:
                    errors.append(issue(("trailing", name), f"{name} needs a stop"))
    return errors


# --- runtime rules -------------------------------------------------------------------------------


@dataclass(frozen=True)
class StopRule:
    type: Literal["percent", "atr", "swing"]
    value: float = 0.0  # percent
    length: int = 14  # atr
    multiplier: float = 2.0  # atr
    lookback: int = 10  # swing
    buffer_pct: float = 0.0  # swing

    def to_dict(self) -> dict[str, Any]:
        if self.type == "percent":
            return {"type": "percent", "value": self.value}
        if self.type == "atr":
            return {"type": "atr", "length": self.length, "multiplier": self.multiplier}
        return {"type": "swing", "lookback": self.lookback, "buffer_pct": self.buffer_pct}


@dataclass(frozen=True)
class TrailingRule:
    type: Literal["percent", "atr", "breakeven"]
    value: float = 0.0  # percent
    length: int = 14  # atr
    multiplier: float = 3.0  # atr
    activation_r: float | None = None
    breakeven_r: float | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.type == "breakeven":
            return {"type": "breakeven", "breakeven_r": self.breakeven_r}
        out: dict[str, Any] = {"type": self.type}
        if self.type == "percent":
            out["value"] = self.value
        else:
            out.update(length=self.length, multiplier=self.multiplier)
        out.update(activation_r=self.activation_r, breakeven_r=self.breakeven_r)
        return out


@dataclass(frozen=True)
class TargetRule:
    """``levels`` = ((distance, close fraction 0-1), ...); distance in % (``percent``) or R."""

    type: Literal["percent", "r_multiple"]
    levels: tuple[tuple[float, float], ...]

    def to_dict(self) -> dict[str, Any]:
        key = "pct" if self.type == "percent" else "r"
        if len(self.levels) == 1 and self.levels[0][1] == 1.0:
            return {"type": self.type, "value": self.levels[0][0]}
        return {
            "type": self.type,
            "levels": [{key: d, "close_pct": round(f * 100, 10)} for d, f in self.levels],
        }


@dataclass(frozen=True)
class Guards:
    max_daily_loss_pct: float | None = None
    max_drawdown_pct: float | None = None
    cooldown_bars: int = 0
    max_consecutive_losses: int | None = None

    @property
    def any(self) -> bool:
        return bool(
            self.max_daily_loss_pct
            or self.max_drawdown_pct
            or self.cooldown_bars
            or self.max_consecutive_losses
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "cooldown_bars": self.cooldown_bars,
            "max_consecutive_losses": self.max_consecutive_losses,
        }


def stop_rule(model: Any) -> StopRule | None:
    if model is None:
        return None
    if isinstance(model, PercentStop):
        return StopRule("percent", value=float(model.value))
    if isinstance(model, AtrStop):
        return StopRule("atr", length=model.length, multiplier=float(model.multiplier))
    return StopRule("swing", lookback=model.lookback, buffer_pct=float(model.buffer_pct))


def trailing_rule(model: Any) -> TrailingRule | None:
    if model is None:
        return None
    if isinstance(model, BreakevenOnly):
        return TrailingRule("breakeven", breakeven_r=float(model.breakeven_r))
    common = {
        "activation_r": None if model.activation_r is None else float(model.activation_r),
        "breakeven_r": None if model.breakeven_r is None else float(model.breakeven_r),
    }
    if isinstance(model, PercentTrailing):
        return TrailingRule("percent", value=float(model.value), **common)
    return TrailingRule("atr", length=model.length, multiplier=float(model.multiplier), **common)


def target_rule(model: Any) -> TargetRule | None:
    if model is None:
        return None
    if model.levels is None:
        return TargetRule(model.type, ((float(model.value), 1.0),))
    key = "pct" if model.type == "percent" else "r"
    return TargetRule(
        model.type, tuple((float(getattr(lv, key)), lv.close_pct / 100) for lv in model.levels)
    )


def guards_rule(model: GuardsIn | None) -> Guards:
    if model is None:
        return Guards()
    return Guards(
        max_daily_loss_pct=model.max_daily_loss_pct,
        max_drawdown_pct=model.max_drawdown_pct,
        cooldown_bars=model.cooldown_bars or 0,
        max_consecutive_losses=model.max_consecutive_losses,
    )


# --- risk configs (profiles) ---------------------------------------------------------------------


TEMPLATES: dict[str, dict[str, Any]] = {
    "conservative": {
        "stop": {"type": "atr", "length": 14, "multiplier": 2.0},
        "take_profit": {"type": "r_multiple", "value": 2},
        "sizing": {"mode": "risk", "risk_pct": 0.5},
        "guards": {"max_drawdown_pct": 10},
    },
    "balanced": {
        "stop": {"type": "atr", "length": 14, "multiplier": 2.0},
        "take_profit": {
            "type": "r_multiple",
            "levels": [{"r": 1, "close_pct": 50}, {"r": 2, "close_pct": 50}],
        },
        "sizing": {"mode": "risk", "risk_pct": 1.0},
    },
    "aggressive": {
        "stop": {"type": "atr", "length": 14, "multiplier": 1.5},
        "trailing": {"type": "atr", "length": 14, "multiplier": 3.0},
        "sizing": {"mode": "risk", "risk_pct": 2.0},
    },
}
DEFAULT_TEMPLATE = "balanced"


def validate_risk_config(data: Any) -> dict[str, Any]:
    """The normalised risk config (defaults explicit), or :class:`ConfigError` with paths."""
    try:
        model = RiskConfigIn.model_validate(data if data is not None else {})
    except ValidationError as exc:
        raise pydantic_errors(exc) from None
    errors = stop_requirements(model)
    if errors:
        raise ConfigError(errors)
    from trading_backtest.config import sizer_from  # noqa: PLC0415 - import cycle

    stop, trailing = stop_rule(model.stop), trailing_rule(model.trailing)
    target = target_rule(model.take_profit)
    return {
        "stop": stop.to_dict() if stop else None,
        "trailing": trailing.to_dict() if trailing else None,
        "take_profit": target.to_dict() if target else None,
        "sizing": sizer_from(model.sizing).to_dict(),
        "guards": guards_rule(model.guards).to_dict(),
        "fee_bps": float(model.fee_bps),
    }


def risk_json_schema() -> dict[str, Any]:
    return RiskConfigIn.model_json_schema()


# --- trade plans ---------------------------------------------------------------------------------


@dataclass
class TradePlan:
    """What to do with a signal: where to stop, where to take profit, how much.

    ``entry_ref`` is the reference entry (the signal bar's close; a real fill is at the next
    open). ``targets`` = ``[{"price", "r", "close_pct"}]``. ``rr`` = reward:risk of the first
    target. ``invalid_reason`` is set when the trade should not be taken (see
    ``INVALID_REASONS``); the other fields are filled as far as they could be computed.

    With contract specs (``plan_trade(..., spec=...)``): ``lots`` = ``quantity`` /
    contract size rounded down to the lot step (0 and ``lots_feasible`` false when it is below
    the minimum or the account currency cannot be converted), ``conversion_rate`` = account
    currency per unit of the quote currency, ``sizing_warnings`` = what was adjusted or missing.
    ``risk_amount`` is then in the account currency (the equity's), ``notional`` stays in the
    quote currency. Without specs these fields are null/empty and nothing else changes.
    """

    side: str  # "long" | "short"
    entry_ref: float
    stop: float | None
    targets: list[dict[str, float | None]] = field(default_factory=list)
    quantity: float = 0.0
    notional: float = 0.0
    risk_amount: float | None = None
    risk_pct: float | None = None
    rr: float | None = None
    invalid_reason: str | None = None
    equity: float = 0.0
    atr: float | None = None
    trailing: dict[str, Any] | None = None
    lots: float | None = None
    lots_feasible: bool | None = None
    lots_risk_amount: float | None = None  # price-move risk of ``lots``, account currency
    conversion_rate: float | None = None
    sizing_warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.invalid_reason is None

    def to_dict(self) -> dict[str, Any]:
        def num(x: float | None, digits: int = 8) -> float | None:
            return None if x is None or not math.isfinite(x) else round(float(x), digits)

        return {
            "side": self.side,
            "entry_ref": num(self.entry_ref),
            "stop": num(self.stop),
            "targets": [
                {"price": num(t["price"]), "r": num(t["r"], 4), "close_pct": num(t["close_pct"], 4)}
                for t in self.targets
            ],
            "quantity": num(self.quantity, 10),
            "notional": num(self.notional, 4),
            "risk_amount": num(self.risk_amount, 4),
            "risk_pct": num(self.risk_pct, 4),
            "rr": num(self.rr, 4),
            "invalid_reason": self.invalid_reason,
            "equity": num(self.equity, 4),
            "atr": num(self.atr),
            "trailing": self.trailing,
            "lots": num(self.lots),
            "lots_feasible": self.lots_feasible,
            "lots_risk_amount": num(self.lots_risk_amount, 4),
            "conversion_rate": num(self.conversion_rate, 10),
            "sizing_warnings": list(self.sizing_warnings),
        }


def breakeven_level(side: int, entry: float, fee: float, slip: float) -> float:
    """The stop price at which an exit covers the entry and the round-trip costs: a long
    exits at ``level * (1 - slip)`` and pays the fee on both fills."""
    if side == LONG:
        return entry * (1 + fee) / ((1 - fee) * (1 - slip))
    return entry * (1 - fee) / ((1 + fee) * (1 + slip))


class RiskContext:
    """The per-bar arrays the risk rules read (ATR by length, swing lows/highs), computed once
    for a frame; every value at bar ``i`` uses bars ``<= i`` only."""

    def __init__(self, df: pd.DataFrame, config: BacktestConfig) -> None:
        self.config = config
        self.close = df["close"].to_numpy(dtype=np.float64)
        exits, sizer = config.exits, config.sizing
        lengths = set()
        if exits.stop is not None and exits.stop.type == "atr":
            lengths.add(exits.stop.length)
        if exits.trailing is not None and exits.trailing.type == "atr":
            lengths.add(exits.trailing.length)
        if sizer.mode == "volatility":
            lengths.add(sizer.length)
        self.atr = {n: ti.atr(df, n).to_numpy(dtype=np.float64) for n in sorted(lengths)}
        self.swing_low = self.swing_high = None
        if exits.stop is not None and exits.stop.type == "swing":
            n = exits.stop.lookback
            lows = df["low"].astype("float64")
            highs = df["high"].astype("float64")
            self.swing_low = lows.rolling(n, min_periods=n).min().to_numpy(copy=True)
            self.swing_high = highs.rolling(n, min_periods=n).max().to_numpy(copy=True)

    def stop_level(self, i: int, side: int, entry: float) -> tuple[float | None, str | None]:
        """(stop price, invalid reason) for an entry on the signal of bar ``i``."""
        rule = self.config.exits.stop
        if rule is None:
            return None, None
        if rule.type == "percent":
            return entry * (1 - side * rule.value / 100), None
        if rule.type == "atr":
            a = self.atr[rule.length][i]
            if not a > 0:
                return None, "stop_unavailable"
            stop = entry - side * rule.multiplier * a
        else:
            extreme = (self.swing_low if side == LONG else self.swing_high)[i]
            if not extreme == extreme:  # NaN
                return None, "stop_unavailable"
            stop = extreme * (1 - side * rule.buffer_pct / 100)
        if side * (entry - stop) <= 0:
            return stop, "stop_wrong_side"
        return stop, None

    def plan(
        self,
        i: int,
        side: int,
        equity: float,
        entry: float | None = None,
        stop_price: float | None = None,
        spec: ContractSpec | None = None,
        conversion_rate: float | None = None,
    ) -> TradePlan:
        """The plan for the signal of bar ``i``: ``entry`` defaults to that bar's close (the
        engine passes the real fill); ``stop_price`` overrides the stop rule. With ``spec`` and
        ``conversion_rate`` (account currency per quote unit), ``equity`` is in the account
        currency and the plan also has ``lots`` (see :class:`TradePlan`)."""
        config = self.config
        entry = float(self.close[i]) if entry is None else float(entry)
        fee = config.fee_rate
        if stop_price is not None:
            stop: float | None = float(stop_price)
            reason = "stop_wrong_side" if side * (entry - stop) <= 0 else None
        else:
            stop, reason = self.stop_level(i, side, entry)
        sizer = config.sizing
        atr_sizing = self.atr[sizer.length][i] if sizer.mode == "volatility" else None
        plan = TradePlan(
            side="long" if side == LONG else "short",
            entry_ref=entry,
            stop=stop,
            equity=equity,
            atr=atr_sizing if atr_sizing is not None and atr_sizing == atr_sizing else None,
            trailing=config.exits.trailing.to_dict() if config.exits.trailing else None,
        )
        per_unit = abs(entry - stop) if stop is not None and reason is None else None
        target = config.exits.take_profit
        if target is not None and reason is None:
            for distance, fraction in target.levels:
                if target.type == "percent":
                    price = entry * (1 + side * distance / 100)
                    r = abs(price - entry) / per_unit if per_unit else None
                else:
                    price = entry + side * distance * per_unit  # stop validated present
                    r = distance
                plan.targets.append({"price": price, "r": r, "close_pct": fraction * 100})
        rate = conversion_rate if spec is not None else None
        if spec is not None:
            plan.lots, plan.lots_feasible, plan.conversion_rate = 0.0, False, rate
            if rate is None:
                plan.sizing_warnings.append(
                    f"no conversion rate from {spec.quote_currency} to the account currency: "
                    "lots not computed, quantity assumes equity in the quote currency"
                )
        if reason is not None:
            plan.invalid_reason = reason
            return plan
        # the sizer works in the quote currency: convert the equity when the rate is known
        qty, size_reason = sizer.size(
            equity / rate if rate else equity, entry, fee, stop, atr_sizing
        )
        plan.quantity, plan.notional = qty, qty * entry
        if per_unit is not None and qty > 0:
            plan.risk_amount = (per_unit * qty + (entry + stop) * qty * fee) * (rate or 1.0)
            plan.risk_pct = plan.risk_amount / equity * 100 if equity > 0 else None
            if plan.targets:
                plan.rr = abs(plan.targets[0]["price"] - entry) / per_unit
        plan.invalid_reason = size_reason
        if spec is not None and rate is not None:
            lots, feasible, warnings = round_lots(qty / spec.contract_size, spec)
            plan.lots, plan.lots_feasible = lots, feasible
            plan.sizing_warnings.extend(warnings)
            if per_unit is not None:
                plan.lots_risk_amount = lots * spec.contract_size * per_unit * rate
        return plan


def plan_trade(
    df: pd.DataFrame,
    signal_bar_index: int,
    side: int | str,
    risk_config: BacktestConfig | Mapping[str, Any] | None,
    equity: float,
    *,
    entry: float | None = None,
    stop: float | None = None,
    spec: ContractSpec | None = None,
    conversion_rate: float | None = None,
) -> TradePlan:
    """The trade plan for a signal on ``df``'s bar ``signal_bar_index`` (bars after it are
    never read). ``side`` = 1/-1 or "buy"/"sell"/"long"/"short". ``risk_config`` is a risk
    config (``RiskConfigIn`` JSON) or a :class:`BacktestConfig`. The backtest engine computes
    every entry with the same code (:meth:`RiskContext.plan`).

    ``spec`` + ``conversion_rate`` (account currency per unit of the quote currency, see
    :mod:`trading_backtest.sizing`): ``equity`` is in the account currency, the size is
    computed on it converted to the quote currency, and the plan gets ``lots``."""
    from trading_backtest.config import BacktestConfig  # noqa: PLC0415 - import cycle

    if isinstance(side, str):
        side = LONG if side in ("buy", "long") else SHORT if side in ("sell", "short") else 0
    if side not in (LONG, SHORT):
        raise ValueError("side must be 1/-1, buy/sell or long/short")
    if not 0 <= signal_bar_index < len(df):
        raise ValueError("signal_bar_index is outside the frame")
    if not isinstance(risk_config, BacktestConfig):
        risk_config = BacktestConfig.from_risk(risk_config)
    ctx = RiskContext(df.iloc[: signal_bar_index + 1], risk_config)
    return ctx.plan(
        signal_bar_index,
        side,
        float(equity),
        entry=entry,
        stop_price=stop,
        spec=spec,
        conversion_rate=conversion_rate,
    )


def history(risk_config: BacktestConfig) -> int:
    """Bars needed before the signal bar for the risk rules' indicators to be settled."""
    needed = 1
    exits, sizer = risk_config.exits, risk_config.sizing
    lengths = []
    if exits.stop is not None and exits.stop.type == "atr":
        lengths.append(exits.stop.length)
    if exits.trailing is not None and exits.trailing.type == "atr":
        lengths.append(exits.trailing.length)
    if sizer.mode == "volatility":
        lengths.append(sizer.length)
    spec = ti.get_indicator("atr")
    for n in lengths:
        needed = max(needed, spec.lookback({"length": n}) + spec.convergence({"length": n}) + 1)
    if exits.stop is not None and exits.stop.type == "swing":
        needed = max(needed, exits.stop.lookback)
    return needed
