"""WhatsApp codes via LightOTP (docs/otp.md): the client against a mock LightOTP, phone
verification, sign-in with a code, limits, error mapping, admin status."""

import json
import logging
from datetime import UTC, datetime

import httpx
import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user import User
from app.otp import lightotp, service
from app.otp.lightotp import LightOtpClient, LightOtpError
from app.schemas.otp import normalize_phone
from tests.utils import bearer

TOKEN = "lotp-test-token-0123456789abcdef"  # also in scripts/check_log_secrets.py
PHONE = "+963944123456"
SEND_URL = "https://api.lightotp.com/SendMessage"
STATUS_URL = "https://api.lightotp.com/CheckMessageStatus"
MSG_ID = "f5b2d2e9-2c1f-4f1d-9c89-2c41f3d9a4e2"


class FakeLightOtp:
    """A mock LightOTP: records requests; ``replies`` (status, body) are used in order, then
    every send succeeds."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.replies: list[tuple[int, dict]] = []

    @property
    def codes(self) -> list[str]:
        return [json.loads(r.content)["otpCode"] for r in self.requests if r.url == SEND_URL]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.replies:
            code, body = self.replies.pop(0)
            return httpx.Response(code, json=body)
        if request.url == STATUS_URL:
            return httpx.Response(
                200,
                json={
                    "id": json.loads(request.content)["id"],
                    "messageStatus": "Delivered",
                    "toPhoneE164": PHONE,
                    "createdAt": "2026-11-16T20:00:00Z",
                    "failureCode": None,
                    "failureTitle": None,
                    "failureReason": None,
                    "failedAt": None,
                },
            )
        return httpx.Response(200, json={"id": MSG_ID, "messageStatus": "Sent"})


async def _clear(redis: Redis) -> None:
    keys = [k async for k in redis.scan_iter(match=f"{get_settings().rate_limit_key_prefix}:otp:*")]
    if keys:
        await redis.delete(*keys)


@pytest.fixture
async def fake(monkeypatch: pytest.MonkeyPatch, redis_client: Redis):
    settings = get_settings()
    monkeypatch.setattr(settings, "lightotp_token", TOKEN)
    monkeypatch.setattr(settings, "lightotp_base_url", "https://api.lightotp.com")
    fake = FakeLightOtp()
    lightotp.set_transport(httpx.MockTransport(fake.handler))
    await _clear(redis_client)
    yield fake
    lightotp.set_transport(None)
    await _clear(redis_client)


async def _verified_user(session: AsyncSession, make_user, phone: str = PHONE) -> User:
    user = await make_user("phone@example.com")
    user.phone_e164 = phone
    user.phone_verified_at = datetime.now(UTC)
    await session.commit()
    return user


# --- the client --------------------------------------------------------------------------


async def test_send_request_follows_the_docs(fake: FakeLightOtp) -> None:
    sent = await LightOtpClient(httpx.MockTransport(fake.handler)).send_otp(
        PHONE, "12345", language="ar", idempotency_key="k-1"
    )
    assert (sent.id, sent.status) == (MSG_ID, "Sent")
    request = fake.requests[0]
    assert request.method == "POST" and str(request.url) == SEND_URL
    assert request.headers["X-Api-Key"] == TOKEN
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "otpCode": "12345",
        "toPhoneE164": PHONE,
        "languageCode": "ar",
        "idempotencyKey": "k-1",
    }


async def test_retry_reuses_the_idempotency_key(fake: FakeLightOtp) -> None:
    fake.replies = [(500, {"errorMessage": "InternalServerError"})]
    sent = await LightOtpClient(httpx.MockTransport(fake.handler)).send_otp(PHONE, "1")
    assert sent.id == MSG_ID and len(fake.requests) == 2
    keys = {json.loads(r.content)["idempotencyKey"] for r in fake.requests}
    assert len(keys) == 1


@pytest.mark.parametrize(
    ("status_code", "message", "kind", "retry"),
    [
        (400, "InvalidphoneNumber", "invalid_phone", None),
        (400, "InsufficientBalance", "unavailable", None),
        (404, "ApiKeyNotFound", "unavailable", None),
        (
            400,
            "You can't send another message to the same number yet. "
            "Please wait 00:01:30 and try again.",
            "cooldown",
            90,
        ),
        (429, "Too many requests", "rate_limited", 60),
    ],
)
async def test_errors_are_classified(
    fake: FakeLightOtp, status_code: int, message: str, kind: str, retry: int | None
) -> None:
    fake.replies = [(status_code, {"errorMessage": message})]
    with pytest.raises(LightOtpError) as info:
        await LightOtpClient(httpx.MockTransport(fake.handler)).send_otp(PHONE, "1")
    assert info.value.kind == kind and info.value.retry_after == retry


async def test_network_failure_is_unavailable(fake: FakeLightOtp) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(LightOtpError) as info:
        await LightOtpClient(httpx.MockTransport(broken)).send_otp(PHONE, "1")
    assert info.value.kind == "unavailable"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("+963 944-123-456", PHONE), ("00963944123456", PHONE), ("+1 (415) 555.0100", "+14155550100")],
)
def test_phone_normalization(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["0944123456", "+0944123456", "+96394412345678901", "abc"])
def test_bad_phone_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone(raw)


# --- phone verification -------------------------------------------------------------------


async def test_verify_phone_flow(
    client: AsyncClient, fake: FakeLightOtp, trader_headers: dict[str, str]
) -> None:
    res = await client.post(
        "/api/v1/users/me/phone", json={"phone": "+963 944 123 456"}, headers=trader_headers
    )
    assert res.status_code == 202, res.text
    assert res.json() == {"expires_in": 300, "resend_in": 60}
    (code,) = fake.codes
    assert len(code) == 5 and code.isdigit()

    wrong = "00000" if code != "00000" else "11111"
    res = await client.post(
        "/api/v1/users/me/phone/verify",
        json={"phone": PHONE, "code": wrong},
        headers=trader_headers,
    )
    assert res.status_code == 400 and res.json()["detail"]["code"] == "invalid_code"

    res = await client.post(
        "/api/v1/users/me/phone/verify", json={"phone": PHONE, "code": code}, headers=trader_headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["phone_e164"] == PHONE and res.json()["phone_verified_at"]

    # a code works once
    res = await client.post(
        "/api/v1/users/me/phone/verify", json={"phone": PHONE, "code": code}, headers=trader_headers
    )
    assert res.status_code == 400

    me = (await client.get("/api/v1/users/me", headers=trader_headers)).json()
    assert me["phone_e164"] == PHONE
    assert (
        await client.delete("/api/v1/users/me/phone", headers=trader_headers)
    ).status_code == 204
    me = (await client.get("/api/v1/users/me", headers=trader_headers)).json()
    assert me["phone_e164"] is None and me["phone_verified_at"] is None


async def test_code_is_bound_to_the_user(
    client: AsyncClient, fake: FakeLightOtp, make_user, login, trader_headers: dict[str, str]
) -> None:
    await client.post("/api/v1/users/me/phone", json={"phone": PHONE}, headers=trader_headers)
    (code,) = fake.codes
    await make_user("other@example.com")
    other = bearer((await login("other@example.com"))["access_token"])
    res = await client.post(
        "/api/v1/users/me/phone/verify", json={"phone": PHONE, "code": code}, headers=other
    )
    assert res.status_code == 400


async def test_phone_of_another_account_is_409(
    client: AsyncClient, fake: FakeLightOtp, session: AsyncSession, make_user, trader_headers
) -> None:
    await _verified_user(session, make_user)
    res = await client.post("/api/v1/users/me/phone", json={"phone": PHONE}, headers=trader_headers)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "phone_taken"
    assert fake.codes == []


async def test_too_many_wrong_codes_drop_the_challenge(
    client: AsyncClient, fake: FakeLightOtp, trader_headers: dict[str, str]
) -> None:
    await client.post("/api/v1/users/me/phone", json={"phone": PHONE}, headers=trader_headers)
    (code,) = fake.codes
    wrong = "00000" if code != "00000" else "11111"
    for _ in range(get_settings().otp_max_attempts):
        res = await client.post(
            "/api/v1/users/me/phone/verify",
            json={"phone": PHONE, "code": wrong},
            headers=trader_headers,
        )
        assert res.status_code == 400
    res = await client.post(
        "/api/v1/users/me/phone/verify", json={"phone": PHONE, "code": code}, headers=trader_headers
    )
    assert res.status_code == 400  # even the right code: a new one must be requested


async def test_resend_wait_and_hourly_cap(
    client: AsyncClient,
    fake: FakeLightOtp,
    trader_headers: dict[str, str],
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, body = "/api/v1/users/me/phone", {"phone": PHONE}
    assert (await client.post(url, json=body, headers=trader_headers)).status_code == 202
    res = await client.post(url, json=body, headers=trader_headers)
    assert res.status_code == 429 and res.json()["detail"]["code"] == "otp_resend_wait"
    assert 1 <= int(res.headers["Retry-After"]) <= 60
    assert len(fake.codes) == 1

    monkeypatch.setattr(get_settings(), "otp_phone_per_hour", 1)
    await redis_client.delete(service._key("resend", service.phone_id(PHONE)))
    res = await client.post(url, json=body, headers=trader_headers)
    assert res.status_code == 429 and res.json()["detail"]["code"] == "otp_too_many"
    assert len(fake.codes) == 1


async def test_lightotp_errors_map_to_api_errors(
    client: AsyncClient, fake: FakeLightOtp, trader_headers: dict[str, str]
) -> None:
    url, body = "/api/v1/users/me/phone", {"phone": PHONE}
    fake.replies = [(400, {"errorMessage": "InvalidphoneNumber"})]
    res = await client.post(url, json=body, headers=trader_headers)
    assert res.status_code == 422 and res.json()["detail"]["code"] == "invalid_phone"

    # the failed send did not take the slot: a retry goes out at once
    fake.replies = [(400, {"errorMessage": "InsufficientBalance"})]
    res = await client.post(url, json=body, headers=trader_headers)
    assert res.status_code == 503 and res.json()["detail"]["code"] == "otp_unavailable"

    fake.replies = [
        (400, {"errorMessage": "You can't send another message yet. Please wait 00:05:00"})
    ]
    res = await client.post(url, json=body, headers=trader_headers)
    assert res.status_code == 429 and res.headers["Retry-After"] == "300"


async def test_not_configured_is_503(
    client: AsyncClient, trader_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "lightotp_token", "")
    res = await client.post("/api/v1/users/me/phone", json={"phone": PHONE}, headers=trader_headers)
    assert res.status_code == 503 and res.json()["detail"]["code"] == "otp_not_configured"
    res = await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    assert res.status_code == 503


async def test_invalid_phone_format_is_422(
    client: AsyncClient, fake: FakeLightOtp, trader_headers: dict[str, str]
) -> None:
    res = await client.post(
        "/api/v1/users/me/phone", json={"phone": "0944123456"}, headers=trader_headers
    )
    assert res.status_code == 422 and fake.requests == []


# --- sign in with a code ------------------------------------------------------------------


async def test_otp_login(
    client: AsyncClient, fake: FakeLightOtp, session: AsyncSession, make_user
) -> None:
    await _verified_user(session, make_user)
    res = await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    assert res.status_code == 202, res.text
    (code,) = fake.codes
    res = await client.post("/api/v1/auth/otp/login", json={"phone": PHONE, "code": code})
    assert res.status_code == 200, res.text
    pair = res.json()
    me = await client.get("/api/v1/users/me", headers=bearer(pair["access_token"]))
    assert me.json()["email"] == "phone@example.com"
    res = await client.post("/api/v1/auth/otp/login", json={"phone": PHONE, "code": code})
    assert res.status_code == 400  # used


async def test_otp_login_unknown_number_reveals_nothing(
    client: AsyncClient, fake: FakeLightOtp
) -> None:
    res = await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    assert res.status_code == 202 and res.json() == {"expires_in": 300, "resend_in": 60}
    assert fake.requests == []  # nothing sent, nothing charged
    res = await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    assert res.status_code == 429  # the same limits as a registered number
    res = await client.post("/api/v1/auth/otp/login", json={"phone": PHONE, "code": "12345"})
    assert res.status_code == 400


async def test_otp_login_inactive_or_unverified(
    client: AsyncClient, fake: FakeLightOtp, session: AsyncSession, make_user
) -> None:
    user = await _verified_user(session, make_user)
    user.is_active = False
    await session.commit()
    await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    assert fake.requests == []


async def test_verify_code_does_not_log_in(
    client: AsyncClient, fake: FakeLightOtp, trader_headers: dict[str, str]
) -> None:
    """A phone-verification code is not a login code."""
    await client.post("/api/v1/users/me/phone", json={"phone": PHONE}, headers=trader_headers)
    (code,) = fake.codes
    res = await client.post("/api/v1/auth/otp/login", json={"phone": PHONE, "code": code})
    assert res.status_code == 400


async def test_secrets_are_not_logged(
    client: AsyncClient,
    fake: FakeLightOtp,
    session: AsyncSession,
    make_user,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _verified_user(session, make_user)
    with caplog.at_level(logging.DEBUG):
        await client.post("/api/v1/auth/otp/request", json={"phone": PHONE})
    (code,) = fake.codes
    assert TOKEN not in caplog.text and PHONE not in caplog.text
    assert f'"{code}"' not in caplog.text


# --- admin --------------------------------------------------------------------------------


async def test_admin_status_and_message_status(
    client: AsyncClient, fake: FakeLightOtp, admin_headers: dict[str, str], trader_headers
) -> None:
    res = await client.get("/api/v1/admin/otp/status", headers=admin_headers)
    assert res.status_code == 200 and res.json()["configured"] is True
    assert TOKEN not in res.text
    res = await client.get(f"/api/v1/admin/otp/messages/{MSG_ID}", headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["message_status"] == "Delivered"
    assert json.loads(fake.requests[-1].content) == {"id": MSG_ID}

    fake.replies = [(404, {"errorMessage": "MessageNotFound"})]
    res = await client.get("/api/v1/admin/otp/messages/nope", headers=admin_headers)
    assert res.status_code == 404

    res = await client.get("/api/v1/admin/otp/status", headers=trader_headers)
    assert res.status_code == 403
