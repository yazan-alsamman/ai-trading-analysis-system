"""News: the ingestion API (idempotency, per-item errors, tags, sentiment push, news:write),
reading (filters, search, tags), the sentiment aggregate, sources, retention, the tagger and
the news WebSocket topics."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.instrument import MarketType
from app.models.news import NewsArticle, NewsArticleInstrument, NewsSource
from app.models.user import UserRole
from app.news import service
from app.news.tagger import Tagger
from app.realtime.topics import news_topic
from tests.api_key_utils import create_key, xkey
from tests.market_utils import make_instrument
from tests.test_signal_engine import Listener
from tests.utils import bearer

INGEST = "/api/v1/ingest/news"
NEWS = "/api/v1/news"
NOW = datetime.now(UTC).replace(microsecond=0)


def article(external_id: str = "a1", **over) -> dict:
    body = {
        "source_key": "finnhub",
        "external_id": external_id,
        "url": f"https://news.example.com/{external_id}",
        "title": f"Bitcoin rallies {external_id}",
        "summary": "<p>Markets <b>rose</b> &amp; fell.</p>",
        "published_at": (NOW - timedelta(minutes=5)).isoformat(),
    }
    body.update(over)
    return body


@pytest.fixture
async def admin(make_user):
    user = await make_user("admin@example.com", role=UserRole.admin)
    return user, bearer(create_access_token(user))


@pytest.fixture
async def writer(client: AsyncClient, admin) -> dict[str, str]:
    """An admin's API key with news:write (what the AI side uses)."""
    key = await create_key(client, admin[1], scopes=("news:write", "news:read"))
    return xkey(key["key"])


@pytest.fixture
async def markets(session: AsyncSession):
    btc = await make_instrument(session, "BTC/USDT", price_precision=2)
    eth = await make_instrument(session, "ETH/USDT")
    eur = await make_instrument(session, "EUR/USD", source="twelvedata", market=MarketType.forex)
    return btc, eth, eur


# --- ingestion -----------------------------------------------------------------------------------


async def test_ingest_is_idempotent_and_reports_counts(
    client: AsyncClient, session: AsyncSession, writer, markets
) -> None:
    batch = [article("a1"), article("a2", title="Ethereum upgrade ships")]
    res = await client.post(INGEST, json={"articles": batch}, headers=writer)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "inserted": 2,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "warnings": [],
    }
    # same batch again: nothing changes
    res = await client.post(INGEST, json={"articles": batch}, headers=writer)
    assert res.json()["skipped"] == 2 and res.json()["inserted"] == 0
    # a changed title is an update
    batch[0]["title"] = "Bitcoin rallies again"
    res = await client.post(INGEST, json={"articles": batch}, headers=writer)
    assert (res.json()["updated"], res.json()["skipped"]) == (1, 1)
    rows = (await session.scalars(select(NewsArticle).order_by(NewsArticle.external_id))).all()
    assert [r.title for r in rows] == ["Bitcoin rallies again", "Ethereum upgrade ships"]
    assert rows[0].summary == "Markets rose & fell."  # HTML stripped, entities decoded
    source = await session.scalar(select(NewsSource).where(NewsSource.key == "finnhub"))
    assert source.kind == "api"  # registered on first use
    # the built-in tagger tagged the new articles
    btc, eth, _ = markets
    tags = dict(
        (
            await session.execute(
                select(NewsArticleInstrument.article_id, NewsArticleInstrument.instrument_id)
            )
        ).all()
    )
    assert tags == {rows[0].id: btc.id, rows[1].id: eth.id}


async def test_ingest_per_item_errors_keep_the_rest(client: AsyncClient, writer, markets) -> None:
    batch = [
        article("ok1"),
        article("bad-url", url="javascript:alert(1)"),
        {"source_key": "finnhub", "external_id": "no-title", "url": "https://x.io/a"},
        article("score", sentiment={"label": "positive", "score": 3, "model": "m"}),
        article("dup"),
        article("dup", title="the later copy wins"),
        article("tags", instruments=[{"symbol": "ETH", "relevance": 0.8}, {"symbol": "NOPE"}]),
    ]
    res = await client.post(INGEST, json={"articles": batch}, headers=writer)
    body = res.json()
    assert res.status_code == 200
    assert body["inserted"] == 3  # ok1, the later dup, tags
    errors = {e["index"]: e["error"] for e in body["errors"]}
    assert set(errors) == {1, 2, 3, 4}
    assert "http(s)" in errors[1] and "title" in errors[2] and "score" in errors[3]
    assert "duplicate" in errors[4]
    assert body["warnings"] == [
        {"index": 6, "external_id": "tags", "error": "unknown symbols ignored: NOPE"}
    ]


async def test_explicit_tags_and_sentiment_replace_stored_ones(
    client: AsyncClient, session: AsyncSession, writer, markets
) -> None:
    btc, eth, eur = markets
    await client.post(INGEST, json={"articles": [article("t1")]}, headers=writer)
    retag = article(
        "t1",
        instruments=[{"symbol": "EUR/USD", "relevance": 0.5}],
        sentiment={"label": "negative", "score": -0.7, "model": "finbert-ft-v1"},
    )
    res = await client.post(INGEST, json={"articles": [retag]}, headers=writer)
    assert res.json()["updated"] == 1
    row = await session.scalar(
        select(NewsArticle)
        .where(NewsArticle.external_id == "t1")
        .execution_options(populate_existing=True)
    )
    assert (row.sentiment_label, row.sentiment_score, row.sentiment_model) == (
        "negative",
        -0.7,
        "finbert-ft-v1",
    )
    tags = (
        await session.execute(
            select(NewsArticleInstrument.instrument_id, NewsArticleInstrument.relevance).where(
                NewsArticleInstrument.article_id == row.id
            )
        )
    ).all()
    assert tags == [(eur.id, 0.5)]
    # an update without sentiment keeps it; without instruments keeps the tags
    res = await client.post(
        INGEST, json={"articles": [article("t1", title="new title")]}, headers=writer
    )
    await session.refresh(row)
    assert row.sentiment_label == "negative" and row.title == "new title"


async def test_sentiment_push(client: AsyncClient, session: AsyncSession, writer, markets) -> None:
    await client.post(INGEST, json={"articles": [article("s1"), article("s2")]}, headers=writer)
    s1 = await session.scalar(select(NewsArticle.id).where(NewsArticle.external_id == "s1"))
    items = [
        {"article_id": str(s1), "label": "positive", "score": 0.9, "model": "finbert"},
        {
            "source_key": "finnhub",
            "external_id": "s2",
            "label": "neutral",
            "score": 0.05,
            "model": "finbert",
        },
        {"article_id": str(uuid.uuid4()), "label": "neutral", "score": 0, "model": "finbert"},
        {"label": "neutral", "score": 0, "model": "finbert"},
    ]
    res = await client.post(f"{INGEST}/sentiment", json={"items": items}, headers=writer)
    assert res.status_code == 200
    body = res.json()
    assert body["updated"] == 2
    assert [(e["index"], e["error"]) for e in body["errors"]] == [
        (2, "article not found"),
        (3, "Value error, give either article_id or source_key + external_id"),
    ]
    rows = dict(
        (
            await session.execute(
                select(NewsArticle.external_id, NewsArticle.sentiment_label).execution_options(
                    populate_existing=True
                )
            )
        ).all()
    )
    assert rows == {"s1": "positive", "s2": "neutral"}


async def test_news_write_is_admin_only(
    client: AsyncClient, make_user, login, admin, markets
) -> None:
    await make_user("analyst@example.com", role=UserRole.analyst)
    analyst = bearer((await login("analyst@example.com"))["access_token"])
    res = await client.post(
        "/api/v1/me/api-keys", json={"name": "x", "scopes": ["news:write"]}, headers=analyst
    )
    assert res.status_code == 403 and "news:write" in res.json()["detail"]
    key = await create_key(client, analyst, scopes=("news:read",))
    res = await client.patch(
        f"/api/v1/me/api-keys/{key['id']}", json={"scopes": ["news:write"]}, headers=analyst
    )
    assert res.status_code == 403
    # a news:read key cannot ingest; a logged-in non-admin neither
    assert (
        await client.post(INGEST, json={"articles": [article()]}, headers=xkey(key["key"]))
    ).status_code == 403
    assert (
        await client.post(INGEST, json={"articles": [article()]}, headers=analyst)
    ).status_code == 403
    # but it reads news
    assert (await client.get(NEWS, headers=xkey(key["key"]))).status_code == 200
    # the scope list for the key form
    scopes = {
        s["scope"]: s
        for s in (await client.get("/api/v1/me/api-keys/scopes", headers=analyst)).json()
    }
    assert scopes["news:write"]["admin_only"] and not scopes["news:write"]["grantable"]
    assert scopes["news:read"]["grantable"]
    admin_scopes = (await client.get("/api/v1/me/api-keys/scopes", headers=admin[1])).json()
    assert all(s["grantable"] for s in admin_scopes)


async def test_a_demoted_admin_key_stops_working(
    client: AsyncClient, session: AsyncSession, admin, writer, markets
) -> None:
    user, _ = admin
    await session.execute(update(type(user)).where(type(user).id == user.id).values(role="analyst"))
    await session.commit()
    res = await client.post(INGEST, json={"articles": [article()]}, headers=writer)
    assert res.status_code == 403


async def test_disabled_source_rejects_items(
    client: AsyncClient, session: AsyncSession, writer, admin, markets
) -> None:
    await client.post(INGEST, json={"articles": [article("d1")]}, headers=writer)
    source = await session.scalar(select(NewsSource).where(NewsSource.key == "finnhub"))
    res = await client.patch(
        f"/api/v1/admin/news/sources/{source.id}",
        json={"is_active": False, "fetch_interval_minutes": 30},
        headers=admin[1],
    )
    assert res.status_code == 200
    assert (res.json()["is_active"], res.json()["fetch_interval_minutes"]) == (False, 30)
    assert res.json()["articles"] == 1
    res = await client.post(INGEST, json={"articles": [article("d2")]}, headers=writer)
    assert res.json()["errors"][0]["error"] == "source is disabled"
    bad = await client.patch(
        f"/api/v1/admin/news/sources/{source.id}",
        json={"fetch_interval_minutes": 1},
        headers=admin[1],
    )
    assert bad.status_code == 422


# --- reading -------------------------------------------------------------------------------------


async def test_list_filters_and_search(client: AsyncClient, writer, admin, markets) -> None:
    btc, eth, _ = markets
    batch = [
        article(
            "r1",
            title="Bitcoin ETF inflows hit record",
            published_at=(NOW - timedelta(hours=1)).isoformat(),
            sentiment={"label": "positive", "score": 0.8, "model": "m"},
        ),
        article(
            "r2",
            title="Ethereum gas fees fall",
            language="en",
            published_at=(NOW - timedelta(hours=2)).isoformat(),
            sentiment={"label": "negative", "score": -0.4, "model": "m"},
        ),
        article(
            "r3",
            title="ارتفاع البيتكوين اليوم",
            summary="خبر",
            language="ar",
            published_at=(NOW - timedelta(days=3)).isoformat(),
        ),
    ]
    await client.post(INGEST, json={"articles": batch}, headers=writer)
    h = admin[1]
    res = await client.get(NEWS, headers=h)
    assert [a["title"] for a in res.json()["items"]][:3] == [
        "Bitcoin ETF inflows hit record",
        "Ethereum gas fees fall",
        "ارتفاع البيتكوين اليوم",
    ]
    first = res.json()["items"][0]
    assert first["source"] == {"key": "finnhub", "name": "finnhub"}
    assert first["sentiment"]["label"] == "positive"
    assert first["instruments"] == [
        {"instrument_id": str(btc.id), "symbol": "BTC/USDT", "relevance": 1.0}
    ]

    async def titles(**params):
        r = await client.get(NEWS, params=params, headers=h)
        assert r.status_code == 200, r.text
        return [a["title"] for a in r.json()["items"]]

    assert await titles(instrument_id=str(btc.id)) == [
        "Bitcoin ETF inflows hit record",
        "ارتفاع البيتكوين اليوم",  # Arabic name with the "ال" prefix
    ]
    assert await titles(sentiment="negative") == ["Ethereum gas fees fall"]
    assert await titles(language="ar") == ["ارتفاع البيتكوين اليوم"]
    assert await titles(since=(NOW - timedelta(hours=1, minutes=30)).isoformat()) == [
        "Bitcoin ETF inflows hit record"
    ]
    assert await titles(q="etf record") == ["Bitcoin ETF inflows hit record"]
    assert await titles(q='"gas fees"') == ["Ethereum gas fees fall"]
    assert await titles(q="bitcoin -etf") == []
    assert await titles(q="البيتكوين") == ["ارتفاع البيتكوين اليوم"]
    assert await titles(source="coindesk_rss") == []

    one = await client.get(f"{NEWS}/{first['id']}", headers=h)
    assert one.status_code == 200 and one.json()["id"] == first["id"]
    assert (await client.get(f"{NEWS}/{uuid.uuid4()}", headers=h)).status_code == 404


async def test_search_uses_the_gin_index(session: AsyncSession) -> None:
    await session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(
        r[0]
        for r in (
            await session.execute(
                text(
                    "EXPLAIN SELECT id FROM news_articles WHERE "
                    "to_tsvector('simple', title || ' ' || coalesce(summary, '')) "
                    "@@ websearch_to_tsquery('simple', 'bitcoin')"
                )
            )
        ).all()
    )
    assert "ix_news_articles_search" in plan


async def test_sentiment_aggregate(client: AsyncClient, writer, admin, markets) -> None:
    btc, eth, _ = markets

    def a(eid, label, score, symbols, hours_ago):
        return article(
            eid,
            title=f"Market note {eid}",
            published_at=(NOW - timedelta(hours=hours_ago)).isoformat(),
            sentiment=None if label is None else {"label": label, "score": score, "model": "m"},
            instruments=[{"symbol": s, "relevance": r} for s, r in symbols],
        )

    batch = [
        a("g1", "positive", 0.8, [("BTC/USDT", 1.0)], 0.5),
        a("g2", "negative", -0.4, [("BTC/USDT", 0.5), ("ETH/USDT", 1.0)], 2),
        a("g3", None, None, [("BTC/USDT", 1.0)], 3),  # unscored: counted, not averaged
        a("g4", "neutral", 0.0, [("ETH/USDT", 1.0)], 30),  # outside 24h
    ]
    res = await client.post(INGEST, json={"articles": batch}, headers=writer)
    assert res.json()["errors"] == []
    agg = (await client.get(f"{NEWS}/sentiment", params={"window": "24h"}, headers=admin[1])).json()
    assert agg["window"] == "24h"
    assert agg["overall"] == {
        "articles": 3,
        "scored": 2,
        "positive": 1,
        "neutral": 0,
        "negative": 1,
        "mean_score": 0.2,
        "weighted_score": None,
    }
    per = {i["symbol"]: i for i in agg["instruments"]}
    assert per["BTC/USDT"]["articles"] == 3 and per["BTC/USDT"]["scored"] == 2
    assert per["BTC/USDT"]["mean_score"] == 0.2
    # weighted by relevance: (0.8*1 + -0.4*0.5) / (1 + 0.5) = 0.4
    assert per["BTC/USDT"]["weighted_score"] == 0.4
    assert (per["ETH/USDT"]["articles"], per["ETH/USDT"]["mean_score"]) == (1, -0.4)
    one_hour = (
        await client.get(
            f"{NEWS}/sentiment",
            params={"window": "1h", "instrument_id": str(btc.id)},
            headers=admin[1],
        )
    ).json()
    assert [i["symbol"] for i in one_hour["instruments"]] == ["BTC/USDT"]
    assert one_hour["overall"]["articles"] == 1 and one_hour["overall"]["mean_score"] == 0.8
    week = (await client.get(f"{NEWS}/sentiment?window=7d", headers=admin[1])).json()
    assert week["overall"]["articles"] == 4
    assert (await client.get(f"{NEWS}/sentiment?window=2d", headers=admin[1])).status_code == 422


async def test_sources_list(client: AsyncClient, admin, trader_headers) -> None:
    res = await client.get(f"{NEWS}/sources", headers=trader_headers)
    keys = {s["key"]: s for s in res.json()}
    assert {"coindesk_rss", "cointelegraph_rss", "investinglive_rss"} <= set(keys)
    assert keys["coindesk_rss"]["kind"] == "rss" and keys["coindesk_rss"]["is_active"]
    res = await client.patch(
        f"/api/v1/admin/news/sources/{keys['coindesk_rss']['id']}",
        json={"is_active": False},
        headers=trader_headers,
    )
    assert res.status_code == 403


async def test_retention(session_factory, session: AsyncSession, monkeypatch) -> None:
    source = await session.scalar(select(NewsSource).where(NewsSource.key == "coindesk_rss"))
    for i, days in enumerate((10, 179, 181, 400)):
        session.add(
            NewsArticle(
                source_id=source.id,
                external_id=f"old{i}",
                url=f"https://x.io/{i}",
                title="t",
                published_at=NOW - timedelta(days=days),
            )
        )
    await session.commit()
    assert await service.cleanup(session_factory, now=NOW, batch=1) == 2
    left = (await session.scalars(select(NewsArticle.external_id))).all()
    assert sorted(left) == ["old0", "old1"]


# --- tagger --------------------------------------------------------------------------------------


def test_tagger_rules() -> None:
    ids = [uuid.uuid4() for _ in range(5)]
    tagger = Tagger.build(
        [
            (ids[0], "BTC/USDT", "BTC", MarketType.crypto),
            (ids[1], "ETH/USDT", "ETH", MarketType.crypto),
            (ids[2], "EUR/USD", "EUR", MarketType.forex),
            (ids[3], "XAU/USD", "XAU", MarketType.commodity),
            (ids[4], "DOGE/USDT", "DOGE", MarketType.crypto),  # not in the alias map
        ]
    )
    assert tagger.tag("BTC breaks 70k", None) == {ids[0]: 1.0}
    assert tagger.tag("Bitcoins and ether", None) == {ids[0]: 1.0, ids[1]: 1.0}
    assert tagger.tag("Whether markets move", "nothing") == {}  # 'ether' inside a word
    assert tagger.tag("btcusd lower case code", None) == {}  # codes are case-sensitive
    assert tagger.tag("Fed decision", "EUR/USD slides; Gold up") == {ids[2]: 0.6, ids[3]: 0.6}
    assert tagger.tag("Europe stocks", None) == {}
    assert tagger.tag("الذهب يرتفع وبيتكوين", None) == {ids[3]: 1.0, ids[0]: 1.0}
    assert tagger.tag("DOGE pumps", None) == {ids[4]: 1.0}


# --- WebSocket topics ----------------------------------------------------------------------------


async def test_new_articles_are_published_on_news_topics(
    client: AsyncClient, redis_client: Redis, writer, markets
) -> None:
    btc, _, _ = markets
    async with Listener(redis_client) as listener:
        await listener.listen(news_topic(), news_topic(btc.id))
        old = article("old", published_at=(NOW - timedelta(days=2)).isoformat())
        await client.post(INGEST, json={"articles": [article("live"), old]}, headers=writer)
        await client.post(INGEST, json={"articles": [article("live")]}, headers=writer)  # skip
        messages = await listener.messages()
    assert sorted(t for t, _ in messages) == sorted([news_topic(), news_topic(btc.id)])
    msg = messages[0][1]
    assert msg["type"] == "news"
    assert msg["article"]["title"] == "Bitcoin rallies live"
    assert msg["article"]["instruments"][0]["symbol"] == "BTC/USDT"
    assert msg["article"]["source"] == {"key": "finnhub", "name": "finnhub"}
