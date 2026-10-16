"""Y11 configs give bit-identical results with ``check_entry_bar: false``.

The reference is the Y11 engine itself (tests/y11_reference.py, kept verbatim from main @
230b5ab), run on the same machine, so float results are compared exactly whatever the platform.
With the default ``check_entry_bar: true`` stops/targets are also checked on the entry bar, so
only runs with stops or targets may differ (docs/risk-management.md).
"""

import numpy as np
import pytest
import trading_strategies as ts

import trading_backtest as tb
from tests.conftest import synthetic_ohlcv
from tests.y11_reference import y11_simulate

CORE = (
    "number", "side", "entry_time", "entry_price", "exit_time", "exit_price", "quantity",
    "gross_pnl", "fees", "net_pnl", "return_pct", "bars_held", "entry_reason", "exit_reason",
    "entry_index", "exit_index",
)  # fmt: skip
CONFIGS = [
    {},
    {"direction": "long_short"},
    {"exits": {"stop_loss_pct": 2, "take_profit_pct": 4, "max_bars_held": 30}},
    {
        "direction": "long_short",
        "sizing": {"mode": "fixed", "value": 2500},
        "exits": {"stop_loss_pct": 1.5},
    },
    {
        "sizing": {"mode": "fraction", "value": 0.5},
        "exits": {"take_profit_pct": 3, "exit_on_opposite_signal": False},
        "fee_bps": 7,
        "slippage_bps": 3,
    },
]
KEYS = ("ma_crossover", "rsi_reversal", "donchian_breakout")
CASES = [(key, k) for key in KEYS for k in range(len(CONFIGS))]


def _core(trades) -> list[tuple]:
    return [tuple(getattr(t, c) for c in CORE) for t in trades]


def _y11(df, key: str, config: dict):
    out = ts.get_strategy(key).generate(df)
    cfg = tb.BacktestConfig.from_dict(config)
    return y11_simulate(df, out["signal"].to_numpy(), out["reason"].to_numpy(dtype=object), cfg)


@pytest.fixture(scope="module")
def df():
    return synthetic_ohlcv(3000)


@pytest.mark.parametrize(("key", "k"), CASES)
def test_y11_results_are_unchanged_without_the_entry_bar_check(df, key: str, k: int) -> None:
    trades, equity = _y11(df, key, CONFIGS[k])
    result = tb.backtest(df, key, None, {**CONFIGS[k], "check_entry_bar": False})
    assert _core(result.trades) == _core(trades)  # exact float equality
    np.testing.assert_array_equal(result.equity.to_numpy(), equity)
    assert trades  # the comparison covers real trades


def test_the_entry_bar_check_changes_only_runs_with_stops_or_targets(df) -> None:
    changed = set()
    for key, k in CASES:
        trades, equity = _y11(df, key, CONFIGS[k])
        result = tb.backtest(df, key, None, CONFIGS[k])
        if _core(result.trades) != _core(trades) or not np.array_equal(
            result.equity.to_numpy(), equity
        ):
            changed.add((key, k))
    assert changed and all(k in (2, 3, 4) for _, k in changed)
