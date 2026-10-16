"""Risk profiles, risk configs (validated by ``trading_backtest``), the position-size
calculator and the per-user trade plans of live signals.

- A profile is created on first read with the ``balanced`` template and 10,000 USDT.
- The rules of a plan come from the activation's ``risk_override`` if set, else the profile,
  else the default template (a user who never opened the profile).
"""

import json
import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import trading_backtest as tb
from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candle import Timeframe
from app.models.risk import RiskProfile, SignalPlan
from app.models.strategy import Signal
from app.models.user import User
from app.schemas.risk import PositionSizeRequest, RiskProfileUpdate
from app.services import indicator_service, market_service

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_SIZE = 10_000.0
DEFAULT_CURRENCY = "USDT"
PLACEHOLDER_STOP = {"type": "percent", "value": 1.0}  # replaced by an explicit stop price


def templates() -> dict[str, dict[str, Any]]:
    return {name: tb.validate_risk_config(cfg) for name, cfg in tb.TEMPLATES.items()}


def default_config() -> dict[str, Any]:
    return tb.validate_risk_config(tb.TEMPLATES[tb.risk.DEFAULT_TEMPLATE])


def config_errors(exc: tb.ConfigError, prefix: Sequence[str]) -> list[dict[str, Any]]:
    """Library errors as FastAPI-style 422 details plus ``path``."""
    return [
        {"loc": [*prefix, *e["loc"]], "msg": e["message"], "type": "value_error", "path": e["path"]}
        for e in exc.errors
    ]


def validate_config(config: Any, prefix: Sequence[str] = ("body", "config")) -> dict[str, Any]:
    """The normalised risk config, or 422 with every error and its path."""
    try:
        return tb.validate_risk_config(config)
    except tb.ConfigError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, config_errors(exc, prefix)
        ) from None


def schema() -> dict[str, Any]:
    return {
        "json_schema": tb.risk_json_schema(),
        "templates": templates(),
        "default_template": tb.risk.DEFAULT_TEMPLATE,
    }


# --- profiles --------------------------------------------------------------------------------


async def get_or_create(session: AsyncSession, user: User) -> RiskProfile:
    row = await session.get(RiskProfile, user.id)
    if row is not None:
        return row
    stmt = (
        insert(RiskProfile)
        .values(
            user_id=user.id,
            account_size=DEFAULT_ACCOUNT_SIZE,
            quote_currency=DEFAULT_CURRENCY,
            config=default_config(),
            template=tb.risk.DEFAULT_TEMPLATE,
        )
        .on_conflict_do_nothing(index_elements=["user_id"])  # two first reads at once
    )
    await session.execute(stmt)
    await session.commit()
    return await session.get(RiskProfile, user.id, populate_existing=True)


def read(row: RiskProfile) -> dict[str, Any]:
    return {
        "account_size": row.account_size,
        "quote_currency": row.quote_currency,
        "config": row.config,
        "template": row.template,
        "updated_at": row.updated_at,
    }


async def update(session: AsyncSession, user: User, data: RiskProfileUpdate) -> RiskProfile:
    row = await get_or_create(session, user)
    if data.template is not None:
        row.config = tb.validate_risk_config(tb.TEMPLATES[data.template])
        row.template = data.template
    elif data.config is not None:
        row.config = validate_config(data.config)
        named = templates()
        row.template = next((n for n, c in named.items() if c == row.config), None)
    if data.account_size is not None:
        row.account_size = data.account_size
    if data.quote_currency is not None:
        row.quote_currency = data.quote_currency
    try:
        await session.commit()
    except IntegrityError:  # pragma: no cover - the check constraint mirrors the schema
        await session.rollback()
        raise
    await session.refresh(row)
    return row


async def profiles_for(
    session: AsyncSession, user_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, RiskProfile]:
    """One query for many users (live signals). Users without a profile are missing."""
    if not user_ids:
        return {}
    rows = await session.scalars(select(RiskProfile).where(RiskProfile.user_id.in_(user_ids)))
    return {r.user_id: r for r in rows}


def effective(
    override: dict[str, Any] | None, profile: RiskProfile | None
) -> tuple[dict[str, Any], float, str, str]:
    """(risk config, account size, currency, source) of an activation's plans."""
    size = profile.account_size if profile else DEFAULT_ACCOUNT_SIZE
    currency = profile.quote_currency if profile else DEFAULT_CURRENCY
    if override is not None:
        return override, size, currency, "override"
    if profile is not None:
        return profile.config, size, currency, "profile"
    return default_config(), size, currency, "default"


def history_for(config: dict[str, Any]) -> int:
    """Bars of candles the plan's indicators need (ATR warm-up + convergence)."""
    return tb.risk.history(tb.BacktestConfig.from_risk(config))


def plan_dict(
    df: pd.DataFrame, side: int, config: dict[str, Any], account_size: float, **kw: Any
) -> dict[str, Any]:
    plan = tb.plan_trade(df, len(df) - 1, side, config, account_size, **kw)
    return plan.to_dict()


# --- calculator ------------------------------------------------------------------------------


async def position_size(
    session: AsyncSession, user: User, data: PositionSizeRequest
) -> dict[str, Any]:
    """A plan on the last closed bar of a market with the caller's (or the given) rules."""
    profile = await get_or_create(session, user)
    raw = data.config if data.config is not None else profile.config
    needs_placeholder = data.stop is not None and not (raw or {}).get("stop")
    config = validate_config(
        {**(raw or {}), "stop": PLACEHOLDER_STOP} if needs_placeholder else raw
    )
    account_size = data.account_size or profile.account_size
    await market_service.get_instrument_or_404(session, data.instrument_id)
    now = datetime.now(UTC)
    last_closed = market_service.floor_to_bucket(now, data.timeframe.interval)
    last_closed -= data.timeframe.interval
    candles = await market_service.get_candles(
        session,
        data.instrument_id,
        data.timeframe,
        end=last_closed,
        limit=min(history_for(config), indicator_service.MAX_HISTORY),
    )
    if not candles:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "No closed candles for this market and timeframe"
        )
    df = indicator_service.frame(candles)
    side = 1 if data.side == "buy" else -1
    plan = plan_dict(df, side, config, account_size, entry=data.entry, stop=data.stop)
    if needs_placeholder:
        config = {**config, "stop": None}
    return {
        "instrument_id": data.instrument_id,
        "timeframe": data.timeframe,
        "bar_time": candles[-1].ts,
        "account_size": account_size,
        "quote_currency": profile.quote_currency,
        "config": config,
        "plan": plan,
    }


# --- plans of live signals -----------------------------------------------------------------------


async def list_plans(
    session: AsyncSession,
    user: User,
    *,
    limit: int,
    offset: int,
    instrument_id: uuid.UUID | None = None,
    timeframe: Timeframe | None = None,
    strategy_key: str | None = None,
    since: datetime | None = None,
) -> tuple[list[tuple[SignalPlan, Signal]], int]:
    filters = [SignalPlan.user_id == user.id]
    if instrument_id is not None:
        filters.append(Signal.instrument_id == instrument_id)
    if timeframe is not None:
        filters.append(Signal.timeframe == timeframe)
    if strategy_key:
        filters.append(Signal.strategy_key == strategy_key)
    if since is not None:
        filters.append(Signal.bar_time >= since)
    joined = select(SignalPlan, Signal).join(Signal, Signal.id == SignalPlan.signal_id)
    total = await session.scalar(
        select(func.count())
        .select_from(SignalPlan)
        .join(Signal, Signal.id == SignalPlan.signal_id)
        .where(and_(*filters))
    )
    rows = await session.execute(
        joined.where(and_(*filters))
        .order_by(Signal.bar_time.desc(), SignalPlan.created_at.desc(), SignalPlan.id)
        .limit(limit)
        .offset(offset)
    )
    return [(p, s) for p, s in rows.all()], total or 0


def config_key(config: dict[str, Any]) -> str:
    return json.dumps(config, sort_keys=True)
