"""The global strategies. Each one documents its buy rule, sell rule and strength."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
import trading_indicators as ti
from trading_indicators import Param

from trading_strategies.base import (
    BUY,
    Strategy,
    crossed_above,
    crossed_below,
    events,
    r,
)


def _length(name: str, default: int, title: str) -> Param:
    return Param(name, "int", default, 1, 500, title)


def _col(frame: pd.DataFrame, name: str) -> np.ndarray:
    return frame[name].to_numpy(dtype=np.float64)


class MaCrossover(Strategy):
    """Buy when the fast EMA crosses above the slow EMA, sell when it crosses below.

    Optional filter: only when ADX >= ``adx_min`` (0 = off).
    Strength: ``ADX / 50`` at the cross (trend strength), capped at 1.
    """

    key = "ma_crossover"
    title = "Moving Average Crossover"
    description = (
        "Follows the trend: a buy signal when the fast exponential moving average crosses above "
        "the slow one, a sell signal when it crosses below. An optional ADX filter ignores "
        "crossings in sideways markets, where they tend to be false alarms."
    )
    category = "trend"
    params = (
        _length("fast", 9, "Fast EMA"),
        _length("slow", 21, "Slow EMA"),
        Param("adx_min", "float", 0.0, 0.0, 100.0, "Minimum ADX (0 = off)"),
    )

    def check(self, p: dict[str, Any]) -> None:
        if p["fast"] >= p["slow"]:
            raise ValueError(
                f"{self.key}: fast ({p['fast']}) must be smaller than slow ({p['slow']})"
            )

    def indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            {"name": "ema", "params": {"length": p["fast"]}},
            {"name": "ema", "params": {"length": p["slow"]}},
        ]

    def computed_indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [*self.indicators(p), {"name": "adx", "params": {"length": 14}}]

    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame:
        fast = ti.ema(df["close"], p["fast"]).to_numpy()
        slow = ti.ema(df["close"], p["slow"]).to_numpy()
        adx = _col(ti.adx(df, 14), "adx")
        buy, sell = crossed_above(fast, slow), crossed_below(fast, slow)
        if p["adx_min"] > 0:
            with np.errstate(invalid="ignore"):
                strong = adx >= p["adx_min"]
            buy, sell = buy & strong, sell & strong

        def describe(t: int, side: int):
            reason = "ema_cross_up" if side == BUY else "ema_cross_down"
            return (
                adx[t] / 50.0,
                reason,
                {
                    "fast_prev": r(fast[t - 1]),
                    "slow_prev": r(slow[t - 1]),
                    "fast": r(fast[t]),
                    "slow": r(slow[t]),
                    "adx": r(adx[t], 2),
                    "adx_min": p["adx_min"],
                },
            )

        return events(df.index, buy, sell, describe)


class RsiReversal(Strategy):
    """Buy when RSI crosses back up through ``oversold`` (prev < oversold <= now), sell when it
    crosses back down through ``overbought`` (prev > overbought >= now).

    Strength: how far RSI went past the level during that excursion:
    buy ``(oversold - min RSI) / oversold``, sell ``(max RSI - overbought) / (100 - overbought)``.
    """

    key = "rsi_reversal"
    title = "RSI Reversal"
    description = (
        "Buys after a sell-off loses steam: when the RSI climbs back above the oversold level. "
        "Sells after a rally loses steam: when the RSI falls back below the overbought level. "
        "Works best in ranging markets."
    )
    category = "mean_reversion"
    params = (
        _length("length", 14, "RSI length"),
        Param("oversold", "float", 30.0, 1.0, 99.0, "Oversold level"),
        Param("overbought", "float", 70.0, 1.0, 99.0, "Overbought level"),
    )
    inputs = ("close",)

    def check(self, p: dict[str, Any]) -> None:
        if p["oversold"] >= p["overbought"]:
            raise ValueError(
                f"{self.key}: oversold ({p['oversold']}) must be below overbought "
                f"({p['overbought']})"
            )

    def indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [{"name": "rsi", "params": {"length": p["length"]}}]

    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame:
        rsi = ti.rsi(df["close"], p["length"]).to_numpy()
        low, high = p["oversold"], p["overbought"]
        prev = ti.core.shift1(rsi)
        with np.errstate(invalid="ignore"):
            buy = (prev < low) & (rsi >= low)
            sell = (prev > high) & (rsi <= high)

        def excursion(t: int, below: bool) -> float:
            """Extreme RSI while it stayed beyond the level, walking back from bar t-1."""
            k, extreme = t - 1, rsi[t - 1]
            while k >= 0 and rsi[k] == rsi[k] and (rsi[k] < low if below else rsi[k] > high):
                extreme = min(extreme, rsi[k]) if below else max(extreme, rsi[k])
                k -= 1
            return extreme

        def describe(t: int, side: int):
            if side == BUY:
                extreme = excursion(t, below=True)
                strength, reason, level = (low - extreme) / low, "rsi_cross_up_oversold", low
            else:
                extreme = excursion(t, below=False)
                strength = (extreme - high) / (100.0 - high)
                reason, level = "rsi_cross_down_overbought", high
            return (
                strength,
                reason,
                {
                    "rsi_prev": r(rsi[t - 1], 2),
                    "rsi": r(rsi[t], 2),
                    "level": level,
                    "extreme": r(extreme, 2),
                },
            )

        return events(df.index, buy, sell, describe)


class MacdCross(Strategy):
    """Buy when the MACD line crosses above its signal line, sell when it crosses below.

    ``zero_filter = 1``: buy only below zero and sell only above zero (crossings against the
    prevailing move). Strength: ``|macd| / ATR(14)`` at the cross, capped at 1.
    """

    key = "macd_cross"
    title = "MACD Signal Cross"
    description = (
        "Momentum turning points: a buy signal when the MACD line crosses above its signal line, "
        "a sell signal when it crosses below. With the zero filter, only buys below the zero "
        "line and sells above it are kept, i.e. turns after a real move."
    )
    category = "momentum"
    params = (
        _length("fast", 12, "Fast EMA"),
        _length("slow", 26, "Slow EMA"),
        _length("signal", 9, "Signal EMA"),
        Param("zero_filter", "int", 0, 0, 1, "Zero-line filter (0 = off, 1 = on)"),
    )
    inputs = ("high", "low", "close")

    def check(self, p: dict[str, Any]) -> None:
        if p["fast"] >= p["slow"]:
            raise ValueError(
                f"{self.key}: fast ({p['fast']}) must be smaller than slow ({p['slow']})"
            )

    def indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "name": "macd",
                "params": {"fast": p["fast"], "slow": p["slow"], "signal": p["signal"]},
            }
        ]

    def computed_indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [*self.indicators(p), {"name": "atr", "params": {"length": 14}}]

    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame:
        m = ti.macd(df["close"], p["fast"], p["slow"], p["signal"])
        line, signal = _col(m, "macd"), _col(m, "signal")
        atr = ti.atr(df, 14).to_numpy()
        buy, sell = crossed_above(line, signal), crossed_below(line, signal)
        if p["zero_filter"]:
            with np.errstate(invalid="ignore"):
                buy, sell = buy & (line < 0), sell & (line > 0)

        def describe(t: int, side: int):
            reason = "macd_cross_up" if side == BUY else "macd_cross_down"
            strength = abs(line[t]) / atr[t] if atr[t] > 0 else 0.0
            return (
                strength,
                reason,
                {
                    "macd_prev": r(line[t - 1]),
                    "signal_prev": r(signal[t - 1]),
                    "macd": r(line[t]),
                    "signal": r(signal[t]),
                    "atr": r(atr[t]),
                    "zero_filter": p["zero_filter"],
                },
            )

        return events(df.index, buy, sell, describe)


class BollingerReversion(Strategy):
    """Buy when the previous close was below the lower band and this close is back inside
    (``>= lower``); sell when the previous close was above the upper band and this close is
    back inside (``<= upper``).

    Strength: how far outside the band the previous close was, in standard deviations
    (1 sigma beyond the band = 1).
    """

    key = "bollinger_reversion"
    title = "Bollinger Band Reversion"
    description = (
        "Mean reversion: after a close outside the Bollinger Bands, a close back inside suggests "
        "the stretch is over. A buy when price comes back above the lower band, a sell when it "
        "comes back below the upper band."
    )
    category = "mean_reversion"
    params = (
        _length("length", 20, "Length"),
        Param("std", "float", 2.0, 0.1, 10.0, "Standard deviations"),
    )
    inputs = ("close",)

    def indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [{"name": "bollinger", "params": {"length": p["length"], "std": p["std"]}}]

    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame:
        bands = ti.bollinger(df["close"], p["length"], p["std"])
        upper, middle, lower = (_col(bands, c) for c in ("upper", "middle", "lower"))
        close = df["close"].to_numpy(dtype=np.float64)
        prev_close, prev_upper, prev_lower = (ti.core.shift1(x) for x in (close, upper, lower))
        with np.errstate(invalid="ignore"):
            buy = (prev_close < prev_lower) & (close >= lower)
            sell = (prev_close > prev_upper) & (close <= upper)
        sigma = (upper - middle) / p["std"]

        def describe(t: int, side: int):
            prev_sigma = sigma[t - 1]
            if side == BUY:
                outside = prev_lower[t] - prev_close[t]
                reason, band = "close_back_above_lower_band", lower
            else:
                outside = prev_close[t] - prev_upper[t]
                reason, band = "close_back_below_upper_band", upper
            strength = outside / prev_sigma if prev_sigma > 0 else 0.0
            return (
                strength,
                reason,
                {
                    "close_prev": r(prev_close[t]),
                    "band_prev": r(band[t - 1]),
                    "close": r(close[t]),
                    "band": r(band[t]),
                    "middle": r(middle[t]),
                },
            )

        return events(df.index, buy, sell, describe)


class SupertrendFlip(Strategy):
    """Buy when the Supertrend direction flips from down to up, sell when it flips to down.

    Strength: distance between the close and the new Supertrend line in units of
    ``multiplier * ATR(length)``, capped at 1.
    """

    key = "supertrend_flip"
    title = "Supertrend Flip"
    description = (
        "Trend following with a volatility stop: a buy when price closes above the Supertrend "
        "line and the trend turns up, a sell when it closes below and the trend turns down."
    )
    category = "trend"
    params = (
        _length("length", 10, "ATR length"),
        Param("multiplier", "float", 3.0, 0.1, 10.0, "ATR multiplier"),
    )

    def indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            {"name": "supertrend", "params": {"length": p["length"], "multiplier": p["multiplier"]}}
        ]

    def computed_indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [*self.indicators(p), {"name": "atr", "params": {"length": p["length"]}}]

    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame:
        st = ti.supertrend(df, p["length"], p["multiplier"])
        line, direction = _col(st, "supertrend"), _col(st, "direction")
        atr = ti.atr(df, p["length"]).to_numpy()
        close = df["close"].to_numpy(dtype=np.float64)
        prev = ti.core.shift1(direction)
        buy = (prev == -1) & (direction == 1)
        sell = (prev == 1) & (direction == -1)

        def describe(t: int, side: int):
            band = p["multiplier"] * atr[t]
            strength = abs(close[t] - line[t]) / band if band > 0 else 0.0
            reason = "supertrend_flip_up" if side == BUY else "supertrend_flip_down"
            return (
                strength,
                reason,
                {
                    "close": r(close[t]),
                    "supertrend": r(line[t]),
                    "atr": r(atr[t]),
                    "direction": int(direction[t]),
                },
            )

        return events(df.index, buy, sell, describe)


class DonchianBreakout(Strategy):
    """Buy on the first close above the highest high of the previous ``length`` bars, sell on
    the first close below their lowest low (no new signal while closes stay beyond).

    Optional filter: ``volume > volume_factor * SMA(volume, length)`` of the previous bars
    (0 = off). Strength: breakout distance in ATR(14) units, capped at 1.
    """

    key = "donchian_breakout"
    title = "Donchian Channel Breakout"
    description = (
        "Classic breakout (the 'Turtle' rule): a buy when the close breaks above the highest "
        "high of the last N bars, a sell when it breaks below the lowest low. An optional volume "
        "filter keeps only breakouts on above-average volume."
    )
    category = "breakout"
    params = (
        _length("length", 20, "Channel length"),
        Param("volume_factor", "float", 0.0, 0.0, 10.0, "Volume factor (0 = off)"),
    )
    inputs = ("high", "low", "close", "volume")

    def indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [{"name": "donchian", "params": {"length": p["length"]}}]

    def computed_indicators(self, p: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [
            *self.indicators(p),
            {"name": "volume_sma", "params": {"length": p["length"]}},
            {"name": "atr", "params": {"length": 14}},
        ]

    def history(self, params: Mapping[str, Any] | None = None) -> int:
        return super().history(params) + 1  # the channel of the *previous* bars is used

    def _generate(self, df: pd.DataFrame, p: dict[str, Any]) -> pd.DataFrame:
        channel = ti.donchian(df, p["length"])
        upper = ti.core.shift1(_col(channel, "upper"))  # previous N bars, excluding this one
        lower = ti.core.shift1(_col(channel, "lower"))
        close = df["close"].to_numpy(dtype=np.float64)
        volume = df["volume"].to_numpy(dtype=np.float64)
        avg_volume = ti.core.shift1(ti.volume_sma(df, p["length"]).to_numpy())
        atr = ti.atr(df, 14).to_numpy()
        with np.errstate(invalid="ignore"):
            above, below = close > upper, close < lower
            buy = above & ~(ti.core.shift1(above.astype(float)) == 1)
            sell = below & ~(ti.core.shift1(below.astype(float)) == 1)
            if p["volume_factor"] > 0:
                loud = volume > p["volume_factor"] * avg_volume
                buy, sell = buy & loud, sell & loud

        def describe(t: int, side: int):
            level = upper[t] if side == BUY else lower[t]
            strength = abs(close[t] - level) / atr[t] if atr[t] > 0 else 0.0
            reason = "close_above_channel_high" if side == BUY else "close_below_channel_low"
            return (
                strength,
                reason,
                {
                    "close": r(close[t]),
                    "channel_high": r(upper[t]),
                    "channel_low": r(lower[t]),
                    "volume": r(volume[t]),
                    "volume_avg": r(avg_volume[t]),
                    "volume_factor": p["volume_factor"],
                },
            )

        return events(df.index, buy, sell, describe)


STRATEGY_CLASSES: tuple[type[Strategy], ...] = (
    MaCrossover,
    RsiReversal,
    MacdCross,
    BollingerReversion,
    SupertrendFlip,
    DonchianBreakout,
)
