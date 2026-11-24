"""Credentials of external market-data feeds (B1, docs/ctrader-feed.md).

One row per provider. The OAuth tokens are stored **encrypted** (``app/feeds/secrets.py``):
the refresh token rotates on every refresh, so it cannot live in ``.env``. Nothing here is ever
returned by the API or logged.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeedCredential(Base):
    __tablename__ = "feed_credentials"
    __table_args__ = (CheckConstraint("env IN ('demo', 'live')", name="ck_feed_credentials_env"),)

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)  # "ctrader"
    env: Mapped[str] = mapped_column(String(8))
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str] = mapped_column(String(16))
    account_id: Mapped[int | None] = mapped_column(BigInteger)  # the chosen trader account
    # the accounts the token can see: [{account_id, is_live, trader_login, broker}]
    accounts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
