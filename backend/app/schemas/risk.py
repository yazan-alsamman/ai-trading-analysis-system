"""Risk management (docs/risk-management.md). The risk config itself is validated by
``trading_backtest`` (``validate_risk_config``), not here."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.candle import Timeframe
from app.schemas.strategies import SignalRead

AccountSize = Annotated[float, Field(gt=0, le=1e12, allow_inf_nan=False)]
Currency = Annotated[str, Field(min_length=1, max_length=10, pattern=r"^[A-Z0-9]+$")]
Template = Literal["conservative", "balanced", "aggressive"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RiskProfileRead(BaseModel):
    account_size: float
    quote_currency: str
    config: dict[str, Any] = Field(description="normalised risk config")
    template: str | None = Field(description="the template it was made from, if unchanged")
    updated_at: datetime


class RiskProfileUpdate(_Strict):
    """Either ``config`` or ``template`` (or neither, to change only the account)."""

    account_size: AccountSize | None = None
    quote_currency: Currency | None = None
    config: dict[str, Any] | None = None
    template: Template | None = None

    @model_validator(mode="after")
    def _one(self) -> Self:
        if self.config is not None and self.template is not None:
            raise ValueError("give either config or template, not both")
        return self


class RiskSchema(BaseModel):
    json_schema: dict[str, Any]
    templates: dict[str, dict[str, Any]] = Field(description="normalised template configs")
    default_template: str


class PositionSizeRequest(_Strict):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    side: Literal["buy", "sell"]
    entry: float | None = Field(
        default=None, gt=0, allow_inf_nan=False, description="default: the last closed close"
    )
    stop: float | None = Field(
        default=None, gt=0, allow_inf_nan=False, description="a stop price (default: the rule)"
    )
    config: dict[str, Any] | None = Field(default=None, description="default: your profile")
    account_size: AccountSize | None = Field(default=None, description="default: your profile")


class PositionSizeResponse(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    bar_time: datetime = Field(description="the last closed bar the rules were computed on")
    account_size: float
    quote_currency: str
    config: dict[str, Any]
    plan: dict[str, Any]


class SignalPlanRead(BaseModel):
    id: uuid.UUID
    user_strategy_id: uuid.UUID | None
    plan: dict[str, Any]
    created_at: datetime
    signal: SignalRead
