from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument, MarketType
from app.schemas.market import CandleIn


async def make_instrument(
    session: AsyncSession,
    symbol: str = "BTC/USDT",
    source: str = "binance",
    market: MarketType = MarketType.crypto,
    **kwargs,
) -> Instrument:
    base, _, quote = symbol.partition("/")
    instrument = Instrument(
        symbol=symbol,
        source=source,
        market=market,
        base_asset=kwargs.pop("base_asset", base),
        quote_asset=kwargs.pop("quote_asset", quote),
        **kwargs,
    )
    session.add(instrument)
    await session.commit()
    return instrument


def known_candles(start: datetime, count: int) -> list[CandleIn]:
    """Deterministic 1m candles: i-th has open 100+i, close 100.5+i, high close+1, low open-1,
    volume i+1 and 10 trades, so every aggregate value can be computed by hand."""
    return [
        CandleIn(
            ts=start + timedelta(minutes=i),
            open=100 + i,
            high=101.5 + i,
            low=99 + i,
            close=100.5 + i,
            volume=i + 1,
            trades=10,
        )
        for i in range(count)
    ]


def candle_json(ts: datetime | str, **overrides) -> dict:
    body = {
        "ts": ts.isoformat() if isinstance(ts, datetime) else ts,
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.5,
        "volume": 3.0,
    }
    body.update(overrides)
    return body
