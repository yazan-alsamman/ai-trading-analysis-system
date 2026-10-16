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
    chat,
    custom_strategies,
    experts,
    health,
    indicators,
    market,
    news,
    notifications,
    posts,
    price_alerts,
    risk,
    strategies,
    subscriptions,
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
limited_router.include_router(notifications.router)
limited_router.include_router(notifications.admin_router)
limited_router.include_router(news.router)
limited_router.include_router(news.admin_router)
limited_router.include_router(news.ingest_router)
limited_router.include_router(posts.router)
limited_router.include_router(posts.admin_router)
limited_router.include_router(price_alerts.router)
limited_router.include_router(experts.router)
limited_router.include_router(subscriptions.router)
limited_router.include_router(subscriptions.admin_router)
limited_router.include_router(chat.router)
limited_router.include_router(chat.admin_router)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(notifications.webhook_router)  # Telegram calls it: no identity limit
# the demo payment page, its form and the payment webhook: no login, so no identity limit
api_router.include_router(subscriptions.public_router)
api_router.include_router(limited_router)
