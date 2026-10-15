"""strategies and signals

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15

user_strategies: users activating a global strategy (defined in code, trading_strategies) on a
market. signals: what the live engine produced, unique per setup and closed bar.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

signal_side = postgresql.ENUM("buy", "sell", name="signal_side")
# Timeframe values in a VARCHAR(8) (non-native enum: validated by the application)
TIMEFRAME = sa.Enum(
    "1m", "5m", "15m", "1h", "4h", "1d", name="timeframe", native_enum=False, length=8
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        )
    ]


def upgrade() -> None:
    signal_side.create(op.get_bind())
    op.create_table(
        "user_strategies",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_key", sa.String(length=64), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("timeframe", TIMEFRAME, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notify", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "strategy_key",
            "params_hash",
            "instrument_id",
            "timeframe",
            name="uq_user_strategies_setup",
        ),
    )
    op.create_index(op.f("ix_user_strategies_user_id"), "user_strategies", ["user_id"])
    op.create_index(
        "ix_user_strategies_market", "user_strategies", ["instrument_id", "timeframe", "is_active"]
    )

    op.create_table(
        "signals",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("timeframe", TIMEFRAME, nullable=False),
        sa.Column("strategy_key", sa.String(length=64), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", postgresql.ENUM(name="signal_side", create_type=False), nullable=False),
        sa.Column("strength", sa.Double(), nullable=False),
        sa.Column("price", sa.Double(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "instrument_id",
            "timeframe",
            "strategy_key",
            "params_hash",
            "bar_time",
            name="uq_signals_bar",
        ),
    )
    op.create_index(
        "ix_signals_market_time",
        "signals",
        ["instrument_id", "timeframe", sa.literal_column("bar_time DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_signals_market_time", table_name="signals")
    op.drop_table("signals")
    op.drop_index("ix_user_strategies_market", table_name="user_strategies")
    op.drop_index(op.f("ix_user_strategies_user_id"), table_name="user_strategies")
    op.drop_table("user_strategies")
    signal_side.drop(op.get_bind())
