from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep, deny_api_keys
from app.api.limits import (
    client_ip,
    limit_login_ip,
    limit_otp_ip,
    limit_refresh_ip,
    limit_register_ip,
    protected_login,
)
from app.core.redis import get_redis
from app.otp import accounts as otp_accounts
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.otp import OtpLogin, OtpSent, PhoneRequest
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service, user_service

# An API key never reaches /auth/*, whatever its scopes.
router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(deny_api_keys)])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_register_ip)],
)
async def register(data: UserCreate, session: SessionDep):
    return await user_service.register(session, data)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(limit_login_ip)])
async def login(data: LoginRequest, request: Request, session: SessionDep):
    return await protected_login(request, session, data.email, data.password)


@router.post(
    "/token",
    response_model=TokenPair,
    summary="Login (OAuth2 form, for Swagger)",
    dependencies=[Depends(limit_login_ip)],
)
async def token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], request: Request, session: SessionDep
):
    return await protected_login(request, session, form.username, form.password)


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(limit_refresh_ip)])
async def refresh(data: RefreshRequest, session: SessionDep):
    """Rotate the refresh token: a new pair in the same login session (the access token keeps
    its ``sid``). A refresh token presented again after its rotation is treated as stolen:
    every session of the user ends and their WebSockets close (4401 ``session ended``)."""
    return await auth_service.refresh(session, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, user: CurrentUser, session: SessionDep) -> None:
    """End this login session: its whole refresh-token family is revoked and its WebSockets
    close at once (4401 ``session ended``). Sessions on other devices stay. Access tokens are
    stateless: REST calls with one keep working until it expires. Idempotent."""
    await auth_service.logout(session, user, data.refresh_token)


@router.post(
    "/otp/request",
    response_model=OtpSent,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_otp_ip)],
)
async def otp_request(data: PhoneRequest, session: SessionDep):
    """Sign in with WhatsApp, step 1: send a code (LightOTP) to a number verified on an account
    (``POST /users/me/phone/verify``). The answer is the same for a number without an account,
    so it does not reveal who is registered. One code per number every ``resend_in`` seconds
    (429 ``otp_resend_wait`` with Retry-After), a few per hour (429 ``otp_too_many``); 503
    ``otp_not_configured`` when LIGHTOTP_TOKEN is not set on the server."""
    return await otp_accounts.request_login_code(session, get_redis(), data.phone)


@router.post("/otp/login", response_model=TokenPair, dependencies=[Depends(limit_login_ip)])
async def otp_login(data: OtpLogin, request: Request, session: SessionDep):
    """Sign in with WhatsApp, step 2: the code from step 1 gives a token pair, like
    ``/auth/login``. A wrong or expired code is 400 ``invalid_code``; after a few wrong codes
    the code is dropped and a new one must be requested. A code works once."""
    client = (client_ip(request), request.headers.get("user-agent", "")[:300])
    return await otp_accounts.login(session, get_redis(), data.phone, data.code, client)
