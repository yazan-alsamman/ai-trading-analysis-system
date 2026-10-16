"""Mobile push through FCM HTTP v1.

Credentials: ``FCM_PROJECT_ID`` and ``FCM_CREDENTIALS_JSON`` (the service-account JSON as one
value, or a path to the file). The OAuth access token (from a signed JWT assertion, RS256) is
cached in Redis until shortly before it expires, so all worker processes share it.
"""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import jwt
from redis.asyncio import Redis

from app.core.config import get_settings
from app.notifications.channels import PermanentError, RateLimited, TransientError

logger = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
TOKEN_KEY = "notif:fcm:access-token"
INVALID_TOKEN_CODES = {"UNREGISTERED", "INVALID_ARGUMENT", "SENDER_ID_MISMATCH"}


@lru_cache(maxsize=4)
def _credentials(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        text = raw if raw.lstrip().startswith("{") else Path(raw).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError):
        logger.warning("FCM_CREDENTIALS_JSON is not valid JSON or a readable file: push disabled")
        return None
    if not {"client_email", "private_key"} <= set(data):
        logger.warning("FCM credentials lack client_email/private_key: push disabled")
        return None
    return data


def credentials() -> dict[str, Any] | None:
    return _credentials(get_settings().fcm_credentials_json)


def enabled() -> bool:
    return bool(get_settings().fcm_project_id) and credentials() is not None


class FcmClient:
    def __init__(self, redis: Redis, transport: httpx.AsyncBaseTransport | None = None):
        settings = get_settings()
        self.redis = redis
        self.project = settings.fcm_project_id
        self.creds = credentials() or {}
        self.timeout = settings.notification_timeout_seconds
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self.transport)

    async def access_token(self) -> str:
        cached = await self.redis.get(TOKEN_KEY)
        if cached:
            return cached if isinstance(cached, str) else cached.decode()
        now = int(time.time())
        token_uri = self.creds.get("token_uri", "https://oauth2.googleapis.com/token")
        assertion = jwt.encode(
            {
                "iss": self.creds["client_email"],
                "scope": SCOPE,
                "aud": token_uri,
                "iat": now,
                "exp": now + 3600,
            },
            self.creds["private_key"],
            algorithm="RS256",
        )
        try:
            async with self._client() as client:
                res = await client.post(
                    token_uri,
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": assertion,
                    },
                )
        except httpx.HTTPError as exc:
            raise TransientError(f"fcm oauth: {type(exc).__name__}") from None
        if res.status_code != 200:
            raise TransientError(f"fcm oauth {res.status_code}")
        body = res.json()
        token = body["access_token"]
        ttl = max(60, int(body.get("expires_in", 3600)) - 120)
        await self.redis.set(TOKEN_KEY, token, ex=ttl)
        return token

    async def send(self, device_token: str, title: str, body: str, data: dict[str, str]) -> str:
        message = {
            "message": {
                "token": device_token,
                "notification": {"title": title, "body": body},
                "data": {k: str(v) for k, v in data.items()},
                "android": {"priority": "high", "notification": {"channel_id": "signals"}},
                "apns": {
                    "headers": {"apns-priority": "10"},
                    "payload": {"aps": {"sound": "default"}},
                },
            }
        }
        access = await self.access_token()
        url = FCM_URL.format(project=self.project)
        try:
            async with self._client() as client:
                res = await client.post(
                    url, json=message, headers={"Authorization": f"Bearer {access}"}
                )
        except httpx.TimeoutException:
            raise TransientError("fcm: timeout") from None
        except httpx.HTTPError as exc:
            raise TransientError(f"fcm: {type(exc).__name__}") from None
        if res.status_code == 200:
            return str(res.json().get("name", ""))
        try:
            error = res.json().get("error", {})
        except ValueError:
            error = {}
        codes = {
            d.get("errorCode")
            for d in error.get("details", [])
            if isinstance(d, dict) and d.get("errorCode")
        }
        status = error.get("status") or ""
        text = f"fcm {res.status_code} {status} {','.join(sorted(codes))}".strip()
        if res.status_code == 404 or codes & INVALID_TOKEN_CODES:
            raise PermanentError(text, action="delete_device")
        if res.status_code == 401:
            await self.redis.delete(TOKEN_KEY)  # expired / revoked: fetch a new one next time
            raise TransientError(text)
        if res.status_code == 429 or "QUOTA_EXCEEDED" in codes:
            raise RateLimited(text, float(res.headers.get("Retry-After", 30)))
        if res.status_code == 400:
            raise PermanentError(text)
        raise TransientError(text)
