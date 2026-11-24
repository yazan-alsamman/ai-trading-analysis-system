"""Seed data: the default instrument list (with *typical* contract specs) and a DEMO candle
generator (random walk).

Demo candles are synthetic. They exist so the web/mobile charts can be developed before the
real collectors run; never use them for analysis or model training. Instruments of a real-feed
source (``REAL_FEED_SOURCES``) never get demo candles.

The typical specs match migration 0013 (which fills them on existing databases; 0021 does the
same for the fxpro XAU/USD ``cost_per_unit``). They are only
written into fields that are still null, with ``spec_source = typical``; the broker adapter
replaces them with the broker's values later.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import SPEC_FIELDS, Instrument, MarketType, SpecSource
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
    specs: dict[str, Any] = field(default_factory=dict)  # typical contract specs


# Candles of these sources only ever come from the real feed.
REAL_FEED_SOURCES = frozenset({"fxpro"})

# FxPro server time is New York + 7 h; in New York time the week opens Sunday 18:00 and closes
# Friday 16:55, with a daily break 16:55-18:00 (docs/instruments.md).
FXPRO_SESSION_CALENDAR: dict[str, Any] = {
    "tz": "America/New_York",
    "week_open": {"day": "sun", "time": "18:00"},
    "week_close": {"day": "fri", "time": "16:55"},
    "daily_breaks": [{"start": "16:55", "end": "18:00"}],
    "holidays": [],
}


def _fx(tick_size: float) -> dict[str, Any]:
    return {
        "contract_size": 100_000.0,
        "tick_size": tick_size,
        "lot_step": 0.01,
        "min_lot": 0.01,
        "max_lot": 100.0,
        "price_basis": "bid",
    }


def _crypto(price_precision: int, quantity_precision: int) -> dict[str, Any]:
    """1 lot = 1 coin; tick from the price precision, step from the quantity precision."""
    step = round(10.0**-quantity_precision, quantity_precision)
    return {
        "contract_size": 1.0,
        "tick_size": round(10.0**-price_precision, price_precision),
        "lot_step": step,
        "min_lot": step,
        "price_basis": "last",
    }


DEFAULT_INSTRUMENTS: tuple[SeedInstrument, ...] = (
    SeedInstrument("BTC/USDT", "binance", MarketType.crypto, 2, 5, 60_000.0, _crypto(2, 5)),
    SeedInstrument("ETH/USDT", "binance", MarketType.crypto, 2, 4, 3_000.0, _crypto(2, 4)),
    SeedInstrument("BNB/USDT", "binance", MarketType.crypto, 2, 3, 550.0, _crypto(2, 3)),
    SeedInstrument("SOL/USDT", "binance", MarketType.crypto, 2, 2, 150.0, _crypto(2, 2)),
    SeedInstrument("XRP/USDT", "binance", MarketType.crypto, 4, 1, 0.6, _crypto(4, 1)),
    SeedInstrument("EUR/USD", "twelvedata", MarketType.forex, 5, None, 1.08, _fx(0.00001)),
    SeedInstrument("GBP/USD", "twelvedata", MarketType.forex, 5, None, 1.27, _fx(0.00001)),
    SeedInstrument("USD/JPY", "twelvedata", MarketType.forex, 3, None, 150.0, _fx(0.001)),
    # left without specs on purpose; the fxpro XAU/USD below is the one the AI engine uses
    SeedInstrument("XAU/USD", "twelvedata", MarketType.commodity, 2, None, 2_400.0),
    SeedInstrument(
        "XAU/USD",
        "fxpro",
        MarketType.commodity,
        2,
        None,
        2_400.0,
        {
            "contract_size": 100.0,
            "tick_size": 0.01,
            "lot_step": 0.01,
            "min_lot": 0.01,
            "max_lot": 100.0,
            "price_basis": "bid",
            "session_calendar": FXPRO_SESSION_CALENDAR,
            # spread and every trading cost, per oz, per round trip (Fadi, 25 Oct; 0021)
            "cost_per_unit": 0.25,
        },
    ),
)

# Per-minute log-return volatility of the demo walk, by market.
DEMO_VOLATILITY = {
    MarketType.crypto: 0.0008,
    MarketType.forex: 0.0001,
    MarketType.commodity: 0.0003,
    MarketType.stock: 0.0005,
}


def fill_typical_specs(instrument: Instrument, specs: dict[str, Any]) -> bool:
    """Write the typical ``specs`` into the fields that are still null. True if any changed."""
    if not specs:
        return False
    values = {**specs, "quote_currency": instrument.quote_asset}
    changed = False
    for name in SPEC_FIELDS:
        if values.get(name) is not None and getattr(instrument, name) is None:
            setattr(instrument, name, values[name])
            changed = True
    if changed:
        instrument.spec_source = instrument.spec_source or SpecSource.typical
        instrument.spec_updated_at = instrument.spec_updated_at or datetime.now(UTC)
    return changed


async def seed_instruments(session: AsyncSession) -> tuple[int, int]:
    """Create the default instruments that do not exist yet and fill the typical specs that are
    still null on existing ones. Returns (created, existing)."""
    created = existing = 0
    for item in DEFAULT_INSTRUMENTS:
        instrument = await market_service.get_instrument_by_symbol(
            session, item.source, item.symbol
        )
        if instrument is not None:
            existing += 1
            fill_typical_specs(instrument, item.specs)
            continue
        base, _, quote = item.symbol.partition("/")
        instrument = Instrument(
            symbol=item.symbol,
            source=item.source,
            market=item.market,
            base_asset=base,
            quote_asset=quote,
            price_precision=item.price_precision,
            quantity_precision=item.quantity_precision,
        )
        fill_typical_specs(instrument, item.specs)
        session.add(instrument)
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
    """A geometric random walk of ``minutes`` consistent 1m candles, the last one at ``end``,
    marked ``source = seed``. Refused for real-feed instruments (``REAL_FEED_SOURCES``)."""
    if instrument.source in REAL_FEED_SOURCES:
        raise ValueError(f"{instrument.source} candles only come from the real feed")
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
    vol = DEMO_VOLATILITY[instrument.market]
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
                source="seed",
            )
        )
        price = round(close, price_digits)  # next candle opens at this close
        ts += timedelta(minutes=1)
    return candles
