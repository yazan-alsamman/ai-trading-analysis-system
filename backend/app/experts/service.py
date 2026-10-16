"""Expert profiles and plans, the directory, the subscribers' signals feed, earnings, the
subscriber's own subscriptions and the admin views."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Text, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.custom_strategy import CustomStrategy, Visibility
from app.models.expert import (
    MAX_ACTIVE_PLANS,
    ExpertProfile,
    Invoice,
    InvoiceStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.models.instrument import Instrument
from app.models.risk import SignalPlan
from app.models.social import Follow
from app.models.strategy import Signal, UserStrategy
from app.models.user import User, UserRole
from app.payments import service as payments
from app.payments.entitlements import Entitlements, entitled_clause
from app.schemas.experts import ExpertProfileIn, PlanIn, PlanUpdate
from app.social import service as social
from app.social.notify import display_name

CENT = Decimal("0.01")


def person(user: User) -> dict[str, Any]:
    return {"id": user.id, "display_name": display_name(user), "role": user.role}


def require_expert(user: User) -> None:
    if user.role != UserRole.expert:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only experts have an expert profile")


# --- profile and plans ---------------------------------------------------------------------------


async def upsert_profile(session: AsyncSession, user: User, data: ExpertProfileIn) -> ExpertProfile:
    require_expert(user)
    profile = await session.get(ExpertProfile, user.id)
    if profile is None:
        profile = ExpertProfile(user_id=user.id)
        session.add(profile)
    for name, value in data.model_dump().items():
        setattr(profile, name, value)
    await session.commit()
    await session.refresh(profile)
    return profile


async def own_profile(session: AsyncSession, user: User) -> ExpertProfile:
    require_expert(user)
    profile = await session.get(ExpertProfile, user.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Create your expert profile first")
    return profile


async def _active_plans(session: AsyncSession, expert_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(SubscriptionPlan)
            .where(SubscriptionPlan.expert_id == expert_id, SubscriptionPlan.is_active.is_(True))
        )
        or 0
    )


async def create_plan(session: AsyncSession, user: User, data: PlanIn) -> SubscriptionPlan:
    await own_profile(session, user)
    if data.is_active and await _active_plans(session, user.id) >= MAX_ACTIVE_PLANS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"At most {MAX_ACTIVE_PLANS} active plans")
    plan = SubscriptionPlan(
        expert_id=user.id, **{**data.model_dump(), "perks": data.perks.model_dump()}
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def own_plan(session: AsyncSession, user: User, plan_id: uuid.UUID) -> SubscriptionPlan:
    require_expert(user)
    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is None or plan.expert_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    return plan


async def update_plan(
    session: AsyncSession, user: User, plan: SubscriptionPlan, data: PlanUpdate
) -> SubscriptionPlan:
    fields = data.model_dump(exclude_unset=True)
    if fields.get("is_active") and not plan.is_active:
        if await _active_plans(session, user.id) >= MAX_ACTIVE_PLANS:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"At most {MAX_ACTIVE_PLANS} active plans"
            )
    for name, value in fields.items():
        setattr(plan, name, value)
    await session.commit()
    await session.refresh(plan)
    return plan


async def list_plans(
    session: AsyncSession, expert_id: uuid.UUID, active_only: bool = True
) -> list[SubscriptionPlan]:
    query = select(SubscriptionPlan).where(SubscriptionPlan.expert_id == expert_id)
    if active_only:
        query = query.where(SubscriptionPlan.is_active.is_(True))
    return list(
        await session.scalars(query.order_by(SubscriptionPlan.price, SubscriptionPlan.created_at))
    )


# --- directory -----------------------------------------------------------------------------------


def _brief(plan: SubscriptionPlan | None) -> dict | None:
    if plan is None:
        return None
    return {
        "id": plan.id,
        "name": plan.name,
        "price": plan.price,
        "currency": plan.currency,
        "interval": plan.interval,
        "trial_days": plan.trial_days,
    }


async def _cards(
    session: AsyncSession, viewer: User, rows: list[tuple[ExpertProfile, User]]
) -> list[dict]:
    ids = [u.id for _, u in rows]
    if not ids:
        return []
    followers = dict(
        (
            await session.execute(
                select(Follow.followee_id, func.count())
                .where(Follow.followee_id.in_(ids))
                .group_by(Follow.followee_id)
            )
        ).all()
    )
    subscribers = dict(
        (
            await session.execute(
                select(Subscription.expert_id, func.count())
                .where(Subscription.expert_id.in_(ids), entitled_clause())
                .group_by(Subscription.expert_id)
            )
        ).all()
    )
    cheapest: dict[uuid.UUID, SubscriptionPlan] = {}
    for plan in await session.scalars(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.expert_id.in_(ids), SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.price)
    ):
        cheapest.setdefault(plan.expert_id, plan)
    mine = set(
        await session.scalars(
            select(Subscription.expert_id).where(
                Subscription.user_id == viewer.id,
                Subscription.expert_id.in_(ids),
                entitled_clause(),
            )
        )
    )
    return [
        {
            "id": user.id,
            "display_name": display_name(user),
            "headline": profile.headline,
            "markets": profile.markets,
            "languages": profile.languages,
            "chat_enabled": profile.chat_enabled,
            "response_time_hint": profile.response_time_hint,
            "followers_count": followers.get(user.id, 0),
            "subscribers_count": subscribers.get(user.id, 0),
            "rating": None,
            "cheapest_plan": _brief(cheapest.get(user.id)),
            "is_subscribed": user.id in mine,
        }
        for profile, user in rows
    ]


async def directory(
    session: AsyncSession,
    viewer: User,
    *,
    market: str | None,
    language: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    where = [
        ExpertProfile.is_listed.is_(True),
        User.is_active.is_(True),
        User.role == UserRole.expert,
    ]
    if market:
        where.append(ExpertProfile.markets.contains([market.lower()]))
    if language:
        where.append(ExpertProfile.languages.contains([language.lower()]))
    if q and q.strip():
        pattern = (
            "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        where.append(
            or_(
                ExpertProfile.headline.ilike(pattern, escape="\\"),
                User.full_name.ilike(pattern, escape="\\"),
                cast(ExpertProfile.bio, Text).ilike(pattern, escape="\\"),
            )
        )
    base = select(ExpertProfile, User).join(User, User.id == ExpertProfile.user_id).where(*where)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    subs = (
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.expert_id == User.id, entitled_clause())
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            base.order_by(subs.desc(), User.full_name, User.id).limit(limit).offset(offset)
        )
    ).all()
    return await _cards(session, viewer, [tuple(r) for r in rows]), total or 0


async def detail(session: AsyncSession, viewer: User, expert_id: uuid.UUID) -> dict:
    """Profile, active plans, the viewer's entitlements and recent posts (premium ones as
    teasers when the viewer is not entitled). Unlisted experts are reachable by id."""
    profile = await payments.expert_profile_or_404(session, expert_id)
    user = await session.get(User, expert_id)
    [card] = await _cards(session, viewer, [(profile, user)])
    ent = Entitlements(session, viewer)
    posts, _ = await social.feed(session, viewer, author_id=expert_id, limit=5, offset=0)
    return {
        **card,
        "bio": profile.bio,
        "member_since": user.created_at,
        "plans": await list_plans(session, expert_id),
        "entitlements": await ent.get(expert_id),
        "recent_posts": await social.serialize_posts(session, viewer, posts, ent),
    }


# --- signals feed --------------------------------------------------------------------------------


async def signals_feed(
    session: AsyncSession, viewer: User, expert_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[dict], int]:
    """Signals of the expert's public custom strategies that the expert has activated, with the
    expert's trade plan (Y13) when one was computed. Needs the ``signals_feed`` perk."""
    await payments.expert_profile_or_404(session, expert_id)
    if not (await Entitlements(session, viewer).get(expert_id))["signals_feed"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The signals feed is for subscribers with that perk"
        )
    public_keys = select(func.concat("custom:", cast(CustomStrategy.id, Text))).where(
        CustomStrategy.user_id == expert_id, CustomStrategy.visibility == Visibility.public
    )
    activated = (
        select(UserStrategy.instrument_id, UserStrategy.timeframe, UserStrategy.strategy_key)
        .where(UserStrategy.user_id == expert_id, UserStrategy.strategy_key.in_(public_keys))
        .distinct()
        .subquery()
    )
    joined = and_(
        Signal.instrument_id == activated.c.instrument_id,
        Signal.timeframe == activated.c.timeframe,
        Signal.strategy_key == activated.c.strategy_key,
    )
    base = select(Signal).join(activated, joined)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    signals = list(
        await session.scalars(
            base.order_by(Signal.bar_time.desc(), Signal.id).limit(limit).offset(offset)
        )
    )
    ids = [s.id for s in signals]
    plans = (
        dict(
            (
                await session.execute(
                    select(SignalPlan.signal_id, SignalPlan.plan).where(
                        SignalPlan.signal_id.in_(ids), SignalPlan.user_id == expert_id
                    )
                )
            ).all()
        )
        if ids
        else {}
    )
    names = {
        f"custom:{cs.id}": cs.name
        for cs in await session.scalars(
            select(CustomStrategy).where(CustomStrategy.user_id == expert_id)
        )
    }
    symbols = dict(
        (
            await session.execute(
                select(Instrument.id, Instrument.symbol).where(
                    Instrument.id.in_({s.instrument_id for s in signals} or {uuid.uuid4()})
                )
            )
        ).all()
    )
    items = [
        {
            "id": s.id,
            "instrument": {"id": s.instrument_id, "symbol": symbols.get(s.instrument_id, "?")},
            "timeframe": s.timeframe.value,
            "strategy_key": s.strategy_key,
            "strategy_name": names.get(s.strategy_key),
            "side": s.side.value,
            "strength": s.strength,
            "price": s.price,
            "reason": s.reason,
            "bar_time": s.bar_time,
            "plan": plans.get(s.id),
        }
        for s in signals
    ]
    return items, total or 0


# --- subscriptions (subscriber) ------------------------------------------------------------------


def _next_charge(sub: Subscription) -> datetime | None:
    if sub.status in (SubscriptionStatus.trialing, SubscriptionStatus.active) and not (
        sub.cancel_at_period_end
    ):
        return sub.current_period_end
    return None


async def my_subscriptions(session: AsyncSession, user: User) -> list[dict]:
    subs = list(
        await session.scalars(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
        )
    )
    return await _read_subs(session, subs)


async def _read_subs(session: AsyncSession, subs: list[Subscription]) -> list[dict]:
    if not subs:
        return []
    invoices = await payments.invoices_of(session, [s.id for s in subs])
    experts = {
        u.id: u
        for u in await session.scalars(select(User).where(User.id.in_({s.expert_id for s in subs})))
    }
    plans = {
        p.id: p
        for p in await session.scalars(
            select(SubscriptionPlan).where(SubscriptionPlan.id.in_({s.plan_id for s in subs}))
        )
    }
    return [
        {
            "id": s.id,
            "expert": person(experts[s.expert_id]),
            "plan": {"id": s.plan_id, "name": plans[s.plan_id].name},
            "status": s.status,
            "price": s.price,
            "currency": s.currency,
            "interval": s.interval,
            "perks": s.perks,
            "current_period_start": s.current_period_start,
            "current_period_end": s.current_period_end,
            "cancel_at_period_end": s.cancel_at_period_end,
            "canceled_at": s.canceled_at,
            "next_charge_at": _next_charge(s),
            "grace_ends_at": payments.grace_end(s)
            if s.status == SubscriptionStatus.past_due
            else None,
            "ended_at": s.ended_at,
            "payment_method": s.payment_method,
            "created_at": s.created_at,
            "invoices": invoices.get(s.id, []),
        }
        for s in subs
    ]


async def read_subscription(session: AsyncSession, sub: Subscription) -> dict:
    return (await _read_subs(session, [sub]))[0]


# --- earnings ------------------------------------------------------------------------------------


async def earnings(session: AsyncSession, user: User, now: datetime | None = None) -> dict:
    require_expert(user)
    now = now or datetime.now(UTC)
    settings = get_settings()
    grace = timedelta(days=settings.subscription_grace_days)
    subs = list(
        await session.scalars(select(Subscription).where(Subscription.expert_id == user.id))
    )

    def entitled(s: Subscription) -> bool:
        if s.status in (SubscriptionStatus.trialing, SubscriptionStatus.active):
            return True
        return s.status == SubscriptionStatus.past_due and s.past_due_since > now - grace

    live = [s for s in subs if entitled(s)]
    by_status: dict[str, int] = defaultdict(int)
    for s in live:
        by_status[s.status.value] += 1
    paying = [s for s in live if s.status != SubscriptionStatus.trialing]
    mrr = sum((payments.monthly(s.price, s.interval) for s in paying), Decimal("0"))
    window = now - timedelta(days=30)
    ended = [
        s
        for s in subs
        if s.status in (SubscriptionStatus.canceled, SubscriptionStatus.expired)
        and s.ended_at is not None
        and s.ended_at >= window
    ]
    base = len(live) + len(ended)
    churn = round(len(ended) / base * 100, 2) if base else None

    month = func.to_char(func.date_trunc("month", Invoice.paid_at), "YYYY-MM")
    rows = (
        await session.execute(
            select(
                month.label("month"),
                func.coalesce(
                    func.sum(Invoice.amount).filter(Invoice.status == InvoiceStatus.paid), 0
                ),
                func.coalesce(
                    func.sum(Invoice.platform_fee).filter(Invoice.status == InvoiceStatus.paid), 0
                ),
                func.coalesce(
                    func.sum(Invoice.expert_amount).filter(Invoice.status == InvoiceStatus.paid), 0
                ),
                func.coalesce(
                    func.sum(Invoice.amount).filter(Invoice.status == InvoiceStatus.refunded), 0
                ),
                func.count(),
            )
            .where(
                Invoice.expert_id == user.id,
                Invoice.paid_at.is_not(None),
                Invoice.paid_at >= now - timedelta(days=366),
                Invoice.status.in_((InvoiceStatus.paid, InvoiceStatus.refunded)),
            )
            .group_by(month)
            .order_by(month.desc())
        )
    ).all()
    months = [
        {
            "month": m,
            "gross": Decimal(g).quantize(CENT),
            "platform_fee": Decimal(f).quantize(CENT),
            "net": Decimal(n).quantize(CENT),
            "refunded": Decimal(r).quantize(CENT),
            "invoices": c,
        }
        for m, g, f, n, r, c in rows
    ]
    recent = (
        await session.execute(
            select(Invoice, User, SubscriptionPlan.name)
            .join(Subscription, Subscription.id == Invoice.subscription_id)
            .join(User, User.id == Invoice.user_id)
            .join(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id)
            .where(Invoice.expert_id == user.id)
            .order_by(Invoice.created_at.desc(), Invoice.number.desc())
            .limit(20)
        )
    ).all()
    currencies = {s.currency for s in subs} or {"USD"}
    return {
        "currency": sorted(currencies)[0],
        "platform_fee_pct": settings.platform_fee_pct,
        "active_subscribers": len(live),
        "by_status": dict(by_status),
        "mrr": mrr.quantize(CENT),
        "churn_30d_pct": churn,
        "ended_30d": len(ended),
        "months": months,
        "recent_invoices": [
            {
                "number": inv.number,
                "kind": inv.kind,
                "amount": inv.amount,
                "currency": inv.currency,
                "status": inv.status.value,
                "platform_fee": inv.platform_fee if inv.status == InvoiceStatus.paid else None,
                "net": inv.expert_amount if inv.status == InvoiceStatus.paid else None,
                "subscriber": display_name(subscriber),
                "plan": plan_name,
                "paid_at": inv.paid_at,
                "created_at": inv.created_at,
            }
            for inv, subscriber, plan_name in recent
        ],
    }


# --- admin ---------------------------------------------------------------------------------------


async def admin_subscriptions(
    session: AsyncSession,
    *,
    status_: SubscriptionStatus | None,
    expert_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    where = []
    if status_ is not None:
        where.append(Subscription.status == status_)
    if expert_id is not None:
        where.append(Subscription.expert_id == expert_id)
    if user_id is not None:
        where.append(Subscription.user_id == user_id)
    total = await session.scalar(select(func.count()).select_from(Subscription).where(*where))
    subs = list(
        await session.scalars(
            select(Subscription)
            .where(*where)
            .order_by(Subscription.created_at.desc(), Subscription.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return [await admin_read(session, s) for s in subs], total or 0


async def admin_read(session: AsyncSession, s: Subscription) -> dict:
    user = await session.get(User, s.user_id)
    expert = await session.get(User, s.expert_id)
    return {
        "id": s.id,
        "user": person(user),
        "expert": person(expert),
        "plan_id": s.plan_id,
        "status": s.status,
        "price": s.price,
        "currency": s.currency,
        "interval": s.interval,
        "current_period_end": s.current_period_end,
        "cancel_at_period_end": s.cancel_at_period_end,
        "past_due_since": s.past_due_since,
        "ended_at": s.ended_at,
        "created_at": s.created_at,
    }


async def payment_stats(session: AsyncSession) -> dict:
    invoices = {
        st.value: {"count": c, "amount": Decimal(a or 0).quantize(CENT)}
        for st, c, a in (
            await session.execute(
                select(Invoice.status, func.count(), func.sum(Invoice.amount)).group_by(
                    Invoice.status
                )
            )
        ).all()
    }
    fees = await session.scalar(
        select(func.coalesce(func.sum(Invoice.platform_fee), 0)).where(
            Invoice.status == InvoiceStatus.paid
        )
    )
    subs = dict(
        (
            await session.execute(
                select(Subscription.status, func.count()).group_by(Subscription.status)
            )
        ).all()
    )
    paying = await session.execute(
        select(Subscription.price, Subscription.interval).where(
            entitled_clause(), Subscription.status != SubscriptionStatus.trialing
        )
    )
    mrr = sum((payments.monthly(p, i) for p, i in paying.all()), Decimal("0"))
    return {
        "invoices": {
            st.value: invoices.get(st.value, {"count": 0, "amount": Decimal("0.00")})
            for st in InvoiceStatus
        },
        "platform_fees": Decimal(fees or 0).quantize(CENT),
        "subscriptions": {st.value: subs.get(st, 0) for st in SubscriptionStatus},
        "mrr": mrr.quantize(CENT),
    }
