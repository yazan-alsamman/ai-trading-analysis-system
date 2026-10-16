"""Checkout, provider events, renewals, cancellation and refunds (docs/subscriptions.md).

Flow: ``POST /subscriptions/checkout`` opens a checkout session and returns the provider's
page. Paying there makes the provider send ``checkout.completed`` (or ``checkout.failed``) to
``POST /payments/webhook/<provider>``. :func:`handle_event` verifies nothing itself (the
provider's ``parse_event`` did), stores the event once (``payment_events.event_id``) and
applies it in the same transaction, so a redelivered event is a no-op.

Renewals run hourly (``subscriptions.renew``): every live subscription whose period ended is
renewed (an invoice charged through the provider), switched to ``past_due`` when the charge
fails, ended when it was canceled, and expired when the grace period of a ``past_due`` one is
over. The same code runs for one subscription in the admin fast-forward tool.
"""

from __future__ import annotations

import calendar
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models.expert import (
    LIVE_STATUSES,
    CheckoutSession,
    CheckoutStatus,
    ExpertProfile,
    Invoice,
    InvoiceStatus,
    PaymentEvent,
    PlanInterval,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.models.notification import NotificationType, Severity
from app.models.user import User, UserRole
from app.notifications import service as notifications
from app.payments.provider import ProviderEvent, get_provider
from app.social.notify import display_name

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")


def add_interval(start: datetime, interval: PlanInterval) -> datetime:
    """One calendar month or year later (the 31st becomes the last day of a shorter month)."""
    months = 1 if interval == PlanInterval.month else 12
    month = start.month - 1 + months
    year, month = start.year + month // 12, month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def monthly(price: Decimal, interval: PlanInterval) -> Decimal:
    """Price normalised to one month (MRR)."""
    return price if interval == PlanInterval.month else (price / 12)


def fee_of(amount: Decimal) -> tuple[Decimal, Decimal]:
    """(platform fee, expert amount) of a paid amount."""
    pct = Decimal(str(get_settings().platform_fee_pct))
    fee = (amount * pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return fee, amount - fee


async def _invoice_number(session: AsyncSession, now: datetime) -> str:
    n = await session.scalar(text("SELECT nextval('invoice_number_seq')"))
    return f"INV-{now.year}-{n:06d}"


def grace_end(sub: Subscription) -> datetime | None:
    if sub.past_due_since is None:
        return None
    return sub.past_due_since + timedelta(days=get_settings().subscription_grace_days)


# --- notifications -------------------------------------------------------------------------------


@dataclass
class Pending:
    """Notifications prepared in the transaction, published after the commit."""

    items: list[notifications.NotifyItem] = field(default_factory=list)
    prepared: notifications.Prepared | None = None


def _sub_data(sub: Subscription, plan_name: str, expert: User, subscriber: User) -> dict:
    return {
        "subscription_id": str(sub.id),
        "expert_id": str(sub.expert_id),
        "expert_name": display_name(expert),
        "subscriber_name": display_name(subscriber),
        "plan_name": plan_name,
        "price": str(sub.price),
        "currency": sub.currency,
        "interval": sub.interval.value,
        "status": sub.status.value,
        "period_end": sub.current_period_end.isoformat(),
    }


async def _notify_sub(
    session: AsyncSession,
    pending: Pending,
    sub: Subscription,
    type_: NotificationType,
    key: str,
    severity: Severity = Severity.info,
    to_expert: bool = False,
    **extra: Any,
) -> None:
    plan = await session.get(SubscriptionPlan, sub.plan_id)
    expert = await session.get(User, sub.expert_id)
    subscriber = await session.get(User, sub.user_id)
    pending.items.append(
        notifications.NotifyItem(
            user_id=sub.expert_id if to_expert else sub.user_id,
            type=type_,
            data={**_sub_data(sub, plan.name if plan else "", expert, subscriber), **extra},
            dedup_key=f"{type_.value}:{sub.id}:{key}",
            severity=severity,
        )
    )


async def flush(session: AsyncSession, redis: Redis | None, pending: Pending) -> None:
    """Store the pending notifications in a savepoint (a failure never breaks the payment);
    call before the commit, then :func:`publish` after it."""
    if not pending.items:
        return
    try:
        async with session.begin_nested():
            pending.prepared = await notifications.prepare(session, redis, pending.items)
    except Exception:  # noqa: BLE001
        logger.exception("subscription notifications failed")
        pending.prepared = notifications.Prepared()


async def publish(redis: Redis | None, pending: Pending) -> None:
    if pending.prepared is not None:
        await notifications.after_commit(redis, pending.prepared)


# --- checkout ------------------------------------------------------------------------------------


async def live_subscription(
    session: AsyncSession, user_id: uuid.UUID, expert_id: uuid.UUID
) -> Subscription | None:
    return await session.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.expert_id == expert_id,
            Subscription.status.in_(LIVE_STATUSES),
        )
    )


async def create_checkout(
    session: AsyncSession, user: User, plan_id: uuid.UUID, return_url: str | None
) -> tuple[CheckoutSession, str]:
    """(session, checkout path). 404 unknown/inactive plan, 400 own plan, 409 already
    subscribed to this expert."""
    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    if plan.expert_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot subscribe to yourself")
    if await live_subscription(session, user.id, plan.expert_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already subscribe to this expert")
    settings = get_settings()
    provider = get_provider()
    checkout = CheckoutSession(
        id=uuid.uuid4(),
        user_id=user.id,
        plan_id=plan.id,
        provider=provider.name,
        return_url=return_url or settings.payment_return_url or None,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.checkout_ttl_minutes),
    )
    start = await provider.create_checkout(checkout.id, plan)
    checkout.provider_ref = start.provider_ref
    session.add(checkout)
    await session.commit()
    return checkout, start.checkout_path


async def open_checkout(session: AsyncSession, checkout_id: uuid.UUID) -> CheckoutSession:
    """The checkout of the demo page; expires it on the way when its time is over."""
    checkout = await session.get(CheckoutSession, checkout_id)
    if checkout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Checkout not found")
    if checkout.status == CheckoutStatus.open and checkout.expires_at <= datetime.now(UTC):
        checkout.status = CheckoutStatus.expired
        await session.commit()
    return checkout


# --- provider events -----------------------------------------------------------------------------


async def handle_event(
    session: AsyncSession, redis: Redis | None, provider: str, event: ProviderEvent
) -> str:
    """Apply a verified provider event once. Returns ``processed`` or ``duplicate``."""
    stored = await session.scalar(
        insert(PaymentEvent)
        .values(provider=provider, event_id=event.event_id, type=event.type, payload=event.data)
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(PaymentEvent.id)
    )
    if stored is None:
        await session.rollback()
        return "duplicate"
    pending = Pending()
    handler = {
        "checkout.completed": _checkout_completed,
        "checkout.failed": _checkout_failed,
        "invoice.paid": _invoice_paid,
        "invoice.payment_failed": _invoice_payment_failed,
    }.get(event.type)
    if handler is not None:
        await handler(session, event.data, pending)
    else:
        logger.info("payments: ignored event type %s", event.type)
    await flush(session, redis, pending)
    await session.commit()
    await publish(redis, pending)
    return "processed"


async def _checkout_completed(session: AsyncSession, data: dict, pending: Pending) -> None:
    checkout = await session.get(
        CheckoutSession, uuid.UUID(data["checkout_id"]), with_for_update=True
    )
    if checkout is None or checkout.status != CheckoutStatus.open:
        return  # unknown, or already handled by an earlier event
    plan = await session.get(SubscriptionPlan, checkout.plan_id)
    now = datetime.now(UTC)
    if await live_subscription(session, checkout.user_id, plan.expert_id) is not None:
        checkout.status, checkout.failure_reason = CheckoutStatus.canceled, "already subscribed"
        return
    trial = plan.trial_days > 0
    end = now + timedelta(days=plan.trial_days) if trial else add_interval(now, plan.interval)
    sub = Subscription(
        id=uuid.uuid4(),
        user_id=checkout.user_id,
        expert_id=plan.expert_id,
        plan_id=plan.id,
        status=SubscriptionStatus.trialing if trial else SubscriptionStatus.active,
        price=plan.price,
        currency=plan.currency,
        interval=plan.interval,
        perks=dict(plan.perks),
        payment_method=data.get("payment_method"),
        current_period_start=now,
        current_period_end=end,
    )
    session.add(sub)
    await session.flush()
    amount = Decimal("0.00") if trial else plan.price
    fee, net = fee_of(amount)
    session.add(
        Invoice(
            number=await _invoice_number(session, now),
            subscription_id=sub.id,
            user_id=sub.user_id,
            expert_id=sub.expert_id,
            kind="trial" if trial else "initial",
            amount=amount,
            currency=plan.currency,
            status=InvoiceStatus.paid,
            period_start=now,
            period_end=end,
            platform_fee=fee,
            expert_amount=net,
            provider=checkout.provider,
            provider_ref=data.get("charge_ref"),
            paid_at=now,
        )
    )
    checkout.status, checkout.subscription_id = CheckoutStatus.completed, sub.id
    await _notify_sub(
        session, pending, sub, NotificationType.subscription_started, "start", trial=trial
    )
    await _notify_sub(
        session,
        pending,
        sub,
        NotificationType.new_subscriber,
        "start",
        to_expert=True,
        trial_days=plan.trial_days,
    )


async def _checkout_failed(session: AsyncSession, data: dict, pending: Pending) -> None:
    checkout = await session.get(
        CheckoutSession, uuid.UUID(data["checkout_id"]), with_for_update=True
    )
    if checkout is not None and checkout.status == CheckoutStatus.open:
        checkout.status = CheckoutStatus.canceled
        checkout.failure_reason = str(data.get("reason") or "payment failed")[:200]


async def _invoice_paid(session: AsyncSession, data: dict, pending: Pending) -> None:
    """A real provider retrying a failed renewal successfully (the demo charges renewals
    synchronously, so this mainly keeps the handler complete)."""
    invoice = await session.get(Invoice, uuid.UUID(data["invoice_id"]), with_for_update=True)
    if invoice is None or invoice.status == InvoiceStatus.paid:
        return
    sub = await session.get(Subscription, invoice.subscription_id, with_for_update=True)
    await _mark_paid(session, invoice, sub, data.get("provider_ref"), datetime.now(UTC), pending)


async def _invoice_payment_failed(session: AsyncSession, data: dict, pending: Pending) -> None:
    invoice = await session.get(Invoice, uuid.UUID(data["invoice_id"]), with_for_update=True)
    if invoice is None or invoice.status != InvoiceStatus.open:
        return
    sub = await session.get(Subscription, invoice.subscription_id, with_for_update=True)
    await _mark_failed(session, invoice, sub, str(data.get("reason") or "payment failed"), pending)


async def _mark_paid(session, invoice: Invoice, sub: Subscription, ref, now, pending) -> None:
    fee, net = fee_of(invoice.amount)
    invoice.status, invoice.paid_at, invoice.provider_ref = InvoiceStatus.paid, now, ref
    invoice.platform_fee, invoice.expert_amount, invoice.failure_reason = fee, net, None
    sub.status, sub.past_due_since = SubscriptionStatus.active, None
    sub.current_period_start, sub.current_period_end = invoice.period_start, invoice.period_end
    await _notify_sub(
        session,
        pending,
        sub,
        NotificationType.subscription_renewed,
        str(invoice.id),
        invoice_number=invoice.number,
        amount=str(invoice.amount),
    )


async def _mark_failed(session, invoice: Invoice, sub: Subscription, reason: str, pending) -> None:
    now = datetime.now(UTC)
    invoice.status, invoice.failure_reason = InvoiceStatus.failed, reason[:200]
    if sub.status in LIVE_STATUSES and sub.status != SubscriptionStatus.past_due:
        sub.status, sub.past_due_since = SubscriptionStatus.past_due, now
    await _notify_sub(
        session,
        pending,
        sub,
        NotificationType.subscription_payment_failed,
        str(invoice.id),
        severity=Severity.warning,
        invoice_number=invoice.number,
        amount=str(invoice.amount),
        reason=reason,
        grace_end=grace_end(sub).isoformat() if grace_end(sub) else None,
    )


# --- renewals ------------------------------------------------------------------------------------


async def _end(session, sub: Subscription, new_status, reason: str, now, pending) -> None:
    sub.status, sub.ended_at = new_status, now
    await _notify_sub(
        session, pending, sub, NotificationType.subscription_canceled, reason, reason=reason
    )


async def process(session: AsyncSession, sub: Subscription, now: datetime, pending: Pending) -> str:
    """Move one subscription forward if its time has come. Returns what happened."""
    if sub.status == SubscriptionStatus.past_due:
        end = grace_end(sub)
        if end is not None and end <= now:
            await _end(session, sub, SubscriptionStatus.expired, "payment_failed", now, pending)
            return "expired"
        return "grace"
    if sub.status not in (SubscriptionStatus.trialing, SubscriptionStatus.active):
        return "ended"
    if sub.current_period_end > now:
        return "not_due"
    if sub.cancel_at_period_end:
        await _end(session, sub, SubscriptionStatus.canceled, "period_end", now, pending)
        return "canceled"
    plan = await session.get(SubscriptionPlan, sub.plan_id)
    if plan is not None and plan.is_active:
        # the plan's current price and perks apply from this renewal on
        sub.price, sub.currency, sub.interval = plan.price, plan.currency, plan.interval
        sub.perks = dict(plan.perks)
    start = sub.current_period_end if sub.current_period_end > now - timedelta(days=1) else now
    invoice = Invoice(
        number=await _invoice_number(session, now),
        subscription_id=sub.id,
        user_id=sub.user_id,
        expert_id=sub.expert_id,
        kind="renewal",
        amount=sub.price,
        currency=sub.currency,
        status=InvoiceStatus.open,
        period_start=start,
        period_end=add_interval(start, sub.interval),
        provider=get_settings().payment_provider,
    )
    session.add(invoice)
    await session.flush()
    result = await get_provider().charge(sub, invoice)
    if result.ok:
        await _mark_paid(session, invoice, sub, result.provider_ref, now, pending)
        return "renewed"
    invoice.provider_ref = result.provider_ref
    await _mark_failed(session, invoice, sub, result.failure_reason or "declined", pending)
    return "past_due"


async def renew_due(
    factory: async_sessionmaker[AsyncSession],
    redis: Redis | None,
    now: datetime | None = None,
    limit: int = 200,
) -> dict[str, int]:
    """The hourly task: due subscriptions (row-locked, SKIP LOCKED) and expired checkouts."""
    now = now or datetime.now(UTC)
    grace = timedelta(days=get_settings().subscription_grace_days)
    counts: dict[str, int] = {}
    async with factory() as session:
        due = await session.scalars(
            select(Subscription)
            .where(
                (
                    Subscription.status.in_(
                        (SubscriptionStatus.trialing, SubscriptionStatus.active)
                    )
                    & (Subscription.current_period_end <= now)
                )
                | (
                    (Subscription.status == SubscriptionStatus.past_due)
                    & (Subscription.past_due_since <= now - grace)
                )
            )
            .order_by(Subscription.current_period_end)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        pending = Pending()
        for sub in list(due):
            outcome = await process(session, sub, now, pending)
            counts[outcome] = counts.get(outcome, 0) + 1
        expired = await session.execute(
            update(CheckoutSession)
            .where(CheckoutSession.status == CheckoutStatus.open, CheckoutSession.expires_at <= now)
            .values(status=CheckoutStatus.expired)
        )
        if expired.rowcount:
            counts["checkouts_expired"] = expired.rowcount
        await flush(session, redis, pending)
        await session.commit()
    await publish(redis, pending)
    return counts


async def fast_forward(
    session: AsyncSession, redis: Redis | None, sub: Subscription, to: str
) -> str:
    """Demo tool: end the current period (or the grace period) now and process the
    subscription at once, as the hourly task would."""
    now = datetime.now(UTC)
    if to == "grace_end":
        if sub.status != SubscriptionStatus.past_due:
            raise HTTPException(status.HTTP_409_CONFLICT, "The subscription is not past_due")
        sub.past_due_since = now - timedelta(days=get_settings().subscription_grace_days, seconds=1)
    else:
        if sub.status not in (SubscriptionStatus.trialing, SubscriptionStatus.active):
            raise HTTPException(status.HTTP_409_CONFLICT, f"The subscription is {sub.status.value}")
        sub.current_period_end = now - timedelta(seconds=1)
    pending = Pending()
    outcome = await process(session, sub, now, pending)
    await flush(session, redis, pending)
    await session.commit()
    await publish(redis, pending)
    return outcome


# --- subscriber actions and admin ----------------------------------------------------------------


async def own_subscription(session: AsyncSession, user: User, sub_id: uuid.UUID) -> Subscription:
    sub = await session.get(Subscription, sub_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    return sub


async def cancel(session: AsyncSession, sub: Subscription, resume: bool = False) -> Subscription:
    """Cancel at period end (access continues until then), or undo that."""
    if sub.status not in LIVE_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The subscription is {sub.status.value}")
    if resume:
        sub.cancel_at_period_end, sub.canceled_at = False, None
    elif not sub.cancel_at_period_end:
        sub.cancel_at_period_end, sub.canceled_at = True, datetime.now(UTC)
    await session.commit()
    await session.refresh(sub)
    return sub


async def refund(session: AsyncSession, redis: Redis | None, invoice: Invoice) -> Invoice:
    """Admin: refund a paid invoice; the subscription it belongs to ends now."""
    if invoice.status != InvoiceStatus.paid:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The invoice is {invoice.status.value}")
    result = await get_provider(invoice.provider).refund(invoice)
    if not result.ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The provider refused the refund")
    now = datetime.now(UTC)
    invoice.status, invoice.refunded_at = InvoiceStatus.refunded, now
    sub = await session.get(Subscription, invoice.subscription_id, with_for_update=True)
    pending = Pending()
    if sub.status in LIVE_STATUSES:
        sub.current_period_end = now
        await _end(session, sub, SubscriptionStatus.canceled, f"refund:{invoice.id}", now, pending)
        pending.items[-1].data["invoice_number"] = invoice.number
    await flush(session, redis, pending)
    await session.commit()
    await publish(redis, pending)
    await session.refresh(invoice)
    return invoice


async def expert_profile_or_404(session: AsyncSession, expert_id: uuid.UUID) -> ExpertProfile:
    profile = await session.get(ExpertProfile, expert_id)
    user = await session.get(User, expert_id)
    if profile is None or user is None or not user.is_active or user.role != UserRole.expert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expert not found")
    return profile


async def invoices_of(session: AsyncSession, sub_ids: list[uuid.UUID]) -> dict:
    out: dict[uuid.UUID, list[Invoice]] = {}
    if not sub_ids:
        return out
    for inv in await session.scalars(
        select(Invoice)
        .where(Invoice.subscription_id.in_(sub_ids))
        .order_by(Invoice.created_at.desc(), Invoice.number.desc())
    ):
        out.setdefault(inv.subscription_id, []).append(inv)
    return out


async def count_live(session: AsyncSession, expert_id: uuid.UUID) -> int:
    from app.payments.entitlements import entitled_clause  # noqa: PLC0415

    return (
        await session.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.expert_id == expert_id, entitled_clause())
        )
        or 0
    )
