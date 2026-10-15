from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: SessionDep):
    return await user_service.register(session, data)


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, session: SessionDep):
    return await auth_service.login(session, data.email, data.password)


@router.post("/token", response_model=TokenPair, summary="Login (OAuth2 form, for Swagger)")
async def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    return await auth_service.login(session, form.username, form.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, session: SessionDep):
    return await auth_service.refresh(session, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, user: CurrentUser, session: SessionDep) -> None:
    await auth_service.logout(session, user, data.refresh_token)
