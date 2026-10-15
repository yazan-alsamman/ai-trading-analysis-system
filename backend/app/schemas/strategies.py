import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from app.models.candle import Timeframe
from app.models.strategy import SignalSide


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_utc)]  # naive values are taken as UTC
Name = Annotated[str, Field(min_length=1, max_length=100)]


class StrategyPreviewRequest(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    params: dict[str, Any] = Field(default_factory=dict)
    start: UtcDatetime | None = None
    end: UtcDatetime | None = None
    limit: int = Field(default=500, ge=1, le=5000)

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start must be <= end")
        return self


class UserStrategyCreate(BaseModel):
    strategy_key: str = Field(min_length=1, max_length=64)
    instrument_id: uuid.UUID
    timeframe: Timeframe
    params: dict[str, Any] = Field(default_factory=dict)
    name: Name | None = None
    is_active: bool = True
    notify: bool = True


class UserStrategyUpdate(BaseModel):
    name: Name | None = None
    params: dict[str, Any] | None = None
    is_active: bool | None = None
    notify: bool | None = None

    @model_validator(mode="after")
    def _no_null_for_required(self) -> Self:
        for field in ("params", "is_active", "notify"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class UserStrategyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    strategy_key: str
    params: dict[str, Any]
    params_hash: str
    instrument_id: uuid.UUID
    timeframe: Timeframe
    name: str | None
    is_active: bool
    notify: bool
    created_at: datetime
    updated_at: datetime


class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: Timeframe
    strategy_key: str
    params: dict[str, Any]
    params_hash: str
    bar_time: datetime
    side: SignalSide
    strength: float
    price: float
    reason: str
    details: dict[str, Any]
    created_at: datetime

    @computed_field
    @property
    def time(self) -> int:
        """``bar_time`` in unix seconds (Lightweight Charts)."""
        return int(self.bar_time.timestamp())
