import uuid
from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.price_alert import AlertCondition, AlertRepeat

WindowMinutes = Annotated[int, Field(ge=1, le=1440)]
CooldownMinutes = Annotated[int, Field(ge=1, le=10_080)]
DEFAULT_COOLDOWN = 60


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def check_combination(
    condition: AlertCondition,
    value: float,
    window: int | None,
    repeat: AlertRepeat,
    cooldown: int | None,
) -> None:
    if condition == AlertCondition.change_pct:
        if window is None:
            raise ValueError("change_pct needs window_minutes")
        if value > 100:
            raise ValueError("change_pct value is a percent (0-100]")
    elif window is not None:
        raise ValueError("window_minutes is only for change_pct")
    if repeat == AlertRepeat.once and cooldown is not None:
        raise ValueError("cooldown_minutes is only for repeat=every")


def _aware(v: datetime | None) -> datetime | None:
    if v is None:
        return v
    v = v if v.tzinfo else v.replace(tzinfo=UTC)
    if v <= datetime.now(UTC):
        raise ValueError("must be in the future")
    return v


class PriceAlertCreate(_Strict):
    instrument_id: uuid.UUID
    condition: AlertCondition
    value: float = Field(gt=0, description="a price, or a percent (e.g. 2.5) for change_pct")
    window_minutes: WindowMinutes | None = Field(default=None, description="change_pct only")
    repeat: AlertRepeat = AlertRepeat.once
    cooldown_minutes: CooldownMinutes | None = Field(
        default=None, description=f"repeat=every only (default {DEFAULT_COOLDOWN})"
    )
    note: Annotated[str, Field(max_length=200)] | None = None
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _expires(cls, v: datetime | None) -> datetime | None:
        return _aware(v)

    @model_validator(mode="after")
    def _combination(self) -> Self:
        if self.repeat == AlertRepeat.every and self.cooldown_minutes is None:
            self.cooldown_minutes = DEFAULT_COOLDOWN
        check_combination(
            self.condition, self.value, self.window_minutes, self.repeat, self.cooldown_minutes
        )
        return self


class PriceAlertUpdate(_Strict):
    """Missing fields keep their value; the combination is checked again as a whole."""

    condition: AlertCondition | None = None
    value: float | None = Field(default=None, gt=0)
    window_minutes: WindowMinutes | None = None
    repeat: AlertRepeat | None = None
    cooldown_minutes: CooldownMinutes | None = None
    note: Annotated[str, Field(max_length=200)] | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _expires(cls, v: datetime | None) -> datetime | None:
        return _aware(v)

    @model_validator(mode="after")
    def _not_null(self) -> Self:
        for name in ("condition", "value", "repeat", "is_active"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class InstrumentRef(BaseModel):
    id: uuid.UUID
    symbol: str


class PriceAlertRead(BaseModel):
    id: uuid.UUID
    instrument: InstrumentRef
    condition: AlertCondition
    value: float
    window_minutes: int | None
    repeat: AlertRepeat
    cooldown_minutes: int | None
    note: str | None
    is_active: bool
    last_triggered_at: datetime | None
    trigger_count: int
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PriceAlertCreated(PriceAlertRead):
    current_price: float | None = Field(description="close of the latest 1m candle")
    would_trigger_now: bool = Field(
        description="above/below: the latest price already meets the condition (the alert is "
        "created anyway and fires on the next closed bar)"
    )


class PriceAlertTrigger(BaseModel):
    notification_id: uuid.UUID
    alert_id: uuid.UUID | None
    instrument_id: uuid.UUID | None
    symbol: str | None
    condition: str | None
    value: float | None
    price: float | None
    bar_time: datetime | None
    change_pct: float | None
    note: str | None
    created_at: datetime
