from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
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
    await user_service.change_password(session, user, data)
