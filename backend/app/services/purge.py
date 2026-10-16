"""Remove accounts made by verification scripts and tests (``python -m app.cli purge-demo``).

Accounts are selected by e-mail prefix (``y19-``, ``e2e-``); everything they own goes with them:
every table with a foreign key to ``users`` is counted, and the database cascades do the
deletion. Subscriptions are deleted first, because a plan cannot be deleted while a subscription
refers to it. Optionally, instruments whose symbol starts with a prefix (the e2e suite's own
markets) are deleted too, with their candles and signals.

Dry run by default. Refuses prefixes that are too short or would remove the last admin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import Base
from app.models.expert import Subscription
from app.models.instrument import Instrument
from app.models.user import User, UserRole

PREFIX = re.compile(r"^[a-z0-9][a-z0-9._+-]{2,63}$")


@dataclass
class PurgeReport:
    users: list[tuple[str, str]] = field(default_factory=list)  # (email, role)
    owned: dict[str, int] = field(default_factory=dict)  # table -> rows referencing them
    instruments: list[str] = field(default_factory=list)
    deleted: bool = False


def _like(prefix: str) -> str:
    return prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def purge_demo(
    factory: async_sessionmaker[AsyncSession],
    prefix: str,
    *,
    instrument_prefix: str | None = None,
    execute: bool = False,
) -> PurgeReport:
    prefix = prefix.strip().lower()
    if not PREFIX.match(prefix):
        raise ValueError("the prefix must be at least 3 characters: letters, digits, . _ + -")
    report = PurgeReport()
    async with factory() as session:
        users = (
            await session.execute(
                select(User.id, User.email, User.role)
                .where(User.email.like(_like(prefix), escape="\\"))
                .order_by(User.email)
            )
        ).all()
        ids = [u.id for u in users]
        report.users = [(u.email, u.role.value) for u in users]
        admins = [u for u in users if u.role == UserRole.admin]
        if admins:
            others = await session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == UserRole.admin, User.id.not_in(ids))
            )
            if not others:
                raise ValueError("refused: this would remove every admin")
        if ids:
            for table in sorted(Base.metadata.sorted_tables, key=lambda t: t.name):
                columns = [
                    fk.parent
                    for fk in table.foreign_keys
                    if fk.column.table.name == "users" and fk.parent.table is table
                ]
                if not columns or table.name == "users":
                    continue
                count = await session.scalar(
                    select(func.count())
                    .select_from(table)
                    .where(or_(*(c.in_(ids) for c in columns)))
                )
                if count:
                    report.owned[table.name] = count
        instrument_ids = []
        if instrument_prefix:
            rows = (
                await session.execute(
                    select(Instrument.id, Instrument.symbol).where(
                        Instrument.symbol.like(_like(instrument_prefix.upper()), escape="\\")
                    )
                )
            ).all()
            instrument_ids = [r.id for r in rows]
            report.instruments = [r.symbol for r in rows]
        if execute and (ids or instrument_ids):
            if ids:
                await session.execute(
                    delete(Subscription).where(
                        or_(Subscription.user_id.in_(ids), Subscription.expert_id.in_(ids))
                    )
                )
                await session.execute(delete(User).where(User.id.in_(ids)))
            if instrument_ids:
                await session.execute(delete(Instrument).where(Instrument.id.in_(instrument_ids)))
            await session.commit()
            report.deleted = True
    return report
