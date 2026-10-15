"""Strategy catalog and the generic ``run()`` entry point."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import pandas as pd

from trading_strategies.base import Strategy
from trading_strategies.strategies import STRATEGY_CLASSES

STRATEGIES: dict[str, Strategy] = {cls.key: cls() for cls in STRATEGY_CLASSES}


def get_strategy(key: str) -> Strategy:
    try:
        return STRATEGIES[key]
    except KeyError:
        raise ValueError(
            f"unknown strategy {key!r} (available: {', '.join(sorted(STRATEGIES))})"
        ) from None


def run(key: str, df: pd.DataFrame, **params: Any) -> pd.DataFrame:
    """Signals of strategy ``key`` on an OHLCV frame (see :class:`Strategy.generate`)."""
    return get_strategy(key).generate(df, params)


def catalog() -> list[dict[str, Any]]:
    """JSON-serializable catalog, including the indicator lines each strategy draws."""
    return [s.to_dict() for s in STRATEGIES.values()]


def params_hash(key: str, params: Mapping[str, Any]) -> str:
    """Stable identity of a strategy configuration: sha256 of the key and the *resolved*
    params with sorted keys (so equal setups hash equally whatever the input order)."""
    resolved = get_strategy(key).resolve(params)
    payload = json.dumps({"key": key, "params": resolved}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:32]
