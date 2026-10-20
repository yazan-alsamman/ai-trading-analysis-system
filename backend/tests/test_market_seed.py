import random
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import seed_demo_candles, seed_instruments, simulate_live
from app.models.candle import Candle, Timeframe
from app.models.instrument import Instrument, MarketType
from app.services import market_service
from app.services.seed_service import generate_demo_candles
from tests.market_utils import make_instrument

NOW = datetime(2026, 1, 5, 12, 34, 56, tzinfo=UTC)


async def test_seed_instruments_is_idempotent(session_factory, session: AsyncSession, capsys):
    assert await seed_instruments(session_factory) == 0
    assert "10 created, 0 already existed" in capsys.readouterr().out
    assert await seed_instruments(session_factory) == 0
    assert "0 created, 10 already existed" in capsys.readouterr().out

    rows = await session.execute(select(Instrument.source, Instrument.symbol, Instrument.market))
    catalog = {(src, sym): market for src, sym, market in rows.all()}
    assert len(catalog) == 10
    for sym in ("BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"):
        assert catalog[("binance", sym)] == MarketType.crypto
    for sym in ("EUR/USD", "GBP/USD", "USD/JPY"):
        assert catalog[("twelvedata", sym)] == MarketType.forex
    assert catalog[("twelvedata", "XAU/USD")] == MarketType.commodity
    assert catalog[("fxpro", "XAU/USD")] == MarketType.commodity


async def test_seed_instruments_typical_specs(session_factory, session: AsyncSession, capsys):
    # an existing instrument with one spec set by an admin keeps it; only nulls are filled
    eurusd = await make_instrument(session, "EUR/USD", "twelvedata", MarketType.forex)
    eurusd.min_lot, eurusd.spec_source = 0.1, "manual"
    await session.commit()
    assert await seed_instruments(session_factory) == 0
    session.expire_all()
    rows = {(i.source, i.symbol): i for i in (await session.scalars(select(Instrument))).all()}

    gold = rows[("fxpro", "XAU/USD")]
    assert (gold.base_asset, gold.quote_asset, gold.price_precision) == ("XAU", "USD", 2)
    assert (gold.contract_size, gold.tick_size, gold.lot_step) == (100, 0.01, 0.01)
    assert (gold.min_lot, gold.max_lot, gold.quote_currency) == (0.01, 100, "USD")
    assert (gold.price_basis, gold.spec_source) == ("bid", "typical")
    assert gold.session_calendar["week_open"] == {"day": "sun", "time": "18:00"}
    assert gold.spec_updated_at is not None

    eur = rows[("twelvedata", "EUR/USD")]
    assert (eur.contract_size, eur.tick_size, eur.lot_step) == (100_000, 0.00001, 0.01)
    assert (eur.min_lot, eur.spec_source) == (0.1, "manual")  # kept
    assert rows[("twelvedata", "USD/JPY")].tick_size == 0.001
    btc = rows[("binance", "BTC/USDT")]
    assert (btc.contract_size, btc.tick_size, btc.lot_step, btc.price_basis) == (
        1,
        0.01,
        0.00001,
        "last",
    )
    assert rows[("binance", "XRP/USDT")].lot_step == 0.1
    # the twelvedata XAU/USD stays without specs
    old_gold = rows[("twelvedata", "XAU/USD")]
    assert old_gold.contract_size is None and old_gold.spec_source is None


async def test_no_demo_candles_for_real_feeds(session_factory, session: AsyncSession, capsys):
    gold = await make_instrument(session, "XAU/USD", "fxpro", MarketType.commodity)
    kwargs = {"session_factory": session_factory}
    assert await seed_demo_candles("XAU/USD", "fxpro", 1, **kwargs) == 2
    assert "real feed" in capsys.readouterr().err
    assert await simulate_live("XAU/USD", "fxpro", 1, max_ticks=1, **kwargs) == 2
    with pytest.raises(ValueError, match="real feed"):
        generate_demo_candles(gold, minutes=1, end=NOW, rng=random.Random(1))
    assert await session.scalar(select(func.count()).select_from(Candle)) == 0


async def _rows(session: AsyncSession, instrument_id) -> list[tuple]:
    session.expire_all()
    result = await session.execute(
        select(Candle.ts, Candle.open, Candle.close, Candle.volume)
        .where(Candle.instrument_id == instrument_id)
        .order_by(Candle.ts)
    )
    return list(result.all())


async def test_seed_demo_candles_is_idempotent(session_factory, session: AsyncSession, capsys):
    instrument = await make_instrument(session, "BTC/USDT", "binance", price_precision=2)
    instrument_id = instrument.id  # _rows() expires ORM objects
    kwargs = {"seed": 7, "refresh": False, "now": NOW, "session_factory": session_factory}

    assert await seed_demo_candles("btc/usdt", "Binance", 1 / 24, **kwargs) == 0
    out = capsys.readouterr().out
    assert "DEMO DATA" in out and "wrote 60 1m candles" in out
    first = await _rows(session, instrument_id)
    assert len(first) == 60
    assert first[-1][0] == NOW.replace(second=0)  # ends at the current minute
    assert first[0][0] == NOW.replace(second=0) - timedelta(minutes=59)

    assert await seed_demo_candles("BTC/USDT", "binance", 1 / 24, **kwargs) == 0
    assert await _rows(session, instrument_id) == first

    # another seed rewrites the same minutes instead of adding rows
    assert await seed_demo_candles("BTC/USDT", "binance", 1 / 24, **(kwargs | {"seed": 8})) == 0
    second = await _rows(session, instrument_id)
    assert [r[0] for r in second] == [r[0] for r in first]
    assert second != first

    # the 5m aggregate is built from them through real-time aggregation
    bars = await market_service.get_candles(session, instrument_id, Timeframe.m5, limit=100)
    assert sum(b.volume for b in bars) == sum(r[3] for r in second)


async def test_seed_demo_candles_errors(session_factory, session: AsyncSession, capsys) -> None:
    assert await seed_demo_candles("NOPE/USDT", "binance", 1, session_factory=session_factory) == 1
    assert "not found" in capsys.readouterr().err
    assert await seed_demo_candles("BTC/USDT", "binance", 0, session_factory=session_factory) == 2
    assert await seed_demo_candles("BTC/USDT", "binance", 400, session_factory=session_factory) == 2
    total = await session.scalar(select(func.count()).select_from(Candle))
    assert total == 0


def test_generate_demo_candles_is_consistent() -> None:
    instrument = Instrument(
        symbol="EUR/USD", source="twelvedata", market=MarketType.forex, price_precision=5
    )
    candles = generate_demo_candles(instrument, minutes=2000, end=NOW, rng=random.Random(1))
    assert len(candles) == 2000
    for prev, cur in zip(candles, candles[1:], strict=False):
        assert cur.ts - prev.ts == timedelta(minutes=1)
        assert cur.open == prev.close  # continuous walk
    for c in candles:
        assert c.high >= max(c.open, c.close) >= min(c.open, c.close) >= c.low > 0
        assert c.volume >= 0 and c.trades is None
        assert c.source == "seed" and c.spread is None
        assert round(c.close, 5) == c.close
    assert 0.9 < candles[-1].close / candles[0].open < 1.1
