from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep, deny_api_keys
from app.api.limits import limit_login_ip, limit_refresh_ip, limit_register_ip, protected_login
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
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
    return await auth_service.refresh(session, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, user: CurrentUser, session: SessionDep) -> None:
    await auth_service.logout(session, user, data.refresh_token)
