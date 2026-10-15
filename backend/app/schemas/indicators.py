import uuid
from datetime import UTC, datetime
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.candle import Timeframe

MAX_INDICATORS_PER_REQUEST = 10
MAX_POINTS = 5000


class IndicatorSpec(BaseModel):
    name: str = Field(min_length=1, max_length=32, examples=["rsi"])
    params: dict[str, Any] = Field(default_factory=dict, examples=[{"length": 14}])


class IndicatorsRequest(BaseModel):
    timeframe: Timeframe
    start: datetime | None = Field(default=None, description="ISO 8601, inclusive (UTC if naive)")
    end: datetime | None = Field(default=None, description="ISO 8601, inclusive (UTC if naive)")
    limit: int = Field(default=500, ge=1, le=MAX_POINTS)
    indicators: list[IndicatorSpec] = Field(min_length=1, max_length=MAX_INDICATORS_PER_REQUEST)

    @field_validator("start", "end")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start must be <= end")
        return self


class IndicatorPoint(BaseModel):
    """Lightweight Charts line data: ``time`` in unix seconds, ``value`` null during warm-up."""

    time: int
    value: float | None


class IndicatorResult(BaseModel):
    name: str
    params: dict[str, int | float]  # resolved, defaults included
    placement: str
    outputs: dict[str, list[IndicatorPoint]]


class IndicatorsResponse(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    results: list[IndicatorResult]
