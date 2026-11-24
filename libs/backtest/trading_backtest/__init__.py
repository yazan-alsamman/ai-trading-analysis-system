"""Backtesting of trading strategies on pandas OHLCV data (no I/O, no look-ahead).

import trading_backtest as tb
result = tb.backtest(df, "ma_crossover", {"fast": 9, "slow": 21}, {"fee_bps": 10})
result.metrics["sharpe"], result.trades_frame(), result.equity
"""

from trading_backtest.api import BacktestResult, backtest, run_backtest
from trading_backtest.config import BacktestConfig, BacktestConfigIn, ExitRules, Sizer
from trading_backtest.engine import EXIT_REASONS, SKIP_REASONS, Trade
from trading_backtest.metrics import downsample_indices, periods_per_year
from trading_backtest.risk import (
    TEMPLATES,
    ConfigError,
    Guards,
    RiskConfigIn,
    RiskContext,
    StopRule,
    TargetRule,
    TradePlan,
    TrailingRule,
    plan_trade,
    risk_json_schema,
    validate_risk_config,
)
from trading_backtest.sizing import (
    ContractSpec,
    LotSize,
    direct_rate,
    lots_for_risk,
    round_lots,
    value_per_price_unit,
)

__version__ = "0.1.0"

__all__ = [
    "EXIT_REASONS",
    "SKIP_REASONS",
    "TEMPLATES",
    "BacktestConfig",
    "BacktestConfigIn",
    "BacktestResult",
    "ConfigError",
    "ContractSpec",
    "ExitRules",
    "Guards",
    "LotSize",
    "RiskConfigIn",
    "RiskContext",
    "Sizer",
    "StopRule",
    "TargetRule",
    "Trade",
    "TradePlan",
    "TrailingRule",
    "__version__",
    "backtest",
    "direct_rate",
    "downsample_indices",
    "lots_for_risk",
    "periods_per_year",
    "plan_trade",
    "risk_json_schema",
    "round_lots",
    "run_backtest",
    "validate_risk_config",
    "value_per_price_unit",
]
