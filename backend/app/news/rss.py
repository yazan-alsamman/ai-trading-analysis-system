"""The built-in RSS/Atom fetcher: conditional GET, 10 s for the whole request, 2 MB at most,
parsed with feedparser (from bytes, so it never fetches anything itself)."""

from __future__ import annotations

import asyncio
import calendar
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

from app.core.config import get_settings
from app.models.news import NewsSource
from app.news.text import clip, is_http_url, normalize_url, strip_html, url_id

logger = logging.getLogger(__name__)

USER_AGENT = "AI-Trading-Platform-NewsBot/1.0 (+RSS reader; contact: admin)"
ACCEPT = "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8"
MAX_ITEMS = 200  # per feed and fetch


class FeedError(Exception):
    """Why a feed could not be read (stored in ``news_sources.last_error``)."""


@dataclass
class FeedResult:
    status: str  # ok | not_modified | error
    items: list[dict[str, Any]] = field(default_factory=list)
    etag: str | None = None
    last_modified: str | None = None
    error: str | None = None


async def download(
    client: httpx.AsyncClient, source: NewsSource
) -> tuple[int, bytes, httpx.Headers]:
    """(status, body, headers). Raises FeedError on timeouts, oversize bodies and HTTP errors."""
    settings = get_settings()
    limit = settings.news_fetch_max_bytes
    headers = {"User-Agent": USER_AGENT, "Accept": ACCEPT}
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        headers["If-Modified-Since"] = source.last_modified
    try:
        # one deadline for the whole request: a server dripping bytes cannot hold the task
        async with asyncio.timeout(settings.news_fetch_timeout_seconds):
            async with client.stream("GET", source.url, headers=headers) as response:
                if response.status_code == 304:
                    return 304, b"", response.headers
                if response.status_code != 200:
                    raise FeedError(f"HTTP {response.status_code}")
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > limit:
                    raise FeedError(f"feed larger than {limit} bytes")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > limit:
                        raise FeedError(f"feed larger than {limit} bytes")
                return 200, bytes(body), response.headers
    except TimeoutError:
        raise FeedError(f"timeout after {settings.news_fetch_timeout_seconds:g}s") from None
    except httpx.HTTPError as exc:
        raise FeedError(f"{type(exc).__name__}") from None


def _when(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), UTC)
    return None


def _image(entry: Any) -> str | None:
    for item in entry.get("media_content") or []:
        url = item.get("url")
        if is_http_url(url) and (
            item.get("medium") == "image" or str(item.get("type", "")).startswith("image/")
        ):
            return url
    for item in entry.get("media_thumbnail") or []:
        if is_http_url(item.get("url")):
            return item["url"]
    for item in entry.get("enclosures") or []:
        if str(item.get("type", "")).startswith("image/") and is_http_url(item.get("href")):
            return item["href"]
    return None


def _summary(entry: Any) -> str | None:
    raw = entry.get("summary") or entry.get("description")
    if not raw and entry.get("content"):
        raw = entry["content"][0].get("value")
    text = strip_html(raw)
    return clip(text) if text else None


def _language(feed: Any, fallback: str) -> str:
    value = str(feed.get("language") or "").strip().lower()
    return (value.split("-")[0] or fallback)[:8] if value else fallback


def parse(body: bytes, source: NewsSource, now: datetime | None = None) -> list[dict[str, Any]]:
    """Article rows (without ``source_id``) from a feed body; entries without a usable link
    or title are left out. Raises FeedError when nothing can be parsed."""
    now = now or datetime.now(UTC)
    parsed = feedparser.parse(body)
    if not parsed.entries and parsed.bozo:
        raise FeedError(f"unparsable feed ({type(parsed.bozo_exception).__name__})")
    language = _language(parsed.feed, source.language)
    rows, seen = [], set()
    for entry in parsed.entries[:MAX_ITEMS]:
        link = entry.get("link")
        title = clip(strip_html(entry.get("title")), 500)
        if not is_http_url(link) or not title:
            continue
        external_id = url_id(link)
        if external_id in seen:
            continue
        seen.add(external_id)
        published = _when(entry) or now
        rows.append(
            {
                "external_id": external_id,
                "url": normalize_url(link)[:2000],
                "title": title,
                "summary": _summary(entry),
                "image_url": (_image(entry) or "")[:2000] or None,
                "author": (strip_html(entry.get("author")) or "")[:200] or None,
                "language": language,
                "published_at": min(published, now),  # no articles from the future
            }
        )
    return rows


async def fetch(client: httpx.AsyncClient, source: NewsSource) -> FeedResult:
    try:
        status, body, headers = await download(client, source)
        if status == 304:
            return FeedResult("not_modified", etag=source.etag, last_modified=source.last_modified)
        # parsing a 2 MB feed takes a few hundred ms of CPU: keep it off the event loop
        items = await asyncio.to_thread(parse, body, source)
    except FeedError as exc:
        return FeedResult("error", error=str(exc)[:500])
    except Exception as exc:  # noqa: BLE001 - one broken feed must not stop the others
        logger.exception("news: feed %s failed", source.key)
        return FeedResult("error", error=f"{type(exc).__name__}"[:500])
    return FeedResult(
        "ok",
        items=items,
        etag=(headers.get("etag") or None),
        last_modified=(headers.get("last-modified") or None),
    )
