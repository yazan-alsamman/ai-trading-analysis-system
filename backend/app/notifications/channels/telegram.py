"""Telegram Bot API client (sendMessage, getUpdates, getMe, deleteWebhook) with timeouts.

The bot token is part of the request URL, so no exception text from httpx is ever stored or
logged: errors carry only the status code and Telegram's ``description``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.notifications.channels import PermanentError, RateLimited, TransientError

logger = logging.getLogger(__name__)

TELEGRAM_MAX_TEXT = 4096


def enabled() -> bool:
    return bool(get_settings().telegram_bot_token)


class TelegramClient:
    def __init__(self, token: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        settings = get_settings()
        self.token = token if token is not None else settings.telegram_bot_token
        self.base = f"{settings.telegram_api_base.rstrip('/')}/bot{self.token}/"
        self.timeout = settings.notification_timeout_seconds
        self.transport = transport

    async def call(self, method: str, payload: dict[str, Any], timeout: float | None = None):
        try:
            async with httpx.AsyncClient(
                timeout=timeout or self.timeout, transport=self.transport
            ) as client:
                res = await client.post(self.base + method, json=payload)
        except httpx.TimeoutException:
            raise TransientError(f"telegram {method}: timeout") from None
        except httpx.HTTPError as exc:
            raise TransientError(f"telegram {method}: {type(exc).__name__}") from None
        try:
            body = res.json()
        except ValueError:
            body = {}
        if res.status_code == 200 and body.get("ok"):
            return body.get("result")
        description = str(body.get("description") or res.reason_phrase or "")[:200]
        code = body.get("error_code") or res.status_code
        message = f"telegram {code}: {description}"
        if code == 429:
            retry_after = (body.get("parameters") or {}).get("retry_after", 5)
            raise RateLimited(message, retry_after)
        if code == 403:  # bot blocked by the user, or kicked from the chat
            raise PermanentError(message, action="unlink")
        if code in (400, 404):
            # chat not found / deactivated user: nobody to deliver to any more
            action = "unlink" if "chat not found" in description.lower() else None
            raise PermanentError(message, action=action)
        if code == 401:
            raise TransientError(message)  # bad token: counted by the circuit breaker
        raise TransientError(message)

    async def send_message(self, chat_id: int | str, text: str) -> str:
        result = await self.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text[:TELEGRAM_MAX_TEXT],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        return str((result or {}).get("message_id", ""))

    async def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return await self.call("getUpdates", payload, timeout=timeout + 10) or []

    async def get_me(self) -> dict[str, Any]:
        return await self.call("getMe", {}) or {}

    async def delete_webhook(self) -> None:
        await self.call("deleteWebhook", {"drop_pending_updates": False})
