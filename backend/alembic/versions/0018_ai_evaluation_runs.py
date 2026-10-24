"""AI evaluation runs (B9) and the sizing source names remote / local

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-24

Additive and safe on existing data:

- ai_evaluation_runs: one row per evaluate run (instrument, profile, bar_close_ts; unique), with
  its status (ok, abstained, skipped, unavailable, contract_error, error), the reason, the
  request size, the bar coverage, the duration and a summary of the answer (or of the local
  abstention when ai-service was not called). Read by GET /admin/system/status.
- ai_setup_sizes.source: 'ai-service' becomes 'remote' (Fadi's naming, B9); the check
  constraint follows. Rows are updated in place, nothing is lost.

Downgrade drops the table and renames 'remote' back to 'ai-service'.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

NOW = sa.text("clock_timestamp()")
STATUSES = "'ok', 'abstained', 'skipped', 'unavailable', 'contract_error', 'error'"


def upgrade() -> None:
    op.create_table(
        "ai_evaluation_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.Uuid(),
            sa.ForeignKey("instruments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile", sa.String(32), nullable=False),
        sa.Column("bar_close_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(64), nullable=True),
        sa.Column("request_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "coverage",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint(
            "instrument_id", "profile", "bar_close_ts", name="uq_ai_evaluation_runs_key"
        ),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_ai_evaluation_runs_status"),
    )
    op.create_index("ix_ai_evaluation_runs_finished", "ai_evaluation_runs", ["finished_at"])

    op.drop_constraint("ck_ai_setup_sizes_source", "ai_setup_sizes", type_="check")
    op.execute("UPDATE ai_setup_sizes SET source = 'remote' WHERE source = 'ai-service'")
    op.create_check_constraint(
        "ck_ai_setup_sizes_source", "ai_setup_sizes", "source IN ('remote', 'local')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_ai_setup_sizes_source", "ai_setup_sizes", type_="check")
    op.execute("UPDATE ai_setup_sizes SET source = 'ai-service' WHERE source = 'remote'")
    op.create_check_constraint(
        "ck_ai_setup_sizes_source", "ai_setup_sizes", "source IN ('ai-service', 'local')"
    )
    op.drop_index("ix_ai_evaluation_runs_finished", table_name="ai_evaluation_runs")
    op.drop_table("ai_evaluation_runs")
