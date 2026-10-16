"""The public OpenAPI document (T07, docs/api/openapi.json), built from the routes.

On top of FastAPI's document:

- **operationId** ``<tag>_<function>`` (e.g. ``market_list_instruments``): stable, readable
  names for generated clients;
- **security** per operation from the route's dependencies: ``BearerJWT`` only for endpoints
  that refuse API keys (``get_current_user``), ``BearerJWT`` or ``ApiKey`` for scoped reads,
  none for public ones;
- **error responses** with one shared ``Error`` schema: 401/403 on authenticated routes, 429 on
  rate-limited ones, and the 400/404/409/410/422/502/503 codes the code behind the route can
  actually raise (found by reading the endpoint and the functions it calls, three levels deep);
- **examples** for the main request bodies (``openapi_examples.py``);
- routes outside the contract are hidden (``include_in_schema=False``: the Telegram webhook);
  the demo payment pages and the payment webhook are tagged ``payments-demo``.
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, routing
from fastapi.openapi.utils import _get_api_route_for_openapi, get_openapi

from app.api.openapi_examples import EXAMPLES

ERROR_SCHEMA = {
    "title": "Error",
    "type": "object",
    "required": ["detail"],
    "properties": {
        "detail": {
            "description": "A message, or a list of problems ({loc, msg, type}) for 422",
            "anyOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "object"}},
                {"type": "object"},
            ],
        },
        "retry_after": {
            "type": "integer",
            "description": "429 only: seconds until the request would be accepted",
        },
    },
    "example": {"detail": "Not found"},
}
DESCRIPTIONS = {
    400: "Bad request (a rule of the endpoint, see the message)",
    401: "Missing, invalid or expired credentials",
    403: "Not allowed: role, API-key scope, or the resource's rules",
    404: "Not found (or not visible to you)",
    409: "Conflict with the current state (version, duplicate, already done)",
    410: "Gone",
    422: "Invalid input",
    429: "Rate limit exceeded (Retry-After header)",
    502: "Upstream provider error",
    503: "Temporarily unavailable",
}
DOCUMENTED = set(DESCRIPTIONS)
TAG_DESCRIPTIONS = {
    "health": "Liveness and readiness (no auth, no rate limit).",
    "auth": "Register, login, refresh, logout (JWT).",
    "users": "The logged-in user's account.",
    "admin": "Admin only: users, instruments and candles, API keys, realtime stats.",
    "market": "Instruments and candles (also with an API key: market:read).",
    "indicators": "Indicator catalog and computation (indicators:read).",
    "strategies": "Strategy catalog, preview, activations, signals (strategies:read).",
    "api-keys": "Your API keys and their usage.",
    "workspaces": "Saved trading screens and shared read-only links.",
    "backtests": "Backtests (backtests:read for reading with an API key).",
    "custom-strategies": "Builder and Composite strategies.",
    "risk": "Risk profile, position sizing, trade plans.",
    "notifications": "Inbox, preferences, channels, devices, Telegram linking.",
    "news": "News, sentiment and the ingestion API of the AI side (news:read / news:write).",
    "posts": "Posts, comments, likes, follows, profiles and moderation.",
    "price-alerts": "Price alerts.",
    "experts": "Experts directory, profiles, plans, signals feed, earnings.",
    "subscriptions": "Checkout, subscriptions, invoices (demo payments) and admin tools.",
    "payments-demo": "The demo provider's hosted payment pages and the payment webhook "
    "(no login; no real money).",
    "chat": "Expert chat (REST; live delivery on the WebSocket, see asyncapi.yaml).",
}
STATUS_RE = re.compile(r"HTTP_(\d{3})_|status_code\s*=\s*(\d{3})")


# --- what a route can answer ---------------------------------------------------------------------


def _dependency_calls(dependant, out: list[Callable]) -> list[Callable]:
    for dep in dependant.dependencies:
        if dep.call is not None:
            out.append(dep.call)
        _dependency_calls(dep, out)
    return out


def _source(fn: Callable) -> str | None:
    try:
        return textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return None


def _callees(fn: Callable, source: str) -> list[Callable]:
    """Functions of the app called by ``fn`` (``service.f(...)``, ``f(...)``)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    namespace = getattr(fn, "__globals__", {})
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = None
        if isinstance(node.func, ast.Name):
            target = namespace.get(node.func.id)
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            owner = namespace.get(node.func.value.id)
            target = getattr(owner, node.func.attr, None) if owner is not None else None
        target = inspect.unwrap(target) if callable(target) else None
        if (
            target is not None
            and (inspect.isfunction(target) or inspect.ismethod(target))
            and getattr(target, "__module__", "").startswith("app.")
        ):
            found.append(target)
    return found


def raised_statuses(fn: Callable, depth: int = 3, seen: set | None = None) -> set[int]:
    """HTTP status codes the code of ``fn`` (and what it calls) raises or returns."""
    seen = seen if seen is not None else set()
    fn = inspect.unwrap(fn)
    if fn in seen:
        return set()
    seen.add(fn)
    source = _source(fn)
    if source is None:
        return set()
    codes = {int(a or b) for a, b in STATUS_RE.findall(source)}
    if "VersionConflict(" in source:
        codes.add(409)  # handled in app.main
    if depth > 0:
        for callee in _callees(fn, source):
            codes |= raised_statuses(callee, depth - 1, seen)
    return codes


def _security(calls: list[Callable]) -> list[dict] | None:
    names = {getattr(c, "__name__", "") for c in calls}
    qualnames = {getattr(c, "__qualname__", "") for c in calls}
    if "get_current_user" in names:
        return [{"BearerJWT": []}]
    if "get_principal" in names or any("require_scope" in q for q in qualnames):
        return [{"BearerJWT": []}, {"ApiKey": []}]
    return None


def _rate_limited(calls: list[Callable]) -> bool:
    return any(
        getattr(c, "__name__", "") == "limit_identity"
        or "limit_ip" in getattr(c, "__qualname__", "")
        or "protected_login" in getattr(c, "__name__", "")
        for c in calls
    )


# --- the document --------------------------------------------------------------------------------


def _error_ref() -> dict:
    return {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}


def build(app: FastAPI) -> dict[str, Any]:
    routes = []
    for context in routing.iter_route_contexts(app.routes):
        route = _get_api_route_for_openapi(context)
        if route is None or not route.include_in_schema:
            continue
        routes.append(route)
    visible = routes
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=(
            "REST API of the AI Trading Platform. Live data and chat use the WebSocket "
            "`/ws/market` (see `asyncapi.yaml`). Errors share the `Error` schema; every "
            "rate-limited response carries `RateLimit-*` headers."
        ),
        routes=visible,
        tags=[{"name": n, "description": d} for n, d in TAG_DESCRIPTIONS.items()],
    )
    components = schema.setdefault("components", {})
    components["securitySchemes"] = {
        "BearerJWT": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Access token from POST /auth/login (30 minutes)",
        },
        "ApiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "An API key (tk_...) with the scope the endpoint needs",
        },
    }
    schemas = components.setdefault("schemas", {})
    schemas["Error"] = ERROR_SCHEMA
    for name, example in EXAMPLES.items():
        if name in schemas:
            schemas[name]["examples"] = [example]
    seen_ids: set[str] = set()
    for route in visible:
        calls = _dependency_calls(route.dependant, [])
        security = _security(calls)
        codes = raised_statuses(route.endpoint) & DOCUMENTED
        for call in calls:
            if getattr(call, "__module__", "").startswith("app."):
                codes |= raised_statuses(call, depth=1) & DOCUMENTED
        if security:
            codes |= {401, 403}
        if _rate_limited(calls):
            codes.add(429)
        if "{" in route.path_format:
            codes.add(404)
        tag = (route.tags or ["default"])[0].replace("-", "_")
        for method in sorted(route.methods or []):
            operation = schema["paths"].get(route.path_format, {}).get(method.lower())
            if operation is None:
                continue
            operation_id = f"{tag}_{route.name}"
            if operation_id in seen_ids:
                operation_id = f"{operation_id}_{method.lower()}"
            seen_ids.add(operation_id)
            operation["operationId"] = operation_id
            operation.setdefault("summary", route.name.replace("_", " ").capitalize())
            operation.pop("security", None)
            if security:
                operation["security"] = security
            responses = operation.setdefault("responses", {})
            for code in sorted(codes):
                key = str(code)
                if key == "422" and key in responses:
                    content = responses[key].get("content", {}).get("application/json", {})
                    ref = content.get("schema")
                    if ref and "anyOf" not in ref:
                        content["schema"] = {"anyOf": [ref, {"$ref": "#/components/schemas/Error"}]}
                    continue
                responses.setdefault(
                    key, {"description": DESCRIPTIONS[code], "content": _error_ref()}
                )
    return schema


def install(app: FastAPI) -> None:
    """Serve the same document at /openapi.json (where it is enabled)."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = build(app)
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
