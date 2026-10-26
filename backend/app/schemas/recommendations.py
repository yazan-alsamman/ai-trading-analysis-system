import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TrackRecord(BaseModel):
    """Y16 outcomes of the same strategy key (or AI profile) on the same instrument and
    timeframe, over every user's predictions."""

    resolved: int = Field(description="tp_hit + sl_hit + expired (data-gap rows left out)")
    decided: int = Field(description="tp_hit + sl_hit: the hit rate's n")
    hit_rate: float | None = Field(description="tp_hit / decided; null when none")
    hit_rate_lower: float | None = Field(
        description="Wilson 95% lower bound of hit_rate; null when none"
    )
    mean_return_pct: float | None = Field(description="strategy signals")
    mean_realized_r: float | None = Field(description="AI setups")


class RecommendationRead(BaseModel):
    id: str = Field(description="the Y16 prediction id: GET /predictions/{id}")
    source: Literal["ai", "strategy"]
    instrument_id: uuid.UUID
    symbol: str
    timeframe: str
    strategy_key: str = Field(description="the strategy key; AI setups: the profile")
    direction: Literal["buy", "sell"]
    generated_at: datetime
    age_bars: int = Field(description="closed bars of its timeframe since it was published")
    user_strategy_id: uuid.UUID | None = Field(description="your activation (strategy signals)")
    plan: dict[str, Any] | None = Field(
        description="your stored plan: the signal's trade plan, or the AI setup's stored size "
        "(lots, risk_amount, currency, margin_required, feasible, warnings, source)"
    )
    plan_missing_reason: Literal["no_plan_stored", "not_sized_yet"] | None
    track_record: TrackRecord
    score: float = Field(
        description="0..1, advisory ranking only (docs/recommendations.md): never a promise"
    )
    score_reasons: list[str]


class BacktestBrief(BaseModel):
    id: uuid.UUID
    total_return_pct: float | None
    win_rate_pct: float | None
    max_drawdown_pct: float | None
    finished_at: datetime | None


class StrategyRecommendation(BaseModel):
    rank: int
    strategy_key: str
    name: str
    kind: Literal["builtin", "custom"]
    resolved: int
    decided: int
    hit_rate: float | None
    hit_rate_lower: float | None = Field(description="the rank key (Wilson 95% lower bound)")
    mean_return_pct: float | None
    insufficient_history: bool = Field(
        description="fewer than RECOMMENDATION_MIN_SAMPLES decided predictions: ranked last"
    )
    already_active: bool = Field(description="you run it on this instrument and timeframe")
    backtest: BacktestBrief | None = Field(
        description="your latest completed backtest here (information only, not ranked)"
    )
