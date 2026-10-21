"""Risk profiles, risk configs (validated by ``trading_backtest``), the position-size
calculator and the per-user trade plans of live signals.

- A profile is created on first read with the ``balanced`` template and 10,000 USDT.
- The rules of a plan come from the activation's ``risk_override`` if set, else the profile,
  else the default template (a user who never opened the profile).
- Instruments with contract specs are sized in the account currency (the profile's
  ``quote_currency``) and get ``lots`` (``lot_sizing``; docs/instruments.md).
"""

import json
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NamedTuple

import pandas as pd
import trading_backtest as tb
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contract import Account, RiskSettings
from app.core.config import get_settings
from app.models.candle import Timeframe
from app.models.instrument import Instrument
from app.models.risk import RiskProfile, SignalPlan
from app.models.strategy import Signal
from app.models.user import User
from app.schemas.risk import PositionSizeRequest, RiskProfileUpdate
from app.services import indicator_service, market_service, strategy_resolver

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_SIZE = 10_000.0
DEFAULT_CURRENCY = "USDT"
PLACEHOLDER_STOP = {"type": "percent", "value": 1.0}  # replaced by an explicit stop price
# Dollar stablecoins count as USD when no exact conversion exists (with a warning on the plan).
USD_ALIASES = frozenset({"USD", "USDT", "USDC"})


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
        "leverage": row.leverage,
        "config": row.config,
        "template": row.template,
        "updated_at": row.updated_at,
        "ai_risk": ai_risk_view(row),
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
        if data.account_size != row.account_size:
            row.balance_set_at = datetime.now(UTC)  # the drawdown guard starts again
        row.account_size = data.account_size
    if data.quote_currency is not None:
        row.quote_currency = data.quote_currency
    if data.leverage is not None:
        row.leverage = data.leverage
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


# --- AI setups (B10) --------------------------------------------------------------------------


class AIRiskInputs(NamedTuple):
    """What ai-service ``/v1/size`` gets for one user, where each value came from (``profile``:
    a column of the profile, ``config``: its risk config, ``default``: an AI_DEFAULT_* setting)
    and the warnings of the mapping."""

    account: Account
    risk: RiskSettings
    warnings: list[str]
    sources: dict[str, str]


def ai_risk_inputs(profile: RiskProfile) -> AIRiskInputs:
    """The five AI risk fields mapped onto the existing profile (no parallel model):

    - ``balance`` = ``account_size``, ``currency`` = ``quote_currency``, ``leverage``;
    - ``risk_per_trade_pct`` = ``config.sizing.risk_pct`` when ``sizing.mode`` is ``risk``,
      else ``AI_DEFAULT_RISK_PCT`` with a warning;
    - ``daily_loss_limit_pct`` = ``config.guards.max_daily_loss_pct``, else
      ``AI_DEFAULT_DAILY_LOSS_PCT``;
    - ``max_drawdown_pct`` = ``config.guards.max_drawdown_pct``, else
      ``AI_DEFAULT_MAX_DRAWDOWN_PCT``.

    Raises ``pydantic.ValidationError`` when the profile cannot be expressed in the contract
    (e.g. a one-letter currency)."""
    settings = get_settings()
    config = profile.config or {}
    sizing, guards = config.get("sizing") or {}, config.get("guards") or {}
    warnings: list[str] = []
    sources = {"balance": "profile", "currency": "profile", "leverage": "profile"}
    if sizing.get("mode") == "risk" and sizing.get("risk_pct"):
        risk_pct, sources["risk_per_trade_pct"] = float(sizing["risk_pct"]), "config"
    else:
        risk_pct, sources["risk_per_trade_pct"] = settings.ai_default_risk_pct, "default"
        warnings.append(f"sizing mode is not risk-based; used {risk_pct:g}%")
    daily = guards.get("max_daily_loss_pct")
    sources["daily_loss_limit_pct"] = "config" if daily else "default"
    drawdown = guards.get("max_drawdown_pct")
    sources["max_drawdown_pct"] = "config" if drawdown else "default"
    account = Account(
        balance=profile.account_size,
        currency=profile.quote_currency,
        leverage=profile.leverage if profile.leverage is not None else 100.0,
    )
    risk = RiskSettings(
        risk_per_trade_pct=risk_pct,
        daily_loss_limit_pct=float(daily) if daily else settings.ai_default_daily_loss_pct,
        max_drawdown_pct=float(drawdown) if drawdown else settings.ai_default_max_drawdown_pct,
    )
    return AIRiskInputs(account, risk, warnings, sources)


def ai_risk_problem(exc: ValidationError) -> str:
    """Why a profile cannot be sent to ai-service, e.g. ``currency: String should match ...``."""
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())[
        :200
    ]


def ai_risk_view(profile: RiskProfile) -> dict[str, Any]:
    """``ai_risk`` of GET /me/risk-profile (read-only)."""
    try:
        inputs = ai_risk_inputs(profile)
    except ValidationError as exc:  # the profile cannot be sent as it is
        return {"error": ai_risk_problem(exc)}
    return {
        **inputs.account.model_dump(),
        **inputs.risk.model_dump(),
        "sources": inputs.sources,
        "warnings": inputs.warnings,
    }


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


@dataclass(frozen=True)
class LotSizing:
    """How to size on an instrument with contract specs for one account currency: the spec,
    the conversion rate (account currency per quote unit; None = not found) and notes for
    the plan's ``sizing_warnings``. Without a spec, plans are computed as before."""

    spec: tb.ContractSpec | None = None
    rate: float | None = None
    notes: tuple[str, ...] = ()


def contract_spec(instrument: Instrument) -> tb.ContractSpec | None:
    if not instrument.has_specs:
        return None
    return tb.ContractSpec(
        contract_size=instrument.contract_size,
        lot_step=instrument.lot_step,
        quote_currency=instrument.pnl_currency,
        min_lot=instrument.min_lot,
        max_lot=instrument.max_lot,
    )


def _usd(currency: str) -> str:
    return "USD" if currency in USD_ALIASES else currency


def _names(currency: str) -> set[str]:
    return set(USD_ALIASES) if currency in USD_ALIASES else {currency}


async def _market_rate(
    session: AsyncSession, quote: set[str], account: set[str]
) -> tuple[float, str] | None:
    """Latest 1m close of an active QUOTE/ACCOUNT market (or 1 / that of ACCOUNT/QUOTE); the
    freshest candle wins when several sources list the pair."""
    rows = await session.scalars(
        select(Instrument).where(
            Instrument.is_active.is_(True),
            ((Instrument.base_asset.in_(quote)) & (Instrument.quote_asset.in_(account)))
            | ((Instrument.base_asset.in_(account)) & (Instrument.quote_asset.in_(quote))),
        )
    )
    best = None
    for market in rows.all():
        latest = await market_service.get_latest_candle(session, market.id, Timeframe.m1)
        if latest is None or not latest.close > 0:
            continue
        if best is None or latest.ts > best[0]:
            inverted = market.base_asset in account
            rate = 1 / latest.close if inverted else latest.close
            best = (latest.ts, rate, f"{market.source}:{market.symbol}")
    return None if best is None else (best[1], best[2])


async def conversion_rate(
    session: AsyncSession, instrument: Instrument, account_currency: str, entry: float
) -> tuple[float | None, list[str]]:
    """(account currency per unit of the instrument's quote currency, notes).

    Same currency: 1. Account currency = base (USD/JPY, USD account): 1 / entry. Otherwise the
    latest close of a matching market. USD, USDT and USDC count as one currency only when there
    is no exact match, and the notes say so. None when nothing matches: never assumed 1."""
    quote, base, account = instrument.pnl_currency, instrument.base_asset, account_currency
    rate = tb.direct_rate(base, quote, account, entry)
    if rate is not None:
        return rate, []
    found = await _market_rate(session, {quote}, {account})
    if found is not None:
        return found[0], []
    if not USD_ALIASES & {quote, base, account}:
        return None, []
    note = "USD, USDT and USDC treated as the same dollar (1:1)"
    rate = tb.direct_rate(_usd(base), _usd(quote), _usd(account), entry)
    if rate is not None:
        return rate, [note]
    found = await _market_rate(session, _names(quote), _names(account))
    if found is not None:
        return found[0], [f"{note}; converted with {found[1]}"]
    return None, []


async def lot_sizing(
    session: AsyncSession, instrument: Instrument, account_currency: str, entry: float
) -> LotSizing:
    spec = contract_spec(instrument)
    if spec is None:
        return LotSizing()
    rate, notes = await conversion_rate(session, instrument, account_currency, entry)
    return LotSizing(spec, rate, tuple(notes))


def plan_dict(
    df: pd.DataFrame,
    side: int,
    config: dict[str, Any],
    account_size: float,
    sizing: LotSizing | None = None,
    **kw: Any,
) -> dict[str, Any]:
    if sizing is not None and sizing.spec is not None:
        kw.update(spec=sizing.spec, conversion_rate=sizing.rate)
    plan = tb.plan_trade(df, len(df) - 1, side, config, account_size, **kw).to_dict()
    if sizing is not None and sizing.notes:
        plan["sizing_warnings"] = [*sizing.notes, *plan["sizing_warnings"]]
    return plan


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
    instrument = await market_service.get_instrument_or_404(session, data.instrument_id)
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
    sizing = await lot_sizing(
        session, instrument, profile.quote_currency, data.entry or candles[-1].close
    )
    plan = plan_dict(df, side, config, account_size, sizing, entry=data.entry, stop=data.stop)
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
    # your own plans, of signals you may still see (a strategy made private hides them)
    filters = [
        SignalPlan.user_id == user.id,
        strategy_resolver.visible_signal(Signal.strategy_key, user),
    ]
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
