"""notifications

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-16

notifications (in-app inbox), notification_deliveries (Telegram / email / push, one row per
target), notification_preferences, telegram_links, user_devices (FCM tokens) and
login_fingerprints (new IP / device detection).

Additive only: new enum types and new tables. No existing table is altered or rewritten, so it
is safe on a populated production database and quick to apply.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

ENUMS = {
    "notification_type": ("signal", "backtest_completed", "backtest_failed", "security", "system"),
    "notification_severity": ("info", "success", "warning", "critical"),
    "notification_channel": ("telegram", "email", "push"),
    "delivery_status": ("pending", "sent", "failed", "skipped"),
    "device_platform": ("android", "ios", "web"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def _ts(name: str, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("clock_timestamp()") if default else None,
        nullable=nullable,
    )


def _user_fk() -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE")


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", _enum("notification_type"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("severity", _enum("notification_severity"), nullable=False),
        sa.Column("dedup_key", sa.String(length=200), nullable=False),
        _ts("read_at", nullable=True, default=False),
        _ts("created_at"),
        _user_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "dedup_key", name="uq_notifications_user_dedup"),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", sa.literal_column("created_at DESC")],
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", sa.literal_column("created_at DESC")],
        postgresql_where=sa.text("read_at IS NULL"),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("channel", _enum("notification_channel"), nullable=False),
        sa.Column("target", sa.String(length=320), nullable=False),
        sa.Column("status", _enum("delivery_status"), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("hold", sa.String(length=16), nullable=True),
        _ts("release_at", nullable=True, default=False),
        _ts("created_at"),
        _ts("sent_at", nullable=True, default=False),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id", "channel", "target", name="uq_notification_deliveries_target"
        ),
    )
    op.create_index(
        "ix_notification_deliveries_due",
        "notification_deliveries",
        ["release_at"],
        postgresql_where=sa.text("status = 'pending' AND hold IS NOT NULL"),
    )
    op.create_index("ix_notification_deliveries_created", "notification_deliveries", ["created_at"])

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("matrix", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("min_signal_strength", sa.Double(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "only_valid_plans", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("quiet_hours", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("language", sa.String(length=2), server_default="ar", nullable=False),
        sa.Column("max_per_hour", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _ts("updated_at"),
        sa.CheckConstraint(
            "min_signal_strength BETWEEN 0 AND 1", name="ck_notification_preferences_strength"
        ),
        _user_fk(),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "telegram_links",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        _ts("linked_at"),
        _user_fk(),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("chat_id"),
    )

    op.create_table(
        "user_devices",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("platform", _enum("device_platform"), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("app_version", sa.String(length=32), nullable=True),
        sa.Column("locale", sa.String(length=16), nullable=True),
        _ts("last_seen_at"),
        _ts("created_at"),
        _user_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_user_devices_user", "user_devices", ["user_id"])

    op.create_table(
        "login_fingerprints",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        _ts("first_seen"),
        _ts("last_seen"),
        _user_fk(),
        sa.PrimaryKeyConstraint("user_id", "fingerprint"),
    )


def downgrade() -> None:
    op.drop_table("login_fingerprints")
    op.drop_index("ix_user_devices_user", table_name="user_devices")
    op.drop_table("user_devices")
    op.drop_table("telegram_links")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notification_deliveries_created", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_due", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    bind = op.get_bind()
    for name in reversed(ENUMS):
        postgresql.ENUM(name=name).drop(bind)
