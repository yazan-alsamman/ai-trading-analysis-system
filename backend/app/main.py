import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import ws
from app.api.limits import RateLimitHeadersMiddleware, rate_limit_exceeded_handler
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import install_token_redaction, quiet_http_clients
from app.core.rate_limit import RATE_LIMIT_HEADERS, RateLimitExceeded
from app.core.redis import close_redis, get_redis
from app.db.session import SessionLocal, engine
from app.models.candle import Timeframe
from app.realtime.hub import HubConfig, WebSocketHub
from app.services import indicator_service, user_service
from app.services.workspace_service import VersionConflict

logger = logging.getLogger(__name__)

settings = get_settings()
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
            await conn.execute(text(f"SELECT * FROM {relation} LIMIT 1"))  # names from code
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


app = FastAPI(title="AI Trading Platform API", version="0.1.0", lifespan=lifespan)

app.add_middleware(RateLimitHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=list(RATE_LIMIT_HEADERS),
)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


@app.exception_handler(VersionConflict)
async def version_conflict_handler(request: Request, exc: VersionConflict) -> JSONResponse:
    """Workspace edited on another device: 409 with the current version to reload."""
    return JSONResponse(exc.body(), status_code=409, headers={"ETag": f'"{exc.current_version}"'})


app.include_router(api_router, prefix="/api/v1")
app.include_router(ws.router)  # /ws/market, at the root: Nginx proxies /ws/ with Upgrade headers
