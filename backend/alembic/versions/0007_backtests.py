"""backtests

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-16

backtests: one run of a global strategy on a market (status, progress, metrics, downsampled
equity curve). backtest_trades: its trades, one row each.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

backtest_status = postgresql.ENUM(
    "queued", "running", "completed", "failed", "cancelled", name="backtest_status"
)
TIMEFRAME = sa.Enum(
    "1m", "5m", "15m", "1h", "4h", "1d", name="timeframe", native_enum=False, length=8
)


def _ts(name: str, nullable: bool = True, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, **kw)


def upgrade() -> None:
    backtest_status.create(op.get_bind())
    op.create_table(
        "backtests",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("timeframe", TIMEFRAME, nullable=False),
        sa.Column("strategy_key", sa.String(length=64), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _ts("range_start", nullable=False),
        _ts("range_end", nullable=False),
        _ts("first_bar_at"),
        _ts("last_bar_at"),
        sa.Column(
            "status",
            postgresql.ENUM(name="backtest_status", create_type=False),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("progress", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("equity_curve", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bars", sa.Integer(), nullable=True),
        _ts("created_at", nullable=False, server_default=sa.text("clock_timestamp()")),
        _ts("started_at"),
        _ts("finished_at"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("engine_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_backtests_progress"),
        sa.CheckConstraint("range_start < range_end", name="ck_backtests_range"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtests_user_created",
        "backtests",
        ["user_id", sa.literal_column("created_at DESC")],
    )
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("backtest_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=5), nullable=False),
        _ts("entry_time", nullable=False),
        sa.Column("entry_price", sa.Double(), nullable=False),
        _ts("exit_time", nullable=False),
        sa.Column("exit_price", sa.Double(), nullable=False),
        sa.Column("quantity", sa.Double(), nullable=False),
        sa.Column("gross_pnl", sa.Double(), nullable=False),
        sa.Column("fees", sa.Double(), nullable=False),
        sa.Column("net_pnl", sa.Double(), nullable=False),
        sa.Column("return_pct", sa.Double(), nullable=False),
        sa.Column("bars_held", sa.Integer(), nullable=False),
        sa.Column("entry_reason", sa.String(length=64), nullable=True),
        sa.Column("exit_reason", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["backtest_id"], ["backtests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_backtest_trades_number", "backtest_trades", ["backtest_id", "number"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_backtest_trades_number", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_index("ix_backtests_user_created", table_name="backtests")
    op.drop_table("backtests")
    backtest_status.drop(op.get_bind())
