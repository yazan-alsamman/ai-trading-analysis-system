"""Management commands.

python -m app.cli create-admin --email admin@example.com --password 'Secret123'
python -m app.cli seed-instruments
python -m app.cli seed-demo-candles --symbol BTC/USDT --source binance --days 30
python -m app.cli simulate-live --symbol BTC/USDT --source binance --interval 2
"""

import argparse
import asyncio
import math
import random
import sys
import time
from collections.abc import Awaitable, Sequence
from datetime import UTC, datetime

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.redis import close_redis
from app.models.candle import Timeframe
from app.schemas.market import CandleIn
from app.schemas.user import NormalizedEmail, Password
from app.services import market_events, market_service, seed_service, user_service

MAX_DEMO_DAYS = 365


def _default_session_factory() -> async_sessionmaker[AsyncSession]:
    from app.db.session import SessionLocal

    return SessionLocal


async def create_admin(
    email: str, password: str, session_factory: async_sessionmaker[AsyncSession] | None = None
) -> int:
    try:
        email = TypeAdapter(NormalizedEmail).validate_python(email)
        password = TypeAdapter(Password).validate_python(password)
    except ValidationError as exc:
        print(f"Invalid input: {exc.errors()[0]['msg']}", file=sys.stderr)
        return 2
    session_factory = session_factory or _default_session_factory()
    async with session_factory() as session:
        user, created = await user_service.ensure_admin(session, email, password)
    if created:
        print(f"Created admin {user.email}")
    else:
        print(f"User {user.email} already exists; ensured role=admin (password unchanged)")
    return 0


async def seed_instruments(session_factory: async_sessionmaker[AsyncSession] | None = None) -> int:
    session_factory = session_factory or _default_session_factory()
    async with session_factory() as session:
        created, existing = await seed_service.seed_instruments(session)
    print(f"Instruments: {created} created, {existing} already existed")
    return 0


async def seed_demo_candles(
    symbol: str,
    source: str,
    days: float,
    *,
    seed: int | None = None,
    refresh: bool = True,
    now: datetime | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    engine: AsyncEngine | None = None,
) -> int:
    if not 0 < days <= MAX_DEMO_DAYS:
        print(f"--days must be > 0 and <= {MAX_DEMO_DAYS}", file=sys.stderr)
        return 2
    session_factory = session_factory or _default_session_factory()
    started = time.perf_counter()
    async with session_factory() as session:
        instrument = await market_service.get_instrument_by_symbol(session, source, symbol)
        if instrument is None:
            print(
                f"Instrument {source}:{symbol} not found (run seed-instruments first)",
                file=sys.stderr,
            )
            return 1
        candles = seed_service.generate_demo_candles(
            instrument,
            minutes=round(days * 24 * 60),
            end=now or datetime.now(UTC),
            rng=random.Random(seed),
        )
        written = await market_service.upsert_candles(session, instrument.id, candles)
        await session.commit()
        await market_events.publish_candle_updates_safely(session, instrument.id, candles)
    print(
        f"DEMO DATA (synthetic random walk, not real prices): wrote {written} 1m candles for "
        f"{instrument.source}:{instrument.symbol} from {candles[0].ts.isoformat()} "
        f"to {candles[-1].ts.isoformat()} in {time.perf_counter() - started:.1f}s"
    )
    if refresh:
        started = time.perf_counter()
        await market_service.refresh_aggregates(candles[0].ts, candles[-1].ts, engine)
        print(f"Refreshed continuous aggregates in {time.perf_counter() - started:.1f}s")
    return 0


async def simulate_live(
    symbol: str,
    source: str,
    interval: float,
    *,
    duration: float | None = None,
    max_ticks: int | None = None,
    seed: int | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> int:
    """DEMO: keep rewriting the current minute's 1m candle with a random walk and publish it."""
    if interval <= 0:
        print("--interval must be > 0", file=sys.stderr)
        return 2
    session_factory = session_factory or _default_session_factory()
    rng = random.Random(seed)
    async with session_factory() as session:
        instrument = await market_service.get_instrument_by_symbol(session, source, symbol)
        if instrument is None:
            print(
                f"Instrument {source}:{symbol} not found (run seed-instruments first)",
                file=sys.stderr,
            )
            return 1
        last = await market_service.get_latest_candle(session, instrument.id, Timeframe.m1)
    seed_item = next(
        (s for s in seed_service.DEFAULT_INSTRUMENTS if s.symbol == instrument.symbol), None
    )
    price = last.close if last else (seed_item.demo_price if seed_item else 100.0)
    digits = instrument.price_precision if instrument.price_precision is not None else 4
    # per-tick volatility scaled from the per-minute demo volatility
    vol = seed_service.DEMO_VOLATILITY[instrument.market] * math.sqrt(min(interval, 60) / 60)
    print(
        f"DEMO LIVE SIMULATION (synthetic prices) for {instrument.source}:{instrument.symbol}, "
        f"tick every {interval}s{f' for {duration}s' if duration else ''}. Ctrl+C to stop."
    )
    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration if duration else math.inf
    candle: CandleIn | None = None
    ticks = 0
    try:
        while loop.time() < deadline and (max_ticks is None or ticks < max_ticks):
            minute = datetime.now(UTC).replace(second=0, microsecond=0)
            previous = price
            price = round(previous * math.exp(rng.gauss(0, vol)), digits)
            if candle is None or candle.ts != minute:
                # a new minute opens at the previous close
                candle = CandleIn(
                    ts=minute,
                    open=previous,
                    high=max(previous, price),
                    low=min(previous, price),
                    close=price,
                    volume=0,
                    trades=0,
                )
            else:
                candle = candle.model_copy(
                    update={
                        "high": max(candle.high, price),
                        "low": min(candle.low, price),
                        "close": price,
                        "volume": round(candle.volume + rng.lognormvariate(0, 0.7), 4),
                        "trades": (candle.trades or 0) + rng.randint(1, 20),
                    }
                )
            async with session_factory() as session:
                await market_service.upsert_candles(session, instrument.id, [candle])
                await session.commit()
                published = await market_events.publish_candle_updates_safely(
                    session, instrument.id, [candle]
                )
            ticks += 1
            print(
                f"[DEMO] {candle.ts:%H:%M} O={candle.open} H={candle.high} L={candle.low} "
                f"C={candle.close} V={candle.volume} -> {','.join(published) or 'not published'}",
                flush=True,
            )
            await asyncio.sleep(max(0.0, min(interval, deadline - loop.time())))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    print(f"Stopped after {ticks} ticks")
    return 0


async def _run(coro: Awaitable[int]) -> int:
    try:
        return await coro
    finally:
        await close_redis()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-admin", help="Create an admin, or promote an existing user")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)

    sub.add_parser("seed-instruments", help="Create the default instruments (idempotent)")

    p = sub.add_parser(
        "seed-demo-candles",
        help="Upsert DEMO 1m candles (synthetic random walk) ending at the current minute",
    )
    p.add_argument("--symbol", required=True, help="e.g. BTC/USDT")
    p.add_argument("--source", required=True, help="e.g. binance")
    p.add_argument("--days", type=float, default=30)
    p.add_argument("--seed", type=int, default=None, help="random seed for reproducible data")
    p.add_argument(
        "--no-refresh",
        action="store_true",
        help="skip refreshing the continuous aggregates afterwards",
    )

    p = sub.add_parser(
        "simulate-live",
        help="DEMO: update the current 1m candle every --interval seconds and publish it live",
    )
    p.add_argument("--symbol", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--interval", type=float, default=2)
    p.add_argument("--duration", type=float, default=None, help="stop after N seconds")
    p.add_argument("--ticks", type=int, default=None, help="stop after N updates")
    p.add_argument("--seed", type=int, default=None)

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return asyncio.run(create_admin(args.email, args.password))
    if args.command == "seed-instruments":
        return asyncio.run(seed_instruments())
    if args.command == "seed-demo-candles":
        return asyncio.run(
            _run(
                seed_demo_candles(
                    args.symbol,
                    args.source,
                    args.days,
                    seed=args.seed,
                    refresh=not args.no_refresh,
                )
            )
        )
    if args.command == "simulate-live":
        try:
            return asyncio.run(
                _run(
                    simulate_live(
                        args.symbol,
                        args.source,
                        args.interval,
                        duration=args.duration,
                        max_ticks=args.ticks,
                        seed=args.seed,
                    )
                )
            )
        except KeyboardInterrupt:
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
