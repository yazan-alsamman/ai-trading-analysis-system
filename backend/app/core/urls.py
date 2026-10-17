"""Absolute URLs of this API as clients see them (e.g. the demo checkout page).

``PUBLIC_BASE_URL`` wins when set. Otherwise the request's scheme and ``Host`` are used: Nginx
forwards the client's ``Host`` with its port (``$http_host``, so ``:8080`` survives) and the
scheme in ``X-Forwarded-Proto``, which uvicorn honours only from the Nginx address
(``--forwarded-allow-ips``). In production the backend port is not published, so only Nginx can
set these headers.
"""

from starlette.requests import Request

from app.core.config import get_settings


def public_base(request: Request) -> str:
    configured = get_settings().public_base_url.rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def absolute(request: Request, path: str) -> str:
    return public_base(request) + path
