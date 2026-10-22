"""Versioned configuration: instrument specs and the research protocol (D23).

    python -m app config    # print the resolved configuration

Values live in the TOML files next to this module so every experiment re-runs from config plus
a data hash."""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, replace
from datetime import date
from functools import cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Instrument:
    symbol: str
    point: float
    price_decimals: int
    contract_size: float
    quote_currency: str
    week_open: str
    week_close: str
    daily_break: tuple[str, str] | None = None
    cost_extra_frac: float | None = None  # costs are configured per instrument (XAUUSD so far)
    cost_extra_min: float | None = None
    sl_slippage: float | None = None


@dataclass(frozen=True)
class Splits:
    server_tz: str
    development: tuple[date, date]
    walk_forward: tuple[date, date]
    walk_forward_test_months: int
    secondary_holdout: tuple[date, date]
    lockbox_start: date
    embargo_days: int


@dataclass(frozen=True)
class Strategy:
    """Strategy v1 parameters (``strategy.toml``); bar counts are in entry-timeframe bars."""

    context_timeframes: tuple[str, ...]
    entry_timeframe: str
    k_context: int
    k_entry: int
    max_age_days: int
    previous_day: bool
    atr_period: int
    min_depth_atr: float
    breakout_depth_atr: float
    close_back_bars: int
    choch_window_bars: int
    fvg_min_size_atr: float
    sl_buffer_atr: float
    min_r: float
    max_r: float
    horizon_bars: int
    entry_window_bars: int
    beyond_max_r: str
    spread_stat: str
    rule_set: str = "v1"
    break_is_gap: bool = False
    sweep_session: tuple[str, str] | None = None
    skip_us_holidays: bool = False
    fvg_required: bool = True
    entry_mode: str = "fvg_limit"  # or "close": market entry at the decision bar's close


def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, "rb") as f:
        return tomllib.load(f)


@cache
def instruments() -> dict[str, Instrument]:
    out = {}
    for symbol, spec in _load("instruments.toml").items():
        if "daily_break" in spec:
            spec["daily_break"] = tuple(spec["daily_break"])
        out[symbol] = Instrument(symbol=symbol, **spec)
    return out


def _period(pair: list[str]) -> tuple[date, date]:
    start, end = (date.fromisoformat(d) for d in pair)
    if not start < end:
        raise ValueError(f"empty period {pair}")
    return start, end


@cache
def splits() -> Splits:
    raw = _load("research.toml")
    s = raw["splits"]
    out = Splits(
        server_tz=raw["clock"]["server_tz"],
        development=_period(s["development"]),
        walk_forward=_period(s["walk_forward"]),
        walk_forward_test_months=s["walk_forward_test_months"],
        secondary_holdout=_period(s["secondary_holdout"]),
        lockbox_start=date.fromisoformat(s["lockbox_start"]),
        embargo_days=s["embargo_days"],
    )
    chain = [out.development, out.walk_forward, out.secondary_holdout]
    for (_, end), (start, _) in zip(chain, chain[1:], strict=False):
        if end != start:
            raise ValueError("the periods must follow each other without gaps or overlaps")
    if out.secondary_holdout[1] != out.lockbox_start:
        raise ValueError("the secondary holdout must end where the lockbox starts")
    return out


@cache
def strategy(rule_set: str = "v1") -> Strategy:
    """v1, or a named variant from ``[variants.<name>]`` applied on top of it."""
    raw = _load("strategy.toml")
    base = Strategy(
        context_timeframes=tuple(raw["timeframes"]["context"]),
        entry_timeframe=raw["timeframes"]["entry"],
        k_context=raw["swings"]["k_context"],
        k_entry=raw["swings"]["k_entry"],
        max_age_days=raw["liquidity"]["max_age_days"],
        previous_day=raw["liquidity"]["previous_day"],
        atr_period=raw["sweep"]["atr_period"],
        min_depth_atr=raw["sweep"]["min_depth_atr"],
        breakout_depth_atr=raw["sweep"]["breakout_depth_atr"],
        close_back_bars=raw["sweep"]["close_back_bars"],
        choch_window_bars=raw["choch"]["window_bars"],
        fvg_min_size_atr=raw["fvg"]["min_size_atr"],
        sl_buffer_atr=raw["trade"]["sl_buffer_atr"],
        min_r=raw["trade"]["min_r"],
        max_r=raw["trade"]["max_r"],
        horizon_bars=raw["trade"]["horizon_bars"],
        entry_window_bars=raw["trade"]["entry_window_bars"],
        beyond_max_r=raw["trade"]["beyond_max_r"],
        spread_stat=raw["trade"]["spread_stat"],
    )
    if rule_set == "v1":
        return base
    variants = raw.get("variants", {})
    if rule_set not in variants:
        raise KeyError(f"unknown rule set {rule_set!r}; known: v1, {', '.join(variants)}")
    changes = dict(variants[rule_set])
    if "sweep_session" in changes:
        changes["sweep_session"] = tuple(changes["sweep_session"])
    return replace(base, rule_set=rule_set, **changes)


def main(argv: list[str] | None = None) -> int:
    summary = {"instruments": {k: asdict(v) for k, v in instruments().items()}}
    summary["splits"] = asdict(splits())
    summary["strategy"] = asdict(strategy())
    print(json.dumps(summary, indent=2, default=str))
    return 0
