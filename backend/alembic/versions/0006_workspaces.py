"""workspaces

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-16

workspaces: saved trading screens of a user (layout, charts, indicators, strategy overlays,
drawings, watchlist) as one validated JSONB document with an optimistic-concurrency version.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("is_shared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("share_slug", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="ck_workspaces_name_length"),
        sa.CheckConstraint("version >= 1", name="ck_workspaces_version_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_slug"),
    )
    op.create_index("ix_workspaces_user_position", "workspaces", ["user_id", "position"])
    # exactly one default workspace per user
    op.create_index(
        "uq_workspaces_default",
        "workspaces",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    # names are unique per user, case-insensitively
    op.create_index(
        "uq_workspaces_user_name",
        "workspaces",
        ["user_id", sa.literal_column("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_workspaces_user_name", table_name="workspaces")
    op.drop_index("uq_workspaces_default", table_name="workspaces")
    op.drop_index("ix_workspaces_user_position", table_name="workspaces")
    op.drop_table("workspaces")
