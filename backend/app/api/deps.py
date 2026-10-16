from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.redis import get_redis
from app.core.security import credentials_exception, decode_token
from app.db.session import SessionLocal, get_session
from app.models.api_key import ALL_SCOPES, ApiKey, Scope
from app.models.user import User, UserRole
from app.services import api_key_service, market_service

# auto_error=False: missing credentials are handled below, so either scheme may be used
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)
API_KEY_HEADER = "X-API-Key"
api_key_scheme = APIKeyHeader(
    name=API_KEY_HEADER,
    auto_error=False,
    description="An API key (tk_...) for external programs; see docs/api-keys.md",
)

get_db = get_session
SessionDep = Annotated[AsyncSession, Depends(get_db)]


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """For long-lived handlers (WebSockets) that open short sessions instead of holding one."""
    return SessionLocal


async def user_from_access_token(session: AsyncSession, token: str) -> User:
    payload = decode_token(token, "access")
    user = await session.get(User, payload["sub"])
    if user is None:
        raise credentials_exception()
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    return user


@dataclass(frozen=True, eq=False)
class Principal:
    """Who is calling: a user with a JWT (every scope) or through one of their API keys (only
    the key's scopes)."""

    user: User
    api_key: ApiKey | None = None

    @property
    def scopes(self) -> frozenset[str]:
        return ALL_SCOPES if self.api_key is None else frozenset(self.api_key.scopes)

    @property
    def identity(self) -> str:
        """The rate-limit identity: the key for API keys, the user for JWTs."""
        if self.api_key is not None:
            return f"key:{self.api_key.id}"
        return f"user:{self.user.id}"


# What the credentials of a request resolve to: a principal, the error to raise when the
# endpoint needs one, or None without credentials. Resolved once per request (FastAPI caches
# dependencies), shared by the rate limiter and the endpoint's own auth dependency.
Credentials = Principal | HTTPException | None


async def resolve_credentials(
    session: SessionDep,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    api_key: Annotated[str | None, Depends(api_key_scheme)],
) -> Credentials:
    """A bearer token wins over an API key when both are sent."""
    try:
        if token is not None:
            return Principal(await user_from_access_token(session, token))
        if api_key is not None:
            user, row = await api_key_service.authenticate(session, get_redis(), api_key)
            return Principal(user, row)
    except HTTPException as exc:
        return exc
    return None


CredentialsDep = Annotated[Credentials, Depends(resolve_credentials)]


def _not_authenticated() -> HTTPException:
    return credentials_exception("Not authenticated")


async def get_principal(credentials: CredentialsDep) -> Principal:
    if isinstance(credentials, HTTPException):
        raise credentials
    if credentials is None:
        raise _not_authenticated()
    return credentials


def require_scope(scope: Scope) -> Callable[..., Coroutine[Any, Any, Principal]]:
    """JWT users pass; API keys need ``scope``."""

    async def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if scope.value not in principal.scopes:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"This API key lacks the '{scope.value}' scope"
            )
        return principal

    return dependency


async def get_current_user(credentials: CredentialsDep) -> User:
    """A user authenticated with a JWT. API keys are refused: account, /me/* and admin
    endpoints are never reachable with one, whatever its scopes."""
    principal = await get_principal(credentials)
    if principal.api_key is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot be used for this endpoint")
    return principal.user


CurrentUser = Annotated[User, Depends(get_current_user)]

MarketReader = Annotated[Principal, Depends(require_scope(Scope.market_read))]
IndicatorsReader = Annotated[Principal, Depends(require_scope(Scope.indicators_read))]
StrategiesReader = Annotated[Principal, Depends(require_scope(Scope.strategies_read))]
SignalsReader = Annotated[Principal, Depends(require_scope(Scope.signals_read))]
BacktestsReader = Annotated[Principal, Depends(require_scope(Scope.backtests_read))]
NewsReader = Annotated[Principal, Depends(require_scope(Scope.news_read))]


async def get_news_writer(
    principal: Annotated[Principal, Depends(require_scope(Scope.news_write))],
) -> Principal:
    """The ingestion API (the AI side): an API key with ``news:write`` (only admins can put it
    on a key) or an admin's own login. The owner must still be an admin when the key is used."""
    if principal.user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "news:write needs an admin account")
    return principal


NewsWriter = Annotated[Principal, Depends(get_news_writer)]


async def deny_api_keys(request: Request) -> None:
    """For routers without user auth (/auth/*): refuse requests that carry an API key."""
    if request.headers.get(API_KEY_HEADER) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot be used for this endpoint")


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
