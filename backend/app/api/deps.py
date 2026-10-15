from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import credentials_exception, decode_token
from app.db.session import get_session
from app.models.user import User, UserRole
from app.services import market_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

get_db = get_session
SessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    session: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    payload = decode_token(token, "access")
    user = await session.get(User, payload["sub"])
    if user is None:
        raise credentials_exception()
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    """Allow only the given roles. Admin always passes; other roles are not hierarchical.

    The role is read from the database, so a role change applies to existing access tokens.
    """
    allowed = frozenset(roles) | {UserRole.admin}

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_roles(UserRole.admin))]


AggregateRefresher = Callable[[datetime, datetime], Awaitable[None]]


def get_aggregate_refresher() -> AggregateRefresher:
    """Overridable in tests: refreshing aggregates needs committed data and its own connection."""
    return market_service.refresh_aggregates


AggregateRefresherDep = Annotated[AggregateRefresher, Depends(get_aggregate_refresher)]
