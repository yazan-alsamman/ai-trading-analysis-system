"""Paper trading (docs/paper-trading.md)."""

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaperOrderCreate(_Strict):
    instrument_id: uuid.UUID
    side: Side
    type: OrderType = "market"
    lots: float = Field(gt=0, le=1000, examples=[0.1])
    price: float | None = Field(
        default=None, gt=0, description="limit / stop price (required for them, none for market)"
    )
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _price(self) -> Self:
        if self.type == "market" and self.price is not None:
            raise ValueError("a market order has no price")
        if self.type != "market" and self.price is None:
            raise ValueError(f"a {self.type} order needs a price")
        return self


class PaperLevelsUpdate(_Strict):
    stop_loss: float | None = Field(default=None, gt=0, description="null removes it")
    take_profit: float | None = Field(default=None, gt=0, description="null removes it")


class PaperLeverageUpdate(_Strict):
    leverage: int = Field(ge=1, le=1000, examples=[100])


class PaperReset(_Strict):
    initial_balance: float | None = Field(
        default=None, ge=100, le=10_000_000, description="default PAPER_INITIAL_BALANCE"
    )


class PaperInstrumentRef(BaseModel):
    id: uuid.UUID
    symbol: str
    price_precision: int | None


class PaperAccountRead(BaseModel):
    """The portfolio: cash, open P/L, equity and margin, all in ``currency``."""

    currency: str
    initial_balance: float
    balance: float = Field(description="cash: initial balance + realized P/L")
    equity: float = Field(description="balance + unrealized P/L")
    unrealized_pnl: float
    realized_pnl: float
    margin_used: float
    free_margin: float
    margin_level_pct: float | None
    leverage: int
    return_pct: float = Field(description="(equity - initial balance) / initial balance")
    today_pnl: float = Field(description="P/L of positions closed today (UTC) + open P/L")
    today_pnl_pct: float | None
    open_positions: int
    pending_orders: int
    created_at: datetime
    reset_at: datetime | None


class PaperOrderRead(BaseModel):
    id: uuid.UUID
    instrument: PaperInstrumentRef | None
    side: Side
    type: OrderType
    lots: float
    price: float | None
    stop_loss: float | None
    take_profit: float | None
    status: Literal["pending", "filled", "cancelled", "rejected"]
    reject_reason: str | None
    fill_price: float | None
    position_id: uuid.UUID | None
    created_at: datetime
    filled_at: datetime | None
    cancelled_at: datetime | None


class PaperPositionRead(BaseModel):
    id: uuid.UUID
    instrument: PaperInstrumentRef | None
    side: Side
    lots: float
    contract_size: float
    entry_price: float
    stop_loss: float | None
    take_profit: float | None
    margin: float
    cost: float = Field(description="round-trip trading cost, taken at close")
    status: Literal["open", "closed"]
    opened_at: datetime
    current_price: float | None = Field(description="open positions: latest 1m close")
    unrealized_pnl: float | None
    closed_at: datetime | None
    close_price: float | None
    close_reason: Literal["manual", "stop_loss", "take_profit", "reset"] | None
    pnl: float | None = Field(description="realized, net of cost")
