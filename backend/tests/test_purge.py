"""purge-demo: dry run by default, deletes accounts by prefix with what they own, refuses
short prefixes and removing the last admin."""

import pytest
from sqlalchemy import func, select

from app.models.instrument import Instrument
from app.models.user import User, UserRole
from app.services import purge
from tests.expert_utils import make_expert, make_person, make_plan, subscribe
from tests.market_utils import make_instrument


async def test_purge_demo(client, make_user, session, session_factory) -> None:
    expert, eh = await make_expert(client, make_user, session, "demo-expert")
    _, th = await make_person(make_user, session, "demo-trader")
    keep, kh = await make_person(make_user, session, "keeper")
    plan = await make_plan(client, eh)
    await subscribe(client, th, plan["id"])
    await subscribe(client, kh, plan["id"])  # someone else's subscription to a demo expert
    await make_instrument(session, "E2EX/USDT")
    dry = await purge.purge_demo(session_factory, "demo-", instrument_prefix="e2e")
    assert not dry.deleted
    assert dry.users == [
        ("demo-expert@example.com", "expert"),
        ("demo-trader@example.com", "trader"),
    ]
    assert dry.owned["subscription_plans"] == 1 and dry.owned["subscriptions"] == 2
    assert dry.owned["expert_profiles"] == 1 and dry.instruments == ["E2EX/USDT"]
    assert await session.scalar(select(func.count()).select_from(User)) == 3
    done = await purge.purge_demo(session_factory, "demo-", instrument_prefix="e2e", execute=True)
    assert done.deleted
    emails = (await session.scalars(select(User.email))).all()
    assert emails == ["keeper@example.com"]
    assert await session.scalar(select(func.count()).select_from(Instrument)) == 0
    assert keep.id


async def test_purge_refuses(make_user, session, session_factory) -> None:
    await make_user("ad-admin@example.com", role=UserRole.admin)
    with pytest.raises(ValueError, match="at least 3"):
        await purge.purge_demo(session_factory, "a")
    with pytest.raises(ValueError, match="every admin"):
        await purge.purge_demo(session_factory, "ad-", execute=True)
