import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.ai import labels
from app.ai.contract import SetupState
from app.core.config import get_settings
from app.schemas.predictions import ExitLabel

EXIT_TYPE_DOC = "null: target (a tp); trailing / time: no tp and no r_multiple (gold_levels)"
EXIT_LABEL_DOC = (
    "ready to show for a setup without a target, Arabic and English, e.g. 'Exit: trailing "
    "stop, or 16:45 New York'; null when the setup has a target"
)


class _Exit(BaseModel):
    """Contract 0.3.0: how a setup exits."""

    exit_type: Literal["target", "trailing", "time"] | None = Field(
        default=None, description=EXIT_TYPE_DOC
    )
    exit_reason: str | None = Field(
        default=None, description="why it exited (e.g. trailing_stop, time, stop, tp_hit)"
    )

    @computed_field(description=EXIT_LABEL_DOC)
    @property
    def exit_label(self) -> ExitLabel | None:
        label = labels.exit_label(self.exit_type)
        return ExitLabel(**label) if label else None


class AISetupRead(_Exit):
    model_config = ConfigDict(from_attributes=True)

    setup_id: str
    instrument_id: uuid.UUID
    profile: str
    direction: str
    state: SetupState
    entry: float | None
    sl: float | None
    tp: float | None
    r_multiple: float | None
    probability: float | None
    ev_r: float | None
    ev_r_lower: float | None
    grade: str | None
    valid_until: datetime | None
    horizon_until: datetime | None
    realized_r: float | None
    strategy_version: str | None
    model_version: str | None
    features_version: str | None
    first_request_id: str
    last_request_id: str
    created_at: datetime
    updated_at: datetime


class AISetupEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_state: SetupState | None = Field(description="null: the setup appeared")
    to_state: SetupState
    at: datetime
    reason: str | None
    realized_r: float | None
    sl: float | None = Field(
        default=None, description="a stop move (reason sl_moved, same state): the new stop"
    )
    request_id: str
    created_at: datetime


class AISetupSizeBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    lots: float
    feasible: bool
    source: str
    computed_at: datetime


class OutboxRead(BaseModel):
    """An alert to send (B11): one per setup state change, DEVELOPING excepted."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    setup_id: str
    from_state: SetupState | None
    to_state: SetupState
    at: datetime
    reason: str | None
    realized_r: float | None
    sl: float | None = Field(default=None, description="a stop move (sl_moved): the new stop")
    created_at: datetime
    status: Literal["pending", "done", "skipped", "failed"]
    attempts: int
    next_attempt_at: datetime
    last_error: str | None = Field(description="the last failure, or why it was skipped")
    processed_at: datetime | None


class SlMoveRead(BaseModel):
    at: datetime
    sl: float = Field(description="the new stop")


class AISetupDetail(AISetupRead):
    evidence: dict[str, Any]
    features: dict[str, Any]
    last_payload: dict[str, Any] = Field(description="the setup exactly as last returned")
    events: list[AISetupEventRead] = Field(description="oldest first")
    sl_history: list[SlMoveRead] = Field(
        default_factory=list, description="the stop moves (sl_moved), oldest first"
    )
    sizes: list[AISetupSizeBrief] = Field(description="the stored per-user sizes (B10)")
    takes_count: int = Field(description="users who said they took it")
    outbox: list[OutboxRead] = Field(description="its alerts (B11), oldest first")


# --- users (B10) ---------------------------------------------------------------------------------


class FollowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_grade: Literal["A", "B", "C", "D"] | None = Field(
        default=None,
        description="only setups of this grade or better (A best); null: all. Stored always, "
        "applied only while grades are enabled (see min_grade_active)",
    )


class FollowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: uuid.UUID
    profile: str
    min_grade: str | None
    created_at: datetime

    @computed_field(
        description="whether min_grade filters the alerts now (AI_GRADES_ENABLED). False in v1: "
        "ai-service returns no grades, every follower gets every ARMED alert and min_grade is "
        "kept for when grades are enabled"
    )
    @property
    def min_grade_active(self) -> bool:
        return get_settings().ai_grades_enabled


class TakeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lots: float | None = Field(
        default=None, gt=0, le=1e6, allow_inf_nan=False, description="default: your stored size"
    )
    entry_price: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class TakeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    setup_id: str
    taken_at: datetime
    lots: float | None
    risk_amount: float | None = Field(description="account currency, at the setup's stop")
    entry_price: float | None
    closed_at: datetime | None
    realized_r: float | None
    pnl: float | None = Field(description="realized_r x risk_amount")
    close_reason: str | None


class AITradeRead(TakeRead, _Exit):
    instrument_id: uuid.UUID
    profile: str
    direction: str
    state: SetupState = Field(description="the setup's state now")
    entry: float | None
    sl: float | None
    tp: float | None


class AISizeInputs(BaseModel):
    balance: float
    currency: str
    leverage: float
    risk_per_trade_pct: float
    daily_loss_limit_pct: float
    max_drawdown_pct: float
    sources: dict[str, str] = Field(description="per field: profile, config or default")


class AISizeRead(BaseModel):
    setup_id: str
    lots: float
    risk_amount: float = Field(description="money at risk at the stop, in the account currency")
    margin_required: float | None = Field(description="account currency; null: no rate")
    feasible: bool
    warnings: list[str]
    source: str = Field(
        description="remote (ai-service /v1/size) or local (the backend's B4 lot sizing; "
        "a local size always has a warning saying so)"
    )
    computed_at: datetime
    inputs: AISizeInputs
    taken: bool = Field(description="you said you took this setup")


class AIExplanationRead(BaseModel):
    setup_id: str
    lang: Literal["ar", "en"]
    explanation: str | None = Field(
        description="null unless verified or the fixed template (no unverified number is shown)"
    )
    explanation_status: Literal["verified", "template", "unavailable"] = Field(
        description="unavailable: show 'الشرح غير متاح' / 'Explanation unavailable'"
    )


class AIModelIn(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    training_from: datetime | None = None
    training_to: datetime | None = None
    data_hash: str | None = Field(default=None, max_length=128)
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)


class AIModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    model_id: str
    created_at: datetime
    training_from: datetime | None
    training_to: datetime | None
    data_hash: str | None
    metrics: dict[str, Any]
    is_active: bool
    notes: str | None


# --- the daily volatility (B13, contract 0.3.0) --------------------------------------------------


class LevelLabel(BaseModel):
    ar: str
    en: str


class Quantiles(BaseModel):
    p20: float | None = None
    p50: float | None = None
    p80: float | None = None


class VolatilityRead(BaseModel):
    """The expected move of one New York trading day (02:00 to 16:45 America/New_York): the
    first ``ok`` answer of ai-service that day, fixed for the whole day."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    instrument_id: uuid.UUID
    day: date = Field(description="the New York trading day")
    status: str = Field(description="ok (another value only as ai-service sent it)")
    model: str | None
    window: str = Field(default="02:00-16:45 America/New_York")
    expected_move_pct: float | None
    range_pct: Quantiles | None = Field(description="p20 / p50 / p80 of the day's range, %")
    range_usd: Quantiles | None = Field(description="p20 / p50 / p80 of the day's range, USD")
    level: str | None = Field(description="quiet, normal, lively, very_lively (as received)")
    news: list[dict[str, Any]] = Field(description="[{ts, title, top3}] as received")
    request_id: str
    created_at: datetime

    @computed_field(description="Arabic and English label of level; null when unknown")
    @property
    def level_label(self) -> LevelLabel | None:
        label = labels.level_label(self.level)
        return LevelLabel(**label) if label else None


class VolatilityToday(BaseModel):
    """Today's card: the stored day, or ``status: pending`` with why."""

    model_config = ConfigDict(protected_namespaces=())

    instrument_id: uuid.UUID
    day: date = Field(description="today's New York trading day")
    status: str = Field(description="ok (stored), or pending")
    reason: Literal["before_window", "weekend", "not_received"] | None = Field(
        description="pending: before 02:00 New York, a weekend day, or no ok answer yet"
    )
    window: str = "02:00-16:45 America/New_York"
    model: str | None = None
    expected_move_pct: float | None = None
    range_pct: Quantiles | None = None
    range_usd: Quantiles | None = None
    level: str | None = None
    level_label: LevelLabel | None = None
    news: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str | None = None
    created_at: datetime | None = None
