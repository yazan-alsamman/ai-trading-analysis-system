"""Subscriptions and demo payments (docs/subscriptions.md).

- JWT: checkout, the subscriber's subscriptions, cancel/resume; admin: lists, stats, refunds,
  the demo fast-forward tool.
- No auth (like a real provider's pages and webhooks): the demo payment page and its form, the
  return page, and ``POST /payments/webhook/{provider}`` (verified by its HMAC signature).
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.api.limits import limit_ip
from app.core.config import get_settings
from app.core.redis import get_redis
from app.experts import service as experts
from app.models.expert import (
    CheckoutStatus,
    Invoice,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.models.user import User
from app.payments import demo_page, service
from app.payments.provider import DemoProvider, InvalidSignature, card_of, get_provider
from app.schemas.common import Page
from app.schemas.experts import (
    AdminSubscriptionRead,
    CheckoutRead,
    CheckoutRequest,
    FastForward,
    FastForwardResult,
    InvoiceRead,
    SubscriptionRead,
)
from app.social.notify import display_name

router = APIRouter(tags=["subscriptions"])
admin_router = APIRouter(prefix="/admin", tags=["subscriptions"])
# no identity rate limit (no login); "payments-demo" in the OpenAPI document
public_router = APIRouter(tags=["payments-demo"])

limit_pay_ip = limit_ip("demo-pay", "auth_login_ip_per_minute")


def _check_return_url(url: str | None) -> str | None:
    """Only to the web app's origins (CORS_ORIGINS) or the configured return URL: the payment
    page must not become an open redirect."""
    if not url:
        return None
    settings = get_settings()
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    allowed = set(settings.cors_origin_list)
    for extra in (settings.payment_return_url, settings.public_base_url):
        if extra:
            p = urlsplit(extra)
            allowed.add(f"{p.scheme}://{p.netloc}")
    if parts.scheme not in ("http", "https") or origin not in allowed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [{"loc": ["body", "return_url"], "msg": "origin not allowed", "type": "value_error"}],
        )
    return url


# --- checkout and the subscriber ---------------------------------------------------------------


@router.post("/subscriptions/checkout", response_model=CheckoutRead, status_code=201)
async def checkout(data: CheckoutRequest, user: CurrentUser, session: SessionDep):
    """Open a checkout (valid 30 minutes) and send the user to ``checkout_url``. The result
    comes back through the payment webhook; follow it with ``GET /me/subscriptions``."""
    return_url = _check_return_url(data.return_url)
    row, path = await service.create_checkout(session, user, data.plan_id, return_url)
    base = get_settings().public_base_url.rstrip("/")
    return CheckoutRead(
        checkout_id=row.id,
        checkout_url=f"{base}{path}" if base else path,
        checkout_path=path,
        status=row.status.value,
        expires_at=row.expires_at,
    )


@router.get("/me/subscriptions", response_model=list[SubscriptionRead])
async def my_subscriptions(user: CurrentUser, session: SessionDep):
    """Newest first, with status, period, next charge, payment method (brand, last 4) and
    invoices."""
    return await experts.my_subscriptions(session, user)


@router.post("/me/subscriptions/{sub_id}/cancel", response_model=SubscriptionRead)
async def cancel_subscription(sub_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """Cancel at period end: access continues until ``current_period_end``."""
    sub = await service.own_subscription(session, user, sub_id)
    return await experts.read_subscription(session, await service.cancel(session, sub))


@router.post("/me/subscriptions/{sub_id}/resume", response_model=SubscriptionRead)
async def resume_subscription(sub_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    sub = await service.own_subscription(session, user, sub_id)
    return await experts.read_subscription(session, await service.cancel(session, sub, True))


# --- admin ---------------------------------------------------------------------------------------


@admin_router.get("/subscriptions", response_model=Page[AdminSubscriptionRead])
async def admin_subscriptions(
    _: AdminUser,
    session: SessionDep,
    status_: Annotated[SubscriptionStatus | None, Query(alias="status")] = None,
    expert_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await experts.admin_subscriptions(
        session, status_=status_, expert_id=expert_id, user_id=user_id, limit=limit, offset=offset
    )
    return Page[AdminSubscriptionRead](items=items, total=total, limit=limit, offset=offset)


@admin_router.get("/payments/stats")
async def payment_stats(_: AdminUser, session: SessionDep) -> dict:
    """Invoice counts and sums per status, platform fees, subscriptions per status, MRR."""
    return await experts.payment_stats(session)


@admin_router.post("/invoices/{invoice_id}/refund", response_model=InvoiceRead)
async def refund_invoice(invoice_id: uuid.UUID, _: AdminUser, session: SessionDep):
    """Refund a paid invoice; its subscription ends now (409 if not paid)."""
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    return await service.refund(session, get_redis(), invoice)


@admin_router.post("/subscriptions/{sub_id}/fast-forward", response_model=FastForwardResult)
async def fast_forward(sub_id: uuid.UUID, data: FastForward, _: AdminUser, session: SessionDep):
    """DEMO ONLY: end the current period (``to=period_end``) or the grace period
    (``to=grace_end``) now and process the subscription as the hourly task would. Disabled in
    production unless ``PAYMENT_DEMO_TOOLS=true`` (403)."""
    if not get_settings().demo_tools_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Demo tools are disabled in production")
    sub = await session.get(Subscription, sub_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    outcome = await service.fast_forward(session, get_redis(), sub, data.to)
    await session.refresh(sub)
    return FastForwardResult(outcome=outcome, subscription=await experts.admin_read(session, sub))


# --- the demo provider's pages and the webhook ---------------------------------------------------


async def _page_for(session, checkout, error: str | None = None, code: int = 200) -> HTMLResponse:
    plan = await session.get(SubscriptionPlan, checkout.plan_id)
    expert = await session.get(User, plan.expert_id)
    if checkout.status != CheckoutStatus.open:
        text = {
            CheckoutStatus.completed: ("Already paid", "This checkout is complete.", True),
            CheckoutStatus.expired: ("Checkout expired", "Start a new checkout in the app.", False),
            CheckoutStatus.canceled: (
                "Payment failed",
                f"{checkout.failure_reason or 'The payment was declined'}. Start a new checkout.",
                False,
            ),
        }[checkout.status]
        return HTMLResponse(demo_page.message_page(*text), status_code=409 if code == 200 else code)
    return HTMLResponse(
        demo_page.checkout_page(
            checkout_id=str(checkout.id),
            expert_name=display_name(expert),
            plan_name=plan.name,
            price=plan.price,
            currency=plan.currency,
            interval=plan.interval.value,
            trial_days=plan.trial_days,
            expires_at=checkout.expires_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M"),
            error=error,
        ),
        status_code=code,
    )


@public_router.get("/pay/demo/{checkout_id}", response_class=HTMLResponse)
async def demo_checkout_page(checkout_id: uuid.UUID, session: SessionDep):
    """The demo provider's hosted payment page (HTML). No real money: test cards only."""
    return await _page_for(session, await service.open_checkout(session, checkout_id))


@public_router.post(
    "/pay/demo/{checkout_id}/confirm",
    response_class=HTMLResponse,
    dependencies=[Depends(limit_pay_ip)],
)
async def demo_checkout_confirm(
    checkout_id: uuid.UUID,
    session: SessionDep,
    card_number: Annotated[str, Form(max_length=30)],
    expiry: Annotated[str, Form(max_length=7)],
    cvc: Annotated[str, Form(max_length=4)],
    name: Annotated[str, Form(max_length=100)],
):
    """The form of the demo page: the "provider" charges the test card and sends the signed
    ``checkout.completed`` / ``checkout.failed`` event to the payment webhook handler (the same
    verification and processing as ``POST /payments/webhook/demo``), then redirects (303)."""
    checkout = await service.open_checkout(session, checkout_id)
    if checkout.status != CheckoutStatus.open:
        return await _page_for(session, checkout)
    card = card_of(card_number)
    error = None
    if card is None:
        error = "Unknown card. Use one of the test cards below."
    elif not _valid_expiry(expiry):
        error = "The expiry date must be MM/YY in the future."
    elif not (cvc.isdigit() and len(cvc) in (3, 4)):
        error = "The CVC must be 3 or 4 digits."
    if error:
        return await _page_for(session, checkout, error, status.HTTP_422_UNPROCESSABLE_CONTENT)
    brand, behavior = card
    digits = "".join(ch for ch in card_number if ch.isdigit())
    method = {"brand": brand, "last4": digits[-4:], "behavior": behavior}  # never the number
    provider = DemoProvider()
    if behavior == "declined":
        event_type = "checkout.failed"
        data = {
            "checkout_id": str(checkout.id),
            "reason": "card_declined",
            "payment_method": method,
        }
    else:
        event_type = "checkout.completed"
        data = {
            "checkout_id": str(checkout.id),
            "payment_method": method,
            "charge_ref": f"demo_ch_{uuid.uuid4().hex[:16]}",
        }
    body, headers = await provider.event(event_type, data)
    event = await provider.parse_event(body, headers)  # exactly what the webhook verifies
    await service.handle_event(session, get_redis(), provider.name, event)
    outcome = "succeeded" if event_type == "checkout.completed" else "failed"
    target = checkout.return_url or f"/api/v1/pay/demo/{checkout.id}/done"
    sep = "&" if "?" in target else "?"
    query = urlencode({"checkout_id": str(checkout.id), "status": outcome})
    return RedirectResponse(f"{target}{sep}{query}", status_code=status.HTTP_303_SEE_OTHER)


def _valid_expiry(value: str) -> bool:
    try:
        month, year = value.strip().split("/")
        month, year = int(month), 2000 + int(year[-2:])
    except ValueError:
        return False
    now = datetime.now(UTC)
    return 1 <= month <= 12 and (year, month) >= (now.year, now.month)


@public_router.get("/pay/demo/{checkout_id}/done", response_class=HTMLResponse)
async def demo_checkout_done(checkout_id: uuid.UUID, session: SessionDep):
    """The default return page (when no ``return_url`` was given)."""
    checkout = await service.open_checkout(session, checkout_id)
    if checkout.status == CheckoutStatus.completed:
        sub = await session.get(Subscription, checkout.subscription_id)
        text = (
            "Payment successful",
            f"Your subscription is {sub.status.value} until "
            f"{sub.current_period_end:%Y-%m-%d}. You can close this page.",
            True,
        )
    elif checkout.status == CheckoutStatus.canceled:
        text = ("Payment failed", checkout.failure_reason or "The card was declined.", False)
    else:
        text = ("Payment pending", f"The checkout is {checkout.status.value}.", False)
    return HTMLResponse(demo_page.message_page(*text))


@public_router.post("/payments/webhook/{provider}")
async def payment_webhook(provider: str, request: Request, session: SessionDep) -> dict:
    """Provider events (``checkout.completed``, ``checkout.failed``, ``invoice.paid``,
    ``invoice.payment_failed``). 401 on a bad signature; a repeated ``event id`` is accepted
    and ignored (``duplicate``)."""
    if provider != get_settings().payment_provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown payment provider")
    body = await request.body()
    try:
        event = await get_provider(provider).parse_event(body, request.headers)
    except InvalidSignature as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid signature: {exc}") from None
    result = await service.handle_event(session, get_redis(), provider, event)
    return {"status": result, "event_id": event.event_id}
