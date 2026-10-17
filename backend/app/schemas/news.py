import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.news import NewsSourceKind, SentimentLabel
from app.news.text import is_http_url

SOURCE_KEY = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,63}$")
MAX_INGEST_ITEMS = 200
MAX_SENTIMENT_ITEMS = 500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- ingestion (the AI side) -----------------------------------------------------------------


class SentimentIn(_Strict):
    label: SentimentLabel
    score: float = Field(ge=-1, le=1, description="-1 (very negative) .. 1 (very positive)")
    model: str = Field(min_length=1, max_length=64, examples=["finbert-ft-v1"])


class InstrumentTagIn(_Strict):
    symbol: str = Field(
        min_length=2, max_length=32, description='"BTC/USDT" (that pair) or "BTC" (every pair)'
    )
    relevance: float = Field(default=1.0, ge=0, le=1)


def _http(value: str | None) -> str | None:
    if value is not None and not is_http_url(value):
        raise ValueError("must be an http(s) URL")
    return value


class ArticleIn(_Strict):
    source_key: str = Field(examples=["finnhub"], description="created as an api source if new")
    external_id: str = Field(min_length=1, max_length=255, description="the provider's id")
    url: str = Field(max_length=2000)
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = Field(default=None, max_length=20_000, description="HTML is stripped")
    published_at: datetime
    language: str | None = Field(default=None, min_length=2, max_length=8)
    image_url: str | None = Field(default=None, max_length=2000)
    author: str | None = Field(default=None, max_length=200)
    instruments: list[InstrumentTagIn] | None = Field(
        default=None, max_length=20, description="replaces the article's tags when given"
    )
    sentiment: SentimentIn | None = None

    @field_validator("source_key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not SOURCE_KEY.match(v):
            raise ValueError("lower-case letters, digits, '_', '.', '-' (2-64 characters)")
        return v

    @field_validator("url", "image_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        return _http(v)

    @field_validator("published_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)


class IngestRequest(_Strict):
    # items are validated one by one by the service, so one bad article does not reject the
    # batch (its error is reported with its index)
    articles: list[dict] = Field(min_length=1, max_length=MAX_INGEST_ITEMS)


class ItemError(BaseModel):
    index: int
    external_id: str | None = None
    error: str


class IngestResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    errors: list[ItemError]
    warnings: list[ItemError] = Field(default_factory=list, description="e.g. unknown symbols")


class SentimentItemIn(_Strict):
    article_id: uuid.UUID | None = None
    source_key: str | None = None
    external_id: str | None = None
    label: SentimentLabel
    score: float = Field(ge=-1, le=1)
    model: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _target(self) -> Self:
        by_id = self.article_id is not None
        by_key = self.source_key is not None and self.external_id is not None
        if by_id == by_key:
            raise ValueError("give either article_id or source_key + external_id")
        return self


class SentimentRequest(_Strict):
    items: list[dict] = Field(min_length=1, max_length=MAX_SENTIMENT_ITEMS)


class SentimentResult(BaseModel):
    updated: int
    errors: list[ItemError]


# --- reading ---------------------------------------------------------------------------------


class SourceRef(BaseModel):
    key: str
    name: str


class SentimentRead(BaseModel):
    label: SentimentLabel
    score: float | None
    model: str | None
    at: datetime | None


class TagRead(BaseModel):
    instrument_id: uuid.UUID
    symbol: str
    relevance: float


class ArticleRead(BaseModel):
    id: uuid.UUID
    source: SourceRef
    url: str
    title: str
    summary: str | None
    image_url: str | None
    author: str | None
    language: str
    published_at: datetime
    fetched_at: datetime
    sentiment: SentimentRead | None
    instruments: list[TagRead]


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    kind: NewsSourceKind
    url: str | None
    language: str
    is_active: bool
    fetch_interval_minutes: int
    last_fetched_at: datetime | None
    last_error: str | None
    articles: int = 0


class SourceUpdate(_Strict):
    is_active: bool | None = None
    fetch_interval_minutes: Annotated[int, Field(ge=5, le=1440)] | None = None


Window = Literal["1h", "24h", "7d"]


class SentimentBucket(BaseModel):
    articles: int
    scored: int
    positive: int
    neutral: int
    negative: int
    mean_score: float | None
    weighted_score: float | None = Field(
        default=None, description="mean score weighted by tag relevance (instruments only)"
    )


class InstrumentSentiment(SentimentBucket):
    instrument_id: uuid.UUID
    symbol: str


class SentimentAggregate(BaseModel):
    window: Window
    since: datetime
    overall: SentimentBucket
    instruments: list[InstrumentSentiment]
