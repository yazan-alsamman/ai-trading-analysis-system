import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import ws
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import install_token_redaction
from app.core.redis import close_redis, get_redis
from app.db.session import SessionLocal, engine
from app.models.candle import Timeframe
from app.realtime.hub import HubConfig, WebSocketHub
from app.services import indicator_service, user_service

logger = logging.getLogger(__name__)

settings = get_settings()
install_token_redaction()  # /ws/market?token=... must not end up in access logs


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws.router)  # /ws/market, at the root: Nginx proxies /ws/ with Upgrade headers
