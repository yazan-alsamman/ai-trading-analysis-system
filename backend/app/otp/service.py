"""One-time codes over WhatsApp (docs/otp.md): issue, deliver with LightOTP, check.

A code is ours: ``otp_length`` random digits, stored in Redis only as an HMAC (keyed with
JWT_SECRET) for ``otp_ttl_seconds``, together with the number of wrong tries and, for
``verify_phone``, the user it was issued to. LightOTP only delivers it (app/otp/lightotp.py).

Per phone number (all purposes together): one code every ``otp_resend_seconds`` and at most
``otp_phone_per_hour`` per hour. A new code replaces the previous one. ``otp_max_attempts``
wrong codes drop the challenge, so a 5-digit code cannot be guessed. A right code is consumed
atomically (it works once). Phone numbers never appear in Redis key names or logs in clear.

Purposes: ``verify_phone`` (a signed-in user proves a number, which is then saved on the
account) and ``login`` (sign in with a code sent to a verified number).
"""

import hashlib
import hmac
import logging
import secrets
import uuid
from enum import StrEnum
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import get_settings
from app.otp import lightotp
from app.otp.lightotp import LightOtpError

logger = logging.getLogger(__name__)


class Purpose(StrEnum):
    verify_phone = "verify_phone"
    login = "login"


def error(status_code: int, code: str, message: str, retry_after: int | None = None):
    headers = {"Retry-After": str(int(retry_after))} if retry_after is not None else None
    return HTTPException(status_code, {"code": code, "message": message}, headers)


def not_configured() -> HTTPException:
    return error(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "otp_not_configured",
        "WhatsApp codes are not available (LIGHTOTP_TOKEN is not set)",
    )


def invalid_code() -> HTTPException:
    return error(
        status.HTTP_400_BAD_REQUEST,
        "invalid_code",
        "The code is wrong or expired; request a new one",
    )


def _digest(value: str) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def phone_id(phone: str) -> str:
    return _digest(f"phone:{phone}")[:32]


def _key(kind: str, *parts: str) -> str:
    # under the rate limiter's prefix ("rl" in production, "test-rl" in tests)
    return ":".join((get_settings().rate_limit_key_prefix, "otp", kind, *parts))


def new_code() -> str:
    length = get_settings().otp_length
    return f"{secrets.randbelow(10**length):0{length}d}"


async def _take_send_slot(redis: Redis, pid: str) -> str:
    """Reserve a send to this number (resend wait and hourly cap); returns the hour key."""
    settings = get_settings()
    resend = _key("resend", pid)
    if not await redis.set(resend, "1", ex=settings.otp_resend_seconds, nx=True):
        wait = max(1, await redis.ttl(resend))
        raise error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "otp_resend_wait",
            f"Wait {wait} seconds before requesting another code",
            wait,
        )
    hour = _key("hour", pid)
    count = await redis.incr(hour)
    if count == 1:
        await redis.expire(hour, 3600)
    if count > settings.otp_phone_per_hour:
        wait = max(1, await redis.ttl(hour))
        raise error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "otp_too_many",
            "Too many codes were sent to this number; try again later",
            wait,
        )
    return hour


async def _give_back(redis: Redis, pid: str, hour: str) -> None:
    """A send that did not happen does not count against the number."""
    await redis.delete(_key("resend", pid))
    await redis.decr(hour)


async def send_code(
    redis: Redis,
    purpose: Purpose,
    phone: str,
    *,
    user_id: uuid.UUID | None = None,
    deliver: bool = True,
) -> dict[str, Any]:
    """Issue a code for ``phone`` and send it over WhatsApp.

    ``deliver=False`` (OTP login to a number no account has) takes the same per-number limits
    and answers the same, but sends and stores nothing, so the answer does not reveal whether
    the number is registered."""
    settings = get_settings()
    if not lightotp.configured():
        raise not_configured()
    pid = phone_id(phone)
    hour = await _take_send_slot(redis, pid)
    answer = {"expires_in": settings.otp_ttl_seconds, "resend_in": settings.otp_resend_seconds}
    if not deliver:
        return answer

    code = new_code()
    try:
        sent = await lightotp.get_client().send_otp(
            phone,
            code,
            language=settings.lightotp_language.strip() or None,
            idempotency_key=str(uuid.uuid4()),
        )
    except LightOtpError as exc:
        if exc.kind == "cooldown":  # LightOTP's own wait for this number is longer than ours
            await redis.set(_key("resend", pid), "1", ex=exc.retry_after or 60)
            raise error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "otp_resend_wait",
                f"Wait {exc.retry_after} seconds before requesting another code",
                exc.retry_after,
            ) from exc
        await _give_back(redis, pid, hour)
        if exc.kind == "invalid_phone":
            raise error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_phone",
                "This number cannot receive WhatsApp messages; check it and the country code",
            ) from exc
        if exc.kind == "rate_limited":
            raise error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "otp_busy",
                "Too many codes are being sent right now; try again shortly",
                exc.retry_after,
            ) from exc
        if exc.kind == "not_configured":
            raise not_configured() from exc
        logger.error("Sending a WhatsApp code failed: %s", exc)
        raise error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "otp_unavailable",
            "The code could not be sent; try again later",
        ) from exc

    challenge = {
        "code": _digest(f"code:{purpose}:{phone}:{code}"),
        "attempts": 0,
        "user": str(user_id) if user_id else "",
        "message": sent.id,
    }
    key = _key("challenge", purpose.value, pid)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(key)  # a new code replaces the previous one (and its wrong tries)
        pipe.hset(key, mapping=challenge)
        pipe.expire(key, settings.otp_ttl_seconds)
        await pipe.execute()
    logger.info("WhatsApp code sent (%s, message %s, status %s)", purpose, sent.id, sent.status)
    return {**answer, "message_id": sent.id}


async def check_code(
    redis: Redis, purpose: Purpose, phone: str, code: str, *, user_id: uuid.UUID | None = None
) -> None:
    """Consume the code or raise 400 ``invalid_code``. Wrong tries count; the last allowed
    wrong try drops the challenge."""
    if not lightotp.configured():
        raise not_configured()
    key = _key("challenge", purpose.value, phone_id(phone))
    stored = await redis.hgetall(key)
    if not stored or (user_id is not None and stored.get("user") != str(user_id)):
        raise invalid_code()
    attempts = await redis.hincrby(key, "attempts", 1)
    if attempts > get_settings().otp_max_attempts:
        await redis.delete(key)
        raise invalid_code()
    expected = stored.get("code", "")
    if not hmac.compare_digest(expected, _digest(f"code:{purpose}:{phone}:{code}")):
        if attempts >= get_settings().otp_max_attempts:
            await redis.delete(key)
        raise invalid_code()
    if not await redis.delete(key):  # a concurrent request used it first
        raise invalid_code()


async def message_status(message_id: str) -> dict[str, Any]:
    """Delivery status of a sent code (admin troubleshooting)."""
    if not lightotp.configured():
        raise not_configured()
    try:
        return await lightotp.get_client().message_status(message_id)
    except LightOtpError as exc:
        if exc.kind == "not_found":
            raise error(status.HTTP_404_NOT_FOUND, "message_not_found", "Unknown message") from exc
        raise error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "otp_unavailable", "LightOTP did not answer"
        ) from exc


def status_view() -> dict[str, Any]:
    settings = get_settings()
    return {
        "provider": "lightotp",
        "configured": lightotp.configured(),
        "base_url": settings.lightotp_base_url,
        "language": settings.lightotp_language or None,
        "code_length": settings.otp_length,
        "ttl_seconds": settings.otp_ttl_seconds,
        "max_attempts": settings.otp_max_attempts,
        "resend_seconds": settings.otp_resend_seconds,
        "per_phone_per_hour": settings.otp_phone_per_hour,
    }
