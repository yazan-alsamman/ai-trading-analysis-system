import uuid
from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    AliasChoices,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.candle import Timeframe
from app.models.instrument import MarketType

MAX_CANDLES_PER_REQUEST = 5000

Symbol = Annotated[
    str, AfterValidator(lambda v: v.strip().upper()), Field(min_length=1, max_length=32)
]
Source = Annotated[
    str, AfterValidator(lambda v: v.strip().lower()), Field(min_length=1, max_length=32)
]
Asset = Annotated[
    str, AfterValidator(lambda v: v.strip().upper()), Field(min_length=1, max_length=16)
]
Precision = Annotated[int, Field(ge=0, le=18)]


# --- instruments ----------------------------------------------------------------------------


class InstrumentCreate(BaseModel):
    symbol: Symbol
    source: Source
    market: MarketType
    base_asset: Asset | None = None
    quote_asset: Asset | None = None
    price_precision: Precision | None = None
    quantity_precision: Precision | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _derive_assets(self) -> Self:
        """``BTC/USDT`` -> base ``BTC``, quote ``USDT`` unless given explicitly."""
        if self.base_asset is None or self.quote_asset is None:
            base, sep, quote = self.symbol.partition("/")
            if not sep or not base or not quote:
                raise ValueError(
                    "base_asset and quote_asset are required when symbol is not BASE/QUOTE"
                )
            self.base_asset = self.base_asset or base
            self.quote_asset = self.quote_asset or quote
        return self


class InstrumentUpdate(BaseModel):
    base_asset: Asset | None = None
    quote_asset: Asset | None = None
    price_precision: Precision | None = None
    quantity_precision: Precision | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _no_null_for_required(self) -> Self:
        for name in ("base_asset", "quote_asset", "is_active"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class InstrumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    source: str
    market: MarketType
    base_asset: str
    quote_asset: str
    price_precision: int | None
    quantity_precision: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- candles --------------------------------------------------------------------------------


class CandleIn(BaseModel):
    """A 1-minute candle to ingest. ``ts`` (alias ``time``) is the UTC start of the minute.

    Accepts ISO 8601 with a timezone, or unix seconds.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    ts: AwareDatetime = Field(validation_alias=AliasChoices("ts", "time"))
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)
    trades: int | None = Field(default=None, ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        self.ts = self.ts.astimezone(UTC)
        if self.ts.second or self.ts.microsecond:
            raise ValueError("ts must be aligned to the minute (seconds = 0)")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= open and close")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= open and close")
        return self


class CandleBatch(BaseModel):
    candles: list[CandleIn] = Field(min_length=1, max_length=MAX_CANDLES_PER_REQUEST)


class CandlesWritten(BaseModel):
    written: int


class CandleOut(BaseModel):
    """Lightweight Charts friendly: ``time`` is unix seconds (UTC) of the bucket start."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_candle(cls, candle) -> "CandleOut":
        """From anything with ts/open/high/low/close/volume (CandleRow, CandleIn)."""
        return cls(
            time=int(candle.ts.timestamp()),
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
        )


class CandleSeries(BaseModel):
    instrument_id: uuid.UUID
    timeframe: Timeframe
    candles: list[CandleOut]
