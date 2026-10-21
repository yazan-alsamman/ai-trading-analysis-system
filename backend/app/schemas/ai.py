import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.contract import SetupState


class AISetupRead(BaseModel):
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
    request_id: str
    created_at: datetime


class AISetupSizeBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    lots: float
    feasible: bool
    source: str
    computed_at: datetime


class AISetupDetail(AISetupRead):
    evidence: dict[str, Any]
    features: dict[str, Any]
    last_payload: dict[str, Any] = Field(description="the setup exactly as last returned")
    events: list[AISetupEventRead] = Field(description="oldest first")
    sizes: list[AISetupSizeBrief] = Field(description="the stored per-user sizes (B10)")
    takes_count: int = Field(description="users who said they took it")


# --- users (B10) ---------------------------------------------------------------------------------


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


class AITradeRead(TakeRead):
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
    source: str = Field(description="ai-service, or local (the backend's B4 lot sizing)")
    computed_at: datetime
    inputs: AISizeInputs
    taken: bool = Field(description="you said you took this setup")


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
