"""No look-ahead for custom strategies: random Builder definitions and Composites built from
them never change a signal when future bars are appended or changed."""

import numpy as np
import pandas as pd
import pytest

import trading_strategies as ts
from tests.conftest import synthetic_ohlcv
from tests.custom_utils import UUID_A, UUID_B, random_builder
from tests.test_no_lookahead import _future


def _strategies(seed: int) -> list[ts.Strategy]:
    rng = np.random.default_rng(seed)
    builders = [random_builder(rng) for _ in range(3)]
    defs = {UUID_A: ("builder", builders[1]), UUID_B: ("builder", builders[2])}
    composite = {
        "schema_version": 1,
        "members": [
            {"ref": "rsi_reversal", "params": {"oversold": 45, "overbought": 55}},
            {"ref": UUID_A, "weight": 2},
            {"ref": UUID_B},
        ],
        "mode": str(rng.choice(["any", "majority", "weighted"])),
        "window": int(rng.integers(1, 6)),
        "threshold": 0.3,
    }
    return [
        ts.BuilderStrategy(builders[0]),
        ts.CompositeStrategy(composite, lambda r: defs[r]),
    ]


@pytest.mark.parametrize("seed", range(8))
def test_appending_future_bars_changes_nothing(seed: int) -> None:
    rng = np.random.default_rng(1000 + seed)
    history = synthetic_ohlcv(700, seed=seed)
    for strategy in _strategies(seed):
        for _ in range(6):
            n = int(rng.integers(0, len(history)))
            past = history.iloc[: n + 1]
            extended = pd.concat([past, _future(past, int(rng.integers(1, 120)), rng)])
            before = strategy.generate(past)
            after = strategy.generate(extended).iloc[: n + 1]
            pd.testing.assert_frame_equal(before, after, check_exact=True)


@pytest.mark.parametrize("seed", range(8))
def test_changing_a_future_bar_changes_nothing_before_it(seed: int) -> None:
    df = synthetic_ohlcv(600, seed=50 + seed)
    shocked = df.copy()
    shocked.iloc[450, :] = shocked.iloc[450, :] * [1.0, 1.3, 0.7, 1.25, 40.0]
    for strategy in _strategies(seed):
        base = strategy.generate(df)
        after = strategy.generate(shocked)
        pd.testing.assert_frame_equal(base.iloc[:450], after.iloc[:450], check_exact=True)


def test_random_definitions_fire() -> None:
    """The property tests above compare real signal rows, not only empty frames."""
    df = synthetic_ohlcv(700, seed=0)
    fired = sum(
        int((s.generate(df)["signal"] != 0).sum()) for k in range(8) for s in _strategies(k)
    )
    assert fired > 50
