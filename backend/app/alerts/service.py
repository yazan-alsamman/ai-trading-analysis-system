"""Price alerts of a user: create, list, update, delete, trigger history."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.notification import Notification, NotificationType
from app.models.price_alert import AlertCondition, AlertRepeat, PriceAlert
from app.models.user import User
from app.schemas.price_alerts import (
    DEFAULT_COOLDOWN,
    PriceAlertCreate,
    PriceAlertUpdate,
    check_combination,
)
from app.services import market_service


def read(alert: PriceAlert, symbol: str) -> dict[str, Any]:
    return {
        "id": alert.id,
        "instrument": {"id": alert.instrument_id, "symbol": symbol},
        "condition": alert.condition,
        "value": alert.value,
        "window_minutes": alert.window_minutes,
        "repeat": alert.repeat,
        "cooldown_minutes": alert.cooldown_minutes,
        "note": alert.note,
        "is_active": alert.is_active,
        "last_triggered_at": alert.last_triggered_at,
        "trigger_count": alert.trigger_count,
        "expires_at": alert.expires_at,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
    }


async def _active_count(session: AsyncSession, user: User) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(PriceAlert)
            .where(PriceAlert.user_id == user.id, PriceAlert.is_active.is_(True))
        )
        or 0
    )


async def _check_limit(session: AsyncSession, user: User) -> None:
    limit = get_settings().price_alert_limit(user.role.value)
    if await _active_count(session, user) >= limit:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"At most {limit} active price alerts for your role"
        )


def would_trigger(condition: AlertCondition, value: float, price: float | None) -> bool:
    if price is None:
        return False
    if condition == AlertCondition.above:
        return price >= value
    if condition == AlertCondition.below:
        return price <= value
    return False  # crosses and moves need a new bar


async def create(session: AsyncSession, user: User, data: PriceAlertCreate) -> dict[str, Any]:
    instrument = await session.get(Instrument, data.instrument_id)
    if instrument is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instrument not found")
    if not instrument.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Instrument is inactive")
    await _check_limit(session, user)
    alert = PriceAlert(user_id=user.id, **data.model_dump())
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    latest = await market_service.get_latest_candle(session, instrument.id, Timeframe.m1)
    price = latest.close if latest else None
    return {
        **read(alert, instrument.symbol),
        "current_price": price,
        "would_trigger_now": would_trigger(alert.condition, alert.value, price),
    }


async def own(session: AsyncSession, user: User, alert_id: uuid.UUID) -> PriceAlert:
    alert = await session.get(PriceAlert, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Price alert not found")
    return alert


async def symbol_of(session: AsyncSession, instrument_id: uuid.UUID) -> str:
    return await session.scalar(select(Instrument.symbol).where(Instrument.id == instrument_id))


async def update(
    session: AsyncSession, user: User, alert: PriceAlert, data: PriceAlertUpdate
) -> dict[str, Any]:
    fields = data.model_dump(exclude_unset=True)
    merged = {
        name: fields.get(name, getattr(alert, name))
        for name in ("condition", "value", "window_minutes", "repeat", "cooldown_minutes")
    }
    if merged["condition"] != AlertCondition.change_pct and "condition" in fields:
        merged["window_minutes"] = None
    if merged["repeat"] == AlertRepeat.once:
        merged["cooldown_minutes"] = None
    elif merged["cooldown_minutes"] is None:
        merged["cooldown_minutes"] = DEFAULT_COOLDOWN
    try:
        check_combination(
            merged["condition"],
            merged["value"],
            merged["window_minutes"],
            merged["repeat"],
            merged["cooldown_minutes"],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    if fields.get("is_active") and not alert.is_active:
        await _check_limit(session, user)
    for name, value in {**fields, **merged}.items():
        setattr(alert, name, value)
    await session.commit()
    await session.refresh(alert)
    return read(alert, await symbol_of(session, alert.instrument_id))


async def remove(session: AsyncSession, alert: PriceAlert) -> None:
    await session.delete(alert)
    await session.commit()


async def list_alerts(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
    offset: int,
    instrument_id: uuid.UUID | None = None,
    is_active: bool | None = None,
) -> tuple[list[dict[str, Any]], int]:
    where = [PriceAlert.user_id == user.id]
    if instrument_id is not None:
        where.append(PriceAlert.instrument_id == instrument_id)
    if is_active is not None:
        where.append(PriceAlert.is_active.is_(is_active))
    total = await session.scalar(select(func.count()).select_from(PriceAlert).where(*where))
    rows = await session.execute(
        select(PriceAlert, Instrument.symbol)
        .join(Instrument, Instrument.id == PriceAlert.instrument_id)
        .where(*where)
        .order_by(PriceAlert.created_at.desc(), PriceAlert.id)
        .limit(limit)
        .offset(offset)
    )
    return [read(a, s) for a, s in rows.all()], total or 0


def _uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


async def history(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
    offset: int,
    alert_id: uuid.UUID | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """The user's ``price_alert`` notifications (they keep the trigger prices), newest first.
    Kept as long as the inbox keeps them (Y15 retention)."""
    where = [Notification.user_id == user.id, Notification.type == NotificationType.price_alert]
    if alert_id is not None:
        where.append(Notification.data["alert_id"].astext == str(alert_id))
    total = await session.scalar(select(func.count()).select_from(Notification).where(*where))
    rows = await session.scalars(
        select(Notification)
        .where(*where)
        .order_by(Notification.created_at.desc(), Notification.id)
        .limit(limit)
        .offset(offset)
    )
    out = []
    for n in rows:
        d = n.data or {}
        instrument = d.get("instrument") or {}
        out.append(
            {
                "notification_id": n.id,
                "alert_id": _uuid(d.get("alert_id")),
                "instrument_id": _uuid(instrument.get("id")),
                "symbol": instrument.get("symbol"),
                "condition": d.get("condition"),
                "value": d.get("value"),
                "price": d.get("price"),
                "bar_time": d.get("bar_time"),
                "change_pct": d.get("change_pct"),
                "note": d.get("note"),
                "created_at": n.created_at,
            }
        )
    return out, total or 0
