"""Storing, reading and publishing news.

Every article goes through :func:`upsert`, idempotent on ``(source_id, external_id)``: a new
article is inserted (and tagged), a changed one updated, an identical one skipped. Articles
pushed by the AI side may carry their own instrument tags (they replace the article's tags) and
a sentiment; the built-in tagger tags new articles that come without tags.

New, recent articles are published on the ``news`` and ``news:{instrument_id}`` topics after
the commit.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import (
    and_,
    bindparam,
    case,
    delete,
    exists,
    func,
    literal_column,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.instrument import Instrument
from app.models.news import (
    SEARCH_VECTOR,
    NewsArticle,
    NewsArticleInstrument,
    NewsSource,
    NewsSourceKind,
    SentimentLabel,
)
from app.news import rss
from app.news.tagger import Tagger
from app.news.text import clip, strip_html
from app.realtime import publisher
from app.realtime.topics import channel_for, news_topic
from app.schemas.news import ArticleIn, ItemError, SentimentItemIn

logger = logging.getLogger(__name__)

LIVE_WINDOW = timedelta(hours=24)  # older articles (backfills, first fetch) are not pushed live
LIVE_MAX = 50  # articles pushed per batch at most
FETCH_CONCURRENCY = 4
WINDOWS = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7)}
CONTENT = ("url", "title", "summary", "image_url", "author", "language", "published_at")

transport: httpx.AsyncBaseTransport | None = None  # tests inject a mock transport


# --- writing -------------------------------------------------------------------------------------


@dataclass
class Upserted:
    inserted: list[uuid.UUID] = field(default_factory=list)
    updated: list[uuid.UUID] = field(default_factory=list)
    skipped: int = 0
    live: list[dict[str, Any]] = field(default_factory=list)  # to publish after the commit


async def upsert(
    session: AsyncSession,
    source_id: uuid.UUID,
    rows: list[dict[str, Any]],
    *,
    tags: dict[str, dict[uuid.UUID, float]] | None = None,
    tagger: Tagger | None = None,
    now: datetime | None = None,
    keep_published: bool = False,
) -> Upserted:
    """Upsert articles of one source (unique ``external_id`` within ``rows``). ``tags``:
    external id -> explicit tags (replace the stored ones); other new articles are tagged by
    ``tagger``. Sentiment fields in a row overwrite the stored ones, absent ones keep them.
    ``keep_published``: the stored ``published_at`` is kept (RSS items without a date get the
    fetch time, which must not turn every re-fetch into an update)."""
    out = Upserted()
    if not rows:
        return out
    now = now or datetime.now(UTC)
    tags = tags or {}
    table = NewsArticle.__table__
    values = []
    for row in rows:
        values.append(
            {
                "id": uuid.uuid4(),
                "source_id": source_id,
                "sentiment_label": None,
                "sentiment_score": None,
                "sentiment_model": None,
                "sentiment_at": None,
                **row,
                "fetched_at": now,
            }
        )
    content = [c for c in CONTENT if not (keep_published and c == "published_at")]
    stmt = insert(table)
    excluded = stmt.excluded
    has_sentiment = excluded.sentiment_label.is_not(None)
    changed = or_(
        tuple_(*(table.c[c] for c in content)).is_distinct_from(
            tuple_(*(excluded[c] for c in content))
        ),
        and_(
            has_sentiment,
            tuple_(
                table.c.sentiment_label, table.c.sentiment_score, table.c.sentiment_model
            ).is_distinct_from(
                tuple_(excluded.sentiment_label, excluded.sentiment_score, excluded.sentiment_model)
            ),
        ),
    )
    keep = {
        c: case((has_sentiment, excluded[c]), else_=table.c[c])
        for c in ("sentiment_label", "sentiment_score", "sentiment_model", "sentiment_at")
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_news_articles_source_external",
        set_={**{c: excluded[c] for c in content}, **keep, "fetched_at": excluded.fetched_at},
        where=changed,
    ).returning(table.c.id, table.c.external_id, literal_column("(xmax = 0)").label("inserted"))
    result = (await session.execute(stmt, values)).all()
    by_external = {r.external_id: r for r in result}
    stored_ids: dict[str, uuid.UUID] = {r.external_id: r.id for r in result}
    out.skipped = len(rows) - len(result)

    # explicit tags of skipped (unchanged) articles still apply: find their ids
    missing = [e for e in tags if e not in stored_ids]
    if missing:
        found = await session.execute(
            select(NewsArticle.external_id, NewsArticle.id).where(
                NewsArticle.source_id == source_id, NewsArticle.external_id.in_(missing)
            )
        )
        stored_ids.update(dict(found.all()))
    retagged = await _replace_tags(
        session, {stored_ids[e]: t for e, t in tags.items() if e in stored_ids}
    )

    new_rows = {r.external_id: r for r in result if r.inserted}
    auto: dict[uuid.UUID, dict[uuid.UUID, float]] = {}
    if tagger is not None:
        for row in rows:
            if row["external_id"] in new_rows and row["external_id"] not in tags:
                found_tags = tagger.tag(row["title"], row.get("summary"))
                if found_tags:
                    auto[new_rows[row["external_id"]].id] = found_tags
        await _insert_tags(session, auto)

    for row in rows:
        r = by_external.get(row["external_id"])
        if r is not None:
            (out.inserted if r.inserted else out.updated).append(r.id)
        elif stored_ids.get(row["external_id"]) in retagged:
            out.updated.append(stored_ids[row["external_id"]])
            out.skipped -= 1
        if r is not None and r.inserted and row["published_at"] >= now - LIVE_WINDOW:
            out.live.append({**row, "id": r.id})
    out.live = sorted(out.live, key=lambda a: a["published_at"], reverse=True)[:LIVE_MAX]
    return out


async def _insert_tags(session: AsyncSession, tags: dict[uuid.UUID, dict[uuid.UUID, float]]):
    rows = [
        {"article_id": aid, "instrument_id": iid, "relevance": rel}
        for aid, found in tags.items()
        for iid, rel in found.items()
    ]
    if rows:
        await session.execute(insert(NewsArticleInstrument).on_conflict_do_nothing(), rows)


async def _replace_tags(
    session: AsyncSession, tags: dict[uuid.UUID, dict[uuid.UUID, float]]
) -> set[uuid.UUID]:
    """Replace the tags of these articles; returns the articles whose tags changed."""
    if not tags:
        return set()
    current: dict[uuid.UUID, dict[uuid.UUID, float]] = defaultdict(dict)
    for aid, iid, rel in (
        await session.execute(
            select(
                NewsArticleInstrument.article_id,
                NewsArticleInstrument.instrument_id,
                NewsArticleInstrument.relevance,
            ).where(NewsArticleInstrument.article_id.in_(list(tags)))
        )
    ).all():
        current[aid][iid] = rel
    changed = {aid for aid, wanted in tags.items() if current.get(aid, {}) != wanted}
    if changed:
        await session.execute(
            delete(NewsArticleInstrument).where(NewsArticleInstrument.article_id.in_(changed))
        )
        await _insert_tags(session, {aid: tags[aid] for aid in changed})
    return changed


async def _instrument_map(session: AsyncSession) -> tuple[dict[str, list], dict[str, list]]:
    """(symbol -> instrument ids, base asset -> instrument ids) of all instruments."""
    by_symbol: dict[str, list[uuid.UUID]] = defaultdict(list)
    by_base: dict[str, list[uuid.UUID]] = defaultdict(list)
    for iid, symbol, base in (
        await session.execute(select(Instrument.id, Instrument.symbol, Instrument.base_asset))
    ).all():
        by_symbol[symbol.upper()].append(iid)
        by_base[base.upper()].append(iid)
    return by_symbol, by_base


async def _source(session: AsyncSession, key: str, cache: dict[str, NewsSource]) -> NewsSource:
    if key in cache:
        return cache[key]
    source = await session.scalar(select(NewsSource).where(NewsSource.key == key))
    if source is None:  # adapters of the AI side register their source on first use
        await session.execute(
            insert(NewsSource)
            .values(key=key, name=key, kind=NewsSourceKind.api)
            .on_conflict_do_nothing(index_elements=["key"])
        )
        source = await session.scalar(select(NewsSource).where(NewsSource.key == key))
    cache[key] = source
    return source


@dataclass
class IngestOutcome:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[ItemError] = field(default_factory=list)
    warnings: list[ItemError] = field(default_factory=list)
    live: list[dict[str, Any]] = field(default_factory=list)


def _error_text(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err.get("loc", ()))
    return f"{where}: {err['msg']}" if where else err["msg"]


async def ingest(session: AsyncSession, items: list[dict[str, Any]]) -> IngestOutcome:
    """``POST /ingest/news``: validate every item on its own, upsert the valid ones per source,
    commit. Errors are reported per item (by index); the rest of the batch is stored."""
    out = IngestOutcome()
    now = datetime.now(UTC)
    per_source: dict[str, dict[str, tuple[int, ArticleIn]]] = defaultdict(dict)
    for index, raw in enumerate(items):
        external_id = raw.get("external_id") if isinstance(raw, dict) else None
        try:
            item = ArticleIn.model_validate(raw)
        except ValidationError as exc:
            out.errors.append(
                ItemError(index=index, external_id=external_id, error=_error_text(exc))
            )
            continue
        previous = per_source[item.source_key].get(item.external_id)
        if previous is not None:  # the later copy wins
            out.errors.append(
                ItemError(
                    index=previous[0],
                    external_id=item.external_id,
                    error="duplicate of a later item in this batch",
                )
            )
        per_source[item.source_key][item.external_id] = (index, item)
    if not per_source:
        return out

    by_symbol, by_base = await _instrument_map(session)
    tagger = await Tagger.load(session)
    sources: dict[str, NewsSource] = {}
    for key, entries in per_source.items():
        source = await _source(session, key, sources)
        if not source.is_active:
            for index, item in entries.values():
                out.errors.append(
                    ItemError(index=index, external_id=item.external_id, error="source is disabled")
                )
            continue
        rows, tags = [], {}
        for index, item in entries.values():
            summary = strip_html(item.summary) if item.summary else ""
            row = {
                "external_id": item.external_id,
                "url": item.url,
                "title": clip(strip_html(item.title), 500) or item.title[:500],
                "summary": clip(summary) if summary else None,
                "image_url": item.image_url,
                "author": item.author,
                "language": (item.language or source.language).lower(),
                "published_at": min(item.published_at, now),
            }
            if item.sentiment is not None:
                row.update(
                    sentiment_label=item.sentiment.label,
                    sentiment_score=item.sentiment.score,
                    sentiment_model=item.sentiment.model,
                    sentiment_at=now,
                )
            rows.append(row)
            if item.instruments is not None:
                found, unknown = _resolve_symbols(item.instruments, by_symbol, by_base)
                tags[item.external_id] = found
                if unknown:
                    out.warnings.append(
                        ItemError(
                            index=index,
                            external_id=item.external_id,
                            error=f"unknown symbols ignored: {', '.join(unknown)}",
                        )
                    )
        result = await upsert(session, source.id, rows, tags=tags, tagger=tagger, now=now)
        out.inserted += len(result.inserted)
        out.updated += len(result.updated)
        out.skipped += result.skipped
        out.live += [{**a, "source": {"key": source.key, "name": source.name}} for a in result.live]
    await session.commit()
    return out


def _resolve_symbols(tags, by_symbol, by_base) -> tuple[dict[uuid.UUID, float], list[str]]:
    found: dict[uuid.UUID, float] = {}
    unknown = []
    for tag in tags:
        symbol = tag.symbol.strip().upper()
        ids = by_symbol.get(symbol) or ([] if "/" in symbol else by_base.get(symbol, []))
        if not ids:
            unknown.append(tag.symbol)
        for iid in ids:
            found[iid] = max(found.get(iid, 0.0), tag.relevance)
    return found, unknown


async def push_sentiment(session: AsyncSession, items: list[dict[str, Any]]):
    """``POST /ingest/news/sentiment``: (updated, errors)."""
    errors: list[ItemError] = []
    valid: list[tuple[int, SentimentItemIn]] = []
    for index, raw in enumerate(items):
        try:
            valid.append((index, SentimentItemIn.model_validate(raw)))
        except ValidationError as exc:
            errors.append(ItemError(index=index, error=_error_text(exc)))
    keys = {(i.source_key, i.external_id) for _, i in valid if i.article_id is None}
    by_key: dict[tuple[str, str], uuid.UUID] = {}
    if keys:
        rows = await session.execute(
            select(NewsSource.key, NewsArticle.external_id, NewsArticle.id)
            .join(NewsSource, NewsSource.id == NewsArticle.source_id)
            .where(tuple_(NewsSource.key, NewsArticle.external_id).in_(list(keys)))
        )
        by_key = {(k, e): aid for k, e, aid in rows.all()}
    ids = {i.article_id for _, i in valid if i.article_id is not None}
    known = (
        set((await session.scalars(select(NewsArticle.id).where(NewsArticle.id.in_(ids)))).all())
        if ids
        else set()
    )
    now = datetime.now(UTC)
    params = []
    for index, item in valid:
        aid = item.article_id or by_key.get((item.source_key, item.external_id))
        if aid is None or (item.article_id is not None and aid not in known):
            errors.append(
                ItemError(index=index, external_id=item.external_id, error="article not found")
            )
            continue
        params.append(
            {"b_id": aid, "label": item.label, "score": item.score, "model": item.model, "at": now}
        )
    if params:
        await session.execute(
            update(NewsArticle.__table__)
            .where(NewsArticle.__table__.c.id == bindparam("b_id"))
            .values(
                sentiment_label=bindparam("label"),
                sentiment_score=bindparam("score"),
                sentiment_model=bindparam("model"),
                sentiment_at=bindparam("at"),
            ),
            params,
        )
    await session.commit()
    return len(params), sorted(errors, key=lambda e: e.index)


# --- real time -----------------------------------------------------------------------------------


def wire(article: dict[str, Any], tags: list[dict[str, Any]]) -> dict[str, Any]:
    """The ``news`` WebSocket message of a new article."""
    published = article["published_at"]
    label = article.get("sentiment_label")
    return {
        "type": "news",
        "article": {
            "id": str(article["id"]),
            "source": article.get("source"),
            "url": article["url"],
            "title": article["title"],
            "summary": article.get("summary"),
            "image_url": article.get("image_url"),
            "language": article.get("language"),
            "published_at": published.isoformat() if published else None,
            "sentiment": (
                {"label": str(label), "score": article.get("sentiment_score")} if label else None
            ),
            "instruments": tags,
        },
    }


async def publish_new(session: AsyncSession, redis: Redis | None, articles: list[dict]) -> int:
    """Publish new articles (after the commit) on ``news`` and ``news:{instrument_id}`` in one
    pipeline. Never raises: the articles are stored and listed by the API anyway."""
    if not articles:
        return 0
    redis = redis or get_redis()
    try:
        tags = await _tags_of(session, [a["id"] for a in articles])
        pipe = redis.pipeline(transaction=False)
        count = 0
        for article in articles:
            article_tags = tags.get(article["id"], [])
            message = wire(article, article_tags)
            for topic in [news_topic(), *(news_topic(t["instrument_id"]) for t in article_tags)]:
                pipe.publish(channel_for(topic), publisher.encode(topic, message))
                count += 1
        await pipe.execute()
        return count
    except Exception:  # noqa: BLE001
        logger.exception("news: publishing %d articles failed", len(articles))
        return 0


async def _tags_of(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    out: dict[uuid.UUID, list[dict]] = defaultdict(list)
    if not ids:
        return out
    rows = await session.execute(
        select(
            NewsArticleInstrument.article_id,
            NewsArticleInstrument.instrument_id,
            Instrument.symbol,
            NewsArticleInstrument.relevance,
        )
        .join(Instrument, Instrument.id == NewsArticleInstrument.instrument_id)
        .where(NewsArticleInstrument.article_id.in_(ids))
        .order_by(NewsArticleInstrument.relevance.desc(), Instrument.symbol)
    )
    for aid, iid, symbol, rel in rows.all():
        out[aid].append({"instrument_id": str(iid), "symbol": symbol, "relevance": rel})
    return out


# --- RSS -----------------------------------------------------------------------------------------


async def due_sources(session: AsyncSession, now: datetime) -> list[NewsSource]:
    rows = await session.scalars(
        select(NewsSource).where(
            NewsSource.kind == NewsSourceKind.rss,
            NewsSource.is_active.is_(True),
            NewsSource.url.is_not(None),
            or_(
                NewsSource.last_fetched_at.is_(None),
                NewsSource.last_fetched_at
                + func.make_interval(0, 0, 0, 0, 0, NewsSource.fetch_interval_minutes)
                <= now,
            ),
        )
    )
    return list(rows.all())


async def fetch_due(
    factory: async_sessionmaker[AsyncSession], redis: Redis | None, now: datetime | None = None
) -> dict[str, Any]:
    """The RSS task: fetch every due feed concurrently (each with its own deadline), store the
    articles, update the source, publish the new ones."""
    now = now or datetime.now(UTC)
    async with factory() as session:
        sources = await due_sources(session, now)
    if not sources:
        return {}
    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
    # no per-operation timeout: rss.download() wraps each feed in one asyncio.timeout (10 s for
    # the whole request), which also stops a server that drips bytes
    async with httpx.AsyncClient(  # nosec B113
        transport=transport, follow_redirects=True, max_redirects=3, timeout=None
    ) as client:

        async def one(source: NewsSource) -> tuple[NewsSource, rss.FeedResult]:
            async with semaphore:
                return source, await rss.fetch(client, source)

        results = await asyncio.gather(*(one(s) for s in sources))
    report: dict[str, Any] = {}
    async with factory() as session:
        tagger = await Tagger.load(session)
        for source, result in results:
            report[source.key] = await _store_feed(session, redis, source, result, tagger, now)
    return report


async def _store_feed(session, redis, source: NewsSource, result: rss.FeedResult, tagger, now):
    values: dict[str, Any] = {"last_fetched_at": now}
    summary: dict[str, Any] = {"status": result.status}
    upserted = Upserted()
    if result.status == "error":
        values["last_error"] = result.error
        summary["error"] = result.error
        logger.warning("news: %s failed: %s", source.key, result.error)
    else:
        values.update(last_error=None, etag=result.etag, last_modified=result.last_modified)
        try:
            upserted = await upsert(
                session, source.id, result.items, tagger=tagger, now=now, keep_published=True
            )
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.exception("news: storing %s failed", source.key)
            values["last_error"] = f"store: {type(exc).__name__}"[:500]
            values.pop("etag", None)  # fetch it again in full next time
            values.pop("last_modified", None)
        summary.update(
            items=len(result.items),
            inserted=len(upserted.inserted),
            updated=len(upserted.updated),
            skipped=upserted.skipped,
        )
    await session.execute(update(NewsSource).where(NewsSource.id == source.id).values(**values))
    await session.commit()
    live = [{**a, "source": {"key": source.key, "name": source.name}} for a in upserted.live]
    summary["published"] = await publish_new(session, redis, live)
    return summary


# --- reading -------------------------------------------------------------------------------------


async def list_articles(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    instrument_id: uuid.UUID | None = None,
    sentiment: SentimentLabel | None = None,
    source: str | None = None,
    language: str | None = None,
    since: datetime | None = None,
    q: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    conditions = []
    if instrument_id is not None:
        conditions.append(
            exists().where(
                NewsArticleInstrument.article_id == NewsArticle.id,
                NewsArticleInstrument.instrument_id == instrument_id,
            )
        )
    if sentiment is not None:
        conditions.append(NewsArticle.sentiment_label == sentiment)
    if source:
        conditions.append(NewsSource.key == source)
    if language:
        conditions.append(NewsArticle.language == language.lower())
    if since is not None:
        conditions.append(NewsArticle.published_at >= since)
    if q and q.strip():
        conditions.append(
            text(f"{SEARCH_VECTOR} @@ websearch_to_tsquery('simple', :q)").bindparams(q=q.strip())
        )
    base = select(NewsArticle, NewsSource.key, NewsSource.name).join(
        NewsSource, NewsSource.id == NewsArticle.source_id
    )
    total = await session.scalar(
        select(func.count())
        .select_from(NewsArticle)
        .join(NewsSource, NewsSource.id == NewsArticle.source_id)
        .where(*conditions)
    )
    rows = (
        await session.execute(
            base.where(*conditions)
            .order_by(NewsArticle.published_at.desc(), NewsArticle.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    tags = await _tags_of(session, [a.id for a, _, _ in rows])
    return [read(a, key, name, tags.get(a.id, [])) for a, key, name in rows], total or 0


async def get_article(session: AsyncSession, article_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        await session.execute(
            select(NewsArticle, NewsSource.key, NewsSource.name)
            .join(NewsSource, NewsSource.id == NewsArticle.source_id)
            .where(NewsArticle.id == article_id)
        )
    ).first()
    if row is None:
        return None
    article, key, name = row
    tags = await _tags_of(session, [article.id])
    return read(article, key, name, tags.get(article.id, []))


def read(article: NewsArticle, key: str, name: str, tags: list[dict]) -> dict[str, Any]:
    sentiment = None
    if article.sentiment_label is not None:
        sentiment = {
            "label": article.sentiment_label,
            "score": article.sentiment_score,
            "model": article.sentiment_model,
            "at": article.sentiment_at,
        }
    return {
        "id": article.id,
        "source": {"key": key, "name": name},
        "url": article.url,
        "title": article.title,
        "summary": article.summary,
        "image_url": article.image_url,
        "author": article.author,
        "language": article.language,
        "published_at": article.published_at,
        "fetched_at": article.fetched_at,
        "sentiment": sentiment,
        "instruments": tags,
    }


def _bucket(row) -> dict[str, Any]:
    return {
        "articles": row.articles,
        "scored": row.scored,
        "positive": row.positive or 0,
        "neutral": row.neutral or 0,
        "negative": row.negative or 0,
        "mean_score": None if row.mean_score is None else round(float(row.mean_score), 4),
    }


def _label_counts(label_column):
    return [
        func.count().filter(label_column == SentimentLabel.positive).label("positive"),
        func.count().filter(label_column == SentimentLabel.neutral).label("neutral"),
        func.count().filter(label_column == SentimentLabel.negative).label("negative"),
    ]


async def sentiment_aggregate(
    session: AsyncSession,
    window: str,
    instrument_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Per instrument (and overall): articles published in the window, counts per label and the
    mean score of the scored ones (plus a relevance-weighted mean per instrument)."""
    now = now or datetime.now(UTC)
    since = now - WINDOWS[window]
    a = NewsArticle
    overall_query = select(
        func.count().label("articles"),
        func.count(a.sentiment_score).label("scored"),
        *_label_counts(a.sentiment_label),
        func.avg(a.sentiment_score).label("mean_score"),
    ).where(a.published_at >= since)
    t = NewsArticleInstrument
    if instrument_id is not None:
        overall_query = overall_query.where(
            exists().where(t.article_id == a.id, t.instrument_id == instrument_id)
        )
    overall = (await session.execute(overall_query)).one()
    weighted = func.sum(a.sentiment_score * t.relevance) / func.nullif(
        func.sum(case((a.sentiment_score.is_not(None), t.relevance), else_=0)), 0
    )
    query = (
        select(
            t.instrument_id,
            Instrument.symbol,
            func.count().label("articles"),
            func.count(a.sentiment_score).label("scored"),
            *_label_counts(a.sentiment_label),
            func.avg(a.sentiment_score).label("mean_score"),
            weighted.label("weighted_score"),
        )
        .join(a, a.id == t.article_id)
        .join(Instrument, Instrument.id == t.instrument_id)
        .where(a.published_at >= since)
        .group_by(t.instrument_id, Instrument.symbol)
        .order_by(func.count().desc(), Instrument.symbol)
    )
    if instrument_id is not None:
        query = query.where(t.instrument_id == instrument_id)
    instruments = []
    for row in (await session.execute(query)).all():
        bucket = _bucket(row)
        bucket["weighted_score"] = (
            None if row.weighted_score is None else round(float(row.weighted_score), 4)
        )
        instruments.append({"instrument_id": row.instrument_id, "symbol": row.symbol, **bucket})
    return {
        "window": window,
        "since": since,
        "overall": _bucket(overall),
        "instruments": instruments,
    }


async def list_sources(session: AsyncSession) -> list[dict[str, Any]]:
    counts = dict(
        (
            await session.execute(
                select(NewsArticle.source_id, func.count()).group_by(NewsArticle.source_id)
            )
        ).all()
    )
    sources = await session.scalars(select(NewsSource).order_by(NewsSource.kind, NewsSource.key))
    return [
        {**{c: getattr(s, c) for c in _SOURCE_FIELDS}, "articles": counts.get(s.id, 0)}
        for s in sources
    ]


_SOURCE_FIELDS = (
    "id",
    "key",
    "name",
    "kind",
    "url",
    "language",
    "is_active",
    "fetch_interval_minutes",
    "last_fetched_at",
    "last_error",
)


# --- retention -----------------------------------------------------------------------------------


async def cleanup(
    factory: async_sessionmaker[AsyncSession], now: datetime | None = None, batch: int = 5000
) -> int:
    """Delete articles published more than ``news_retention_days`` ago, in batches."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=get_settings().news_retention_days)
    total = 0
    while True:
        async with factory() as session:
            ids = (
                select(NewsArticle.id)
                .where(NewsArticle.published_at < cutoff)
                .limit(batch)
                .scalar_subquery()
            )
            result = await session.execute(delete(NewsArticle).where(NewsArticle.id.in_(ids)))
            await session.commit()
        total += result.rowcount or 0
        if (result.rowcount or 0) < batch:
            return total
