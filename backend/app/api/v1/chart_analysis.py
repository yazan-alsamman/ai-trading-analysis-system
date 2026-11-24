"""Chart image analysis (Y14, docs/chart-analysis.md): upload a chart screenshot, get a
structured, checked analysis from Gemini. Logged-in users only; a daily quota per role; the
image is never stored. Not financial advice: every result carries the disclaimer."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.api.limits import EXPENSIVE
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.chart_analysis import ChartAnalysisRecord
from app.schemas.chart_analysis import ChartAnalysisPage, ChartAnalysisRead, ChartQuota
from app.vision import service

router = APIRouter(prefix="/analysis/chart-image", tags=["chart-analysis"])

ERRORS = {
    413: {"description": "image_too_large (over CHART_IMAGE_MAX_BYTES)"},
    415: {"description": "unsupported_image (only PNG, JPEG, WebP, by their bytes)"},
    422: {
        "description": "image_too_small, image_too_many_pixels, invalid_image, not_a_chart "
        "(counted), could_not_analyse (counted: blocked or empty answer)"
    },
    429: {"description": "quota_exceeded: Retry-After = seconds to 00:00 UTC"},
    503: {"description": "not_configured, model_busy, model_unavailable, timeout (Retry-After)"},
}


def read(row: ChartAnalysisRecord, cached: bool = False) -> ChartAnalysisRead:
    ok = row.status in ("ok", "not_chart")
    return ChartAnalysisRead(
        id=row.id,
        created_at=row.created_at,
        status=row.status,
        language=row.language,
        symbol_hint=row.symbol_hint,
        timeframe_hint=row.timeframe_hint,
        model=row.model,
        prompt_version=row.prompt_version,
        image={
            "sha256": row.image_sha256,
            "bytes": row.image_bytes,
            "width": row.width,
            "height": row.height,
            "mime": row.mime,
        },
        result=row.result if ok else None,
        error=None if ok else row.result,
        usage={
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "latency_ms": row.latency_ms,
        },
        cached=cached,
    )


@router.post("", response_model=ChartAnalysisRead, openapi_extra=EXPENSIVE, responses=ERRORS)
async def analyse_chart_image(
    user: CurrentUser,
    session: SessionDep,
    image: Annotated[UploadFile, File(description="PNG, JPEG or WebP, at most 5 MB, >= 200x200")],
    language: Annotated[
        Literal["ar", "en"] | None, Form(description="default: your profile's language, else ar")
    ] = None,
    symbol: Annotated[
        str | None, Form(max_length=32, pattern=r"^[A-Za-z0-9/._:\- ]+$", description="a hint")
    ] = None,
    timeframe: Annotated[
        str | None, Form(max_length=8, pattern=r"^[0-9]{1,3}[A-Za-z]{1,2}$", description="a hint")
    ] = None,
):
    """Analyse one chart image, synchronously (up to ``CHART_VISION_TIMEOUT_SECONDS``), and
    return the stored result. The type is read from the image bytes; the image is re-encoded
    without metadata and **never stored** (only its SHA-256). The same image, language and hints
    within 24 h returns the stored result (``cached``), with no new call and no quota. Each new
    call takes one unit of your daily quota (``GET .../quota``); an image that is not a chart
    (422 ``not_a_chart``) is counted too. The result always carries a disclaimer: it is not
    financial advice."""
    service.require_enabled()
    data = await image.read(get_settings().chart_image_max_bytes + 1)
    row, cached = await service.analyse(
        session, get_redis(), user, data, language, (symbol or "").strip() or None, timeframe
    )
    return read(row, cached)


@router.get("", response_model=ChartAnalysisPage)
async def chart_analysis_history(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Your analyses, newest first (every status)."""
    service.require_enabled()
    rows, total = await service.history(session, user, limit, offset)
    return {"items": [read(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/quota", response_model=ChartQuota)
async def chart_analysis_quota(user: CurrentUser):
    """Used and remaining analyses today (UTC) for your role, and when the count resets."""
    service.require_enabled()
    return await service.quota(get_redis(), user)


@router.get("/{analysis_id}", response_model=ChartAnalysisRead)
async def get_chart_analysis(analysis_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """One of your analyses (404 for anyone else's)."""
    service.require_enabled()
    return read(await service.get_own(session, user, analysis_id))


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chart_analysis(analysis_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Delete one of your analyses (404 for anyone else's). The quota is not given back."""
    service.require_enabled()
    await service.delete_own(session, user, analysis_id)
