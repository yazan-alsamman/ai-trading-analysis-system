"""Experts (Y19): public profiles, subscription plans, subscriptions and the demo payment
records (invoices, checkout sessions, provider events)."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BIO_MAX = 5_000
HEADLINE_MAX = 120
MAX_ACTIVE_PLANS = 3
PERKS = ("premium_posts", "chat", "signals_feed")


class PlanInterval(StrEnum):
    month = "month"
    year = "year"


class SubscriptionStatus(StrEnum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"  # a renewal failed; entitled during the grace period
    canceled = "canceled"  # ended by the subscriber (at period end) or a refund
    expired = "expired"  # ended because payment failed past the grace period


# a subscription in one of these is "not ended" (at most one per user and expert)
LIVE_STATUSES = (
    SubscriptionStatus.trialing,
    SubscriptionStatus.active,
    SubscriptionStatus.past_due,
)


class InvoiceStatus(StrEnum):
    open = "open"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"
    void = "void"


class CheckoutStatus(StrEnum):
    open = "open"
    completed = "completed"
    expired = "expired"
    canceled = "canceled"  # declined card or abandoned


def _enum(cls, name: str) -> SAEnum:
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


def _ts(**kw):
    return mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp(), **kw)


class ExpertProfile(Base):
    """An expert's public profile, shown in the experts directory when listed."""

    __tablename__ = "expert_profiles"
    __table_args__ = (Index("ix_expert_profiles_listed", "is_listed"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    headline: Mapped[str] = mapped_column(String(HEADLINE_MAX))
    bio: Mapped[str] = mapped_column(Text, default="", server_default="")
    markets: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list, server_default=text("'{}'")
    )
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(8)), default=list, server_default=text("'{}'")
    )
    chat_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    response_time_hint: Mapped[str | None] = mapped_column(String(60))
    is_listed: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts(onupdate=func.clock_timestamp())


class SubscriptionPlan(Base):
    """An expert's offer. Price changes only apply to new subscriptions: a subscription keeps
    the price it was bought at (copied onto it) until it ends."""

    __tablename__ = "subscription_plans"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_subscription_plans_price"),
        CheckConstraint("trial_days BETWEEN 0 AND 30", name="ck_subscription_plans_trial"),
        Index("ix_subscription_plans_expert", "expert_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    expert_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    interval: Mapped[PlanInterval] = mapped_column(_enum(PlanInterval, "plan_interval"))
    trial_days: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    perks: Mapped[dict[str, Any]] = mapped_column(JSONB)  # premium_posts, chat, signals_feed
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = _ts()


class Subscription(Base):
    """``price``, ``currency``, ``interval`` and ``perks`` are copied from the plan when the
    subscription starts and when it renews. ``payment_method`` keeps only
    ``{brand, last4, behavior}`` (never a card number)."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("user_id <> expert_id", name="ck_subscriptions_not_self"),
        Index(
            "uq_subscriptions_live",
            "user_id",
            "expert_id",
            unique=True,
            postgresql_where=text("status IN ('trialing', 'active', 'past_due')"),
        ),
        Index("ix_subscriptions_expert_status", "expert_id", "status"),
        Index("ix_subscriptions_user", "user_id", text("created_at DESC")),
        Index(
            "ix_subscriptions_due",
            "current_period_end",
            postgresql_where=text("status IN ('trialing', 'active', 'past_due')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    expert_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subscription_plans.id", ondelete="RESTRICT")
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        _enum(SubscriptionStatus, "subscription_status")
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    interval: Mapped[PlanInterval] = mapped_column(_enum(PlanInterval, "plan_interval"))
    perks: Mapped[dict[str, Any]] = mapped_column(JSONB)
    payment_method: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    past_due_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()


class Invoice(Base):
    """A charge for one subscription period (trial 0.00, initial, renewal); fee and expert
    share are set when paid."""

    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_subscription", "subscription_id", text("created_at DESC")),
        Index("ix_invoices_expert_paid", "expert_id", "paid_at"),
        Index("ix_invoices_user", "user_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    number: Mapped[str] = mapped_column(String(20), unique=True)  # INV-2026-000123
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subscriptions.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    expert_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # initial | trial | renewal
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[InvoiceStatus] = mapped_column(_enum(InvoiceStatus, "invoice_status"))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    platform_fee: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # set when paid
    expert_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    provider: Mapped[str] = mapped_column(String(16))
    provider_ref: Mapped[str | None] = mapped_column(String(100))
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()


class CheckoutSession(Base):
    """One payment attempt for a plan on the provider's hosted page (valid 30 minutes)."""

    __tablename__ = "checkout_sessions"
    __table_args__ = (Index("ix_checkout_sessions_user", "user_id", text("created_at DESC")),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subscription_plans.id", ondelete="CASCADE")
    )
    status: Mapped[CheckoutStatus] = mapped_column(
        _enum(CheckoutStatus, "checkout_status"),
        default=CheckoutStatus.open,
        server_default=CheckoutStatus.open.value,
    )
    provider: Mapped[str] = mapped_column(String(16))
    provider_ref: Mapped[str | None] = mapped_column(String(100))
    return_url: Mapped[str | None] = mapped_column(String(500))
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()


class PaymentEvent(Base):
    """Every provider event processed, once (``event_id`` unique)."""

    __tablename__ = "payment_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(String(16))
    event_id: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    processed_at: Mapped[datetime] = _ts()
