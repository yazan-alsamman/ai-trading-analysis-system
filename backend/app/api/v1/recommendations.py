"""Recommendations (Y17, docs/recommendations.md): advisory, read-only rankings. What to look
at now from your own activations and follows, and which strategies have worked on a market."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep, StrategiesReader
from app.core.redis import get_redis
from app.models.candle import Timeframe
from app.schemas.recommendations import RecommendationRead, StrategyRecommendation
from app.services import market_service, recommendation_service

router = APIRouter(tags=["recommendations"])


@router.get("/me/recommendations", response_model=list[RecommendationRead])
async def my_recommendations(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
):
    """What is actionable now, best score first (then newest): the open buy/sell signals of your
    **active** activations, at most ``RECOMMENDATION_MAX_AGE_BARS`` bars old, and the ARMED or
    ACTIVE AI setups of the instruments and profiles you follow. Each item carries your stored
    plan (or why there is none), the track record of its strategy (or AI profile) on that
    market, and an advisory ``score`` with its reasons. Never a guarantee."""
    return await recommendation_service.for_user(session, get_redis(), user, limit)


@router.get("/recommendations/strategies", response_model=list[StrategyRecommendation])
async def recommended_strategies(
    principal: StrategiesReader,
    session: SessionDep,
    instrument_id: uuid.UUID,
    timeframe: Timeframe,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
):
    """Which strategy has worked on this market: every strategy you may use (built-in, your
    own and public custom ones), ranked by the Wilson 95% lower bound of its Y16 hit rate here.
    Too little history (``RECOMMENDATION_MIN_SAMPLES``): ranked last. ``already_active`` and
    your latest completed backtest here are attached. 404 unknown instrument."""
    await market_service.get_instrument_or_404(session, instrument_id)
    return await recommendation_service.strategies(
        session, get_redis(), principal.user, instrument_id, timeframe, limit
    )
