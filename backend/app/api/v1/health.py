from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.redis import get_redis
from app.db.session import engine
from app.models.candle import Timeframe
from app.services import data_health
from app.services.data_quality import BAD_STATUSES, QualityCheck, QualityStatus

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/live")
async def live() -> dict:
    """The process answers (no dependency checked): for liveness probes."""
    return {"status": "ok"}


async def _data_summary(redis: Redis) -> str:
    """Worst stored data-quality status, for information only (never computed here)."""
    names = data_health.monitored()
    if not names:
        return "disabled"
    reports = list((await data_health.cached(redis, names)).values())
    if len(reports) < len(names):
        return "unknown"
    return data_health.worst(reports).value


@router.get("/health/ready")
async def ready() -> dict:
    """``status`` is ``ok`` when the database and Redis answer (the deploy waits for it).
    ``data`` is the worst data-quality status (``/health/data``), for information only: it
    never changes ``status`` or the HTTP code."""
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc.__class__.__name__}"
    data = "unknown"
    try:
        redis = Redis.from_url(get_settings().redis_url)
        try:
            await redis.ping()
            checks["redis"] = "ok"
            try:
                data = await _data_summary(redis)
            except Exception:  # noqa: BLE001 - informational only
                data = "unknown"
        finally:
            await redis.aclose()
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc.__class__.__name__}"
    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks, "data": data}


class InstrumentDataHealth(BaseModel):
    instrument: str = Field(examples=["fxpro:XAU/USD"])
    timeframe: Timeframe
    status: QualityStatus
    last_closed_bar: datetime | None
    lag_seconds: float | None
    next_open: datetime | None = None
    evaluated_at: datetime
    failed_checks: list[QualityCheck]


class DataHealth(BaseModel):
    status: str = Field(
        description="worst instrument status; `disabled` when no instrument is monitored"
    )
    instruments: list[InstrumentDataHealth]


@router.get(
    "/health/data",
    response_model=DataHealth,
    responses={503: {"model": DataHealth, "description": "an instrument is degraded or no_data"}},
)
async def data(session: SessionDep):
    """Data quality of every monitored instrument (``DATA_QUALITY_INSTRUMENTS``): the latest
    report of the ``data_quality.check`` task (computed now if there is none). **503** when
    any instrument is ``degraded`` or ``no_data``, 200 when all are ``ok`` or ``closed``.
    Public and read-only; ``/health/ready`` does not depend on it (docs/data-quality.md)."""
    reports = await data_health.current(session, get_redis())
    body = DataHealth(
        status=data_health.worst(reports) or "disabled",
        instruments=[
            InstrumentDataHealth(
                instrument=r.instrument,
                timeframe=r.timeframe,
                status=r.status,
                last_closed_bar=r.last_closed_bar,
                lag_seconds=r.lag_seconds,
                next_open=r.next_open,
                evaluated_at=r.evaluated_at,
                failed_checks=r.failed,
            )
            for r in reports
        ],
    )
    bad = any(r.status in BAD_STATUSES for r in reports)
    return JSONResponse(body.model_dump(mode="json"), status_code=503 if bad else 200)
