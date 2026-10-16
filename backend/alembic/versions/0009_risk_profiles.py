"""risk profiles

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-16

risk_profiles: one per user (account size, quote currency, risk config). signal_plans: the
trade plan of a live signal for each user running the setup. user_strategies.risk_override:
per-activation risk rules. backtest_trades: initial stop, money at risk, R multiple, fills.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_size", sa.Double(), server_default=sa.text("10000"), nullable=False),
        sa.Column("quote_currency", sa.String(length=10), server_default="USDT", nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("template", sa.String(length=20), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("account_size > 0", name="ck_risk_profiles_account_size_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "signal_plans",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("user_strategy_id", sa.Uuid(), nullable=True),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_strategy_id"], ["user_strategies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "signal_id",
            "user_id",
            "user_strategy_id",
            name="uq_signal_plans_signal_user_setup",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_signal_plans_user_created",
        "signal_plans",
        ["user_id", sa.literal_column("created_at DESC")],
    )
    op.add_column(
        "user_strategies",
        sa.Column("risk_override", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    for name in ("initial_stop", "risk_amount", "r_multiple"):
        op.add_column("backtest_trades", sa.Column(name, sa.Double(), nullable=True))
    op.add_column(
        "backtest_trades",
        sa.Column("fills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    for name in ("fills", "r_multiple", "risk_amount", "initial_stop"):
        op.drop_column("backtest_trades", name)
    op.drop_column("user_strategies", "risk_override")
    op.drop_index("ix_signal_plans_user_created", table_name="signal_plans")
    op.drop_table("signal_plans")
    op.drop_table("risk_profiles")
