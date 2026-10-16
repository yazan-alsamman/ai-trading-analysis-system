"""News (Y18): sources, articles with sentiment (filled by the AI side), instrument tags."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# The full-text expression of news search. The index and the queries must use exactly this
# text for Postgres to use the index ('simple': no stemming, works for Arabic and English).
SEARCH_VECTOR = (
    "to_tsvector('simple'::regconfig, (title::text || ' '::text) || COALESCE(summary, ''::text))"
)
SUMMARY_MAX = 2000


class NewsSourceKind(StrEnum):
    rss = "rss"  # fetched by the built-in RSS task
    api = "api"  # pushed through POST /ingest/news (the AI side's adapters)
    manual = "manual"


class SentimentLabel(StrEnum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


def _enum(cls, name: str) -> SAEnum:
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class NewsSource(Base):
    """Where articles come from: an RSS feed the platform fetches, or an API source that pushes
    through the ingestion API."""

    __tablename__ = "news_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[NewsSourceKind] = mapped_column(_enum(NewsSourceKind, "news_source_kind"))
    url: Mapped[str | None] = mapped_column(String(1000))
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    fetch_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=15, server_default=text("15")
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    # conditional GET of RSS feeds (answers 304 when nothing changed)
    etag: Mapped[str | None] = mapped_column(String(255))
    last_modified: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class NewsArticle(Base):
    """``external_id``: the provider's id, or a hash of the normalised URL (RSS)."""

    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_news_articles_source_external"),
        CheckConstraint(
            "sentiment_score IS NULL OR sentiment_score BETWEEN -1 AND 1",
            name="ck_news_articles_sentiment_score",
        ),
        CheckConstraint(
            f"summary IS NULL OR char_length(summary) <= {SUMMARY_MAX}",
            name="ck_news_articles_summary_length",
        ),
        Index("ix_news_articles_published", text("published_at DESC")),
        Index("ix_news_articles_sentiment", "sentiment_label", text("published_at DESC")),
        Index("ix_news_articles_source", "source_id", text("published_at DESC")),
        Index("ix_news_articles_search", text(SEARCH_VECTOR), postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("news_sources.id", ondelete="CASCADE")
    )
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2000))
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2000))
    author: Mapped[str | None] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    sentiment_label: Mapped[SentimentLabel | None] = mapped_column(
        _enum(SentimentLabel, "sentiment_label")
    )
    sentiment_score: Mapped[float | None] = mapped_column(Double)
    sentiment_model: Mapped[str | None] = mapped_column(String(64))
    sentiment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NewsArticleInstrument(Base):
    """An instrument tag of an article with its relevance (0..1)."""

    __tablename__ = "news_article_instruments"
    __table_args__ = (
        CheckConstraint("relevance BETWEEN 0 AND 1", name="ck_news_article_instruments_relevance"),
        Index("ix_news_article_instruments_instrument", "instrument_id"),
    )

    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    relevance: Mapped[float] = mapped_column(Double, default=1.0, server_default=text("1"))
