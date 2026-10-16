from fastapi import APIRouter, Depends

from app.api.limits import limit_identity
from app.api.v1 import (
    admin,
    admin_api_keys,
    admin_market,
    admin_realtime,
    api_keys,
    auth,
    backtests,
    custom_strategies,
    health,
    indicators,
    market,
    risk,
    strategies,
    users,
    workspaces,
)

# Every /api/v1 route except /health* is rate limited per identity (user or API key).
# The unauthenticated auth endpoints have per-IP (and per-email) limits on top.
limited_router = APIRouter(dependencies=[Depends(limit_identity)])
limited_router.include_router(auth.router)
limited_router.include_router(users.router)
limited_router.include_router(admin.router)
limited_router.include_router(market.router)
limited_router.include_router(admin_market.router)
limited_router.include_router(admin_realtime.router)
limited_router.include_router(admin_api_keys.router)
limited_router.include_router(indicators.router)
limited_router.include_router(strategies.router)
limited_router.include_router(api_keys.router)
limited_router.include_router(workspaces.router)
limited_router.include_router(workspaces.shared_router)
limited_router.include_router(backtests.router)
limited_router.include_router(custom_strategies.router)
limited_router.include_router(custom_strategies.public_router)
limited_router.include_router(risk.router)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(limited_router)
