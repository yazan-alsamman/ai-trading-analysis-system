import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.backtest import BacktestStatus
from app.models.candle import Timeframe
from app.schemas.strategies import UtcDatetime

HEADLINE_METRICS = (
    "total_return_pct",
    "buy_and_hold_return_pct",
    "max_drawdown_pct",
    "sharpe",
    "trades",
    "win_rate_pct",
    "profit_factor",
)


class BacktestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: uuid.UUID
    timeframe: Timeframe
    strategy_key: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    start: UtcDatetime = Field(description="inclusive (UTC if naive)")
    end: UtcDatetime = Field(description="inclusive, not in the future")
    config: dict[str, Any] | None = Field(
        default=None,
        description="initial_capital, fee_bps, slippage_bps, direction, sizing, stop, trailing, "
        "take_profit, guards, check_entry_bar, exits {max_bars_held, exit_on_opposite_signal, "
        "stop_loss_pct, take_profit_pct} (docs/risk-management.md); risk_profile: true uses "
        "your risk profile. An instrument with a fixed cost per unit (XAU/USD: 0.25) gets "
        "config.cost_per_unit from the server, and fee_bps / slippage_bps are then ignored",
    )

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.start >= self.end:
            raise ValueError("start must be before end")
        return self


class BacktestAccepted(BaseModel):
    id: uuid.UUID
    status: BacktestStatus


class InstrumentRef(BaseModel):
    id: uuid.UUID
    symbol: str
    source: str


class BacktestSummary(BaseModel):
    id: uuid.UUID
    status: BacktestStatus
    progress: int
    instrument: InstrumentRef
    timeframe: Timeframe
    strategy_key: str
    params: dict[str, Any]
    start: datetime
    end: datetime
    bars: int | None
    error: str | None
    headline: dict[str, Any] | None  # HEADLINE_METRICS, once completed
    created_at: datetime
    finished_at: datetime | None


class Point(BaseModel):
    time: int  # unix seconds
    value: float


class BacktestRead(BacktestSummary):
    params_hash: str
    config: dict[str, Any]
    cost_model: Literal["bps", "fixed_per_unit"] = Field(
        description="bps: fee_bps + slippage_bps of notional; fixed_per_unit: the instrument's "
        "cost_per_unit x quantity per round trip, charged at the entry (fees and slippage "
        "ignored)"
    )
    cost_per_unit: float | None = Field(
        description="price units per unit, round trip (fixed_per_unit only)"
    )
    first_bar: datetime | None
    last_bar: datetime | None
    metrics: dict[str, Any] | None
    equity: list[Point]
    drawdown: list[Point]  # percent below the running peak
    markers: list[dict[str, Any]]  # Lightweight Charts markers for entries and exits
    started_at: datetime | None
    duration_ms: int | None
    engine_ms: int | None


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: int
    side: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    net_pnl: float
    return_pct: float
    bars_held: int
    entry_reason: str | None
    exit_reason: str
    initial_stop: float | None = None
    risk_amount: float | None = None
    r_multiple: float | None = None
    fills: list[dict[str, Any]] | None = None


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[uuid.UUID] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        if len(set(self.ids)) != len(self.ids):
            raise ValueError("ids must be different")
        return self


class CompareItem(BaseModel):
    id: uuid.UUID
    instrument: InstrumentRef
    timeframe: Timeframe
    strategy_key: str
    params: dict[str, Any]
    config: dict[str, Any]
    start: datetime
    end: datetime
    metrics: dict[str, Any]
    equity: list[Point]  # normalised: 100 at the start


class CompareResponse(BaseModel):
    items: list[CompareItem]
