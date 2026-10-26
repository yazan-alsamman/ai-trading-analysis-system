import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Outcome = Literal["tp_hit", "sl_hit", "expired", "open"]
Source = Literal["ai", "strategy"]


class PredictionRead(BaseModel):
    id: str = Field(description="``ai:<setup_id>`` or ``sig:<signal uuid>``")
    source: Source
    instrument_id: uuid.UUID
    symbol: str
    timeframe: str = Field(description="the signal's timeframe; AI setups: 15m (the decision bar)")
    strategy_key: str = Field(description="the strategy key; AI setups: their profile")
    direction: Literal["buy", "sell"]
    probability: float | None = Field(
        description="0..1, AI setups only (null in v1: no model). Strategy signals: null, "
        "their strength is not a probability"
    )
    risk_reward: float | None = Field(description="AI setups: r_multiple; signals: null")
    generated_at: datetime = Field(
        description="AI: when it was first published (ARMED); signals: when it was stored"
    )
    resolved_at: datetime | None
    outcome: Outcome
    realized_r: float | None = Field(description="AI setups only")
    return_pct: float | None = Field(
        description="signals only: the move over the horizon in %, signed in the signal's direction"
    )
    model_version: str | None
    taken_by_user: bool = Field(description="you marked this AI setup taken")
    note: str | None = Field(
        description="signals resolved over a data gap: why there is no result (outcome expired, "
        "left out of the stats)"
    )


class PredictionEvent(BaseModel):
    from_state: str | None
    to_state: str
    at: datetime
    reason: str | None
    realized_r: float | None


class AIPredictionDetail(BaseModel):
    setup_id: str
    state: str
    entry: float | None
    sl: float | None
    tp: float | None
    grade: str | None
    ev_r: float | None
    valid_until: datetime | None
    events: list[PredictionEvent] = Field(description="state events, oldest first")


class SignalOutcomeRead(BaseModel):
    horizon_bars: int
    exit_ts: datetime | None
    exit_price: float | None
    return_pct: float | None
    mfe_pct: float | None = Field(description="best move in the signal's direction, in %")
    mae_pct: float | None = Field(description="worst move (negative: against the signal), in %")
    correct: bool | None = Field(description="null: a data gap in the horizon")
    cost_per_unit: float = Field(description="the instrument's fixed cost used (0: none)")
    note: str | None
    resolved_at: datetime


class SignalPredictionDetail(BaseModel):
    signal_id: uuid.UUID
    bar_time: datetime
    price: float = Field(description="the entry the outcome is measured from")
    strength: float = Field(description="0..1 signal strength (not a probability)")
    reason: str
    outcome: SignalOutcomeRead | None = Field(description="null while open")


class PredictionDetail(PredictionRead):
    ai: AIPredictionDetail | None = None
    signal: SignalPredictionDetail | None = None


class PredictionPage(BaseModel):
    items: list[PredictionRead]
    total: int


class CalibrationBin(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: float = Field(alias="from", description="inclusive")
    to: float = Field(description="exclusive (1.0 inclusive in the last bin)")
    count: int
    mean_predicted: float
    observed_rate: float = Field(description="share of tp_hit in the bin")


class StrategyStats(BaseModel):
    source: Source
    strategy_key: str
    total: int
    resolved: int
    hit_rate: float | None


class PredictionStats(BaseModel):
    total: int = Field(description="open + resolved (rows with a data gap are left out)")
    resolved: int = Field(description="tp_hit + sl_hit + expired")
    open: int
    hit_rate: float | None = Field(description="tp_hit / (tp_hit + sl_hit); null when none")
    tp_hit_count: int
    sl_hit_count: int
    expired_count: int
    excluded_count: int = Field(description="signals resolved over a data gap (not counted)")
    mean_realized_r: float | None = Field(description="AI setups, tp_hit and sl_hit")
    mean_return_pct: float | None = Field(description="strategy signals, tp_hit and sl_hit")
    with_probability: int = Field(description="decided rows that have a probability")
    mean_predicted: float | None
    brier_score: float | None = Field(description="null without probabilities (v1)")
    calibration: list[CalibrationBin] = Field(description="non-empty 0.1 bins; [] in v1")
    by_strategy: list[StrategyStats]


class ResolverStatus(BaseModel):
    horizon_bars: int = Field(description="PREDICTION_HORIZON_BARS now")
    batch: int = Field(description="PREDICTION_RESOLVE_BATCH now")
    interval_seconds: int
    last_run_at: datetime | None
    last_status: Literal["ok", "error"] | None
    last_resolved: int | None
    last_gaps: int | None
    last_waiting: int | None
    last_duration_ms: int | None
    last_error: str | None
    last_error_at: datetime | None
    backlog: int = Field(description="signals without an outcome yet (due or not)")
    resolved_total: int
