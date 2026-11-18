import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

_E164 = re.compile(r"^\+[1-9]\d{6,14}$")
_SEPARATORS = re.compile(r"[\s\-().]")


def normalize_phone(value: str) -> str:
    """E.164: ``+`` and the country code, then the number. Spaces, dashes, dots and brackets
    are dropped and a leading ``00`` becomes ``+`` (``00963 944-123-456`` -> ``+963944123456``).
    LightOTP checks the number against its country's rules when sending."""
    phone = _SEPARATORS.sub("", value.strip())
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if not _E164.match(phone):
        raise ValueError(
            "Phone must be in international format with the country code, e.g. +963944123456"
        )
    return phone


Phone = Annotated[str, Field(min_length=8, max_length=24), AfterValidator(normalize_phone)]
Code = Annotated[str, Field(min_length=4, max_length=8, pattern=r"^\d+$")]


class PhoneRequest(BaseModel):
    phone: Phone


class PhoneVerify(BaseModel):
    phone: Phone
    code: Code


class OtpLogin(BaseModel):
    phone: Phone
    code: Code


class OtpSent(BaseModel):
    """The code was sent (or, for OTP login, would have been if the number had an account)."""

    expires_in: int  # seconds the code is valid
    resend_in: int  # seconds before another code can be requested


class OtpMessageStatus(BaseModel):
    id: str | None
    message_status: str | None  # Pending, Sent, Delivered, Read, Failed, Deleted
    to_phone_e164: str | None
    created_at: str | None
    failure_code: int | None
    failure_title: str | None
    failure_reason: str | None
    failed_at: str | None
