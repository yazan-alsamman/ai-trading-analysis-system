"""The built-in RSS fetcher on fixture feeds (no network): parsing (HTML stripped, URLs
normalised, Atom), conditional GET (ETag / Last-Modified -> 304), timeout, size limit, errors
stored on the source, idempotent re-fetch, due intervals and the disabled setting."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.news import NewsArticle, NewsArticleInstrument, NewsSource, NewsSourceKind
from app.news import rss, service
from app.news.text import normalize_url, strip_html, url_id
from app.tasks import news as news_tasks
from tests.market_utils import make_instrument

FEED_URL = "https://feeds.test/rss"
NOW = datetime.now(UTC).replace(microsecond=0)


def rss_feed(items: str = "") -> bytes:
    published = (NOW - timedelta(minutes=10)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Test feed</title><language>en-us</language>
<item>
  <title>Bitcoin &lt;b&gt;jumps&lt;/b&gt; 5%</title>
  <link>https://News.Test/markets/btc-jumps/?utm_source=rss&amp;utm_medium=feed&amp;id=7#top</link>
  <description><![CDATA[<p>BTC rose <script>alert(1)</script>after the
    <a href="x">Fed</a>.</p>]]></description>
  <pubDate>{published}</pubDate>
  <author>Jane Doe</author>
  <media:content url="https://img.test/btc.jpg" medium="image"/>
</item>
<item>
  <title>Gold steadies</title>
  <link>https://news.test/gold?fbclid=abc</link>
  <description>Plain text summary</description>
</item>
<item><title>No link</title></item>
<item><title>Bad link</title><link>javascript:alert(1)</link></item>
{items}
</channel></rss>""".encode()


ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title>
<entry><title>Ethereum upgrade</title><link href="https://atom.test/eth"/>
<updated>2026-10-16T10:00:00Z</updated><summary type="html">&lt;i&gt;ETH&lt;/i&gt; news</summary>
</entry></feed>"""


class FakeFeeds:
    """Answers feed requests like a server: ETag / 304, slow or huge bodies on demand."""

    def __init__(self, body: bytes = b"", etag: str = '"v1"') -> None:
        self.body, self.etag = body, etag
        self.requests: list[httpx.Request] = []
        self.status = 200
        self.delay = 0.0
        self.chunked_size: int | None = None

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if request.headers.get("if-none-match") == self.etag:
            return httpx.Response(304)
        if self.chunked_size is not None:

            async def stream():
                for _ in range(self.chunked_size // 65536 + 1):
                    yield b"x" * 65536

            return httpx.Response(200, content=stream())
        return httpx.Response(
            self.status,
            content=self.body,
            headers={"ETag": self.etag, "Last-Modified": "Fri, 16 Oct 2026 10:00:00 GMT"},
        )


@pytest.fixture
def feeds(monkeypatch) -> FakeFeeds:
    fake = FakeFeeds(rss_feed())
    monkeypatch.setattr(service, "transport", httpx.MockTransport(fake.handler))
    return fake


@pytest.fixture
async def source(session: AsyncSession) -> NewsSource:
    # the seeded public feeds are not fetched in tests
    await session.execute(update(NewsSource).values(is_active=False))
    row = NewsSource(key="test_rss", name="Test", kind=NewsSourceKind.rss, url=FEED_URL)
    session.add(row)
    await session.commit()
    return row


def test_text_helpers() -> None:
    assert strip_html("<p>a <b>b</b><br>c &amp; d<style>x{}</style></p>") == "a b c & d"
    assert (
        normalize_url("HTTPS://Example.COM:443/a/b/?utm_campaign=x&b=2&a=1&gclid=z#frag")
        == "https://example.com/a/b?a=1&b=2"
    )
    assert normalize_url("http://example.com/") == "http://example.com"
    assert url_id("https://example.com/a?utm_source=x") == url_id("https://EXAMPLE.com/a/")


def test_parse_rss_and_atom() -> None:
    src = NewsSource(key="t", name="t", url=FEED_URL, language="ar")
    items = rss.parse(rss_feed(), src, now=NOW)
    assert [i["title"] for i in items] == ["Bitcoin jumps 5%", "Gold steadies"]
    btc = items[0]
    assert btc["url"] == "https://news.test/markets/btc-jumps?id=7"
    assert btc["external_id"] == url_id("https://news.test/markets/btc-jumps?id=7")
    assert btc["summary"] == "BTC rose after the Fed."
    assert btc["image_url"] == "https://img.test/btc.jpg"
    assert btc["author"] == "Jane Doe"
    assert btc["language"] == "en"  # the feed's language wins over the source's
    assert btc["published_at"] == NOW - timedelta(minutes=10)
    assert items[1]["url"] == "https://news.test/gold"
    assert items[1]["published_at"] == NOW  # no date: the fetch time
    [eth] = rss.parse(ATOM, src, now=NOW)
    assert (eth["title"], eth["summary"], eth["language"]) == ("Ethereum upgrade", "ETH news", "ar")
    with pytest.raises(rss.FeedError, match="unparsable"):
        rss.parse(b"<html><body>not a feed", src)


def test_long_summaries_are_clipped() -> None:
    long = "word " * 1000
    feed = rss_feed(
        f"<item><title>Long</title><link>https://x.test/l</link>"
        f"<description>{long}</description></item>"
    )
    item = next(i for i in rss.parse(feed, NewsSource(language="en")) if i["title"] == "Long")
    assert len(item["summary"]) <= 2000 and item["summary"].endswith("…")


async def test_fetch_due_stores_tags_and_uses_etag(
    session_factory, session: AsyncSession, redis_client, feeds: FakeFeeds, source: NewsSource
) -> None:
    btc = await make_instrument(session, "BTC/USDT")
    report = await service.fetch_due(session_factory, redis_client, now=NOW)
    assert report == {
        "test_rss": {
            "status": "ok",
            "items": 2,
            "inserted": 2,
            "updated": 0,
            "skipped": 0,
            "published": 3,  # 2 on "news" + 1 on "news:{btc}"
        }
    }
    await session.refresh(source)
    assert (source.etag, source.last_error, source.last_fetched_at) == ('"v1"', None, NOW)
    tags = (await session.execute(select(NewsArticleInstrument.instrument_id))).scalars().all()
    assert tags == [btc.id]
    # not due again before the interval
    assert await service.fetch_due(session_factory, redis_client, now=NOW) == {}
    # due later: the server answers 304 to If-None-Match
    later = NOW + timedelta(minutes=15)
    report = await service.fetch_due(session_factory, redis_client, now=later)
    assert report["test_rss"]["status"] == "not_modified"
    assert feeds.requests[-1].headers["if-none-match"] == '"v1"'
    assert feeds.requests[-1].headers["if-modified-since"] == "Fri, 16 Oct 2026 10:00:00 GMT"
    # a new version of the feed: the same articles are skipped, idempotently
    feeds.etag = '"v2"'
    report = await service.fetch_due(
        session_factory, redis_client, now=later + timedelta(minutes=15)
    )
    assert (report["test_rss"]["inserted"], report["test_rss"]["skipped"]) == (0, 2)
    count = len((await session.scalars(select(NewsArticle.id))).all())
    assert count == 2


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        (lambda f: setattr(f, "status", 503), "HTTP 503"),
        (lambda f: setattr(f, "delay", 0.5), "timeout after 0.2s"),
        (lambda f: setattr(f, "chunked_size", 300_000), "feed larger than 100000 bytes"),
        (lambda f: setattr(f, "body", b"x" * 200_000), "feed larger than 100000 bytes"),
    ],
)
async def test_feed_errors_are_stored(
    session_factory, session, redis_client, feeds: FakeFeeds, source, monkeypatch, setup, error
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "news_fetch_timeout_seconds", 0.2)
    monkeypatch.setattr(settings, "news_fetch_max_bytes", 100_000)
    setup(feeds)
    report = await service.fetch_due(session_factory, redis_client, now=NOW)
    assert report["test_rss"] == {"status": "error", "error": error, "published": 0}
    await session.refresh(source)
    assert source.last_error == error and source.last_fetched_at == NOW


async def test_task_respects_the_setting(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "news_rss_enabled", False)
    assert news_tasks.fetch.run() == {"disabled": True}
