"""gold_levels setups and the daily volatility: exit_type, exit_reason, sl, ai_volatility_daily

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-13

Additive and safe on existing data (B13, docs/ai-contract.md, contract 0.3.0):

- ``ai_setups``: nullable ``exit_type`` (null means ``target``, as every existing row) with a
  check on its values, and nullable ``exit_reason``;
- ``ai_setup_events``: nullable ``sl`` (the new stop of an ``sl_moved`` event);
- ``ai_setup_outbox``: nullable ``sl`` (an ``sl_moved`` alert). Its unique constraint
  ``(setup_id, to_state)`` becomes a unique index on the same columns for the rows without
  ``sl`` (every existing row), and stop moves get their own unique index ``(setup_id, at)``:
  several moves of one setup are kept, a replayed one is not enqueued twice. Existing rows
  satisfy both indexes as they are;
- a new table ``ai_volatility_daily`` (FK to ``instruments``, ON DELETE CASCADE), primary key
  ``(instrument_id, day)``.

No row is written or changed. Downgrade removes the stop-move outbox rows (they would break
the old constraint), restores the constraint and drops the new columns and the table.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_setups", sa.Column("exit_type", sa.String(length=16), nullable=True))
    op.add_column("ai_setups", sa.Column("exit_reason", sa.String(length=64), nullable=True))
    op.create_check_constraint(
        "ck_ai_setups_exit_type",
        "ai_setups",
        "exit_type IS NULL OR exit_type IN ('target', 'trailing', 'time')",
    )
    op.add_column("ai_setup_events", sa.Column("sl", sa.Double(), nullable=True))
    op.add_column("ai_setup_outbox", sa.Column("sl", sa.Double(), nullable=True))
    op.drop_constraint("uq_ai_setup_outbox_setup_state", "ai_setup_outbox", type_="unique")
    op.create_index(
        "uq_ai_setup_outbox_setup_state",
        "ai_setup_outbox",
        ["setup_id", "to_state"],
        unique=True,
        postgresql_where=sa.text("sl IS NULL"),
    )
    op.create_index(
        "uq_ai_setup_outbox_sl_moved",
        "ai_setup_outbox",
        ["setup_id", "at"],
        unique=True,
        postgresql_where=sa.text("sl IS NOT NULL"),
    )
    op.create_table(
        "ai_volatility_daily",
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("expected_move_pct", sa.Double(), nullable=True),
        sa.Column("range_pct", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("range_usd", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("level", sa.String(length=32), nullable=True),
        sa.Column(
            "news",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("instrument_id", "day"),
    )


def downgrade() -> None:
    op.drop_table("ai_volatility_daily")
    op.execute("DELETE FROM ai_setup_outbox WHERE sl IS NOT NULL")
    op.drop_index("uq_ai_setup_outbox_sl_moved", table_name="ai_setup_outbox")
    op.drop_index("uq_ai_setup_outbox_setup_state", table_name="ai_setup_outbox")
    op.create_unique_constraint(
        "uq_ai_setup_outbox_setup_state", "ai_setup_outbox", ["setup_id", "to_state"]
    )
    op.drop_column("ai_setup_outbox", "sl")
    op.drop_column("ai_setup_events", "sl")
    op.drop_constraint("ck_ai_setups_exit_type", "ai_setups", type_="check")
    op.drop_column("ai_setups", "exit_reason")
    op.drop_column("ai_setups", "exit_type")
