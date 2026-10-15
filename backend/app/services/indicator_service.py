"""Indicator lines for the charts, computed with the shared ``trading_indicators`` package."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import trading_indicators as ti
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Timeframe
from app.schemas.indicators import IndicatorSpec
from app.services import market_service
from app.services.market_service import CandleRow

MAX_HISTORY = 5000  # bars loaded before the window, at most


@dataclass(frozen=True)
class ResolvedIndicator:
    spec: ti.Indicator
    params: dict[str, int | float]

    @property
    def history(self) -> int:
        """Bars needed before the window: warm-up plus convergence of recursive smoothing."""
        return self.spec.lookback(self.params) + self.spec.convergence(self.params)


def warm_up() -> None:
    """Run every indicator once on a small synthetic frame so the first real request does not
    pay for pandas/numpy first-use initialisation (called at startup, in a thread)."""
    n = 300
    index = pd.date_range("2000-01-01", periods=n, freq="h", tz="UTC")
    close = 100 + np.sin(np.arange(n) / 7.0)
    df = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0},
        index=index,
    )
    for name in ti.INDICATORS:
        ti.compute(name, df)


def resolve(requests: list[IndicatorSpec]) -> list[ResolvedIndicator]:
    """Validate names and params against the catalog (422 with a clear message)."""
    resolved = []
    for i, request in enumerate(requests):
        try:
            spec = ti.get_indicator(request.name)
            resolved.append(ResolvedIndicator(spec, spec.resolve(request.params)))
        except ValueError as exc:
            raise HTTPException(422, f"indicators[{i}]: {exc}") from None
    return resolved


def frame(rows: list[CandleRow]) -> pd.DataFrame:
    """OHLCV DataFrame (UTC DatetimeIndex) from candle rows."""
    return pd.DataFrame(
        {
            "open": [r.open for r in rows],
            "high": [r.high for r in rows],
            "low": [r.low for r in rows],
            "close": [r.close for r in rows],
            "volume": [r.volume for r in rows],
        },
        index=pd.DatetimeIndex([r.ts for r in rows]),
        dtype=np.float64,
    )


def lines(
    df: pd.DataFrame, times: list[int], indicators: list[ResolvedIndicator]
) -> list[dict[str, Any]]:
    """Indicator results over the last ``len(times)`` rows of ``df`` as Lightweight Charts
    points (``{time, value}``, null during warm-up)."""
    first = len(df) - len(times)
    results = []
    for ind in indicators:
        out = ind.spec.compute(df, **ind.params).iloc[first:]
        outputs = {}
        for column in out.columns:
            values = out[column].to_numpy(dtype=np.float64).tolist()
            # NaN (warm-up) -> null; "v != v" is the fastest NaN test on Python floats
            outputs[column] = [
                {"time": t, "value": None if v != v else v}
                for t, v in zip(times, values, strict=True)
            ]
        results.append(
            {
                "name": ind.spec.name,
                "params": ind.params,
                "placement": ind.spec.placement,
                "outputs": outputs,
            }
        )
    return results


def _compute(
    candles: list[CandleRow], window: int, indicators: list[ResolvedIndicator]
) -> list[dict[str, Any]]:
    """CPU-bound part (runs in a worker thread so the event loop stays responsive)."""
    times = [int(r.ts.timestamp()) for r in candles[len(candles) - window :]]
    return lines(frame(candles), times, indicators)


async def load_candles(
    session: AsyncSession,
    instrument_id: uuid.UUID,
    timeframe: Timeframe,
    *,
    history: int,
    day_anchor: bool = False,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> tuple[list[CandleRow], list[CandleRow]]:
    """``(history, window)``: the window the candles endpoint returns for these parameters, and
    up to ``history`` bars before it (capped at MAX_HISTORY). With ``day_anchor`` the history
    also reaches back to 00:00 UTC of the first window candle (for VWAP)."""
    window = await market_service.get_candles(
        session, instrument_id, timeframe, start=start, end=end, limit=limit
    )
    before_rows: list[CandleRow] = []
    if window:
        before = window[0].ts - timedelta(microseconds=1)
        needed = min(history, MAX_HISTORY)
        if needed:
            before_rows = await market_service.get_candles(
                session, instrument_id, timeframe, end=before, limit=needed
            )
        day_start = window[0].ts.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        if (
            day_anchor
            and day_start < window[0].ts
            and (not before_rows or before_rows[0].ts > day_start)
        ):
            # [day_start, window) is a superset of the count-based history here
            before_rows = await market_service.get_candles(
                session, instrument_id, timeframe, start=day_start, end=before, limit=MAX_HISTORY
            )
    return before_rows, window


def needs(indicators: list[ResolvedIndicator]) -> tuple[int, bool]:
    """(history bars, day anchor) the given indicators need."""
    return (
        max((i.history for i in indicators), default=0),
        any(i.spec.anchor == "day" for i in indicators),
    )


async def compute_indicators(
    session: AsyncSession,
    instrument_id: uuid.UUID,
    timeframe: Timeframe,
    indicators: list[ResolvedIndicator],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Indicator lines over the same candle window the candles endpoint returns.

    Before the window, the service also loads the history the indicators need: their warm-up
    (lookback) plus the bars recursive smoothing needs to converge (so EMA/RSI/ATR values do not
    depend on where the chart starts), and for day-anchored indicators (VWAP) every bar since
    00:00 UTC of the first candle. That history is trimmed off afterwards, so the first points
    are valid and stable whenever enough data exists.
    """
    history, anchored = needs(indicators)
    before, window = await load_candles(
        session,
        instrument_id,
        timeframe,
        history=history,
        day_anchor=anchored,
        start=start,
        end=end,
        limit=limit,
    )
    return await asyncio.to_thread(_compute, before + window, len(window), indicators)
