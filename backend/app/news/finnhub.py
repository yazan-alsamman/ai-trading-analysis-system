"""Finnhub Market News adapter for the existing news ingestion service."""

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.news.rss import FeedError
from app.news.text import clip, is_http_url, normalize_url, strip_html
from app.schemas.news import MAX_INGEST_ITEMS

URL = "https://finnhub.io/api/v1/news"
CATEGORIES = ("forex", "general")
GOLD_SYMBOL = "XAU/USD"
_GOLD = re.compile(r"\b(?:gold|bullion|xau|xauusd|precious metals?|gld)\b", re.IGNORECASE)
_MACRO = re.compile(
    r"\b(?:central bank gold|safe haven|fed|fomc|powell|treasury yields|real yields|"
    r"dollar index|dxy)\b",
    re.IGNORECASE,
)


def matches_gold(title: str, summary: str | None) -> bool:
    """Apply the sentiment registration's Appendix A to plain text."""
    value = f"{title}\n{summary or ''}"
    return bool(_GOLD.search(value)) or len({term.lower() for term in _MACRO.findall(value)}) >= 2


def parse_articles(payload: Any, now: datetime) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise FeedError("expected a news list")
    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        article_id, timestamp = item.get("id"), item.get("datetime")
        headline, summary, url = item.get("headline"), item.get("summary"), item.get("url")
        if type(article_id) is not int or article_id <= 0 or type(timestamp) is not int:
            continue
        if not isinstance(headline, str) or not isinstance(url, str):
            continue
        title = strip_html(headline)
        summary = strip_html(summary) if isinstance(summary, str) else ""
        if not title or not matches_gold(title, summary):
            continue
        try:
            published_at = datetime.fromtimestamp(timestamp, UTC)
            if not is_http_url(url):
                continue
            url = normalize_url(url)
        except (ValueError, OverflowError, OSError):
            continue
        if timestamp <= 0 or published_at > now or len(url) > 2000:
            continue
        rows.append(
            {
                "source_key": "finnhub",
                "external_id": str(article_id),
                "url": url,
                "title": clip(title, 500),
                "summary": clip(summary) or None,
                "published_at": published_at,
                "language": "en",
                "instruments": [{"symbol": GOLD_SYMBOL}],
            }
        )
    return rows


async def fetch_category(
    client: httpx.AsyncClient, category: str, api_key: str, now: datetime
) -> list[dict[str, Any]]:
    settings = get_settings()
    try:
        async with asyncio.timeout(settings.news_fetch_timeout_seconds):
            async with client.stream(
                "GET", URL, params={"category": category}, headers={"X-Finnhub-Token": api_key}
            ) as response:
                if response.status_code != 200:
                    raise FeedError(f"HTTP {response.status_code}")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > settings.news_fetch_max_bytes:
                        raise FeedError("response exceeds the news size limit")
        rows = parse_articles(json.loads(body), now)
    except (TimeoutError, httpx.HTTPError, ValueError) as exc:
        raise FeedError(type(exc).__name__) from None
    unique = {}
    for row in sorted(rows, key=lambda article: article["published_at"], reverse=True):
        unique.setdefault(row["external_id"], row)
    return list(unique.values())[:MAX_INGEST_ITEMS]
