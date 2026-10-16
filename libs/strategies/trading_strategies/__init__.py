"""Trading strategies (Strategy pattern) on pandas OHLCV data, built on ``trading_indicators``.

import trading_strategies as ts
signals = ts.run("rsi_reversal", df, length=14, oversold=30, overbought=70)
ts.catalog()

Custom strategies (Y12): ``BuilderStrategy`` (rules as JSON) and ``CompositeStrategy`` (several
strategies voting), see ``trading_strategies.custom``.
"""

from trading_strategies.base import SIGNAL_COLUMNS, Strategy
from trading_strategies.builder import BuilderStrategy, DefinitionError, validate_builder
from trading_strategies.composite import CompositeStrategy, is_custom
from trading_strategies.custom import (
    build,
    from_snapshot,
    json_schemas,
    operand_catalog,
    snapshot,
    snapshot_hash,
    validate,
)
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
    "BuilderStrategy",
    "CompositeStrategy",
    "DefinitionError",
    "DonchianBreakout",
    "MaCrossover",
    "MacdCross",
    "RsiReversal",
    "Strategy",
    "SupertrendFlip",
    "__version__",
    "build",
    "catalog",
    "from_snapshot",
    "get_strategy",
    "is_custom",
    "json_schemas",
    "operand_catalog",
    "params_hash",
    "run",
    "snapshot",
    "snapshot_hash",
    "validate",
    "validate_builder",
]
