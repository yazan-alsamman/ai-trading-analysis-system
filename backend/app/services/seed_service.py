"""Seed data: the default instrument list and a DEMO candle generator (random walk).

Demo candles are synthetic. They exist so the web/mobile charts can be developed before the
real collectors run; never use them for analysis or model training.
"""

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument, MarketType
from app.schemas.market import CandleIn
from app.services import market_service


@dataclass(frozen=True)
class SeedInstrument:
    symbol: str
    source: str
    market: MarketType
    price_precision: int
    quantity_precision: int | None
    demo_price: float  # starting price of the demo random walk


DEFAULT_INSTRUMENTS: tuple[SeedInstrument, ...] = (
    SeedInstrument("BTC/USDT", "binance", MarketType.crypto, 2, 5, 60_000.0),
    SeedInstrument("ETH/USDT", "binance", MarketType.crypto, 2, 4, 3_000.0),
    SeedInstrument("BNB/USDT", "binance", MarketType.crypto, 2, 3, 550.0),
    SeedInstrument("SOL/USDT", "binance", MarketType.crypto, 2, 2, 150.0),
    SeedInstrument("XRP/USDT", "binance", MarketType.crypto, 4, 1, 0.6),
    SeedInstrument("EUR/USD", "twelvedata", MarketType.forex, 5, None, 1.08),
    SeedInstrument("GBP/USD", "twelvedata", MarketType.forex, 5, None, 1.27),
    SeedInstrument("USD/JPY", "twelvedata", MarketType.forex, 3, None, 150.0),
    SeedInstrument("XAU/USD", "twelvedata", MarketType.commodity, 2, None, 2_400.0),
)

# Per-minute log-return volatility of the demo walk, by market.
_DEMO_VOLATILITY = {
    MarketType.crypto: 0.0008,
    MarketType.forex: 0.0001,
    MarketType.commodity: 0.0003,
    MarketType.stock: 0.0005,
}


async def seed_instruments(session: AsyncSession) -> tuple[int, int]:
    """Create the default instruments that do not exist yet. Returns (created, existing)."""
    created = existing = 0
    for item in DEFAULT_INSTRUMENTS:
        if await market_service.get_instrument_by_symbol(session, item.source, item.symbol):
            existing += 1
            continue
        base, _, quote = item.symbol.partition("/")
        session.add(
            Instrument(
                symbol=item.symbol,
                source=item.source,
                market=item.market,
                base_asset=base,
                quote_asset=quote,
                price_precision=item.price_precision,
                quantity_precision=item.quantity_precision,
            )
        )
        created += 1
    await session.commit()
    return created, existing


def generate_demo_candles(
    instrument: Instrument,
    *,
    minutes: int,
    end: datetime,
    rng: random.Random,
    start_price: float | None = None,
) -> list[CandleIn]:
    """A geometric random walk of ``minutes`` consistent 1m candles, the last one at ``end``."""
    end = end.astimezone(UTC).replace(second=0, microsecond=0)
    seed_item = next(
        (
            s
            for s in DEFAULT_INSTRUMENTS
            if (s.source, s.symbol) == (instrument.source, instrument.symbol)
        ),
        None,
    )
    price_digits = instrument.price_precision if instrument.price_precision is not None else 4
    price = round(start_price or (seed_item.demo_price if seed_item else 100.0), price_digits)
    vol = _DEMO_VOLATILITY[instrument.market]
    qty_digits = instrument.quantity_precision if instrument.quantity_precision is not None else 2
    is_crypto = instrument.market == MarketType.crypto
    # ~100k quote units per minute for crypto, tick-volume-like numbers otherwise.
    base_volume = 100_000 / price if is_crypto else 100.0

    candles: list[CandleIn] = []
    ts = end - timedelta(minutes=minutes - 1)
    for _ in range(minutes):
        open_ = price
        close = open_ * math.exp(rng.gauss(0, vol))
        high = max(open_, close) * (1 + abs(rng.gauss(0, vol / 2)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, vol / 2)))
        # Rounding is monotonic, so high >= max(open, close) >= min(open, close) >= low holds.
        candles.append(
            CandleIn(
                ts=ts,
                open=round(open_, price_digits),
                high=round(high, price_digits),
                low=round(low, price_digits),
                close=round(close, price_digits),
                volume=round(base_volume * rng.lognormvariate(0, 0.7), qty_digits),
                trades=rng.randint(20, 400) if is_crypto else None,
            )
        )
        price = round(close, price_digits)  # next candle opens at this close
        ts += timedelta(minutes=1)
    return candles
