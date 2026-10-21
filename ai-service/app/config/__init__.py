"""Versioned configuration: instrument specs and the research protocol (D23).

    python -m app config    # print the resolved configuration

Values live in the TOML files next to this module so every experiment re-runs from config plus
a data hash."""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass
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


@dataclass(frozen=True)
class Splits:
    server_tz: str
    development: tuple[date, date]
    walk_forward: tuple[date, date]
    walk_forward_test_months: int
    secondary_holdout: tuple[date, date]
    lockbox_start: date
    embargo_days: int


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


def main(argv: list[str] | None = None) -> int:
    summary = {"instruments": {k: asdict(v) for k, v in instruments().items()}}
    summary["splits"] = asdict(splits())
    print(json.dumps(summary, indent=2, default=str))
    return 0
