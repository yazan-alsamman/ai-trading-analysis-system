"""Technical indicators on pandas OHLCV data (numpy/pandas only, no look-ahead).

import trading_indicators as ti
ti.rsi(df["close"], 14)
ti.compute("macd", df, fast=12, slow=26, signal=9)
ti.catalog()
"""

from trading_indicators.momentum import cci, mfi, roc, rsi, stoch, stochrsi, williams_r
from trading_indicators.registry import (
    INDICATORS,
    Indicator,
    Param,
    catalog,
    compute,
    get_indicator,
    lookback,
)
from trading_indicators.trend import adx, ema, ichimoku, macd, sma, supertrend, wma
from trading_indicators.volatility import atr, bollinger, donchian, keltner
from trading_indicators.volume import obv, volume_sma, vwap

__version__ = "0.1.0"

__all__ = [
    "INDICATORS",
    "Indicator",
    "Param",
    "__version__",
    "adx",
    "atr",
    "bollinger",
    "catalog",
    "cci",
    "compute",
    "donchian",
    "ema",
    "get_indicator",
    "ichimoku",
    "keltner",
    "lookback",
    "macd",
    "mfi",
    "obv",
    "roc",
    "rsi",
    "sma",
    "stoch",
    "stochrsi",
    "supertrend",
    "volume_sma",
    "vwap",
    "williams_r",
    "wma",
]
