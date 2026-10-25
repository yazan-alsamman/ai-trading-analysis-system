import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketType(StrEnum):
    crypto = "crypto"
    forex = "forex"
    stock = "stock"
    commodity = "commodity"


class PriceBasis(StrEnum):
    """Which price the candles are built from."""

    bid = "bid"
    mid = "mid"
    last = "last"


class SpecSource(StrEnum):
    """Where an instrument's contract specs came from."""

    typical = "typical"  # usual broker values, to be replaced by the broker's own
    fxpro_ctrader = "fxpro_ctrader"  # read from the broker (cTrader Open API)
    manual = "manual"  # set by an admin


# The spec fields an admin can edit (any change sets spec_source = manual).
SPEC_FIELDS = (
    "contract_size",
    "tick_size",
    "lot_step",
    "min_lot",
    "max_lot",
    "quote_currency",
    "margin_rate",
    "price_basis",
    "session_calendar",
    "cost_per_unit",
)


class Instrument(Base):
    """A market (symbol on a data source) with its price and quantity precision and, when known,
    its contract specs (lot size and limits, tick, margin, price basis, trading sessions)."""

    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("source", "symbol", name="uq_instruments_source_symbol"),
        CheckConstraint("symbol = upper(symbol)", name="ck_instruments_symbol_upper"),
        CheckConstraint("source = lower(source)", name="ck_instruments_source_lower"),
        CheckConstraint(
            "contract_size IS NULL OR contract_size > 0", name="ck_instruments_contract_size"
        ),
        CheckConstraint("tick_size IS NULL OR tick_size > 0", name="ck_instruments_tick_size"),
        CheckConstraint("lot_step IS NULL OR lot_step > 0", name="ck_instruments_lot_step"),
        CheckConstraint("min_lot IS NULL OR min_lot > 0", name="ck_instruments_min_lot"),
        CheckConstraint("max_lot IS NULL OR max_lot > 0", name="ck_instruments_max_lot"),
        CheckConstraint(
            "min_lot IS NULL OR max_lot IS NULL OR min_lot <= max_lot",
            name="ck_instruments_lot_range",
        ),
        CheckConstraint(
            "margin_rate IS NULL OR (margin_rate > 0 AND margin_rate <= 1)",
            name="ck_instruments_margin_rate",
        ),
        CheckConstraint(
            "price_basis IS NULL OR price_basis IN ('bid', 'mid', 'last')",
            name="ck_instruments_price_basis",
        ),
        CheckConstraint(
            "cost_per_unit IS NULL OR cost_per_unit >= 0", name="ck_instruments_cost_per_unit"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    symbol: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32))
    market: Mapped[MarketType] = mapped_column(
        SAEnum(MarketType, name="market_type", values_callable=lambda e: [m.value for m in e])
    )
    base_asset: Mapped[str] = mapped_column(String(16))
    quote_asset: Mapped[str] = mapped_column(String(16))
    price_precision: Mapped[int | None] = mapped_column(Integer)
    quantity_precision: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # contract specs (migration 0013); null = unknown
    contract_size: Mapped[float | None] = mapped_column(Double)  # units per 1.0 lot
    tick_size: Mapped[float | None] = mapped_column(Double)  # minimum price increment
    lot_step: Mapped[float | None] = mapped_column(Double)  # volume step in lots
    min_lot: Mapped[float | None] = mapped_column(Double)
    max_lot: Mapped[float | None] = mapped_column(Double)
    # currency of the P&L per price unit; null = quote_asset (see ``pnl_currency``)
    quote_currency: Mapped[str | None] = mapped_column(String(16))
    # margin as a fraction of notional at 1:1 (0.01 = 1:100); null = the user's leverage
    margin_rate: Mapped[float | None] = mapped_column(Double)
    price_basis: Mapped[str | None] = mapped_column(String(8))  # PriceBasis
    session_calendar: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # SessionCalendar
    # fixed trading cost per unit of quantity, price units, round trip (migration 0021; XAU/USD
    # 0.25 per oz, Fadi): backtests and sizing use it instead of fee_bps / slippage_bps;
    # null = the bps fees as before. Candles keep their real spread
    cost_per_unit: Mapped[float | None] = mapped_column(Double)
    spec_source: Mapped[str | None] = mapped_column(String(32))  # SpecSource
    spec_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def pnl_currency(self) -> str:
        """The currency a 1.0 price move is worth ``contract_size`` of, per lot."""
        return self.quote_currency or self.quote_asset

    @property
    def has_specs(self) -> bool:
        """Enough specs to size in lots (contract size and lot step)."""
        return self.contract_size is not None and self.lot_step is not None
