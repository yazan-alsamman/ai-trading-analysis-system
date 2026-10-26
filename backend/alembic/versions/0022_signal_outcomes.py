"""Prediction tracking: signal_outcomes

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-27

Additive (Y16, docs/predictions.md): a new table ``signal_outcomes``, one row per resolved
buy/sell signal (FK to ``signals``, ON DELETE CASCADE), with an index on ``resolved_at``. No
existing table is changed and no row is written: the ``predictions.resolve_signals`` task
fills it gradually, in batches.

Downgrade drops the table.
"""

import sqlalchemy as sa

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_outcomes",
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("horizon_bars", sa.Integer(), nullable=False),
        sa.Column("exit_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Double(), nullable=True),
        sa.Column("return_pct", sa.Double(), nullable=True),
        sa.Column("mfe_pct", sa.Double(), nullable=True),
        sa.Column("mae_pct", sa.Double(), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("cost_per_unit", sa.Double(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("horizon_bars > 0", name="ck_signal_outcomes_horizon"),
        sa.CheckConstraint("cost_per_unit >= 0", name="ck_signal_outcomes_cost"),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("signal_id"),
    )
    op.create_index("ix_signal_outcomes_resolved_at", "signal_outcomes", ["resolved_at"])


def downgrade() -> None:
    op.drop_index("ix_signal_outcomes_resolved_at", table_name="signal_outcomes")
    op.drop_table("signal_outcomes")
