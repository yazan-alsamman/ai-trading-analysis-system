"""Y11 configs give bit-identical results with ``check_entry_bar: false``.

The fingerprints were produced by the Y11 engine (main @ 230b5ab, before risk management):
sha256 of every trade's core fields and of the equity curve, for 3 strategies x 5 configs.
With the default ``check_entry_bar: true`` stops/targets are also checked on the entry bar, so
runs with stops or targets may differ (the entry-bar fix, docs/risk-management.md).
"""

import hashlib

import pytest

import trading_backtest as tb
from tests.conftest import synthetic_ohlcv

CORE = (
    "number", "side", "entry_price", "exit_price", "quantity", "gross_pnl", "fees", "net_pnl",
    "return_pct", "bars_held", "exit_reason", "entry_index", "exit_index",
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
Y11 = {
    "ma_crossover/0": "df97a6a192da4be8",
    "ma_crossover/1": "56ab506cf21b5aeb",
    "ma_crossover/2": "32e3cc57d37f948e",
    "ma_crossover/3": "6bf7343a2d639b0e",
    "ma_crossover/4": "9434fcb38f8188c5",
    "rsi_reversal/0": "cac135e8fae238a5",
    "rsi_reversal/1": "6842457b02487a15",
    "rsi_reversal/2": "f954f43eb6caaef8",
    "rsi_reversal/3": "b9118bcc47508397",
    "rsi_reversal/4": "99c3e75730c40121",
    "donchian_breakout/0": "3bdd95067648adbf",
    "donchian_breakout/1": "470084dc3abb15b4",
    "donchian_breakout/2": "4d63196679da4dbc",
    "donchian_breakout/3": "473aa37b0557eabd",
    "donchian_breakout/4": "ea8a15490f22934d",
}


def fingerprint(result: tb.BacktestResult) -> str:
    trades = [[repr(getattr(t, c)) for c in CORE] for t in result.trades]
    payload = repr(trades) + repr(result.equity.tolist())
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@pytest.mark.parametrize("case", sorted(Y11))
def test_y11_results_are_unchanged_without_the_entry_bar_check(case: str) -> None:
    key, k = case.split("/")
    df = synthetic_ohlcv(3000)
    result = tb.backtest(df, key, None, {**CONFIGS[int(k)], "check_entry_bar": False})
    assert fingerprint(result) == Y11[case]


def test_the_entry_bar_check_changes_only_runs_with_stops_or_targets() -> None:
    df = synthetic_ohlcv(3000)
    changed = set()
    for case in Y11:
        key, k = case.split("/")
        if fingerprint(tb.backtest(df, key, None, CONFIGS[int(k)])) != Y11[case]:
            changed.add(case)
    assert changed and all(case.split("/")[1] in ("2", "3", "4") for case in changed)
