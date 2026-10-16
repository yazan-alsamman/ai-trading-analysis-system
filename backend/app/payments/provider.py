"""The payment provider interface and the demo provider (no real money).

A provider does four things for the platform:

- ``create_checkout``: start a hosted payment page for a plan and return its URL;
- ``charge``: charge the saved payment method for an invoice (renewals, trial end);
- ``refund``: refund a paid invoice;
- ``parse_event``: verify and decode a webhook call (signature, timestamp) into an event.

Mapping a real provider (Stripe), for later: ``create_checkout`` = Checkout Session in
``subscription`` or ``payment`` mode with the plan as a Price (``checkout_url`` = its ``url``,
``provider_ref`` = ``cs_…``); the ``checkout.session.completed`` webhook = our
``checkout.completed``; renewals are charged by Stripe itself and arrive as
``invoice.paid`` / ``invoice.payment_failed`` (so ``charge`` would only be used for manual
retries, via PaymentIntents on the saved method); ``refund`` = Refunds API on the invoice's
PaymentIntent; ``parse_event`` = ``stripe.Webhook.construct_event`` with the endpoint secret
(header ``Stripe-Signature``, the same ``t=…,v1=…`` HMAC scheme the demo uses). The webhook path
would be ``/payments/webhook/stripe``; the event handler stays the same.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.redis import get_redis

SIGNATURE_HEADER = "Demo-Signature"
SIGNATURE_TOLERANCE_SECONDS = 300
SECRET_KEY = "payments:demo:webhook-secret"

# Test cards of the demo page (digits only) -> (brand, behavior)
TEST_CARDS = {
    "4242424242424242": ("visa", "ok"),  # succeeds, renewals too
    "4000000000000002": ("visa", "declined"),  # declined at checkout
    "4000000000009995": ("visa", "fail_renewal"),  # succeeds now, renewals fail
}
DECLINED = "card_declined"
RENEWAL_DECLINED = "card_declined: insufficient funds"


class InvalidSignature(Exception):
    pass


@dataclass
class CheckoutStart:
    provider_ref: str
    checkout_path: str  # the hosted page, relative to the site root


@dataclass
class ChargeResult:
    ok: bool
    provider_ref: str
    failure_reason: str | None = None


@dataclass
class ProviderEvent:
    event_id: str
    type: str  # checkout.completed | checkout.failed | invoice.paid | invoice.payment_failed
    data: dict[str, Any] = field(default_factory=dict)
    created: int = 0


class PaymentProvider(Protocol):
    name: str

    async def create_checkout(self, checkout_id: uuid.UUID, plan: Any) -> CheckoutStart: ...

    async def charge(self, subscription: Any, invoice: Any) -> ChargeResult: ...

    async def refund(self, invoice: Any) -> ChargeResult: ...

    async def parse_event(self, body: bytes, headers: Any) -> ProviderEvent: ...


async def demo_secret(redis: Redis | None = None) -> str:
    """``PAYMENT_DEMO_WEBHOOK_SECRET``, or one generated on first use and shared by every
    process through Redis (so each deploy gets its own without configuration)."""
    configured = get_settings().payment_demo_webhook_secret
    if configured:
        return configured
    redis = redis or get_redis()
    await redis.set(SECRET_KEY, secrets.token_urlsafe(32), nx=True)
    return await redis.get(SECRET_KEY)


def sign(secret: str, body: bytes, timestamp: int | None = None) -> str:
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return f"t={timestamp},v1={digest.hexdigest()}"


def card_of(number: str) -> tuple[str, str] | None:
    """(brand, behavior) of a demo test card, or None."""
    return TEST_CARDS.get("".join(ch for ch in number if ch.isdigit()))


class DemoProvider:
    """Behaves like a hosted-checkout provider. The "card" is one of the test cards; only its
    brand, last 4 digits and test behavior are kept (on the subscription)."""

    name = "demo"

    async def create_checkout(self, checkout_id: uuid.UUID, plan: Any) -> CheckoutStart:
        return CheckoutStart(
            provider_ref=f"demo_cs_{secrets.token_hex(8)}",
            checkout_path=f"/api/v1/pay/demo/{checkout_id}",
        )

    async def charge(self, subscription: Any, invoice: Any) -> ChargeResult:
        ref = f"demo_ch_{secrets.token_hex(8)}"
        if invoice.amount == 0:
            return ChargeResult(True, ref)
        behavior = (subscription.payment_method or {}).get("behavior")
        if behavior == "ok":
            return ChargeResult(True, ref)
        if behavior == "fail_renewal":
            return ChargeResult(False, ref, RENEWAL_DECLINED)
        return ChargeResult(False, ref, DECLINED)

    async def refund(self, invoice: Any) -> ChargeResult:
        return ChargeResult(True, f"demo_re_{secrets.token_hex(8)}")

    async def parse_event(self, body: bytes, headers: Any) -> ProviderEvent:
        header = headers.get(SIGNATURE_HEADER) or headers.get(SIGNATURE_HEADER.lower()) or ""
        parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
        try:
            timestamp = int(parts.get("t", ""))
        except ValueError:
            raise InvalidSignature("missing timestamp") from None
        if abs(time.time() - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
            raise InvalidSignature("timestamp outside the tolerance")
        expected = sign(await demo_secret(), body, timestamp).split("v1=", 1)[1]
        if not hmac.compare_digest(expected, parts.get("v1", "")):
            raise InvalidSignature("bad signature")
        try:
            raw = json.loads(body)
            return ProviderEvent(
                event_id=str(raw["id"]),
                type=str(raw["type"]),
                data=dict(raw.get("data") or {}),
                created=int(raw.get("created") or timestamp),
            )
        except (ValueError, KeyError, TypeError):
            raise InvalidSignature("malformed event") from None

    async def event(self, type_: str, data: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        """A signed event as the demo "provider" sends it to the webhook: (body, headers)."""
        body = json.dumps(
            {
                "id": f"evt_demo_{secrets.token_hex(12)}",
                "type": type_,
                "created": int(time.time()),
                "data": data,
            },
            separators=(",", ":"),
        ).encode()
        return body, {SIGNATURE_HEADER: sign(await demo_secret(), body)}


PROVIDERS: dict[str, type] = {"demo": DemoProvider}


def get_provider(name: str | None = None) -> PaymentProvider:
    name = name or get_settings().payment_provider
    if name not in PROVIDERS:
        raise RuntimeError(f"Unknown PAYMENT_PROVIDER {name!r} (available: demo)")
    return PROVIDERS[name]()
