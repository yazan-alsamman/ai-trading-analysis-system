"""Sizing AI setups for users (B10, docs/risk-management.md#ai-setups).

For one setup (ARMED or ACTIVE) and one user:

1. the inputs: the setup as last returned (``last_payload``), the instrument's B4 specs and
   the user's risk (``risk_service.ai_risk_inputs``);
2. the backend's guards, before any call: the daily loss and the drawdown of the user's
   closed taken trades. A guard that is reached gives ``feasible = false``, 0 lots, and no
   call;
3. ai-service ``/v1/size`` (``AI_SIZE_MODE``: ``auto`` falls back to the local B4 lot sizing
   when ai-service is unavailable or has no ``/v1/size`` yet, ``remote`` never falls back,
   ``local`` never calls). A contract error (another 4xx, a bad body) is not hidden by a
   fallback: it raises ``SizeContractError``;
4. the result is stored in ``ai_setup_sizes`` with the inputs it depends on; the same inputs
   later reuse it without a call.

``size_setup_for_users`` does the same for many users (one profile query, ai-service calls
with ``AI_SIZE_CONCURRENCY`` at most at once; one user's failure does not stop the others).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import trading_backtest as tb
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIContractError, AIServiceClient, AIUnavailableError
from app.ai.contract import PRICED_STATES, Setup, SizeRequest, SizeResponse
from app.ai.specs import MissingSpecs, instrument_spec, spec_hash
from app.core.config import get_settings
from app.models.ai import AISetup, AISetupSize, AISetupTake
from app.models.instrument import Instrument
from app.models.risk import RiskProfile
from app.models.user import User
from app.services import risk_service

logger = logging.getLogger(__name__)

DAILY_LOSS = "daily_loss_limit_reached"
DRAWDOWN = "max_drawdown_reached"
EPSILON = 1e-9
PRICED = frozenset(s.value for s in PRICED_STATES)


class SizingError(Exception):
    """Why a setup cannot be sized; ``status`` is the API answer."""

    status = 500


class NotPriced(SizingError):
    status = 409


class NoSpecs(SizingError):
    status = 409


class SizeUnavailable(SizingError):
    status = 503


class SizeContractError(SizingError):
    status = 502


class ProfileError(SizingError):
    """The user's profile cannot be expressed in the contract (e.g. its currency)."""

    status = 422


@dataclass
class SizeResult:
    setup_id: str
    user_id: uuid.UUID
    lots: float
    risk_amount: float  # in the account currency
    margin_required: float | None
    feasible: bool
    warnings: list[str]
    source: str  # ai-service | local
    computed_at: datetime
    inputs: dict[str, Any]
    cached: bool = False

    @classmethod
    def from_row(cls, row: AISetupSize, *, cached: bool) -> SizeResult:
        return cls(
            setup_id=row.setup_id,
            user_id=row.user_id,
            lots=row.lots,
            risk_amount=row.risk_usd,
            margin_required=row.margin_required,
            feasible=row.feasible,
            warnings=list(row.warnings or []),
            source=row.source,
            computed_at=row.computed_at,
            inputs=row.inputs,
            cached=cached,
        )


@dataclass
class _Job:
    user_id: uuid.UUID
    risk: risk_service.AIRiskInputs
    key: dict[str, Any]
    guards: list[str]
    stored: AISetupSize | None
    response: SizeResponse | None = None
    error: Exception | None = None
    notes: list[str] = field(default_factory=list)


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _num(value: float | None, digits: int = 8) -> float | None:
    return None if value is None or not math.isfinite(value) else round(float(value), digits)


# --- guards ------------------------------------------------------------------------------------


async def guards(
    session: AsyncSession,
    user_id: uuid.UUID,
    profile: RiskProfile,
    risk: risk_service.AIRiskInputs,
    now: datetime,
) -> list[str]:
    """The guards that block a new trade, with a sentence each (empty: none).

    - Daily loss: the sum of ``pnl`` of the user's takes closed since 00:00 UTC today; a loss
      of at least ``daily_loss_limit_pct`` of the balance blocks.
    - Drawdown: the running sum of ``pnl`` of the takes closed since the balance was last set
      (``balance_set_at``; null: all); its fall from the highest point (0 at the start) to now,
      as a % of the balance, blocks at ``max_drawdown_pct``.
    """
    balance = risk.account.balance
    currency = risk.account.currency
    found: list[str] = []
    day_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today = await session.scalar(
        select(func.coalesce(func.sum(AISetupTake.pnl), 0.0)).where(
            AISetupTake.user_id == user_id,
            AISetupTake.closed_at >= day_start,
            AISetupTake.pnl.is_not(None),
        )
    )
    loss = max(0.0, -float(today))
    limit = balance * risk.risk.daily_loss_limit_pct / 100
    if loss > 0 and loss >= limit - EPSILON:
        found += [
            DAILY_LOSS,
            f"lost {loss:.2f} {currency} today ({loss / balance * 100:.2f}% of the balance), "
            f"the limit is {risk.risk.daily_loss_limit_pct:g}%",
        ]
    query = select(AISetupTake.pnl).where(
        AISetupTake.user_id == user_id,
        AISetupTake.closed_at.is_not(None),
        AISetupTake.pnl.is_not(None),
    )
    if profile.balance_set_at is not None:
        query = query.where(AISetupTake.closed_at >= profile.balance_set_at)
    running = peak = 0.0
    for pnl in await session.scalars(query.order_by(AISetupTake.closed_at)):
        running += pnl
        peak = max(peak, running)
    drawdown = peak - running
    if drawdown > 0 and drawdown >= balance * risk.risk.max_drawdown_pct / 100 - EPSILON:
        found += [
            DRAWDOWN,
            f"down {drawdown:.2f} {currency} from the best point "
            f"({drawdown / balance * 100:.2f}% of the balance), "
            f"the limit is {risk.risk.max_drawdown_pct:g}%",
        ]
    return found


# --- local sizing (B4) ---------------------------------------------------------------------------


async def local_size(
    session: AsyncSession, instrument: Instrument, setup: Setup, risk: risk_service.AIRiskInputs
) -> tuple[float, float, float | None, bool, list[str]]:
    """(lots, risk amount, margin, feasible, warnings) with the platform's B4 lot sizing:
    risk amount = balance x risk %, lots rounded down to ``lot_step`` and limited to
    ``min_lot``/``max_lot``, margin = entry x contract size x lots / leverage converted to the
    account currency (null without a conversion rate)."""
    account = risk.account
    spec = risk_service.contract_spec(instrument)
    if spec is None:
        raise NoSpecs(f"{instrument.source}:{instrument.symbol} has no contract specs")
    rate, notes = await risk_service.conversion_rate(
        session, instrument, account.currency, setup.entry
    )
    amount = account.balance * risk.risk.risk_per_trade_pct / 100
    sized = tb.lots_for_risk(amount, setup.entry, setup.sl, spec, account.currency, rate)
    warnings = [*notes, *sized.warnings]
    margin = None
    if sized.conversion_rate is not None:
        notional = setup.entry * spec.contract_size * sized.lots * sized.conversion_rate
        margin = notional / account.leverage
    else:
        warnings.append(
            f"no conversion rate from {spec.quote_currency} to {account.currency}: "
            "the margin is unknown"
        )
    return (
        _num(sized.lots),
        _num(sized.risk_amount or 0.0, 4),
        _num(margin, 4),
        sized.feasible,
        warnings,
    )


# --- sizing ------------------------------------------------------------------------------------


async def _prepare(
    session: AsyncSession,
    setup_row: AISetup,
    profile: RiskProfile,
    spec_digest: str,
    now: datetime,
) -> _Job:
    try:
        risk = risk_service.ai_risk_inputs(profile)
    except ValidationError as exc:
        raise ProfileError(
            f"the risk profile cannot be used: {risk_service.ai_risk_problem(exc)}"
        ) from None
    blocked = await guards(session, profile.user_id, profile, risk, now)
    key = {
        "account": risk.account.model_dump(),
        "risk": risk.risk.model_dump(),
        "spec_hash": spec_digest,
        "setup_hash": _hash(setup_row.last_payload),
        "guards": [g for g in blocked if g in (DAILY_LOSS, DRAWDOWN)],
        "mode": get_settings().ai_size_mode,
    }
    stored = await session.get(AISetupSize, (setup_row.setup_id, profile.user_id))
    return _Job(profile.user_id, risk, key, blocked, stored)


async def _call(
    client: AIServiceClient, semaphore: asyncio.Semaphore, request: SizeRequest, job: _Job
) -> None:
    async with semaphore:
        try:
            job.response = await client.size(request)
        except Exception as exc:  # noqa: BLE001 - decided per job in _finish
            job.error = exc


async def _finish(
    session: AsyncSession,
    setup_row: AISetup,
    instrument: Instrument,
    setup: Setup,
    job: _Job,
    now: datetime,
) -> SizeResult:
    mode = get_settings().ai_size_mode
    warnings = list(job.risk.warnings)
    if job.guards:
        lots, amount, margin, feasible, source = 0.0, 0.0, None, False, "local"
        warnings += job.guards
    elif job.response is not None:
        r = job.response
        lots, amount, margin, feasible = r.lots, r.risk_usd, r.margin_required, r.feasible
        warnings += r.warnings
        source = "ai-service"
    else:
        error = job.error
        if isinstance(error, AIContractError) and error.status != 404:
            logger.error(
                "ai-service /v1/size contract error for setup %s: %s (%s)",
                setup_row.setup_id,
                error,
                error.detail,
            )
            raise SizeContractError(f"ai-service answered outside the contract: {error}")
        if error is not None and mode == "remote":
            raise SizeUnavailable(f"ai-service /v1/size is unavailable: {error}")
        if error is not None and not isinstance(error, AIContractError | AIUnavailableError):
            raise error
        if isinstance(error, AIContractError):
            warnings.append("ai-service has no /v1/size yet (404); sized by the backend")
        elif error is not None:
            warnings.append("ai-service is unavailable; sized by the backend")
        lots, amount, margin, feasible, local_warnings = await local_size(
            session, instrument, setup, job.risk
        )
        warnings += local_warnings
        source = "local"
    values = {
        "lots": lots,
        "risk_usd": amount,
        "margin_required": margin,
        "feasible": feasible,
        "warnings": warnings,
        "inputs": job.key,
        "source": source,
        "computed_at": now,
    }
    await session.execute(
        insert(AISetupSize)
        .values(setup_id=setup_row.setup_id, user_id=job.user_id, created_at=now, **values)
        .on_conflict_do_update(index_elements=["setup_id", "user_id"], set_=values)
    )
    return SizeResult(
        setup_id=setup_row.setup_id,
        user_id=job.user_id,
        lots=lots,
        risk_amount=amount,
        margin_required=margin,
        feasible=feasible,
        warnings=warnings,
        source=source,
        computed_at=now,
        inputs=job.key,
    )


async def _size(
    session: AsyncSession,
    setup_row: AISetup,
    profiles: dict[uuid.UUID, RiskProfile],
    *,
    client: AIServiceClient | None,
    now: datetime | None,
) -> dict[uuid.UUID, SizeResult | SizingError]:
    now = now or datetime.now(UTC)
    if setup_row.state not in PRICED:
        raise NotPriced(f"a {setup_row.state} setup has no prices to size")
    instrument = await session.get(Instrument, setup_row.instrument_id)
    try:
        spec = instrument_spec(instrument)
    except MissingSpecs as exc:
        raise NoSpecs(str(exc)) from None
    setup = Setup.model_validate(setup_row.last_payload)
    digest = spec_hash(spec)
    out: dict[uuid.UUID, SizeResult | SizingError] = {}
    jobs: list[_Job] = []
    for user_id, profile in profiles.items():
        try:
            job = await _prepare(session, setup_row, profile, digest, now)
        except SizingError as exc:
            out[user_id] = exc
            continue
        if job.stored is not None and job.stored.inputs == job.key:
            out[user_id] = SizeResult.from_row(job.stored, cached=True)
            continue
        jobs.append(job)

    calls = []
    if get_settings().ai_size_mode != "local":
        for job in [j for j in jobs if not j.guards]:
            try:
                request = SizeRequest(
                    setup=setup, instrument_spec=spec, account=job.risk.account, risk=job.risk.risk
                )
            except ValueError as exc:
                job.error = ProfileError(str(exc).splitlines()[0][:200])
                continue
            calls.append((request, job))
    if calls:
        own = client is None
        client = client or AIServiceClient()
        semaphore = asyncio.Semaphore(max(1, get_settings().ai_size_concurrency))
        try:
            await asyncio.gather(*(_call(client, semaphore, r, j) for r, j in calls))
        finally:
            if own:
                await client.aclose()
    for job in jobs:
        try:
            if isinstance(job.error, SizingError):
                raise job.error
            out[job.user_id] = await _finish(session, setup_row, instrument, setup, job, now)
        except SizingError as exc:
            out[job.user_id] = exc
        except Exception as exc:  # noqa: BLE001 - one user's failure must not stop the others
            logger.exception("sizing setup %s for %s failed", setup_row.setup_id, job.user_id)
            out[job.user_id] = SizingError(f"sizing failed: {type(exc).__name__}")
    await session.commit()
    return out


async def size_setup_for_user(
    session: AsyncSession,
    setup_row: AISetup,
    user: User,
    *,
    client: AIServiceClient | None = None,
    now: datetime | None = None,
) -> SizeResult:
    """Size ``setup_row`` for ``user`` (stored; reused while the inputs are the same). Raises a
    ``SizingError`` (its ``status`` is the API answer)."""
    profile = await risk_service.get_or_create(session, user)
    result = (await _size(session, setup_row, {user.id: profile}, client=client, now=now))[user.id]
    if isinstance(result, SizingError):
        raise result
    return result


async def size_setup_for_users(
    session: AsyncSession,
    setup_row: AISetup,
    user_ids: Sequence[uuid.UUID],
    *,
    client: AIServiceClient | None = None,
    now: datetime | None = None,
) -> dict[uuid.UUID, SizeResult | SizingError]:
    """The batch form (B9/B11, when a setup becomes ARMED): the profiles in one query (users
    without one get the default profile), at most ``AI_SIZE_CONCURRENCY`` ai-service calls at
    once, one result or error per user."""
    profiles = await risk_service.profiles_for(session, user_ids)
    missing = [u for u in user_ids if u not in profiles]
    if missing:
        users = await session.scalars(select(User).where(User.id.in_(missing)))
        for user in users:
            profiles[user.id] = await risk_service.get_or_create(session, user)
    ordered = {u: profiles[u] for u in user_ids if u in profiles}
    return await _size(session, setup_row, ordered, client=client, now=now)
