"""Chart image analysis for users (Y14, docs/chart-analysis.md): validation, duplicates, the
daily quota, the Gemini call, storage, history.

Flow of one ``POST``:

1. The feature is on (key set, ``CHART_ANALYSIS_ENABLED``), else 503 ``not_configured``.
2. The image is checked and re-encoded off the event loop, on one thread per worker
   (``images.prepare``: 413/415/422).
3. The same user, image (SHA-256), language and hints within 24 h: the stored result is
   returned, with no model call and no quota.
4. A slot: at most ``CHART_ANALYSIS_MAX_CONCURRENT`` analyses in flight per API worker; no
   slot within 10 s: 503 ``busy`` + Retry-After (no quota taken).
5. One unit of the daily quota is taken in Redis (per user per UTC day, by role). Used up:
   429 + Retry-After (seconds to the next UTC midnight).
6. Gemini answers: ``ok`` (200), ``not_chart`` (422, counted), ``refused`` (422, counted).
   Unavailable or timed out: the unit is given back, the row is stored as ``error``, 503 +
   Retry-After.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
import weakref
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.chart_analysis import ChartAnalysisRecord
from app.models.notification import NotificationPreference
from app.models.user import User
from app.vision import gemini
from app.vision.images import ImageRejected, prepare
from app.vision.schemas import finalize

logger = logging.getLogger(__name__)

QUOTA_PREFIX = "chart:quota:"
DUPLICATE_WINDOW = timedelta(hours=24)
# image checks and re-encoding: off the event loop, one at a time per API worker (bounded
# memory: a 5 MB JPEG decodes to ~18 MB, and one thread keeps one malloc arena)
_IMAGE_THREAD = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chart-image")
QUEUE_SECONDS = 10  # the longest wait for a free slot (Nginx allows 60 s on this route)
BUSY_RETRY_AFTER = 10


def utcnow() -> datetime:
    return datetime.now(UTC)


def _error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    headers = None
    if (retry := extra.pop("retry_after", None)) is not None:
        headers = {"Retry-After": str(int(retry))}
    return HTTPException(status_code, {"code": code, "message": message, **extra}, headers)


def require_enabled() -> None:
    enabled, reason = gemini.configured()
    if not enabled:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "not_configured",
            "chart analysis is not configured",
            reason=reason,
        )


# --- quota ---------------------------------------------------------------------------------------


def daily_limit(user: User) -> int:
    settings = get_settings()
    return int(getattr(settings, f"chart_analysis_daily_limit_{user.role.value}"))


def _day_key(user_id: uuid.UUID, now: datetime) -> str:
    return f"{QUOTA_PREFIX}{user_id}:{now:%Y%m%d}"


def _reset_at(now: datetime) -> datetime:
    return datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)


async def quota(redis: Redis, user: User) -> dict[str, Any]:
    now = utcnow()
    used = int(await redis.get(_day_key(user.id, now)) or 0)
    limit = daily_limit(user)
    return {
        "limit": limit,
        "used": min(used, limit),
        "remaining": max(0, limit - used),
        "resets_at": _reset_at(now),
    }


async def _take_quota(redis: Redis, user: User) -> str:
    """Takes one unit (atomic INCR) or raises 429. Returns the key, to give it back."""
    now = utcnow()
    key, limit = _day_key(user.id, now), daily_limit(user)
    used = await redis.incr(key)
    if used == 1:
        await redis.expire(key, 2 * 86400)
    if used > limit:
        await redis.decr(key)
        retry = max(1, int((_reset_at(now) - now).total_seconds()))
        raise _error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "quota_exceeded",
            f"daily limit of {limit} chart analyses reached",
            retry_after=retry,
            limit=limit,
            resets_at=_reset_at(now).isoformat(),
        )
    return key


async def _give_back(redis: Redis, key: str) -> None:
    try:
        await redis.decr(key)
    except Exception:  # noqa: BLE001
        logger.warning("chart analysis: could not give a quota unit back")


# --- analyse -------------------------------------------------------------------------------------


async def default_language(session: AsyncSession, user: User) -> str:
    row = await session.get(NotificationPreference, user.id)
    language = row.language if row is not None else "ar"
    return language if language in ("ar", "en") else "ar"


async def _duplicate(
    session: AsyncSession, user: User, sha: str, language: str, symbol, timeframe
) -> ChartAnalysisRecord | None:
    return await session.scalar(
        select(ChartAnalysisRecord)
        .where(
            ChartAnalysisRecord.user_id == user.id,
            ChartAnalysisRecord.image_sha256 == sha,
            ChartAnalysisRecord.language == language,
            ChartAnalysisRecord.symbol_hint.is_not_distinct_from(symbol),
            ChartAnalysisRecord.timeframe_hint.is_not_distinct_from(timeframe),
            ChartAnalysisRecord.status.in_(("ok", "not_chart")),
            ChartAnalysisRecord.created_at >= utcnow() - DUPLICATE_WINDOW,
        )
        .order_by(ChartAnalysisRecord.created_at.desc())
        .limit(1)
    )


def _not_chart(row: ChartAnalysisRecord) -> HTTPException:
    return _error(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "not_a_chart",
        "the image is not a price chart",
        analysis_id=str(row.id),
    )


async def analyse(
    session: AsyncSession,
    redis: Redis,
    user: User,
    data: bytes,
    language: str | None,
    symbol: str | None,
    timeframe: str | None,
    *,
    client: Any = None,
) -> tuple[ChartAnalysisRecord, bool]:
    """(the stored row, served from a duplicate). Raises HTTPException (module docstring)."""
    require_enabled()
    settings = get_settings()
    try:
        image = await asyncio.get_running_loop().run_in_executor(
            _IMAGE_THREAD, prepare, data, settings.chart_image_max_bytes
        )
    except ImageRejected as exc:
        raise _error(exc.status, exc.code, exc.message) from None
    language = language or await default_language(session, user)
    same = await _duplicate(session, user, image.sha256, language, symbol, timeframe)
    if same is not None:
        if same.status == "not_chart":
            raise _not_chart(same)
        return same, True
    async with _slot():
        return await _analyse_new(
            session, redis, user, image, language, symbol, timeframe, client
        ), False


class _slot:
    """At most ``CHART_ANALYSIS_MAX_CONCURRENT`` analyses in flight per API worker (memory:
    each holds its image and request until the model answers). A request that waits longer
    than ``QUEUE_SECONDS`` gets 503 ``busy`` + Retry-After, and no quota is taken."""

    _by_loop: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()  # one per event loop

    def __init__(self) -> None:
        loop = asyncio.get_running_loop()
        size = max(1, get_settings().chart_analysis_max_concurrent)
        if loop not in self._by_loop:
            self._by_loop[loop] = asyncio.Semaphore(size)
        self.sem = self._by_loop[loop]

    async def __aenter__(self) -> None:
        try:
            await asyncio.wait_for(self.sem.acquire(), timeout=QUEUE_SECONDS)
        except TimeoutError:
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "busy",
                "chart analysis is busy, try again shortly",
                retry_after=BUSY_RETRY_AFTER,
            ) from None

    async def __aexit__(self, *_exc: object) -> None:
        self.sem.release()


async def _analyse_new(
    session: AsyncSession,
    redis: Redis,
    user: User,
    image: Any,
    language: str,
    symbol: str | None,
    timeframe: str | None,
    client: Any,
) -> ChartAnalysisRecord:
    settings = get_settings()
    key = await _take_quota(redis, user)
    row = ChartAnalysisRecord(
        user_id=user.id,
        image_sha256=image.sha256,
        image_bytes=image.original_bytes,
        width=image.width,
        height=image.height,
        mime=image.original_mime,
        language=language,
        symbol_hint=symbol,
        timeframe_hint=timeframe,
        model=settings.chart_vision_model,
        prompt_version=gemini.PROMPT_VERSION,
    )
    try:
        result = await gemini.analyse(image, language, symbol, timeframe, client=client)
    except gemini.VisionError as exc:
        if exc.status == status.HTTP_422_UNPROCESSABLE_CONTENT:
            row.status = "refused"  # the model was called: counted
        else:
            row.status = "error"
            await _give_back(redis, key)
        row.result = {"code": exc.code, "message": exc.message}
        session.add(row)
        await session.commit()
        raise _error(
            exc.status, exc.code, exc.message, retry_after=exc.retry_after, analysis_id=str(row.id)
        ) from None
    analysis = finalize(result.analysis, language)
    row.status = "ok" if analysis.is_chart else "not_chart"
    row.result = json.loads(analysis.model_dump_json())
    row.model = result.model
    row.input_tokens, row.output_tokens = result.input_tokens, result.output_tokens
    row.latency_ms = result.latency_ms
    session.add(row)
    await session.commit()
    await session.refresh(row)
    if row.status == "not_chart":
        raise _not_chart(row)
    return row


# --- history -------------------------------------------------------------------------------------


async def history(
    session: AsyncSession, user: User, limit: int, offset: int
) -> tuple[list[ChartAnalysisRecord], int]:
    where = ChartAnalysisRecord.user_id == user.id
    total = await session.scalar(select(func.count()).select_from(ChartAnalysisRecord).where(where))
    rows = await session.scalars(
        select(ChartAnalysisRecord)
        .where(where)
        .order_by(ChartAnalysisRecord.created_at.desc(), ChartAnalysisRecord.id)
        .limit(limit)
        .offset(offset)
    )
    return list(rows.all()), total


async def get_own(session: AsyncSession, user: User, analysis_id: uuid.UUID) -> ChartAnalysisRecord:
    row = await session.get(ChartAnalysisRecord, analysis_id)
    if row is None or row.user_id != user.id:
        raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Analysis not found")
    return row


async def delete_own(session: AsyncSession, user: User, analysis_id: uuid.UUID) -> None:
    row = await get_own(session, user, analysis_id)
    await session.delete(row)
    await session.commit()


# --- admin status --------------------------------------------------------------------------------


async def status_view(session: AsyncSession) -> dict[str, Any]:
    """``chart_analysis`` of /admin/system/status: disabled is a state, not an error."""
    enabled, reason = gemini.configured()
    settings = get_settings()
    since = utcnow() - timedelta(hours=24)
    rows = await session.execute(
        select(
            ChartAnalysisRecord.status,
            func.count(),
            func.coalesce(func.sum(ChartAnalysisRecord.input_tokens), 0),
            func.coalesce(func.sum(ChartAnalysisRecord.output_tokens), 0),
            func.avg(ChartAnalysisRecord.latency_ms),
        )
        .where(ChartAnalysisRecord.created_at >= since)
        .group_by(ChartAnalysisRecord.status)
    )
    last = {s: {"count": n, "input_tokens": i, "output_tokens": o, "avg_latency_ms": a}
            for s, n, i, o, a in rows.all()}  # fmt: skip
    return {
        "enabled": enabled,
        "disabled_reason": reason,
        "model": settings.chart_vision_model,
        "prompt_version": gemini.PROMPT_VERSION,
        "last_24h": last,
    }
