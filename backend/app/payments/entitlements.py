"""What a user may do with an expert's paid features: ``{premium_posts, chat, signals_feed}``.

A subscription entitles while it is ``trialing`` or ``active``, and while ``past_due`` within
the grace period (``SUBSCRIPTION_GRACE_DAYS``). The perks are the ones copied onto the
subscription from its plan. Experts are entitled to their own content, admins to everything.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.expert import PERKS, Subscription, SubscriptionStatus
from app.models.user import User, UserRole

NONE = dict.fromkeys(PERKS, False)
ALL = dict.fromkeys(PERKS, True)


def entitled_clause(now: datetime | None = None):
    """SQL condition: the subscription currently entitles."""
    now = now or datetime.now(UTC)
    grace = timedelta(days=get_settings().subscription_grace_days)
    return or_(
        Subscription.status.in_((SubscriptionStatus.trialing, SubscriptionStatus.active)),
        and_(
            Subscription.status == SubscriptionStatus.past_due,
            Subscription.past_due_since > now - grace,
        ),
    )


def _perks(raw: dict | None) -> dict[str, bool]:
    return {p: bool((raw or {}).get(p)) for p in PERKS}


class Entitlements:
    """Per-request cache: ``await ent.get(expert_id)``; ``await ent.load(ids)`` first for many
    experts in one query."""

    def __init__(self, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user
        self._cache: dict[uuid.UUID, dict[str, bool]] = {}

    async def load(self, expert_ids: Iterable[uuid.UUID]) -> None:
        wanted = {e for e in expert_ids if e not in self._cache}
        if self.user.role == UserRole.admin:
            self._cache.update(dict.fromkeys(wanted, ALL))
            return
        if self.user.id in wanted:
            self._cache[self.user.id] = ALL
            wanted.discard(self.user.id)
        if not wanted:
            return
        rows = await self.session.execute(
            select(Subscription.expert_id, Subscription.perks).where(
                Subscription.user_id == self.user.id,
                Subscription.expert_id.in_(wanted),
                entitled_clause(),
            )
        )
        found = {expert_id: _perks(perks) for expert_id, perks in rows.all()}
        for expert_id in wanted:
            self._cache[expert_id] = found.get(expert_id, NONE)

    async def get(self, expert_id: uuid.UUID) -> dict[str, bool]:
        if expert_id not in self._cache:
            await self.load([expert_id])
        return self._cache[expert_id]


async def entitlements(session: AsyncSession, user: User, expert_id: uuid.UUID) -> dict:
    return await Entitlements(session, user).get(expert_id)


async def subscriber_ids(session: AsyncSession, expert_id: uuid.UUID, perk: str) -> list[uuid.UUID]:
    """Users currently entitled to ``perk`` of this expert."""
    rows = await session.execute(
        select(Subscription.user_id).where(
            Subscription.expert_id == expert_id,
            entitled_clause(),
            Subscription.perks[perk].as_boolean().is_(True),
        )
    )
    return [r[0] for r in rows.all()]
