"""Admin: WhatsApp codes via LightOTP (docs/otp.md). Settings (never the key) and the
delivery status of a sent code."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.deps import AdminUser
from app.otp import service
from app.schemas.otp import OtpMessageStatus

router = APIRouter(prefix="/admin/otp", tags=["admin"])


@router.get("/status")
async def otp_status(_: AdminUser) -> dict:
    """Whether LIGHTOTP_TOKEN is set (``configured``) and the code settings. The key itself is
    never returned."""
    return service.status_view()


@router.get("/messages/{message_id}", response_model=OtpMessageStatus)
async def otp_message_status(
    _: AdminUser, message_id: Annotated[str, Path(min_length=1, max_length=64)]
):
    """LightOTP's delivery status of a sent code (``messageStatus``: Pending, Sent, Delivered,
    Read, Failed, Deleted; failure fields when it failed). The message id is in the backend
    log line "WhatsApp code sent". 404 ``message_not_found``."""
    return await service.message_status(message_id)
