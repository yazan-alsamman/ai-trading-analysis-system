"""Request context: an ``X-Request-ID`` per request (the client's, if sane, else a new one),
echoed in the response and attached to every log record; one log line per request (method,
route template, status, duration, user); unhandled errors counted for the system status."""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import ops
from app.core.logging import request_id_var, user_id_var
from app.core.redis import get_redis

logger = logging.getLogger("app.request")

HEADER = "x-request-id"
SANE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
QUIET_PREFIX = "/api/v1/health"  # probes every few seconds: logged only when they fail
_templates: dict[int, dict[object, str]] = {}


def route_template(scope: Scope) -> str:
    """The full path template (``/api/v1/posts/{post_id}``) of the matched route. The route in
    the scope only knows its path inside its router, so the full ones are mapped once per app
    from the flattened routes (keyed by endpoint function)."""
    app = scope.get("app")
    endpoint = scope.get("endpoint")
    if app is None or endpoint is None:
        return scope.get("path", "")
    table = _templates.get(id(app))
    if table is None:
        from fastapi import routing  # noqa: PLC0415

        table = {}
        for context in routing.iter_route_contexts(getattr(app, "routes", [])):
            ep = getattr(context, "endpoint", None)
            if ep is not None:
                table.setdefault(ep, getattr(context, "path_format", None) or context.path)
        _templates[id(app)] = table
    return table.get(endpoint) or scope.get("path", "")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(HEADER.encode(), b"").decode("latin-1")
        request_id = incoming if SANE.match(incoming) else uuid.uuid4().hex
        rid_token = request_id_var.set(request_id)
        uid_token = user_id_var.set(None)
        status = {"code": 500}
        started = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            status["code"] = 500
            raise
        finally:
            code = status["code"]
            path = scope.get("path", "")
            # a probe answering 503 (/health/data: bad market data) is a result, not a crash
            probe_503 = code == 503 and path.startswith(QUIET_PREFIX)
            if code >= 500 and not probe_503:
                await ops.count_error(get_redis())
            if code >= 400 or not path.startswith(QUIET_PREFIX):
                route = route_template(scope)
                client = scope.get("client")
                level = logging.ERROR if code >= 500 else logging.INFO
                logger.log(
                    logging.WARNING if probe_503 else level,
                    "%s %s %s",
                    scope.get("method"),
                    route,
                    code,
                    extra={
                        "method": scope.get("method"),
                        "route": route,
                        "status": code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "client": client[0] if client else None,
                        "user_id": user_id_var.get(),
                        "request_id": request_id,
                    },
                )
            request_id_var.reset(rid_token)
            user_id_var.reset(uid_token)
