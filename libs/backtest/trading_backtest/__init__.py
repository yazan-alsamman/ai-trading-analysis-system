"""Backtesting of trading strategies on pandas OHLCV data (no I/O, no look-ahead).

import trading_backtest as tb
result = tb.backtest(df, "ma_crossover", {"fast": 9, "slow": 21}, {"fee_bps": 10})
result.metrics["sharpe"], result.trades_frame(), result.equity
"""

from trading_backtest.api import BacktestResult, backtest, run_backtest
from trading_backtest.config import BacktestConfig, ExitRules, Sizer
from trading_backtest.engine import EXIT_REASONS, Trade
from trading_backtest.metrics import downsample_indices, periods_per_year

__version__ = "0.1.0"

__all__ = [
    "EXIT_REASONS",
    "BacktestConfig",
    "BacktestResult",
    "ExitRules",
    "Sizer",
    "Trade",
    "__version__",
    "backtest",
    "downsample_indices",
    "periods_per_year",
    "run_backtest",
]
