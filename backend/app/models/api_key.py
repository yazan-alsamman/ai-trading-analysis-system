import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import UserRole


class Scope(StrEnum):
    """What an API key may read. The single source of truth for scope names."""

    market_read = "market:read"  # instruments, candles
    indicators_read = "indicators:read"  # indicator catalog + computation
    strategies_read = "strategies:read"  # strategy catalog + preview
    signals_read = "signals:read"  # GET /signals
    stream = "stream"  # WebSocket /ws/market
    backtests_read = "backtests:read"  # GET /backtests*
    news_read = "news:read"  # GET /news*, WebSocket news topics
    news_write = "news:write"  # POST /ingest/news* (the AI side); admin keys only


ALL_SCOPES: frozenset[str] = frozenset(s.value for s in Scope)
# Scopes only an admin may put on a key (checked on create and update).
ADMIN_ONLY_SCOPES: frozenset[str] = frozenset({Scope.news_write.value})
SCOPE_DESCRIPTIONS: dict[str, str] = {
    Scope.market_read: "Instruments and candles",
    Scope.indicators_read: "Indicator catalog and computation",
    Scope.strategies_read: "Strategy catalog and preview",
    Scope.signals_read: "Signals",
    Scope.stream: "WebSocket /ws/market",
    Scope.backtests_read: "Your backtests (read only)",
    Scope.news_read: "News, sentiment and the news WebSocket topics",
    Scope.news_write: "Push news and sentiment (POST /ingest/news*). Admins only",
}

# Usable (not revoked, not expired) keys a user may hold at the same time.
MAX_KEYS_PER_ROLE: dict[UserRole, int] = {
    UserRole.trader: 2,
    UserRole.analyst: 5,
    UserRole.expert: 5,
    UserRole.admin: 10,
}


class ApiKey(Base):
    """A key for external programs: ``tk_<prefix>_<secret>``. Only the SHA-256 of the full key
    is stored; ``prefix`` identifies the row (and is shown in lists)."""

    __tablename__ = "api_keys"
    __table_args__ = (
        CheckConstraint(
            "rate_limit_per_minute IS NULL OR rate_limit_per_minute > 0",
            name="ck_api_keys_rate_limit_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
