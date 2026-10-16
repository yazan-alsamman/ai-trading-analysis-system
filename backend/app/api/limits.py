"""Rate-limit dependencies (the limiter itself: app/core/rate_limit.py).

- ``limit_identity``: router-level on every /api/v1 route except /health*. Per user (JWT) or per
  API key, per minute: the owner's tier or the key's own lower limit. Routes declare a higher
  cost with ``openapi_extra=EXPENSIVE``.
- ``limit_ip(...)``: per client IP for the unauthenticated auth endpoints.
- ``protected_login``: per-email limit and the failed-login lockout around authentication.

Redis down: normal endpoints fail open (allowed, warning logged, counted in
``rate_limit.fail_open``); login fails closed with 503, because the lockout is what stops
password guessing and must not silently disappear.
"""

import hashlib
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.deps import CredentialsDep, Principal
from app.core import rate_limit
from app.core.config import get_settings
from app.core.rate_limit import Decision, LimiterUnavailable, RateLimitExceeded
from app.core.redis import get_redis
from app.services import auth_service

logger = logging.getLogger(__name__)

COST_KEY = "x-rate-limit-cost"
# openapi_extra of routes that cost more (also documents the cost in the OpenAPI schema)
EXPENSIVE = {COST_KEY: get_settings().rate_limit_expensive_cost}


def client_ip(request_or_ws) -> str:
    """The client address. Behind Nginx this comes from X-Forwarded-For, which uvicorn only
    honours from the proxy (--forwarded-allow-ips); a direct client cannot spoof it."""
    client = request_or_ws.client
    return client.host if client else "unknown"


def route_group(request: Request) -> str:
    route = request.scope.get("route")
    tags = getattr(route, "tags", None)
    return str(tags[0]) if tags else "other"


def _route_cost(request: Request) -> int:
    extra = getattr(request.scope.get("route"), "openapi_extra", None) or {}
    return int(extra.get(COST_KEY, 1))


def _remember(request: Request, decision: Decision) -> None:
    """Keep the most restrictive decision of the request for the RateLimit-* headers
    (written by RateLimitHeadersMiddleware, also on errors and raw Response bodies)."""
    current: Decision | None = getattr(request.state, "rate_limit", None)
    if current is not None and not current.allowed:
        return
    if current is None or not decision.allowed or decision.remaining < current.remaining:
        request.state.rate_limit = decision


def enforce(request: Request, decision: Decision) -> None:
    _remember(request, decision)
    if not decision.allowed:
        raise RateLimitExceeded(decision)


def principal_limit(principal: Principal) -> tuple[int, str]:
    """(requests per minute, tier name). A key's own limit never exceeds its owner's tier."""
    tier = principal.user.role.value
    limit = get_settings().tier_limit(tier)
    if principal.api_key is not None and principal.api_key.rate_limit_per_minute:
        limit = min(limit, principal.api_key.rate_limit_per_minute)
    return limit, tier


async def limit_identity(request: Request, credentials: CredentialsDep) -> None:
    """Without valid credentials there is no identity to limit: the endpoint itself answers
    401/403 (or, for /auth/*, the per-IP limits apply)."""
    if not get_settings().rate_limit_enabled or not isinstance(credentials, Principal):
        return
    limit, tier = principal_limit(credentials)
    api_key = credentials.api_key
    try:
        decision = await rate_limit.hit(
            get_redis(),
            credentials.identity,
            limit,
            cost=_route_cost(request),
            tier=tier,
            group=route_group(request),
            api_key_id=api_key.id if api_key is not None else None,
        )
    except LimiterUnavailable as exc:
        rate_limit.fail_open.record("identity", exc)
        return
    enforce(request, decision)


def _unavailable() -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Login is temporarily unavailable")


def limit_ip(
    name: str, setting: str, *, fail_closed: bool = False
) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """Per-IP limit ``settings.<setting>`` per minute on bucket ``<name>``."""

    async def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        try:
            decision = await rate_limit.hit(
                get_redis(),
                f"ip:{name}:{client_ip(request)}",
                getattr(settings, setting),
                tier="ip",
                group=route_group(request),
            )
        except LimiterUnavailable as exc:
            if fail_closed:
                logger.warning("Rate limiter unavailable, refusing %s: %r", name, exc)
                raise _unavailable() from exc
            rate_limit.fail_open.record(name, exc)
            return
        enforce(request, decision)

    return dependency


limit_login_ip = limit_ip("login", "auth_login_ip_per_minute", fail_closed=True)
limit_register_ip = limit_ip("register", "auth_register_ip_per_minute")
limit_refresh_ip = limit_ip("refresh", "auth_refresh_ip_per_minute")


def _email_id(email: str) -> str:
    """Emails are not stored in Redis key names in clear."""
    return hashlib.sha256(email.lower().encode()).hexdigest()[:32]


async def _locked_for(redis: Redis, email_id: str) -> int:
    """Seconds left of a lockout of this email (0 = not locked)."""
    ttl_ms = await redis.pttl(rate_limit.key("login-lock", email_id))
    return max(1, -(-ttl_ms // 1000)) if ttl_ms > 0 else 0


async def protected_login(request: Request, session: AsyncSession, email: str, password: str):
    """``auth_service.login`` behind the per-email limit and the failed-login lockout.

    Unknown and known emails go through exactly the same steps and answers, so neither the
    limit nor the lockout reveals whether an email is registered.
    """
    settings = get_settings()
    client = (client_ip(request), request.headers.get("user-agent", "")[:300])
    if not settings.rate_limit_enabled:
        return await auth_service.login(session, email, password, client)
    redis, email_id = get_redis(), _email_id(email)
    try:
        locked = await _locked_for(redis, email_id)
        if locked:  # even the right password is refused until the lock expires
            limit = settings.auth_login_email_per_minute
            enforce(request, Decision(False, limit, 0, locked, locked))
        decision = await rate_limit.hit(
            redis,
            f"email:login:{email_id}",
            settings.auth_login_email_per_minute,
            tier="email",
            group=route_group(request),
        )
    except (LimiterUnavailable, RedisError, OSError) as exc:
        logger.warning("Rate limiter unavailable, refusing login: %r", exc)
        raise _unavailable() from exc
    enforce(request, decision)

    try:
        pair = await auth_service.login(session, email, password, client)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and await _record_failure(
            redis, email_id
        ):
            from app.notifications import security  # noqa: PLC0415

            await security.account_locked(
                session, email, settings.login_lockout_seconds, settings.login_lockout_failures
            )
        raise
    try:
        await redis.delete(rate_limit.key("login-fail", email_id))
    except (RedisError, OSError):
        logger.warning("Could not clear the failed-login counter")
    return pair


async def _record_failure(redis: Redis, email_id: str) -> bool:
    """True if this failure locked the email."""
    settings = get_settings()
    try:
        script = redis.register_script(rate_limit.LOGIN_FAILURE_LUA)
        locked = await script(
            keys=[rate_limit.key("login-fail", email_id), rate_limit.key("login-lock", email_id)],
            args=[
                settings.login_lockout_failures,
                settings.login_lockout_window_seconds,
                settings.login_lockout_seconds,
            ],
        )
    except (RedisError, OSError):
        logger.warning("Could not record a failed login")
        return False
    if locked:
        logger.warning(
            "Login locked for %ss after %s failures (email id %s)",
            settings.login_lockout_seconds,
            settings.login_lockout_failures,
            email_id[:8],
        )
    return bool(locked)


class RateLimitHeadersMiddleware:
    """Adds RateLimit-Limit/-Remaining/-Reset (and Retry-After on 429) to every response of a
    limited request, including error responses and endpoints that return a raw Response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                decision: Decision | None = scope.get("state", {}).get("rate_limit")
                if decision is not None:
                    headers = MutableHeaders(scope=message)
                    for name, value in decision.headers().items():
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RateLimitExceeded)
    retry_after = exc.decision.retry_after
    return JSONResponse(
        {"detail": "Rate limit exceeded", "retry_after": retry_after},
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(retry_after)},
    )


# --- WebSocket -----------------------------------------------------------------------------


async def ws_ip_allowed(ip: str) -> bool:
    """At most ``ws_new_connections_ip_per_minute`` new connections per IP (fails open)."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return True
    try:
        decision = await rate_limit.hit(
            get_redis(),
            f"ip:ws:{ip}",
            settings.ws_new_connections_ip_per_minute,
            tier="ip",
            group="realtime",
        )
    except LimiterUnavailable as exc:
        rate_limit.fail_open.record("ws-ip", exc)
        return True
    return decision.allowed


class WsConnectionSlot:
    """One of the ``ws_max_connections_per_identity`` concurrent connections of an identity,
    shared by all API processes through a Redis sorted set. The connection refreshes its entry
    on every heartbeat; entries of a crashed process expire after ``stale_seconds``."""

    def __init__(self, identity: str, connection_id: str, stale_seconds: float) -> None:
        self.key = rate_limit.key("ws", identity)
        self.member = connection_id
        self.stale_ms = int(stale_seconds * 1000)
        self.held = False

    async def acquire(self) -> bool:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return True
        redis = get_redis()
        try:
            script = redis.register_script(rate_limit.WS_ACQUIRE_LUA)
            args = [settings.ws_max_connections_per_identity, self.member, self.stale_ms]
            self.held = bool(await script(keys=[self.key], args=args))
        except (RedisError, OSError) as exc:
            rate_limit.fail_open.record("ws-connections", exc)
            return True
        if not self.held:
            await rate_limit.record_rejection(redis, "identity", "realtime")
        return self.held

    async def touch(self) -> None:
        if not self.held:
            return
        redis = get_redis()
        try:
            script = redis.register_script(rate_limit.WS_TOUCH_LUA)
            await script(keys=[self.key], args=[self.member, self.stale_ms])
        except (RedisError, OSError):
            pass  # the entry expires after stale_ms at worst

    async def release(self) -> None:
        if not self.held:
            return
        self.held = False
        try:
            await get_redis().zrem(self.key, self.member)
        except (RedisError, OSError):
            pass
