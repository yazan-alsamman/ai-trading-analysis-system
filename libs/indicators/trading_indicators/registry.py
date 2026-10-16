"""Indicator catalog and the generic ``compute()`` entry point.

The catalog drives the indicator picker of the web/mobile apps and validates the parameters
the API receives, so everything here must stay JSON-serializable.
"""

from __future__ import annotations

import numbers
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from trading_indicators import core, momentum, trend, volatility, volume

Category = Literal["trend", "momentum", "volatility", "volume"]
Placement = Literal["overlay", "pane"]


@dataclass(frozen=True)
class Param:
    name: str
    type: Literal["int", "float"]
    default: int | float
    min: int | float
    max: int | float
    title: str = ""

    def validate(self, value: Any) -> int | float:
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise ValueError(f"{self.name} must be a number, got {value!r}")
        if self.type == "int":
            if isinstance(value, float) and not value.is_integer():
                raise ValueError(f"{self.name} must be an integer, got {value!r}")
            value = int(value)
        else:
            value = float(value)
        if not self.min <= value <= self.max:
            raise ValueError(f"{self.name} must be between {self.min} and {self.max}, got {value}")
        return value

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "min": self.min,
            "max": self.max,
            "title": self.title,
        }


@dataclass(frozen=True)
class Indicator:
    name: str
    title: str
    category: Category
    placement: Placement
    inputs: tuple[str, ...]  # ("close",) -> called with the close Series, else with the frame
    outputs: tuple[str, ...]
    params: tuple[Param, ...]
    func: Callable[..., pd.Series | pd.DataFrame]
    lookback_fn: Callable[[Mapping[str, Any]], int]
    levels: tuple[float, ...] = ()
    description: str = field(default="")
    # Extra history after the lookback for recursive smoothing (EMA/Wilder) to forget its seed
    # (initial error below ~1e-6). Window-based indicators need none.
    convergence_fn: Callable[[Mapping[str, Any]], int] = lambda p: 0
    # "day": values depend on every bar since 00:00 UTC (VWAP)
    anchor: Literal["day"] | None = None

    def resolve(self, params: Mapping[str, Any] | None = None) -> dict[str, int | float]:
        """Validate ``params`` against the catalog and fill in defaults."""
        params = dict(params or {})
        known = {p.name: p for p in self.params}
        unknown = sorted(set(params) - set(known))
        if unknown:
            allowed = ", ".join(known) or "none"
            raise ValueError(
                f"{self.name}: unknown parameter(s) {', '.join(unknown)} (allowed: {allowed})"
            )
        resolved = {}
        for name, spec in known.items():
            try:
                resolved[name] = spec.validate(params[name]) if name in params else spec.default
            except ValueError as exc:
                raise ValueError(f"{self.name}: {exc}") from None
        if self.name == "macd" and resolved["fast"] >= resolved["slow"]:
            raise ValueError(
                f"macd: fast ({resolved['fast']}) must be smaller than slow ({resolved['slow']})"
            )
        return resolved

    def lookback(self, params: Mapping[str, Any] | None = None) -> int:
        """Bars of history needed before the first value of every output is valid."""
        return self.lookback_fn(self.resolve(params))

    def convergence(self, params: Mapping[str, Any] | None = None) -> int:
        """Extra bars, on top of :meth:`lookback`, after which recursive smoothing no longer
        depends on where the data started (so values match a computation on longer history)."""
        return self.convergence_fn(self.resolve(params))

    def compute(self, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
        """One column per output, aligned to ``df.index``."""
        resolved = self.resolve(params)
        core.check_frame(df, self.inputs)
        source = df["close"] if self.inputs == ("close",) else df
        result = self.func(source, **resolved)
        if isinstance(result, pd.Series):
            result = result.to_frame(self.outputs[0])
        return result.loc[:, list(self.outputs)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "placement": self.placement,
            "inputs": list(self.inputs),
            "params": [p.to_dict() for p in self.params],
            "outputs": list(self.outputs),
            "levels": list(self.levels),
            "lookback": self.lookback(),  # with the default parameters
            "convergence": self.convergence(),
            "anchor": self.anchor,
            "description": self.description,
        }


def _length(default: int, title: str = "Length", name: str = "length") -> Param:
    return Param(name, "int", default, 1, 1000, title)


def _mult(name: str, default: float, title: str) -> Param:
    return Param(name, "float", default, 0.1, 10.0, title)


_CLOSE = ("close",)
_HLC = ("high", "low", "close")

_INDICATORS: tuple[Indicator, ...] = (
    # --- trend -----------------------------------------------------------------------------
    Indicator(
        "sma", "Simple Moving Average", "trend", "overlay", _CLOSE, ("sma",),
        (_length(20),), trend.sma, lambda p: p["length"] - 1,
        description="Arithmetic mean of the last N closes.",
    ),
    Indicator(
        "ema", "Exponential Moving Average", "trend", "overlay", _CLOSE, ("ema",),
        (_length(20),), trend.ema, lambda p: p["length"] - 1,
        description="EMA with alpha 2/(N+1), seeded with an SMA (TA-Lib).",
        convergence_fn=lambda p: 7 * p["length"],
    ),
    Indicator(
        "wma", "Weighted Moving Average", "trend", "overlay", _CLOSE, ("wma",),
        (_length(20),), trend.wma, lambda p: p["length"] - 1,
        description="Linearly weighted mean, newest close weighs most.",
    ),
    Indicator(
        "macd", "MACD", "trend", "pane", _CLOSE, ("macd", "signal", "histogram"),
        (
            _length(12, "Fast length", "fast"),
            _length(26, "Slow length", "slow"),
            _length(9, "Signal length", "signal"),
        ),
        trend.macd, lambda p: p["slow"] + p["signal"] - 2, levels=(0.0,),
        description="EMA(fast) - EMA(slow), its EMA signal line and the histogram.",
        convergence_fn=lambda p: 7 * (p["slow"] + p["signal"]),
    ),
    Indicator(
        "adx", "Average Directional Index", "trend", "pane", _HLC,
        ("adx", "plus_di", "minus_di"), (_length(14),), trend.adx,
        lambda p: 2 * p["length"] - 1, levels=(25.0,),
        description="Trend strength (ADX) with +DI/-DI, Wilder smoothing.",
        convergence_fn=lambda p: 28 * p["length"],
    ),
    Indicator(
        "supertrend", "Supertrend", "trend", "overlay", _HLC, ("supertrend", "direction"),
        (_length(10, "ATR length"), _mult("multiplier", 3.0, "ATR multiplier")),
        trend.supertrend, lambda p: p["length"],
        description="ATR trailing stop; direction +1 up, -1 down.",
        convergence_fn=lambda p: 14 * p["length"],
    ),
    Indicator(
        "ichimoku", "Ichimoku Cloud", "trend", "overlay", ("high", "low"),
        ("tenkan", "kijun", "senkou_a", "senkou_b"),
        (
            _length(9, "Conversion line", "tenkan"),
            _length(26, "Base line", "kijun"),
            _length(52, "Leading span B", "senkou"),
            Param("displacement", "int", 26, 0, 500, "Displacement"),
        ),
        trend.ichimoku,
        lambda p: max(p["tenkan"], p["kijun"], p["senkou"]) - 1 + p["displacement"],
        description="Tenkan, kijun and the cloud at each bar (no chikou: it needs future data).",
    ),
    # --- momentum --------------------------------------------------------------------------
    Indicator(
        "rsi", "Relative Strength Index", "momentum", "pane", _CLOSE, ("rsi",),
        (_length(14),), momentum.rsi, lambda p: p["length"], levels=(30.0, 70.0),
        description="Wilder RSI, 0-100; 50 when prices do not move.",
        convergence_fn=lambda p: 14 * p["length"],
    ),
    Indicator(
        "stoch", "Stochastic", "momentum", "pane", _HLC, ("k", "d"),
        (
            _length(14, "%K length", "k_length"),
            _length(3, "%K smoothing", "k_smooth"),
            _length(3, "%D smoothing", "d_smooth"),
        ),
        momentum.stoch, lambda p: p["k_length"] + p["k_smooth"] + p["d_smooth"] - 3,
        levels=(20.0, 80.0),
        description="Slow stochastic %K/%D, 0-100.",
    ),
    Indicator(
        "stochrsi", "Stochastic RSI", "momentum", "pane", _CLOSE, ("k", "d"),
        (
            _length(14, "RSI length", "rsi_length"),
            _length(14, "Stochastic length", "stoch_length"),
            _length(3, "%K smoothing", "k_smooth"),
            _length(3, "%D smoothing", "d_smooth"),
        ),
        momentum.stochrsi,
        lambda p: p["rsi_length"] + p["stoch_length"] + p["k_smooth"] + p["d_smooth"] - 3,
        levels=(20.0, 80.0),
        description="Stochastic of RSI, 0-100.",
        convergence_fn=lambda p: 14 * p["rsi_length"],
    ),
    Indicator(
        "cci", "Commodity Channel Index", "momentum", "pane", _HLC, ("cci",),
        (_length(20), Param("constant", "float", 0.015, 0.001, 1.0, "Constant")),
        momentum.cci, lambda p: p["length"] - 1, levels=(-100.0, 100.0),
        description="Deviation of the typical price from its mean, in mean deviations.",
    ),
    Indicator(
        "williams_r", "Williams %R", "momentum", "pane", _HLC, ("williams_r",),
        (_length(14),), momentum.williams_r, lambda p: p["length"] - 1,
        levels=(-80.0, -20.0),
        description="Close within the N-bar range, -100 to 0.",
    ),
    Indicator(
        "roc", "Rate of Change", "momentum", "pane", _CLOSE, ("roc",),
        (_length(10),), momentum.roc, lambda p: p["length"], levels=(0.0,),
        description="Percent change over N bars.",
    ),
    Indicator(
        "mfi", "Money Flow Index", "momentum", "pane", ("high", "low", "close", "volume"),
        ("mfi",), (_length(14),), momentum.mfi, lambda p: p["length"], levels=(20.0, 80.0),
        description="Volume-weighted RSI, 0-100; 50 when there is no flow.",
    ),
    # --- volatility ------------------------------------------------------------------------
    Indicator(
        "bollinger", "Bollinger Bands", "volatility", "overlay", _CLOSE,
        ("upper", "middle", "lower"),
        (_length(20), _mult("std", 2.0, "Standard deviations")),
        volatility.bollinger, lambda p: p["length"] - 1,
        description="SMA +/- k population standard deviations.",
    ),
    Indicator(
        "atr", "Average True Range", "volatility", "pane", _HLC, ("atr",),
        (_length(14),), volatility.atr, lambda p: p["length"],
        description="Wilder average of the true range.",
        convergence_fn=lambda p: 14 * p["length"],
    ),
    Indicator(
        "keltner", "Keltner Channels", "volatility", "overlay", _HLC,
        ("upper", "middle", "lower"),
        (
            _length(20, "EMA length"),
            _mult("multiplier", 2.0, "ATR multiplier"),
            _length(10, "ATR length", "atr_length"),
        ),
        volatility.keltner, lambda p: max(p["length"] - 1, p["atr_length"]),
        description="EMA +/- k ATR.",
        convergence_fn=lambda p: max(7 * p["length"], 14 * p["atr_length"]),
    ),
    Indicator(
        "donchian", "Donchian Channels", "volatility", "overlay", ("high", "low"),
        ("upper", "middle", "lower"), (_length(20),), volatility.donchian,
        lambda p: p["length"] - 1,
        description="Highest high / lowest low of the last N bars.",
    ),
    # --- volume ----------------------------------------------------------------------------
    Indicator(
        "obv", "On-Balance Volume", "volume", "pane", ("close", "volume"), ("obv",),
        (), volume.obv, lambda p: 0,
        description="Cumulative volume signed by the close direction.",
    ),
    Indicator(
        "vwap", "VWAP (daily, UTC)", "volume", "overlay",
        ("high", "low", "close", "volume"), ("vwap",), (), volume.vwap, lambda p: 0,
        description="Volume-weighted average price, reset at 00:00 UTC.",
        anchor="day",
    ),
    Indicator(
        "volume_sma", "Volume SMA", "volume", "pane", ("volume",), ("volume_sma",),
        (_length(20),), volume.volume_sma, lambda p: p["length"] - 1,
        description="Moving average of volume.",
    ),
)  # fmt: skip

INDICATORS: dict[str, Indicator] = {i.name: i for i in _INDICATORS}


def get_indicator(name: str) -> Indicator:
    try:
        return INDICATORS[name]
    except KeyError:
        raise ValueError(
            f"unknown indicator {name!r} (available: {', '.join(sorted(INDICATORS))})"
        ) from None


def compute(name: str, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """Compute indicator ``name`` on an OHLCV frame; one column per output."""
    return get_indicator(name).compute(df, **params)


def lookback(name: str, **params: Any) -> int:
    return get_indicator(name).lookback(params)


def catalog() -> list[dict[str, Any]]:
    """The JSON-serializable catalog of every indicator."""
    return [i.to_dict() for i in _INDICATORS]
