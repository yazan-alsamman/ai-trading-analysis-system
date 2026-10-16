"""Helpers for the custom strategy tests: operand shorthands, hand-built frames and a small
random definition generator."""

import numpy as np
import pandas as pd

UUID_A = "custom:aaaaaaaa-0000-4000-8000-000000000001"
UUID_B = "custom:bbbbbbbb-0000-4000-8000-000000000002"
UUID_C = "custom:cccccccc-0000-4000-8000-000000000003"
UUID_D = "custom:dddddddd-0000-4000-8000-000000000004"


def ind(
    name: str, shift: int = 0, output: str | None = None, multiplier: float = 1.0, **params
) -> dict:
    op = {"type": "indicator", "name": name, "params": params, "shift": shift}
    if multiplier != 1.0:
        op["multiplier"] = multiplier
    if output is not None:
        op["output"] = output
    return op


def price(field: str = "close", shift: int = 0) -> dict:
    return {"type": "price", "field": field, "shift": shift}


def const(value: float, shift: int = 0) -> dict:
    return {"type": "constant", "value": value, "shift": shift}


def cond(left: dict, op: str, right: dict) -> dict:
    return {"left": left, "op": op, "right": right}


def builder(buy=None, sell=None, strength: str = "fixed", category: str = "trend") -> dict:
    d = {"schema_version": 1, "strength": strength, "category": category}
    if buy is not None:
        d["buy"] = buy
    if sell is not None:
        d["sell"] = sell
    return d


def frame(close, *, open_=None, high=None, low=None, volume=None) -> pd.DataFrame:
    close = np.asarray(close, dtype=float)
    data = {
        "open": close if open_ is None else np.asarray(open_, dtype=float),
        "high": close + 0.5 if high is None else np.asarray(high, dtype=float),
        "low": close - 0.5 if low is None else np.asarray(low, dtype=float),
        "close": close,
        "volume": np.ones(len(close)) if volume is None else np.asarray(volume, dtype=float),
    }
    index = pd.date_range("2026-01-01", periods=len(close), freq="h", tz="UTC")
    return pd.DataFrame(data, index=index)


def signal_bars(out: pd.DataFrame) -> dict[int, int]:
    sig = out["signal"].to_numpy()
    return {int(t): int(sig[t]) for t in np.flatnonzero(sig)}


MA_CROSSOVER_REPLICA = builder(
    buy={"all": [cond(ind("ema", length=9), "crosses_above", ind("ema", length=21))]},
    sell={"all": [cond(ind("ema", length=9), "crosses_below", ind("ema", length=21))]},
)
RSI_REVERSAL_REPLICA = builder(  # prev RSI < 30 <= RSI now; prev RSI > 70 >= RSI now
    buy={
        "all": [
            cond(ind("rsi", shift=1, length=14), "<", const(30)),
            cond(ind("rsi", length=14), ">=", const(30)),
        ]
    },
    sell={
        "all": [
            cond(ind("rsi", shift=1, length=14), ">", const(70)),
            cond(ind("rsi", length=14), "<=", const(70)),
        ]
    },
    category="mean_reversion",
)


# --- random definitions ------------------------------------------------------------------------

_INDICATORS = [
    lambda rng: ind("rsi", length=int(rng.integers(2, 20))),
    lambda rng: ind("ema", length=int(rng.integers(2, 30))),
    lambda rng: ind("sma", length=int(rng.integers(2, 30))),
    lambda rng: ind("bollinger", output=str(rng.choice(["upper", "middle", "lower"])), length=10),
    lambda rng: ind("macd", output=str(rng.choice(["macd", "signal", "histogram"]))),
    lambda rng: ind("atr", length=int(rng.integers(2, 20))),
    lambda rng: ind("volume_sma", length=int(rng.integers(2, 20))),
]


def random_operand(rng: np.random.Generator) -> dict:
    kind = rng.integers(0, 3)
    if kind == 0:
        op = _INDICATORS[int(rng.integers(0, len(_INDICATORS)))](rng)
    elif kind == 1:
        op = price(str(rng.choice(["open", "high", "low", "close", "volume", "hl2", "hlc3"])))
    else:
        op = const(float(rng.choice([0, 30, 50, 70, 100])))
    op["shift"] = int(rng.choice([0, 0, 0, 1, 2, 5]))
    return op


def random_condition(rng: np.random.Generator) -> dict:
    kind = rng.integers(0, 10)
    if kind < 6:
        op = str(rng.choice([">", "<", ">=", "<=", "crosses_above", "crosses_below"]))
        return cond(random_operand(rng), op, random_operand(rng))
    if kind < 8:
        return {
            "op": str(rng.choice(["rising", "falling"])),
            "value": random_operand(rng),
            "bars": int(rng.integers(1, 4)),
        }
    return {
        "op": "between",
        "value": random_operand(rng),
        "lower": random_operand(rng),
        "upper": random_operand(rng),
    }


def random_group(rng: np.random.Generator, depth: int = 1) -> dict:
    children = []
    for _ in range(int(rng.integers(1, 4))):
        if depth < 3 and rng.random() < 0.25:
            children.append(random_group(rng, depth + 1))
        else:
            children.append(random_condition(rng))
    return {str(rng.choice(["all", "any"])): children}


def random_builder(rng: np.random.Generator) -> dict:
    return builder(
        buy=random_group(rng),
        sell=random_group(rng),
        strength=str(rng.choice(["fixed", "rule_ratio"])),
    )


def twenty_conditions() -> dict:
    """20 conditions, depth 2: buy = any of 9 upward crosses AND RSI between 20 and 70; sell
    mirrored (the performance check of docs/custom-strategies.md)."""

    def crosses(op: str) -> list[dict]:
        out = [cond(price("close"), op, ind("ema", length=n)) for n in (10, 20, 30, 50)]
        out += [cond(price("close"), op, ind("sma", length=n)) for n in (20, 50)]
        out += [cond(ind("rsi", length=n), op, const(50)) for n in (7, 14)]
        out.append(cond(ind("macd", output="macd"), op, ind("macd", output="signal")))
        return out

    rsi = ind("rsi", length=14)
    return builder(
        buy={
            "all": [
                {"any": crosses("crosses_above")},
                {"op": "between", "value": rsi, "lower": const(20), "upper": const(70)},
            ]
        },
        sell={
            "all": [
                {"any": crosses("crosses_below")},
                {"op": "between", "value": rsi, "lower": const(30), "upper": const(80)},
            ]
        },
        strength="rule_ratio",
        category="momentum",
    )
