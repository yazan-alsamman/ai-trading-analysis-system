"""News (docs/news-posts.md) and the ingestion API of the AI side (docs/news-ingestion.md).

Reading works with a login or an API key with ``news:read``; ingestion needs ``news:write``
(admin keys only)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import AdminUser, CurrentUser, NewsReader, NewsWriter, SessionDep
from app.api.limits import COST_KEY
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.news import NewsSource, SentimentLabel
from app.news import comments, service
from app.schemas.common import Page
from app.schemas.news import (
    ArticleRead,
    IngestRequest,
    IngestResult,
    NewsCommentCreate,
    NewsCommentModeration,
    NewsCommentRead,
    NewsCommentUpdate,
    SentimentAggregate,
    SentimentRequest,
    SentimentResult,
    SourceRead,
    SourceUpdate,
    Window,
)

router = APIRouter(prefix="/news", tags=["news"])
admin_router = APIRouter(prefix="/admin/news", tags=["news"])
ingest_router = APIRouter(prefix="/ingest/news", tags=["news"])


@router.get("", response_model=Page[ArticleRead])
async def list_news(
    _: NewsReader,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    instrument_id: uuid.UUID | None = None,
    sentiment: SentimentLabel | None = None,
    source: Annotated[str | None, Query(max_length=64)] = None,
    language: Annotated[str | None, Query(min_length=2, max_length=8)] = None,
    since: datetime | None = None,
    q: Annotated[
        str | None, Query(max_length=200, description="full-text search in title + summary")
    ] = None,
):
    """Newest first. ``q`` uses Postgres full text (``simple`` configuration: whole words, no
    stemming; ``"exact phrase"``, ``or`` and ``-word`` work as in web searches)."""
    items, total = await service.list_articles(
        session,
        limit=limit,
        offset=offset,
        instrument_id=instrument_id,
        sentiment=sentiment,
        source=source,
        language=language,
        since=since,
        q=q,
    )
    return Page[ArticleRead](items=items, total=total, limit=limit, offset=offset)


@router.get("/sentiment", response_model=SentimentAggregate)
async def news_sentiment(
    _: NewsReader,
    session: SessionDep,
    window: Window = "24h",
    instrument_id: uuid.UUID | None = None,
):
    """Per instrument: articles published in the window, counts per sentiment label and the
    mean score of the scored ones (and a relevance-weighted mean); ``overall`` covers every
    article of the window."""
    return await service.sentiment_aggregate(session, window, instrument_id)


@router.get("/sources", response_model=list[SourceRead])
async def news_sources(_: CurrentUser, session: SessionDep):
    return await service.list_sources(session)


@router.get("/{article_id}", response_model=ArticleRead)
async def get_news(article_id: uuid.UUID, _: NewsReader, session: SessionDep):
    article = await service.get_article(session, article_id)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    return article


# --- reader comments (docs/news-comments.md) ----------------------------------------------------

COMMENT_COST = {COST_KEY: get_settings().content_create_cost}


@router.get("/{article_id}/comments", response_model=Page[NewsCommentRead])
async def list_article_comments(
    article_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    parent_id: Annotated[
        uuid.UUID | None, Query(description="only the replies of this comment, oldest first")
    ] = None,
):
    """Comments of an article, newest first (top-level comments and replies; a reply has
    ``parent_id``). Deleted comments are left out."""
    comments.require_enabled()
    article = await comments.article_or_404(session, article_id)
    items, total = await comments.list_comments(
        session, user, article, limit=limit, offset=offset, parent_id=parent_id
    )
    return Page[NewsCommentRead](items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/{article_id}/comments",
    response_model=NewsCommentRead,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=COMMENT_COST,
)
async def create_article_comment(
    article_id: uuid.UUID, data: NewsCommentCreate, user: CurrentUser, session: SessionDep
):
    """Comment on an article (or reply with ``parent_id``). The article's ``comments_count``
    goes up at once. 429 + Retry-After over ``COMMENTS_PER_HOUR``."""
    comments.require_enabled()
    article = await comments.article_or_404(session, article_id)
    return await comments.create(session, user, article, data.body, data.parent_id)


@router.patch("/comments/{comment_id}", response_model=NewsCommentRead)
async def update_article_comment(
    comment_id: uuid.UUID, data: NewsCommentUpdate, user: CurrentUser, session: SessionDep
):
    """Only the author edits a published comment."""
    comment = await comments.own_or_404(session, comment_id)
    return await comments.edit(session, user, comment, data.body)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article_comment(
    comment_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Response:
    """The author or an admin. Soft delete: replies stay."""
    comment = await comments.own_or_404(session, comment_id)
    await comments.delete(session, user, comment)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post("/comments/{comment_id}/moderate", status_code=status.HTTP_204_NO_CONTENT)
async def moderate_article_comment(
    comment_id: uuid.UUID, data: NewsCommentModeration, _: AdminUser, session: SessionDep
) -> Response:
    """Hide a comment (only its author still sees it) or publish it again."""
    comment = await comments.own_or_404(session, comment_id)
    await comments.hide(session, comment, data.hidden)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.patch("/sources/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: uuid.UUID, data: SourceUpdate, _: AdminUser, session: SessionDep
):
    """Enable or disable a source and change how often an RSS feed is fetched (5-1440 min)."""
    source = await session.get(NewsSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    for name, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(source, name, value)
    await session.commit()
    return next(s for s in await service.list_sources(session) if s["id"] == source_id)


@ingest_router.post("", response_model=IngestResult)
async def ingest_news(data: IngestRequest, _: NewsWriter, session: SessionDep):
    """Upsert up to 200 articles (idempotent on ``source_key`` + ``external_id``). Every item is
    validated on its own: invalid ones are listed in ``errors`` by index, the rest is stored."""
    outcome = await service.ingest(session, data.articles)
    await service.publish_new(session, get_redis(), outcome.live)
    return IngestResult(
        inserted=outcome.inserted,
        updated=outcome.updated,
        skipped=outcome.skipped,
        errors=sorted(outcome.errors, key=lambda e: e.index),
        warnings=outcome.warnings,
    )


@ingest_router.post("/sentiment", response_model=SentimentResult)
async def ingest_sentiment(data: SentimentRequest, _: NewsWriter, session: SessionDep):
    """Set the sentiment of up to 500 existing articles (by ``article_id`` or ``source_key`` +
    ``external_id``); the last write wins."""
    updated, errors = await service.push_sentiment(session, data.items)
    return SentimentResult(updated=updated, errors=errors)
