"""Global strategies (from ``trading_strategies``), user activations, previews and signals."""

import asyncio
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import trading_indicators as ti
import trading_strategies as ts
from fastapi import HTTPException, status
from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.strategy import Signal, UserStrategy
from app.models.user import User
from app.schemas.strategies import StrategyPreviewRequest, UserStrategyCreate, UserStrategyUpdate
from app.services import indicator_service, market_service
from app.services.indicator_service import ResolvedIndicator

MAX_USER_STRATEGIES = 20

BUY_COLOR, SELL_COLOR = "#26a69a", "#ef5350"


# --- catalog / params ------------------------------------------------------------------------


def get_strategy(key: str) -> ts.Strategy:
    try:
        return ts.get_strategy(key)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


def resolve_params(strategy: ts.Strategy, params: dict[str, Any] | None) -> dict[str, Any]:
    try:
        return strategy.resolve(params)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


def chart_indicators(strategy: ts.Strategy, params: dict[str, Any]) -> list[ResolvedIndicator]:
    """The indicator lines the strategy draws, resolved for indicator_service."""
    out = []
    for ind in strategy.indicators(params):
        spec = ti.get_indicator(ind["name"])
        out.append(ResolvedIndicator(spec, spec.resolve(ind["params"])))
    return out


# --- preview ---------------------------------------------------------------------------------


def _marker(time: int, side: int, strength: float) -> dict[str, Any]:
    buy = side == 1
    return {
        "time": time,
        "position": "belowBar" if buy else "aboveBar",
        "shape": "arrowUp" if buy else "arrowDown",
        "color": BUY_COLOR if buy else SELL_COLOR,
        "text": f"{'BUY' if buy else 'SELL'} {strength:.2f}",
    }


def _preview(
    candles: list[market_service.CandleRow],
    window: int,
    strategy: ts.Strategy,
    params: dict[str, Any],
    indicators: list[ResolvedIndicator],
) -> dict[str, Any]:
    """CPU-bound part of the preview (worker thread)."""
    df = indicator_service.frame(candles)
    first = len(candles) - window
    times = [int(r.ts.timestamp()) for r in candles[first:]]
    out = strategy.generate(df, params).iloc[first:]
    closes = df["close"].to_numpy()[first:]
    signals, markers = [], []
    for i, (side, strength, reason, details) in enumerate(
        zip(out["signal"], out["strength"], out["reason"], out["details"], strict=True)
    ):
        if side == 0:
            continue
        signals.append(
            {
                "time": times[i],
                "side": "buy" if side == 1 else "sell",
                "strength": float(strength),
                "price": float(closes[i]),
                "reason": reason,
                "details": details,
            }
        )
        markers.append(_marker(times[i], int(side), float(strength)))
    return {
        "signals": signals,
        "markers": markers,
        "indicators": indicator_service.lines(df, times, indicators),
        "bars": window,
    }


async def preview(session: AsyncSession, key: str, data: StrategyPreviewRequest) -> dict[str, Any]:
    """Run a strategy over the candle window (same window semantics and warm-up handling as
    the indicators endpoint) and return its signals, chart markers and indicator lines."""
    strategy = get_strategy(key)
    params = resolve_params(strategy, data.params)
    await market_service.get_instrument_or_404(session, data.instrument_id)
    indicators = chart_indicators(strategy, params)
    lines_history, anchored = indicator_service.needs(indicators)
    before, window = await indicator_service.load_candles(
        session,
        data.instrument_id,
        data.timeframe,
        history=max(strategy.history(params), lines_history),
        day_anchor=anchored,
        start=data.start,
        end=data.end,
        limit=data.limit,
    )
    result = await asyncio.to_thread(
        _preview, before + window, len(window), strategy, params, indicators
    )
    return {
        "strategy_key": key,
        "params": params,
        "instrument_id": str(data.instrument_id),
        "timeframe": data.timeframe.value,
        **result,
    }


# --- user activations ------------------------------------------------------------------------


async def _active_instrument(session: AsyncSession, instrument_id: uuid.UUID) -> Instrument:
    instrument = await session.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "instrument not found")
    if not instrument.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "instrument is inactive")
    return instrument


async def list_user_strategies(session: AsyncSession, user: User) -> Sequence[UserStrategy]:
    rows = await session.scalars(
        select(UserStrategy)
        .where(UserStrategy.user_id == user.id)
        .order_by(UserStrategy.created_at, UserStrategy.id)
    )
    return rows.all()


async def get_user_strategy_or_404(
    session: AsyncSession, user: User, user_strategy_id: uuid.UUID
) -> UserStrategy:
    row = await session.scalar(
        select(UserStrategy).where(
            UserStrategy.id == user_strategy_id, UserStrategy.user_id == user.id
        )
    )
    if row is None:  # also for other users' activations: do not reveal they exist
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy activation not found")
    return row


async def _commit_or_409(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "You already run this strategy with these parameters on this market and timeframe",
        ) from exc


async def create_user_strategy(
    session: AsyncSession, user: User, data: UserStrategyCreate
) -> UserStrategy:
    strategy = get_strategy(data.strategy_key)
    params = resolve_params(strategy, data.params)
    await _active_instrument(session, data.instrument_id)
    count = await session.scalar(
        select(func.count()).select_from(UserStrategy).where(UserStrategy.user_id == user.id)
    )
    if count >= MAX_USER_STRATEGIES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"At most {MAX_USER_STRATEGIES} strategy activations per user",
        )
    row = UserStrategy(
        user_id=user.id,
        strategy_key=strategy.key,
        params=params,
        params_hash=ts.params_hash(strategy.key, params),
        instrument_id=data.instrument_id,
        timeframe=data.timeframe,
        name=data.name,
        is_active=data.is_active,
        notify=data.notify,
    )
    session.add(row)
    await _commit_or_409(session)
    await session.refresh(row)
    return row


async def update_user_strategy(
    session: AsyncSession, row: UserStrategy, data: UserStrategyUpdate
) -> UserStrategy:
    changes = data.model_dump(exclude_unset=True)
    if "params" in changes:
        strategy = get_strategy(row.strategy_key)
        params = resolve_params(strategy, changes.pop("params"))
        row.params, row.params_hash = params, ts.params_hash(strategy.key, params)
    if changes.get("is_active"):
        await _active_instrument(session, row.instrument_id)
    for name, value in changes.items():
        setattr(row, name, value)
    await _commit_or_409(session)
    await session.refresh(row)
    return row


async def delete_user_strategy(session: AsyncSession, row: UserStrategy) -> None:
    await session.delete(row)
    await session.commit()


# --- signals ---------------------------------------------------------------------------------


async def list_signals(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
    offset: int,
    instrument_id: uuid.UUID | None = None,
    timeframe: Timeframe | None = None,
    strategy_key: str | None = None,
    since: datetime | None = None,
    mine: bool = False,
) -> tuple[Sequence[Signal], int]:
    filters = []
    if instrument_id is not None:
        filters.append(Signal.instrument_id == instrument_id)
    if timeframe is not None:
        filters.append(Signal.timeframe == timeframe)
    if strategy_key:
        filters.append(Signal.strategy_key == strategy_key)
    if since is not None:
        filters.append(Signal.bar_time >= since)
    if mine:
        setups = (
            select(
                UserStrategy.instrument_id,
                UserStrategy.timeframe,
                UserStrategy.strategy_key,
                UserStrategy.params_hash,
            )
            .where(UserStrategy.user_id == user.id, UserStrategy.is_active.is_(True))
            .subquery()
        )
        filters.append(
            tuple_(
                Signal.instrument_id, Signal.timeframe, Signal.strategy_key, Signal.params_hash
            ).in_(select(setups))
        )
    where = and_(*filters) if filters else None
    count_q = select(func.count()).select_from(Signal)
    rows_q = select(Signal).order_by(Signal.bar_time.desc(), Signal.created_at.desc(), Signal.id)
    if where is not None:
        count_q, rows_q = count_q.where(where), rows_q.where(where)
    total = await session.scalar(count_q)
    rows = await session.scalars(rows_q.limit(limit).offset(offset))
    return rows.all(), total or 0
