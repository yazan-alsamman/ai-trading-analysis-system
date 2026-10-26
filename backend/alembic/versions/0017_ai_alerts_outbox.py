"""AI setup alerts: outbox, follows, notification type ai_setup, delivery sweeper

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-21

Additive and safe on existing data:

- notification_type gains 'ai_setup' (``ALTER TYPE ... ADD VALUE IF NOT EXISTS`` in an
  autocommit block, as in 0011/0012);
- ai_setup_outbox: setup state changes to notify, written in the evaluation's transaction
  (unique (setup_id, to_state); partial index on next_attempt_at of the pending rows);
- ai_alert_follows: who wants ARMED alerts of an instrument and profile;
- notification_deliveries.next_attempt_at (nullable: existing rows keep null) and a partial
  index for the stuck-delivery sweeper (pending deliveries without a hold).

Downgrade drops the tables, the column and the index, and deletes the notifications of type
'ai_setup' (PostgreSQL cannot drop an enum value, so 0016 code must never read one).
"""

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

# Kept literal here on purpose: migrations must not depend on application code.
STATES = "'DEVELOPING', 'ARMED', 'ACTIVE', 'CLOSED', 'EXPIRED', 'INVALIDATED'"
NOW = sa.text("clock_timestamp()")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'ai_setup'")

    op.create_table(
        "ai_setup_outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "setup_id",
            sa.String(128),
            sa.ForeignKey("ai_setups.setup_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(16), nullable=True),
        sa.Column("to_state", sa.String(16), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("realized_r", sa.Double(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW
        ),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("setup_id", "to_state", name="uq_ai_setup_outbox_setup_state"),
        sa.CheckConstraint(
            "status IN ('pending', 'done', 'skipped', 'failed')", name="ck_ai_setup_outbox_status"
        ),
        sa.CheckConstraint(f"to_state IN ({STATES})", name="ck_ai_setup_outbox_to"),
    )
    op.create_index(
        "ix_ai_setup_outbox_due",
        "ai_setup_outbox",
        ["next_attempt_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "ai_alert_follows",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "instrument_id",
            sa.Uuid(),
            sa.ForeignKey("instruments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("profile", sa.String(32), primary_key=True),
        sa.Column("min_grade", sa.String(1), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint(
            "min_grade IS NULL OR min_grade IN ('A', 'B', 'C', 'D')",
            name="ck_ai_alert_follows_grade",
        ),
    )
    op.create_index("ix_ai_alert_follows_market", "ai_alert_follows", ["instrument_id", "profile"])

    op.add_column(
        "notification_deliveries",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_notification_deliveries_unsent",
        "notification_deliveries",
        [sa.text("coalesce(next_attempt_at, created_at)")],
        postgresql_where=sa.text("status = 'pending' AND hold IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_unsent", table_name="notification_deliveries")
    op.drop_column("notification_deliveries", "next_attempt_at")
    op.drop_table("ai_alert_follows")
    op.drop_table("ai_setup_outbox")
    # the enum value stays (no DROP VALUE); no row may use it under 0016
    op.execute("DELETE FROM notifications WHERE type = 'ai_setup'")
