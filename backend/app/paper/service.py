"""Paper trading (docs/paper-trading.md): a simulated account per user with virtual USD, filled
on the platform's own 1m candles. No broker and no real money.

Prices and money:

- A market order fills at the close of the latest 1m candle, which must be at most
  ``PAPER_MAX_PRICE_AGE_MINUTES`` old (else 409 ``market_closed``). Limit and stop orders wait;
  the engine (``app/paper/engine.py``) fills them on the closed 1m bars.
- P/L = (exit - entry) x lots x contract size (sell: the opposite sign), in the quote currency.
  Only instruments quoted in USD (or USDT/USDC) are supported: the account is in USD.
- Margin = entry x lots x contract size x max(1 / leverage, instrument margin rate). A new
  position needs free margin (equity - margin used) for its margin.
- Cost = ``cost_per_unit`` x units (the instrument's fixed round-trip cost, as in backtests),
  taken from the P/L at close.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.paper import (
    PaperAccount,
    PaperOrder,
    PaperOrderStatus,
    PaperOrderType,
    PaperPosition,
    PaperPositionStatus,
)
from app.models.user import User
from app.services import market_service

USD_QUOTES = {"USD", "USDT", "USDC"}
MINUTE = timedelta(minutes=1)
EPS = 1e-9


def utcnow() -> datetime:
    return datetime.now(UTC)


def floor_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def _error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code, {"code": code, "message": message, **extra})


def require_enabled() -> None:
    if not get_settings().paper_trading_enabled:
        raise _error(503, "not_configured", "paper trading is turned off")


# --- money ---------------------------------------------------------------------------------------


def direction(side: str) -> int:
    return 1 if side == "buy" else -1


def gross_pnl(side: str, entry: float, price: float, lots: float, contract_size: float) -> float:
    return (price - entry) * direction(side) * lots * contract_size


def margin_for(instrument: Instrument, price: float, lots: float, leverage: int) -> float:
    rate = max(1.0 / max(leverage, 1), instrument.margin_rate or 0.0)
    return price * lots * (instrument.contract_size or 0.0) * rate


def cost_for(instrument: Instrument, lots: float, contract_size: float) -> float:
    return (instrument.cost_per_unit or 0.0) * lots * contract_size


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


# --- account -------------------------------------------------------------------------------------


async def get_account(session: AsyncSession, user_id: uuid.UUID) -> PaperAccount:
    account = await session.get(PaperAccount, user_id)
    if account is None:
        settings = get_settings()
        account = PaperAccount(
            user_id=user_id,
            currency="USD",
            initial_balance=settings.paper_initial_balance,
            balance=settings.paper_initial_balance,
            leverage=settings.paper_default_leverage,
        )
        session.add(account)
        await session.flush()
        await session.refresh(account)
    return account


@dataclass
class Quote:
    price: float
    at: datetime


async def latest_quote(session: AsyncSession, instrument_id: uuid.UUID) -> Quote | None:
    latest = await market_service.get_latest_candle(session, instrument_id, Timeframe.m1)
    return Quote(latest.close, latest.ts) if latest is not None else None


async def _open_positions(session: AsyncSession, user_id: uuid.UUID) -> list[PaperPosition]:
    return list(
        await session.scalars(
            select(PaperPosition)
            .where(PaperPosition.user_id == user_id, PaperPosition.status == "open")
            .order_by(PaperPosition.opened_at)
        )
    )


async def _quotes(session: AsyncSession, instrument_ids) -> dict[uuid.UUID, Quote | None]:
    return {iid: await latest_quote(session, iid) for iid in set(instrument_ids)}


async def summary(session: AsyncSession, account: PaperAccount) -> dict[str, Any]:
    positions = await _open_positions(session, account.user_id)
    quotes = await _quotes(session, [p.instrument_id for p in positions])
    unrealized = 0.0
    margin_used = 0.0
    for p in positions:
        quote = quotes.get(p.instrument_id)
        price = quote.price if quote else p.entry_price
        unrealized += gross_pnl(p.side, p.entry_price, price, p.lots, p.contract_size)
        margin_used += p.margin
    equity = account.balance + unrealized
    day_start = floor_minute(utcnow()).replace(hour=0, minute=0)
    closed_today = await session.scalar(
        select(func.coalesce(func.sum(PaperPosition.pnl), 0.0)).where(
            PaperPosition.user_id == account.user_id,
            PaperPosition.status == "closed",
            PaperPosition.closed_at >= day_start,
        )
    )
    pending = await session.scalar(
        select(func.count())
        .select_from(PaperOrder)
        .where(PaperOrder.user_id == account.user_id, PaperOrder.status == "pending")
    )
    today = float(closed_today or 0.0) + unrealized
    start_of_day_equity = equity - today
    return {
        "currency": account.currency,
        "initial_balance": _round(account.initial_balance),
        "balance": _round(account.balance),
        "equity": _round(equity),
        "unrealized_pnl": _round(unrealized),
        "realized_pnl": _round(account.balance - account.initial_balance),
        "margin_used": _round(margin_used),
        "free_margin": _round(equity - margin_used),
        "margin_level_pct": _round(equity / margin_used * 100) if margin_used > EPS else None,
        "leverage": account.leverage,
        "return_pct": _round((equity - account.initial_balance) / account.initial_balance * 100),
        "today_pnl": _round(today),
        "today_pnl_pct": (
            _round(today / start_of_day_equity * 100) if start_of_day_equity > EPS else None
        ),
        "open_positions": len(positions),
        "pending_orders": int(pending or 0),
        "created_at": account.created_at,
        "reset_at": account.reset_at,
    }


async def set_leverage(session: AsyncSession, user: User, leverage: int) -> PaperAccount:
    if leverage > get_settings().paper_max_leverage:
        raise _error(
            422, "invalid_leverage", f"leverage is at most {get_settings().paper_max_leverage}"
        )
    account = await get_account(session, user.id)
    account.leverage = leverage
    account.updated_at = utcnow()
    await session.commit()
    return account


async def reset(session: AsyncSession, user: User, initial_balance: float | None) -> PaperAccount:
    """Deletes every order and position of the user and starts again with a fresh balance."""
    account = await get_account(session, user.id)
    await session.execute(delete(PaperOrder).where(PaperOrder.user_id == user.id))
    await session.execute(delete(PaperPosition).where(PaperPosition.user_id == user.id))
    amount = initial_balance or get_settings().paper_initial_balance
    account.initial_balance = amount
    account.balance = amount
    account.reset_at = account.updated_at = utcnow()
    await session.commit()
    return account


# --- validation ----------------------------------------------------------------------------------


async def tradable_instrument(session: AsyncSession, instrument_id: uuid.UUID) -> Instrument:
    instrument = await session.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrument not found")
    if not instrument.is_active:
        raise _error(422, "inactive_instrument", "the instrument is inactive")
    if not instrument.contract_size:
        raise _error(
            422, "no_contract_spec", "the instrument has no contract size: it cannot be traded"
        )
    quote = (instrument.quote_currency or instrument.quote_asset or "").upper()
    if quote not in USD_QUOTES:
        raise _error(
            422, "unsupported_currency", "only instruments quoted in USD can be paper traded"
        )
    return instrument


def check_lots(instrument: Instrument, lots: float) -> None:
    min_lot = instrument.min_lot or 0.01
    step = instrument.lot_step or 0.01
    max_lot = instrument.max_lot or 100.0
    if lots < min_lot - EPS or lots > max_lot + EPS:
        raise _error(
            422, "invalid_lots", f"lots must be between {min_lot:g} and {max_lot:g}",
            min_lot=min_lot, max_lot=max_lot, lot_step=step,
        )  # fmt: skip
    steps = lots / step
    if abs(steps - round(steps)) > 1e-6:
        raise _error(
            422, "invalid_lots", f"lots must be a multiple of {step:g}",
            min_lot=min_lot, max_lot=max_lot, lot_step=step,
        )  # fmt: skip


def check_levels(side: str, entry: float, stop_loss: float | None, take_profit: float | None):
    if side == "buy":
        if stop_loss is not None and stop_loss >= entry:
            raise _error(422, "invalid_stop_loss", "a buy's stop loss must be below the entry")
        if take_profit is not None and take_profit <= entry:
            raise _error(422, "invalid_take_profit", "a buy's take profit must be above the entry")
    else:
        if stop_loss is not None and stop_loss <= entry:
            raise _error(422, "invalid_stop_loss", "a sell's stop loss must be above the entry")
        if take_profit is not None and take_profit >= entry:
            raise _error(422, "invalid_take_profit", "a sell's take profit must be below the entry")


def check_trigger(side: str, type_: str, price: float, reference: float) -> None:
    """Limit: a better price than now (buy below, sell above). Stop: a worse one (buy above,
    sell below). Otherwise the order would fill at once: use a market order."""
    above = price > reference
    want_above = (type_ == "limit" and side == "sell") or (type_ == "stop" and side == "buy")
    if above != want_above or math.isclose(price, reference):
        where = "above" if want_above else "below"
        raise _error(
            422,
            "invalid_price",
            f"a {side} {type_} order needs a price {where} the current price {reference:g}",
            current_price=reference,
        )


# --- orders and positions ------------------------------------------------------------------------


async def _fresh_quote(session: AsyncSession, instrument: Instrument) -> Quote:
    quote = await latest_quote(session, instrument.id)
    max_age = timedelta(minutes=get_settings().paper_max_price_age_minutes)
    if quote is None or utcnow() - quote.at > max_age:
        raise _error(
            409,
            "market_closed",
            "no live price for this instrument now (the market is closed): place a limit or "
            "stop order instead",
            last_price_at=quote.at.isoformat() if quote else None,
        )
    return quote


async def open_position(
    session: AsyncSession,
    account: PaperAccount,
    instrument: Instrument,
    order: PaperOrder,
    fill_price: float,
    at: datetime,
    checked_until: datetime,
) -> PaperPosition | None:
    """Fills ``order`` (flushes; the caller commits). None, and the order rejected with
    ``insufficient_margin``, when the free margin is too small."""
    margin = margin_for(instrument, fill_price, order.lots, account.leverage)
    free = (await summary(session, account))["free_margin"] or 0.0
    if margin > free + EPS:
        order.status = PaperOrderStatus.rejected
        order.reject_reason = "insufficient_margin"
        order.cancelled_at = at
        await session.flush()
        return None
    position = PaperPosition(
        user_id=order.user_id,
        instrument_id=instrument.id,
        side=order.side,
        lots=order.lots,
        contract_size=instrument.contract_size,
        entry_price=fill_price,
        stop_loss=order.stop_loss,
        take_profit=order.take_profit,
        margin=margin,
        cost=cost_for(instrument, order.lots, instrument.contract_size),
        opened_at=at,
        checked_until=checked_until,
    )
    session.add(position)
    await session.flush()
    order.status = PaperOrderStatus.filled
    order.fill_price = fill_price
    order.filled_at = at
    order.position_id = position.id
    await session.flush()
    return position


async def place_order(session: AsyncSession, user: User, data) -> dict[str, Any]:
    settings = get_settings()
    instrument = await tradable_instrument(session, data.instrument_id)
    check_lots(instrument, data.lots)
    account = await get_account(session, user.id)
    pending = await session.scalar(
        select(func.count())
        .select_from(PaperOrder)
        .where(PaperOrder.user_id == user.id, PaperOrder.status == "pending")
    )
    open_count = await session.scalar(
        select(func.count())
        .select_from(PaperPosition)
        .where(PaperPosition.user_id == user.id, PaperPosition.status == "open")
    )
    now = utcnow()
    order = PaperOrder(
        user_id=user.id,
        instrument_id=instrument.id,
        side=data.side,
        type=data.type,
        lots=data.lots,
        price=data.price,
        stop_loss=data.stop_loss,
        take_profit=data.take_profit,
        status=PaperOrderStatus.pending,
        created_at=now,
    )
    if data.type == PaperOrderType.market:
        if (open_count or 0) >= settings.paper_max_open_positions:
            raise _error(409, "too_many_positions", "too many open positions")
        quote = await _fresh_quote(session, instrument)
        check_levels(data.side, quote.price, data.stop_loss, data.take_profit)
        session.add(order)
        await session.flush()
        position = await open_position(
            session, account, instrument, order, quote.price, now, floor_minute(now) + MINUTE
        )
        if position is None:
            raise _error(
                422,
                "insufficient_margin",
                "not enough free margin for this position (lower the lots or raise the leverage)",
                required_margin=_round(
                    margin_for(instrument, quote.price, data.lots, account.leverage)
                ),
            )
    else:
        if (pending or 0) >= settings.paper_max_pending_orders:
            raise _error(409, "too_many_orders", "too many pending orders")
        quote = await latest_quote(session, instrument.id)
        if quote is None:
            raise _error(409, "no_price", "this instrument has no price data yet")
        check_trigger(data.side, data.type, data.price, quote.price)
        check_levels(data.side, data.price, data.stop_loss, data.take_profit)
        order.checked_until = floor_minute(now) + MINUTE
        session.add(order)
        await session.flush()
    await session.commit()
    return (await serialize_orders(session, [order]))[0]


async def own_order(session: AsyncSession, user: User, order_id: uuid.UUID) -> PaperOrder:
    order = await session.scalar(
        select(PaperOrder).where(PaperOrder.id == order_id).with_for_update()
    )
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


async def cancel_order(session: AsyncSession, user: User, order_id: uuid.UUID) -> dict:
    order = await own_order(session, user, order_id)
    if order.status != PaperOrderStatus.pending:
        raise _error(409, "not_pending", f"the order is {order.status}")
    order.status = PaperOrderStatus.cancelled
    order.cancelled_at = utcnow()
    await session.commit()
    return (await serialize_orders(session, [order]))[0]


async def own_position(session: AsyncSession, user: User, position_id: uuid.UUID) -> PaperPosition:
    position = await session.scalar(
        select(PaperPosition).where(PaperPosition.id == position_id).with_for_update()
    )
    if position is None or position.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Position not found")
    return position


async def close(
    session: AsyncSession, position: PaperPosition, price: float, at: datetime, reason: str
) -> float:
    """Closes ``position`` at ``price`` and books the net P/L into the balance (flushes)."""
    pnl = gross_pnl(
        position.side, position.entry_price, price, position.lots, position.contract_size
    )
    pnl -= position.cost
    position.status = PaperPositionStatus.closed
    position.close_price = price
    position.closed_at = at
    position.close_reason = reason
    position.pnl = pnl
    await session.execute(
        update(PaperAccount)
        .where(PaperAccount.user_id == position.user_id)
        .values(balance=PaperAccount.balance + pnl, updated_at=at)
    )
    await session.flush()
    return pnl


async def close_position(session: AsyncSession, user: User, position_id: uuid.UUID) -> dict:
    position = await own_position(session, user, position_id)
    if position.status != PaperPositionStatus.open:
        raise _error(409, "not_open", "the position is already closed")
    instrument = await session.get(Instrument, position.instrument_id)
    quote = await _fresh_quote(session, instrument)
    await close(session, position, quote.price, utcnow(), "manual")
    await session.commit()
    return (await serialize_positions(session, [position]))[0]


async def update_levels(session: AsyncSession, user: User, position_id: uuid.UUID, data) -> dict:
    position = await own_position(session, user, position_id)
    if position.status != PaperPositionStatus.open:
        raise _error(409, "not_open", "the position is already closed")
    fields = data.model_dump(exclude_unset=True)
    stop_loss = fields.get("stop_loss", position.stop_loss)
    take_profit = fields.get("take_profit", position.take_profit)
    quote = await latest_quote(session, position.instrument_id)
    reference = quote.price if quote else position.entry_price
    check_levels(position.side, reference, stop_loss, take_profit)
    position.stop_loss, position.take_profit = stop_loss, take_profit
    await session.commit()
    return (await serialize_positions(session, [position]))[0]


# --- reading -------------------------------------------------------------------------------------


async def _instruments(session: AsyncSession, ids) -> dict[uuid.UUID, Instrument]:
    ids = set(ids)
    if not ids:
        return {}
    return {
        i.id: i for i in await session.scalars(select(Instrument).where(Instrument.id.in_(ids)))
    }


def _instrument_ref(instrument: Instrument | None) -> dict[str, Any] | None:
    if instrument is None:
        return None
    return {
        "id": instrument.id,
        "symbol": instrument.symbol,
        "price_precision": instrument.price_precision,
    }


async def serialize_orders(session: AsyncSession, orders: list[PaperOrder]) -> list[dict]:
    instruments = await _instruments(session, [o.instrument_id for o in orders])
    return [
        {
            "id": o.id,
            "instrument": _instrument_ref(instruments.get(o.instrument_id)),
            "side": o.side,
            "type": o.type,
            "lots": o.lots,
            "price": o.price,
            "stop_loss": o.stop_loss,
            "take_profit": o.take_profit,
            "status": o.status,
            "reject_reason": o.reject_reason,
            "fill_price": o.fill_price,
            "position_id": o.position_id,
            "created_at": o.created_at,
            "filled_at": o.filled_at,
            "cancelled_at": o.cancelled_at,
        }
        for o in orders
    ]


async def serialize_positions(session: AsyncSession, positions: list[PaperPosition]) -> list[dict]:
    instruments = await _instruments(session, [p.instrument_id for p in positions])
    quotes = await _quotes(
        session, [p.instrument_id for p in positions if p.status == PaperPositionStatus.open]
    )
    out = []
    for p in positions:
        quote = quotes.get(p.instrument_id) if p.status == PaperPositionStatus.open else None
        unrealized = (
            gross_pnl(p.side, p.entry_price, quote.price, p.lots, p.contract_size)
            if quote is not None
            else None
        )
        out.append(
            {
                "id": p.id,
                "instrument": _instrument_ref(instruments.get(p.instrument_id)),
                "side": p.side,
                "lots": p.lots,
                "contract_size": p.contract_size,
                "entry_price": p.entry_price,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "margin": _round(p.margin),
                "cost": _round(p.cost),
                "status": p.status,
                "opened_at": p.opened_at,
                "current_price": quote.price if quote else None,
                "unrealized_pnl": _round(unrealized),
                "closed_at": p.closed_at,
                "close_price": p.close_price,
                "close_reason": p.close_reason,
                "pnl": _round(p.pnl),
            }
        )
    return out


async def list_orders(
    session: AsyncSession, user: User, *, status_: str | None, limit: int, offset: int
) -> tuple[list[dict], int]:
    conditions = [PaperOrder.user_id == user.id]
    if status_:
        conditions.append(PaperOrder.status == status_)
    total = await session.scalar(select(func.count()).select_from(PaperOrder).where(*conditions))
    rows = list(
        await session.scalars(
            select(PaperOrder)
            .where(*conditions)
            .order_by(PaperOrder.created_at.desc(), PaperOrder.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return await serialize_orders(session, rows), total or 0


async def list_positions(
    session: AsyncSession, user: User, *, status_: str | None, limit: int, offset: int
) -> tuple[list[dict], int]:
    conditions = [PaperPosition.user_id == user.id]
    if status_:
        conditions.append(PaperPosition.status == status_)
    order = (
        PaperPosition.opened_at.desc() if status_ != "closed" else PaperPosition.closed_at.desc()
    )
    total = await session.scalar(select(func.count()).select_from(PaperPosition).where(*conditions))
    rows = list(
        await session.scalars(
            select(PaperPosition)
            .where(*conditions)
            .order_by(order, PaperPosition.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return await serialize_positions(session, rows), total or 0
