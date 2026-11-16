"""LightOTP HTTP client: WhatsApp OTP delivery (https://lightotp.com/en/docs/otp-messages).

LightOTP only delivers a code we generate; generating, storing and checking it is ours
(app/otp/service.py). Two endpoints, both ``POST`` with a JSON body and the API key in the
``X-Api-Key`` header:

- ``/SendMessage`` ``{"otpCode", "toPhoneE164", "languageCode"?, "idempotencyKey"?}`` ->
  ``200 {"id", "messageStatus"}``. ``otpCode`` is 1-8 letters or digits, ``toPhoneE164`` an
  E.164 number. ``idempotencyKey`` (a UUID) makes a retry replay the first answer without a
  second message or charge, so the one retry here reuses it.
- ``/CheckMessageStatus`` ``{"id"}`` -> ``{"id", "messageStatus", "toPhoneE164", "createdAt",
  "failureCode", "failureTitle", "failureReason", "failedAt"}``.

``messageStatus`` is one of Pending, Sent, Delivered, Read, Failed, Deleted. Errors are JSON
``{"errorMessage": "<code or text>"}`` (e.g. ``InsufficientBalance``, ``InvalidphoneNumber``);
a repeated send to the same number within LightOTP's own growing cooldown (30 s up to 6 h) is
refused with "... Please wait HH:mm:ss and try again.", and its per-IP limit answers 429.

The key is never logged: requests are logged by path only, and errors by LightOTP's code.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SEND_PATH = "/SendMessage"
STATUS_PATH = "/CheckMessageStatus"
MESSAGE_STATUSES = ("Pending", "Sent", "Delivered", "Read", "Failed", "Deleted")

# errorMessage codes that mean the destination number is wrong (the caller's fault, 422)
PHONE_ERRORS = frozenset(
    {"InvalidphoneNumber", "PhoneNumberCanNotBeEmpty", "DestinationPhoneNumberIsRequired"}
)
_WAIT = re.compile(r"(\d+):(\d{2}):(\d{2})")


class LightOtpError(Exception):
    """A failed call. ``kind``: ``not_configured`` (no token), ``invalid_phone``,
    ``cooldown`` (``retry_after`` seconds), ``rate_limited``, ``not_found`` (status check of an
    unknown id) or ``unavailable`` (key, balance, sender, template, WhatsApp, network, 5xx:
    nothing the user can fix)."""

    def __init__(
        self,
        kind: str,
        error_message: str = "",
        status_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(f"LightOTP {kind}: {status_code} {error_message}".strip())
        self.kind = kind
        self.error_message = error_message
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass(frozen=True)
class SentMessage:
    id: str
    status: str


def configured() -> bool:
    return bool(get_settings().lightotp_token.strip())


def _wait_seconds(text: str) -> int | None:
    """``HH:mm:ss`` in a cooldown message, in seconds."""
    match = _WAIT.search(text)
    if match is None:
        return None
    h, m, s = (int(x) for x in match.groups())
    return h * 3600 + m * 60 + s


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        return str(body.get("errorMessage") or body.get("title") or "")[:300]
    return ""


def _classify(response: httpx.Response) -> LightOtpError:
    message = _error_message(response)
    code = response.status_code
    if code == 429:
        retry = response.headers.get("Retry-After")
        return LightOtpError(
            "rate_limited", message, code, int(retry) if retry and retry.isdigit() else 60
        )
    if message in PHONE_ERRORS:
        return LightOtpError("invalid_phone", message, code)
    wait = _wait_seconds(message)
    if wait is not None and "wait" in message.lower():
        return LightOtpError("cooldown", message, code, max(1, wait))
    if message == "MessageNotFound":
        return LightOtpError("not_found", message, code)
    return LightOtpError("unavailable", message, code)


class LightOtpClient:
    """One instance per call site; ``transport`` is for tests (httpx.MockTransport)."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        settings = get_settings()
        return httpx.AsyncClient(
            base_url=settings.lightotp_base_url.rstrip("/"),
            timeout=settings.lightotp_timeout_seconds,
            transport=self._transport,
            headers={
                "X-Api-Key": settings.lightotp_token.strip(),
                "Accept": "application/json",
                "Accept-Language": "en",  # error codes in English (we map them)
            },
        )

    async def _post(self, path: str, body: dict[str, Any], *, retries: int) -> httpx.Response:
        if not configured():
            raise LightOtpError("not_configured", "LIGHTOTP_TOKEN is not set")
        last: Exception | None = None
        async with self._client() as client:
            for attempt in range(retries + 1):
                try:
                    response = await client.post(path, json=body)
                except httpx.HTTPError as exc:  # timeout, DNS, connection reset
                    last = exc
                    logger.warning("LightOTP %s failed (attempt %d): %r", path, attempt + 1, exc)
                    continue
                if response.status_code >= 500 and attempt < retries:
                    logger.warning("LightOTP %s answered %d, retrying", path, response.status_code)
                    continue
                return response
        raise LightOtpError("unavailable", repr(last)) from last

    async def send_otp(
        self,
        phone_e164: str,
        code: str,
        *,
        language: str | None = None,
        idempotency_key: str | None = None,
    ) -> SentMessage:
        body: dict[str, Any] = {
            "otpCode": code,
            "toPhoneE164": phone_e164,
            # the same key on the retry: LightOTP replays its first answer, no second charge
            "idempotencyKey": idempotency_key or str(uuid.uuid4()),
        }
        if language:
            body["languageCode"] = language
        response = await self._post(SEND_PATH, body, retries=1)
        if response.status_code != 200:
            error = _classify(response)
            logger.warning(
                "LightOTP send refused: %s %s", response.status_code, error.error_message
            )
            raise error
        data = response.json()
        return SentMessage(id=str(data["id"]), status=str(data.get("messageStatus", "")))

    async def message_status(self, message_id: str) -> dict[str, Any]:
        response = await self._post(STATUS_PATH, {"id": message_id}, retries=1)
        if response.status_code != 200:
            raise _classify(response)
        data = response.json()
        return {
            "id": data.get("id"),
            "message_status": data.get("messageStatus"),
            "to_phone_e164": data.get("toPhoneE164"),
            "created_at": data.get("createdAt"),
            "failure_code": data.get("failureCode"),
            "failure_title": data.get("failureTitle"),
            "failure_reason": data.get("failureReason"),
            "failed_at": data.get("failedAt"),
        }


_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Tests route every client to a mock transport."""
    global _transport
    _transport = transport


def get_client() -> LightOtpClient:
    return LightOtpClient(_transport)
