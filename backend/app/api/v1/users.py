from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, SessionDep
from app.api.limits import limit_otp_ip
from app.core.redis import get_redis
from app.otp import accounts as otp_accounts
from app.schemas.otp import OtpSent, PhoneRequest, PhoneVerify
from app.schemas.user import PasswordChange, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep):
    return await user_service.update_profile(session, user, data)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(data: PasswordChange, user: CurrentUser, session: SessionDep) -> None:
    """Change your password. Every login session ends (refresh tokens revoked) and every
    WebSocket opened with a login closes (4401 ``session ended``); API keys and their sockets
    are not affected."""
    await user_service.change_password(session, user, data)


@router.post(
    "/me/phone",
    response_model=OtpSent,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_otp_ip)],
)
async def request_phone_code(data: PhoneRequest, user: CurrentUser, session: SessionDep):
    """Add or change your WhatsApp number, step 1: a code is sent to it over WhatsApp
    (LightOTP). The number is international with the country code (``+963944123456``; spaces,
    dashes and a leading ``00`` are accepted). 409 ``phone_taken`` if another account has it,
    422 ``invalid_phone`` if WhatsApp cannot reach it, 429 ``otp_resend_wait`` /
    ``otp_too_many`` (Retry-After), 503 ``otp_not_configured`` / ``otp_unavailable``."""
    return await otp_accounts.request_verification(session, get_redis(), user, data.phone)


@router.post("/me/phone/verify", response_model=UserRead)
async def verify_phone(data: PhoneVerify, user: CurrentUser, session: SessionDep):
    """Step 2: the code saves the number on your account (``phone_e164``,
    ``phone_verified_at``); you can then sign in with ``/auth/otp/request`` + ``/auth/otp/login``.
    A wrong or expired code is 400 ``invalid_code``; a code works once."""
    return await otp_accounts.confirm(session, get_redis(), user, data.phone, data.code)


@router.delete("/me/phone", status_code=status.HTTP_204_NO_CONTENT)
async def remove_phone(user: CurrentUser, session: SessionDep) -> None:
    """Remove your WhatsApp number (WhatsApp sign-in stops working). Idempotent."""
    await otp_accounts.remove(session, user)
