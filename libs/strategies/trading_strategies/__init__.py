"""Trading strategies (Strategy pattern) on pandas OHLCV data, built on ``trading_indicators``.

import trading_strategies as ts
signals = ts.run("rsi_reversal", df, length=14, oversold=30, overbought=70)
ts.catalog()
"""

from trading_strategies.base import SIGNAL_COLUMNS, Strategy
from trading_strategies.registry import STRATEGIES, catalog, get_strategy, params_hash, run
from trading_strategies.strategies import (
    BollingerReversion,
    DonchianBreakout,
    MacdCross,
    MaCrossover,
    RsiReversal,
    SupertrendFlip,
)

__version__ = "0.1.0"

__all__ = [
    "SIGNAL_COLUMNS",
    "STRATEGIES",
    "BollingerReversion",
    "DonchianBreakout",
    "MaCrossover",
    "MacdCross",
    "RsiReversal",
    "Strategy",
    "SupertrendFlip",
    "__version__",
    "catalog",
    "get_strategy",
    "params_hash",
    "run",
]
