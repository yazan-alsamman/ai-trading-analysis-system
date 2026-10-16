import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketType(StrEnum):
    crypto = "crypto"
    forex = "forex"
    stock = "stock"
    commodity = "commodity"


class Instrument(Base):
    """A market (symbol on a data source) with its price and quantity precision."""

    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("source", "symbol", name="uq_instruments_source_symbol"),
        CheckConstraint("symbol = upper(symbol)", name="ck_instruments_symbol_upper"),
        CheckConstraint("source = lower(source)", name="ck_instruments_source_lower"),
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
