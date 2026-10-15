from fastapi import APIRouter

from app.api.v1 import admin, admin_market, auth, health, market, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(market.router)
api_router.include_router(admin_market.router)
