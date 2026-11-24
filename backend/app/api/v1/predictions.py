"""Prediction history and accuracy (Y16, docs/predictions.md): AI setups and strategy signals
with their outcomes, and aggregate stats. Every row passes B12 visibility: private strategies'
signals only for users who may use them, AI setups only for users who may read them."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select

from app.api.deps import AdminUser, SessionDep, SignalsReader
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.prediction import SignalOutcome
from app.schemas.predictions import (
    Outcome,
    PredictionDetail,
    PredictionPage,
    PredictionStats,
    ResolverStatus,
    Source,
)
from app.services import prediction_resolver, prediction_service
from app.services.prediction_service import Filters

router = APIRouter(prefix="/predictions", tags=["predictions"])
admin_router = APIRouter(prefix="/admin/predictions", tags=["admin"])


def filters(
    source: Source | None = None,
    instrument_id: uuid.UUID | None = None,
    timeframe: Annotated[str | None, Query(max_length=8)] = None,
    strategy_key: Annotated[
        str | None, Query(max_length=64, description="a strategy key, or an AI profile")
    ] = None,
    profile: Annotated[str | None, Query(max_length=32, description="AI setups only")] = None,
    outcome: Outcome | None = None,
    from_: Annotated[
        datetime | None, Query(alias="from", description="generated_at >= from")
    ] = None,
    to: Annotated[datetime | None, Query(description="generated_at <= to")] = None,
) -> Filters:
    return Filters(source, instrument_id, timeframe, strategy_key, profile, outcome, from_, to)


FiltersDep = Annotated[Filters, Depends(filters)]


@router.get("", response_model=PredictionPage)
async def list_predictions(
    principal: SignalsReader,
    session: SessionDep,
    f: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Every published prediction you may read with its outcome, newest first: AI setups that
    reached ARMED (``source=ai``) and buy/sell strategy signals (``source=strategy``).
    ``outcome``: ``open``, ``tp_hit``, ``sl_hit`` or ``expired`` (rules in
    docs/predictions.md)."""
    items, total = await prediction_service.list_predictions(
        session, principal.user, f, limit, offset
    )
    return {"items": items, "total": total}


@router.get("/stats", response_model=PredictionStats)
async def prediction_stats(principal: SignalsReader, session: SessionDep, f: FiltersDep):
    """Accuracy over the same rows as the list (same filters): counts, ``hit_rate`` =
    tp_hit / (tp_hit + sl_hit) (expired and data-gap rows are not in it), mean realized R (AI)
    and mean return % (signals), and, over rows that have a probability, the Brier score and a
    0.1-bin calibration. v1 has no probabilities: ``brier_score`` null, ``calibration`` []."""
    return await prediction_service.stats(session, principal.user, f)


@router.get("/{prediction_id}", response_model=PredictionDetail)
async def get_prediction(
    prediction_id: Annotated[str, Path(max_length=140)],
    principal: SignalsReader,
    session: SessionDep,
):
    """One prediction (``ai:<setup_id>`` or ``sig:<uuid>``) with its details: the AI setup's
    prices and state events, or the signal with its outcome row (MFE/MAE). 404 when unknown or
    not yours to read."""
    return await prediction_service.get_prediction(session, principal.user, prediction_id)


@admin_router.get("/resolver", response_model=ResolverStatus)
async def resolver_status(_: AdminUser, session: SessionDep):
    """The ``predictions.resolve_signals`` task: its last run (resolved, gaps, signals waiting
    for the market to reopen, duration, error) and the backlog of signals without an outcome."""
    settings = get_settings()
    state = await prediction_resolver.read_status(get_redis())
    return {
        "horizon_bars": settings.prediction_horizon_bars,
        "batch": settings.prediction_resolve_batch,
        "interval_seconds": settings.prediction_resolve_interval_seconds,
        "last_run_at": state.get("last_run_at"),
        "last_status": state.get("last_status"),
        "last_resolved": state.get("last_resolved"),
        "last_gaps": state.get("last_gaps"),
        "last_waiting": state.get("last_waiting"),
        "last_duration_ms": state.get("last_duration_ms"),
        "last_error": state.get("last_error"),
        "last_error_at": state.get("last_error_at"),
        "backlog": await prediction_resolver.backlog(session),
        "resolved_total": await session.scalar(select(func.count()).select_from(SignalOutcome)),
    }
