"""Chart image analyses: chart_analyses

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-27

Additive (Y14, docs/chart-analysis.md): a new table ``chart_analyses`` (FK to ``users``, ON
DELETE CASCADE) with two indexes: the user's history, newest first, and the duplicate lookup
by image hash. The image itself is never stored, only its SHA-256. No existing table is changed
and no row is written.

Downgrade drops the table.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chart_analyses",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("image_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("mime", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("symbol_hint", sa.String(length=32), nullable=True),
        sa.Column("timeframe_hint", sa.String(length=8), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('ok', 'not_chart', 'refused', 'error')", name="ck_chart_analyses_status"
        ),
        sa.CheckConstraint("language IN ('ar', 'en')", name="ck_chart_analyses_language"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chart_analyses_user_created",
        "chart_analyses",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_chart_analyses_user_sha", "chart_analyses", ["user_id", "image_sha256"])


def downgrade() -> None:
    op.drop_index("ix_chart_analyses_user_sha", table_name="chart_analyses")
    op.drop_index("ix_chart_analyses_user_created", table_name="chart_analyses")
    op.drop_table("chart_analyses")
