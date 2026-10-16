"""System status for admins (operations view)."""

from fastapi import APIRouter, Request

from app.api.deps import AdminUser, SessionDep
from app.core.redis import get_redis
from app.services import system_status

router = APIRouter(prefix="/admin/system", tags=["admin"])


@router.get("/status")
async def system_status_view(_: AdminUser, session: SessionDep, request: Request) -> dict:
    """Version, uptime, database (size, connections, migration, slowest queries when
    pg_stat_statements is installed), Redis, Celery (queue lengths, live workers, last run of the
    scheduled tasks), market data freshness per active instrument, WebSocket clients of this API
    process, notification channels, unhandled errors in the last hour, the last daily summary."""
    hub = getattr(request.app.state, "hub", None)
    return await system_status.collect(session, get_redis(), hub)
