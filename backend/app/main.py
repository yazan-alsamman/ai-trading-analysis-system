import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.api import ws
from app.api.limits import RateLimitHeadersMiddleware, rate_limit_exceeded_handler
from app.api.middleware import RequestContextMiddleware
from app.api.openapi import install as install_openapi
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import install_token_redaction, quiet_http_clients, setup_logging
from app.core.rate_limit import RATE_LIMIT_HEADERS, RateLimitExceeded
from app.core.redis import close_redis, get_redis
from app.db.session import SessionLocal, engine
from app.models.candle import Timeframe
from app.realtime.hub import HubConfig, WebSocketHub
from app.services import indicator_service, user_service
from app.services.workspace_service import VersionConflict

logger = logging.getLogger(__name__)
POOL_RETRY_AFTER = 2  # seconds, on 503 when the database pool is exhausted

settings = get_settings()
# one root handler (JSON in production): uvicorn's loggers propagate to it
setup_logging(loggers=("uvicorn", "uvicorn.error"))
# RequestContextMiddleware logs one line per request; uvicorn's access log would repeat it.
# uvicorn logs access lines whenever this logger has handlers (it checks hasHandlers()), so
# --no-access-log alone is undone as soon as the logger propagates to the root handler.
_access_log = logging.getLogger("uvicorn.access")
_access_log.handlers = []
_access_log.propagate = False
install_token_redaction()  # ?token=, ?api_key= and the Telegram webhook secret stay out of logs
quiet_http_clients()  # httpx logs URLs (the Telegram bot token is in them)


async def bootstrap_first_admin() -> None:
    """Create FIRST_ADMIN_EMAIL as admin if it is configured and no admin exists yet."""
    if not (settings.first_admin_email and settings.first_admin_password):
        return
    async with SessionLocal() as session:
        if await user_service.admin_exists(session):
            return
        user, created = await user_service.ensure_admin(
            session, settings.first_admin_email, settings.first_admin_password
        )
        logger.warning("First admin %s: %s", "created" if created else "promoted", user.email)


async def warm_up() -> None:
    """Pay first-use costs before traffic: open a DB connection and load Postgres' per-session
    catalog/plan caches for the market relations, and run every indicator once."""
    async with engine.connect() as conn:
        for relation in ("users", "instruments", *(tf.relation for tf in Timeframe)):
            # relation names come from the Timeframe enum, never from input
            await conn.execute(text(f"SELECT * FROM {relation} LIMIT 1"))  # nosec B608
    await asyncio.to_thread(indicator_service.warm_up)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await bootstrap_first_admin()
    except Exception:
        logger.exception("Could not bootstrap the first admin")
    try:
        await warm_up()
    except Exception:
        logger.exception("Startup warm-up failed")
    hub = WebSocketHub(get_redis(), HubConfig.from_settings(settings))
    await hub.start()
    app.state.hub = hub
    try:
        yield
    finally:
        await hub.stop()
        await close_redis()


# Swagger UI, ReDoc and /openapi.json only outside production: the public contract is the
# committed docs/api/openapi.json (T07), so production does not advertise its own surface.
_docs = settings.environment != "production"
app = FastAPI(
    title="AI Trading Platform API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

app.add_middleware(RateLimitHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[*RATE_LIMIT_HEADERS, "X-Request-ID"],
)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.exception_handler(PoolTimeout)
async def pool_timeout_handler(request: Request, exc: PoolTimeout) -> JSONResponse:
    """Every database connection busy for db_pool_timeout seconds (overload): 503 and a hint
    when to retry, instead of an unhandled 500."""
    return JSONResponse(
        {"detail": "Server busy, try again shortly", "retry_after": POOL_RETRY_AFTER},
        status_code=503,
        headers={"Retry-After": str(POOL_RETRY_AFTER)},
    )


@app.exception_handler(VersionConflict)
async def version_conflict_handler(request: Request, exc: VersionConflict) -> JSONResponse:
    """Workspace edited on another device: 409 with the current version to reload."""
    return JSONResponse(exc.body(), status_code=409, headers={"ETag": f'"{exc.current_version}"'})


app.include_router(api_router, prefix="/api/v1")
app.include_router(ws.router)  # /ws/market, at the root: Nginx proxies /ws/ with Upgrade headers
install_openapi(app)
