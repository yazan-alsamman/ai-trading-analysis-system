"""AI risk settings, taken trades and sizing source

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-21

Additive and safe on existing data:

- risk_profiles.leverage (not null, server default 100, check 0 < leverage <= 10000): existing
  profiles get 100; risk_profiles.balance_set_at (nullable: the drawdown guard then counts
  every closed taken trade).
- ai_setup_sizes.source ('ai-service' | 'local', server default 'local') and computed_at
  (server default now). The table is still empty in production (B8 created it for B10).
- ai_setup_takes: a user took a setup (PK setup_id + user_id, both cascading), with the result
  filled when the setup ends; index (user_id, taken_at DESC).

Downgrade drops the table and the columns.
"""

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

NOW = sa.text("clock_timestamp()")


def upgrade() -> None:
    op.add_column(
        "risk_profiles",
        sa.Column("leverage", sa.Double(), nullable=False, server_default=sa.text("100")),
    )
    op.add_column(
        "risk_profiles", sa.Column("balance_set_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_risk_profiles_leverage", "risk_profiles", "leverage > 0 AND leverage <= 10000"
    )

    op.add_column(
        "ai_setup_sizes",
        sa.Column("source", sa.String(16), nullable=False, server_default="local"),
    )
    op.add_column(
        "ai_setup_sizes",
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_check_constraint(
        "ck_ai_setup_sizes_source", "ai_setup_sizes", "source IN ('ai-service', 'local')"
    )

    op.create_table(
        "ai_setup_takes",
        sa.Column(
            "setup_id",
            sa.String(128),
            sa.ForeignKey("ai_setups.setup_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("lots", sa.Double(), nullable=True),
        sa.Column("risk_amount", sa.Double(), nullable=True),
        sa.Column("entry_price", sa.Double(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realized_r", sa.Double(), nullable=True),
        sa.Column("pnl", sa.Double(), nullable=True),
        sa.Column("close_reason", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_ai_setup_takes_user", "ai_setup_takes", ["user_id", sa.text("taken_at DESC")]
    )


def downgrade() -> None:
    op.drop_table("ai_setup_takes")
    op.drop_constraint("ck_ai_setup_sizes_source", "ai_setup_sizes", type_="check")
    op.drop_column("ai_setup_sizes", "computed_at")
    op.drop_column("ai_setup_sizes", "source")
    op.drop_constraint("ck_risk_profiles_leverage", "risk_profiles", type_="check")
    op.drop_column("risk_profiles", "balance_set_at")
    op.drop_column("risk_profiles", "leverage")
