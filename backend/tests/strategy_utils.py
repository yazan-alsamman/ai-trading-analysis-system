from datetime import datetime, timedelta

import trading_strategies as ts
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Timeframe
from app.models.strategy import UserStrategy
from app.schemas.market import CandleIn
from app.services import market_service

RSI1 = {"length": 1, "oversold": 30.0, "overbought": 70.0}  # RSI(1): 100 up, 0 down, 50 flat


async def add_closes(
    session: AsyncSession, instrument_id, start: datetime, closes: list[float]
) -> list[CandleIn]:
    """1m candles with the given closes (open = previous close, small wicks)."""
    candles, prev = [], closes[0]
    for i, close in enumerate(closes):
        candles.append(
            CandleIn(
                ts=start + timedelta(minutes=i),
                open=prev,
                high=max(prev, close) + 0.1,
                low=min(prev, close) - 0.1,
                close=close,
                volume=1.0,
            )
        )
        prev = close
    await market_service.upsert_candles(session, instrument_id, candles)
    await session.commit()
    return candles


async def activate(
    session: AsyncSession,
    user,
    instrument,
    key: str = "rsi_reversal",
    params: dict | None = None,
    timeframe: Timeframe = Timeframe.m1,
    notify: bool = True,
    is_active: bool = True,
) -> UserStrategy:
    resolved = ts.get_strategy(key).resolve(params or {})
    row = UserStrategy(
        user_id=user.id,
        strategy_key=key,
        params=resolved,
        params_hash=ts.params_hash(key, resolved),
        instrument_id=instrument.id,
        timeframe=timeframe,
        notify=notify,
        is_active=is_active,
    )
    session.add(row)
    await session.commit()
    return row
