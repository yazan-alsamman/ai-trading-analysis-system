"""experts, subscriptions (demo payments) and chat

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-16

expert_profiles, subscription_plans, subscriptions, invoices (+ the invoice_number_seq
sequence), checkout_sessions, payment_events, conversations, messages; new enum values for
notification_type, post_visibility ('subscribers') and report_target ('message').

Additive only: new types, tables and enum values; no existing table is altered or rewritten.

Enum values use ``ALTER TYPE ... ADD VALUE IF NOT EXISTS`` in an Alembic
``autocommit_block()`` (outside the migration transaction), as in 0011. The downgrade cannot
remove them (PostgreSQL has no ``DROP VALUE``); it deletes or rewrites the rows that use them
so the 0011 code never reads an unknown value: notifications of the new types are deleted,
reports on messages are deleted, and posts with visibility 'subscribers' become 'followers'
(the closest restricted audience that 0011 knows).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

NEW_VALUES = {
    "notification_type": (
        "chat_message",
        "subscription_started",
        "subscription_renewed",
        "subscription_payment_failed",
        "subscription_canceled",
        "new_subscriber",
    ),
    "post_visibility": ("subscribers",),
    "report_target": ("message",),
}
ENUMS = {
    "plan_interval": ("month", "year"),
    "subscription_status": ("trialing", "active", "past_due", "canceled", "expired"),
    "invoice_status": ("open", "paid", "failed", "refunded", "void"),
    "checkout_status": ("open", "completed", "expired", "canceled"),
    "conversation_status": ("open", "closed", "blocked"),
}
LIVE = "status IN ('trialing', 'active', 'past_due')"


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def _ts(name: str, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("clock_timestamp()") if default else None,
        nullable=nullable,
    )


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _fk(column: str, table: str, ondelete: str = "CASCADE") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [f"{table}.id"], ondelete=ondelete)


def _desc(column: str):
    return sa.literal_column(f"{column} DESC")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for type_name, values in NEW_VALUES.items():
            for value in values:
                op.execute(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}'")

    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.execute("CREATE SEQUENCE IF NOT EXISTS invoice_number_seq")

    op.create_table(
        "expert_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("headline", sa.String(length=120), nullable=False),
        sa.Column("bio", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "markets", postgresql.ARRAY(sa.String(length=32)), server_default="{}", nullable=False
        ),
        sa.Column(
            "languages", postgresql.ARRAY(sa.String(length=8)), server_default="{}", nullable=False
        ),
        sa.Column("chat_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("response_time_hint", sa.String(length=60), nullable=True),
        sa.Column("is_listed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _fk("user_id", "users"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_expert_profiles_listed", "expert_profiles", ["is_listed"])

    op.create_table(
        "subscription_plans",
        _id(),
        sa.Column("expert_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("interval", _enum("plan_interval"), nullable=False),
        sa.Column("trial_days", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("perks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _ts("created_at"),
        _fk("expert_id", "users"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("price >= 0", name="ck_subscription_plans_price"),
        sa.CheckConstraint("trial_days BETWEEN 0 AND 30", name="ck_subscription_plans_trial"),
    )
    op.create_index(
        "ix_subscription_plans_expert", "subscription_plans", ["expert_id", "is_active"]
    )

    op.create_table(
        "subscriptions",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expert_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("status", _enum("subscription_status"), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("interval", _enum("plan_interval"), nullable=False),
        sa.Column("perks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payment_method", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _ts("current_period_start", default=False),
        _ts("current_period_end", default=False),
        sa.Column(
            "cancel_at_period_end", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        _ts("canceled_at", nullable=True, default=False),
        _ts("past_due_since", nullable=True, default=False),
        _ts("ended_at", nullable=True, default=False),
        _ts("created_at"),
        _fk("user_id", "users"),
        _fk("expert_id", "users"),
        _fk("plan_id", "subscription_plans", "RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("user_id <> expert_id", name="ck_subscriptions_not_self"),
    )
    op.create_index(
        "uq_subscriptions_live",
        "subscriptions",
        ["user_id", "expert_id"],
        unique=True,
        postgresql_where=sa.text(LIVE),
    )
    op.create_index("ix_subscriptions_expert_status", "subscriptions", ["expert_id", "status"])
    op.create_index("ix_subscriptions_user", "subscriptions", ["user_id", _desc("created_at")])
    op.create_index(
        "ix_subscriptions_due",
        "subscriptions",
        ["current_period_end"],
        postgresql_where=sa.text(LIVE),
    )

    op.create_table(
        "invoices",
        _id(),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expert_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", _enum("invoice_status"), nullable=False),
        _ts("period_start", default=False),
        _ts("period_end", default=False),
        sa.Column("platform_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("expert_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("provider_ref", sa.String(length=100), nullable=True),
        sa.Column("failure_reason", sa.String(length=200), nullable=True),
        _ts("paid_at", nullable=True, default=False),
        _ts("refunded_at", nullable=True, default=False),
        _ts("created_at"),
        _fk("subscription_id", "subscriptions"),
        _fk("user_id", "users"),
        _fk("expert_id", "users"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index(
        "ix_invoices_subscription", "invoices", ["subscription_id", _desc("created_at")]
    )
    op.create_index("ix_invoices_expert_paid", "invoices", ["expert_id", "paid_at"])
    op.create_index("ix_invoices_user", "invoices", ["user_id", _desc("created_at")])

    op.create_table(
        "checkout_sessions",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("status", _enum("checkout_status"), server_default="open", nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("provider_ref", sa.String(length=100), nullable=True),
        sa.Column("return_url", sa.String(length=500), nullable=True),
        sa.Column("failure_reason", sa.String(length=200), nullable=True),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        _ts("expires_at", default=False),
        _ts("created_at"),
        _fk("user_id", "users"),
        _fk("plan_id", "subscription_plans"),
        _fk("subscription_id", "subscriptions", "SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_checkout_sessions_user", "checkout_sessions", ["user_id", _desc("created_at")]
    )

    op.create_table(
        "payment_events",
        _id(),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _ts("processed_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )

    op.create_table(
        "conversations",
        _id(),
        sa.Column("expert_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", _enum("conversation_status"), server_default="open", nullable=False),
        sa.Column("blocked_by", sa.Uuid(), nullable=True),
        _ts("last_message_at", nullable=True, default=False),
        _ts("expert_last_read_at", nullable=True, default=False),
        _ts("user_last_read_at", nullable=True, default=False),
        _ts("created_at"),
        _fk("expert_id", "users"),
        _fk("user_id", "users"),
        _fk("blocked_by", "users", "SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expert_id", "user_id", name="uq_conversations_pair"),
    )
    op.create_index(
        "ix_conversations_user_last",
        "conversations",
        ["user_id", sa.literal_column("last_message_at DESC NULLS LAST")],
    )
    op.create_index(
        "ix_conversations_expert_last",
        "conversations",
        ["expert_id", sa.literal_column("last_message_at DESC NULLS LAST")],
    )

    op.create_table(
        "messages",
        _id(),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "attachments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        _ts("edited_at", nullable=True, default=False),
        _ts("deleted_at", nullable=True, default=False),
        _ts("created_at"),
        _fk("conversation_id", "conversations"),
        _fk("sender_id", "users"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sender_id", "client_id", name="uq_messages_sender_client"),
    )
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", _desc("created_at")]
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("payment_events")
    op.drop_table("checkout_sessions")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
    op.drop_table("subscription_plans")
    op.drop_table("expert_profiles")
    op.execute("DROP SEQUENCE IF EXISTS invoice_number_seq")
    bind = op.get_bind()
    for name in reversed(ENUMS):
        postgresql.ENUM(name=name).drop(bind)
    # enum values stay (no DROP VALUE); rows that use them are removed or rewritten
    types = ", ".join(f"'{v}'" for v in NEW_VALUES["notification_type"])
    op.execute(f"DELETE FROM notifications WHERE type::text IN ({types})")
    op.execute("DELETE FROM content_reports WHERE target_type::text = 'message'")
    op.execute("UPDATE posts SET visibility = 'followers' WHERE visibility::text = 'subscribers'")
