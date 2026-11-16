"""The paper trading engine (docs/paper-trading.md): every minute (``paper.tick`` at the 1m
boundary + 10 s), on the closed 1m bars that arrived since the last run:

1. pending limit / stop orders whose price was reached are filled (a bar that opens beyond the
   price fills at its open: a gap), or rejected with ``insufficient_margin``;
2. open positions whose stop loss or take profit was reached are closed at that level (or at
   the bar's open on a gap). When one bar reaches both, the stop loss wins (conservative).

Each order and position remembers ``checked_until`` (the end of the last bar checked), so a bar
is never used twice and bars that arrive late are still checked. One run at a time (Redis
lock). Every fill, rejection and SL/TP close stores a ``paper_trade`` notification (inbox,
WebSocket, push). Rows are locked (``FOR UPDATE SKIP LOCKED``) against a manual close.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.notification import NotificationType, Severity
from app.models.paper import PaperOrder, PaperPosition
from app.notifications import service as notifications
from app.paper import service
from app.services import market_service
from app.services.market_service import CandleRow

logger = logging.getLogger(__name__)

MINUTE = timedelta(minutes=1)
LOCK_KEY = "lock:paper:engine"
LOCK_TTL_MS = 55_000
MAX_BARS = 2_000  # per instrument and run (a long outage is caught up over several runs)


@dataclass
class PaperRun:
    status: str = "done"  # done | locked
    instruments: int = 0
    orders: int = 0
    positions: int = 0
    filled: int = 0
    rejected: int = 0
    closed: int = 0
    notifications: int = 0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


def order_trigger(order: PaperOrder, bar: CandleRow) -> float | None:
    """The fill price of a pending order on ``bar``, or None."""
    p = order.price
    if order.type == "limit" and order.side == "buy" and bar.low <= p:
        return min(bar.open, p)
    if order.type == "limit" and order.side == "sell" and bar.high >= p:
        return max(bar.open, p)
    if order.type == "stop" and order.side == "buy" and bar.high >= p:
        return max(bar.open, p)
    if order.type == "stop" and order.side == "sell" and bar.low <= p:
        return min(bar.open, p)
    return None


def exit_trigger(position: PaperPosition, bar: CandleRow) -> tuple[float, str] | None:
    """(price, reason) when ``bar`` reaches the stop loss or take profit; the stop wins a tie."""
    sl, tp = position.stop_loss, position.take_profit
    if position.side == "buy":
        if sl is not None and bar.low <= sl:
            return min(bar.open, sl), "stop_loss"
        if tp is not None and bar.high >= tp:
            return max(bar.open, tp), "take_profit"
    else:
        if sl is not None and bar.high >= sl:
            return max(bar.open, sl), "stop_loss"
        if tp is not None and bar.low <= tp:
            return min(bar.open, tp), "take_profit"
    return None


def _payload(event: str, instrument: Instrument, **data: Any) -> dict[str, Any]:
    return {
        "event": event,
        "instrument": {
            "id": str(instrument.id),
            "symbol": instrument.symbol,
            "price_precision": instrument.price_precision,
        },
        **{k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in data.items()},
    }


async def evaluate(
    factory: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> PaperRun:
    started = time.perf_counter()
    now = now or datetime.now(UTC)
    run = PaperRun()
    token = uuid.uuid4().hex
    if not await redis.set(LOCK_KEY, token, nx=True, px=LOCK_TTL_MS):
        run.status = "locked"
        return run
    try:
        prepared = await _evaluate(factory, redis, run, now)
        await notifications.after_commit(redis, prepared)
    finally:
        if await redis.get(LOCK_KEY) == token:
            await redis.delete(LOCK_KEY)
    run.duration_ms = round((time.perf_counter() - started) * 1000, 1)
    return run


async def _evaluate(factory, redis, run: PaperRun, now: datetime):
    closed_until = service.floor_minute(now)  # bars starting before this are closed
    prepared = notifications.Prepared()
    async with factory() as session:
        order_rows = list(
            await session.execute(
                select(PaperOrder.instrument_id).where(PaperOrder.status == "pending").distinct()
            )
        )
        position_rows = list(
            await session.execute(
                select(PaperPosition.instrument_id)
                .where(
                    PaperPosition.status == "open",
                    or_(
                        PaperPosition.stop_loss.is_not(None),
                        PaperPosition.take_profit.is_not(None),
                    ),
                )
                .distinct()
            )
        )
    instrument_ids = {r[0] for r in order_rows} | {r[0] for r in position_rows}
    run.instruments = len(instrument_ids)
    for instrument_id in instrument_ids:
        try:
            async with factory() as session:
                items = await _instrument(session, run, instrument_id, closed_until)
                if items:
                    prepared.extend(await notifications.prepare(session, redis, items))
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - one instrument never stops the others
            logger.exception("paper engine: instrument %s failed", instrument_id)
            run.errors.append(f"{instrument_id}: {type(exc).__name__}")
    run.notifications = len(prepared.notifications)
    return prepared


async def _instrument(
    session: AsyncSession, run: PaperRun, instrument_id: uuid.UUID, closed_until: datetime
) -> list[notifications.NotifyItem]:
    instrument = await session.get(Instrument, instrument_id)
    orders = list(
        await session.scalars(
            select(PaperOrder)
            .where(PaperOrder.instrument_id == instrument_id, PaperOrder.status == "pending")
            .order_by(PaperOrder.created_at)
            .with_for_update(skip_locked=True)
        )
    )
    positions = list(
        await session.scalars(
            select(PaperPosition)
            .where(
                PaperPosition.instrument_id == instrument_id,
                PaperPosition.status == "open",
                or_(
                    PaperPosition.stop_loss.is_not(None),
                    PaperPosition.take_profit.is_not(None),
                ),
            )
            .order_by(PaperPosition.opened_at)
            .with_for_update(skip_locked=True)
        )
    )
    run.orders += len(orders)
    run.positions += len(positions)
    starts = [o.checked_until or service.floor_minute(o.created_at) + MINUTE for o in orders]
    starts += [p.checked_until for p in positions]
    if instrument is None or not starts:
        return []
    start = min(starts)
    if start >= closed_until:
        return []
    bars = [
        b
        for b in await market_service.get_candles(
            session, instrument_id, Timeframe.m1, start=start, limit=MAX_BARS
        )
        if b.ts + MINUTE <= closed_until
    ]
    if not bars:
        return []
    last_end = bars[-1].ts + MINUTE
    items: list[notifications.NotifyItem] = []

    accounts: dict[uuid.UUID, Any] = {}
    for order in orders:
        since = order.checked_until or service.floor_minute(order.created_at) + MINUTE
        filled = False
        for bar in bars:
            if bar.ts < since:
                continue
            price = order_trigger(order, bar)
            if price is None:
                continue
            at = bar.ts + MINUTE
            if order.user_id not in accounts:
                accounts[order.user_id] = await service.get_account(session, order.user_id)
            position = await service.open_position(
                session, accounts[order.user_id], instrument, order, price, at, at
            )
            filled = True
            if position is None:
                run.rejected += 1
                items.append(_item(order.user_id, "order_rejected", instrument, order=order))
            else:
                run.filled += 1
                positions.append(position)
                items.append(
                    _item(order.user_id, "order_filled", instrument, order=order, position=position)
                )
            break
        if not filled:
            order.checked_until = max(since, last_end)

    for position in positions:
        if position.status != "open" or (
            position.stop_loss is None and position.take_profit is None
        ):
            continue
        hit = None
        for bar in bars:
            if bar.ts < position.checked_until:
                continue
            hit = exit_trigger(position, bar)
            if hit is not None:
                price, reason = hit
                await service.close(session, position, price, bar.ts + MINUTE, reason)
                run.closed += 1
                items.append(_item(position.user_id, reason, instrument, position=position))
                break
        if hit is None:
            position.checked_until = max(position.checked_until, last_end)
    await session.flush()
    return items


def _item(
    user_id: uuid.UUID,
    event: str,
    instrument: Instrument,
    *,
    order: PaperOrder | None = None,
    position: PaperPosition | None = None,
) -> notifications.NotifyItem:
    data: dict[str, Any] = {}
    if order is not None:
        data.update(
            order_id=order.id,
            order_type=order.type,
            side=order.side,
            lots=order.lots,
            price=order.price,
            reject_reason=order.reject_reason,
        )
    if position is not None:
        data.update(
            position_id=position.id,
            side=position.side,
            lots=position.lots,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            close_price=position.close_price,
            pnl=None if position.pnl is None else round(position.pnl, 2),
        )
    ref = (position.id if position is not None and event != "order_filled" else None) or (
        order.id if order is not None else None
    )
    severity = {
        "order_filled": Severity.info,
        "order_rejected": Severity.warning,
        "take_profit": Severity.success,
        "stop_loss": Severity.warning,
    }[event]
    return notifications.NotifyItem(
        user_id=user_id,
        type=NotificationType.paper_trade,
        data=_payload(event, instrument, **data),
        dedup_key=f"paper:{event}:{ref}",
        severity=severity,
    )


__all__ = ["PaperRun", "evaluate", "exit_trigger", "order_trigger"]
