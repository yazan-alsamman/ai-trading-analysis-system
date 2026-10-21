"""Migration 0012: new enum values (added outside the transaction), tables, partial unique
index, invoice number sequence."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _labels(session: AsyncSession, type_name: str) -> list[str]:
    rows = await session.execute(
        text(
            "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_type.oid = enumtypid "
            "WHERE typname = :t ORDER BY enumsortorder"
        ),
        {"t": type_name},
    )
    return list(rows.scalars())


async def test_enum_values(session: AsyncSession) -> None:
    assert (await _labels(session, "post_visibility"))[-1] == "subscribers"
    assert (await _labels(session, "report_target"))[-1] == "message"
    labels = await _labels(session, "notification_type")
    start = labels.index("chat_message")  # later migrations append after them (0017: ai_setup)
    assert labels[start : start + 6] == [
        "chat_message",
        "subscription_started",
        "subscription_renewed",
        "subscription_payment_failed",
        "subscription_canceled",
        "new_subscriber",
    ]
    assert await _labels(session, "subscription_status") == [
        "trialing",
        "active",
        "past_due",
        "canceled",
        "expired",
    ]


async def test_tables_indexes_sequence(session: AsyncSession) -> None:
    tables = set(
        (
            await session.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        ).scalars()
    )
    assert {
        "expert_profiles",
        "subscription_plans",
        "subscriptions",
        "invoices",
        "checkout_sessions",
        "payment_events",
        "conversations",
        "messages",
    } <= tables
    definition = await session.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_subscriptions_live'")
    )
    assert "UNIQUE" in definition and "past_due" in definition
    assert await session.scalar(text("SELECT nextval('invoice_number_seq')")) >= 1
