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


class AISetupDetail(AISetupRead):
    evidence: dict[str, Any]
    features: dict[str, Any]
    last_payload: dict[str, Any] = Field(description="the setup exactly as last returned")
    events: list[AISetupEventRead] = Field(description="oldest first")


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
