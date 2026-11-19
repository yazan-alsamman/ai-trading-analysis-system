from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import get_settings
from app.news import finnhub, service
from app.news.rss import FeedError
from app.schemas.news import ArticleIn

NOW = datetime(2026, 11, 19, tzinfo=UTC)


@pytest.mark.parametrize(
    ("title", "summary", "expected"),
    [
        ("Bullion rises", None, True),
        ("Treasury yields rise", "The dollar index falls", True),
        ("Fed holds rates", "The Fed will meet again", False),
        ("Goldman shares rise", None, False),
        ("New FOMC projections", None, False),
    ],
)
def test_gold_filter(title, summary, expected):
    assert finnhub.matches_gold(title, summary) is expected


@pytest.mark.asyncio
async def test_finnhub_market_news():
    def respond(request):
        assert request.url.path == "/api/v1/news"
        assert request.url.params == httpx.QueryParams(category="forex")
        assert request.headers["X-Finnhub-Token"] == "test-key"
        article = {
            "id": 3,
            "datetime": int(NOW.timestamp()) - 1,
            "headline": "<b>Gold rises</b>",
            "url": "https://example.com/news?utm_source=feed",
        }
        return httpx.Response(
            200,
            json=[
                article,
                {**article, "id": 4, "headline": "Fed holds rates"},
                {**article, "id": 5, "datetime": int(NOW.timestamp()) + 1},
                {**article, "id": 6, "url": "https://[invalid"},
                {**article, "id": 7, "headline": None},
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        rows = await finnhub.fetch_category(client, "forex", "test-key", NOW)
    (article,) = map(ArticleIn.model_validate, rows)
    assert article.source_key == "finnhub"
    assert article.external_id == "3"
    assert article.title == "Gold rises"
    assert article.url == "https://example.com/news"
    assert article.instruments[0].symbol == "XAU/USD"
    assert article.sentiment is None


@pytest.mark.asyncio
async def test_finnhub_rate_limit_does_not_expose_response():
    transport = httpx.MockTransport(lambda _: httpx.Response(429, text="private response"))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(FeedError, match="^HTTP 429$"):
            await finnhub.fetch_category(client, "general", "test-key", NOW)


@pytest.mark.asyncio
async def test_schedule_ingests_successful_category_when_other_is_rate_limited(monkeypatch):
    monkeypatch.setenv("NEWS_RSS_ENABLED", "false")
    monkeypatch.setenv("NEWS_FINNHUB_ENABLED", "true")
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    get_settings.cache_clear()

    def respond(request):
        if request.url.params["category"] == "forex":
            return httpx.Response(429)
        return httpx.Response(
            200,
            json=[
                {
                    "id": 3,
                    "datetime": int(datetime.now(UTC).timestamp()) - 1,
                    "headline": "Gold rises",
                    "url": "https://example.com/news",
                }
            ],
        )

    @asynccontextmanager
    async def factory():
        yield None

    monkeypatch.setattr(service, "transport", httpx.MockTransport(respond))
    ingest = AsyncMock(return_value=service.IngestOutcome(inserted=1))
    monkeypatch.setattr(service, "ingest", ingest)
    monkeypatch.setattr(service, "publish_new", AsyncMock(return_value=0))
    try:
        report = await service.fetch_scheduled(factory, None)
    finally:
        get_settings.cache_clear()
    assert report["finnhub"]["forex"] == {"status": "error", "error": "HTTP 429"}
    assert report["finnhub"]["general"]["inserted"] == 1
    ingest.assert_awaited_once()
    assert ingest.await_args.args[1][0]["external_id"] == "3"
