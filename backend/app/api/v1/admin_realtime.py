from fastapi import APIRouter, Request

from app.api.deps import AdminUser

router = APIRouter(prefix="/admin/realtime", tags=["admin"])


@router.get("/stats")
async def realtime_stats(_: AdminUser, request: Request) -> dict:
    """WebSocket hub metrics of the API process that serves this request."""
    return request.app.state.hub.stats()
