"""custom strategies

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-16

custom_strategies: a user's own strategies, Builder (rules) or Composite (several strategies
voting), as one validated JSONB definition with a hash, an optimistic-concurrency version and
private/public visibility. Used everywhere a global strategy is, as ``custom:<uuid>``.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

kind = postgresql.ENUM("builder", "composite", name="custom_strategy_kind")
visibility = postgresql.ENUM("private", "public", name="custom_strategy_visibility")


def upgrade() -> None:
    bind = op.get_bind()
    kind.create(bind)
    visibility.create(bind)
    op.create_table(
        "custom_strategies",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=500), server_default="", nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(name="custom_strategy_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("definition_hash", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "visibility",
            postgresql.ENUM(name="custom_strategy_visibility", create_type=False),
            server_default="private",
            nullable=False,
        ),
        sa.Column("cloned_from", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 60", name="ck_custom_strategies_name_length"
        ),
        sa.CheckConstraint(
            "char_length(description) <= 500", name="ck_custom_strategies_description_length"
        ),
        sa.CheckConstraint("version >= 1", name="ck_custom_strategies_version_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cloned_from"], ["custom_strategies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_custom_strategies_user_name",
        "custom_strategies",
        ["user_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_custom_strategies_visibility_updated",
        "custom_strategies",
        ["visibility", sa.literal_column("updated_at DESC")],
    )
    op.create_index(
        "ix_custom_strategies_user_created", "custom_strategies", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_custom_strategies_user_created", table_name="custom_strategies")
    op.drop_index("ix_custom_strategies_visibility_updated", table_name="custom_strategies")
    op.drop_index("uq_custom_strategies_user_name", table_name="custom_strategies")
    op.drop_table("custom_strategies")
    bind = op.get_bind()
    visibility.drop(bind)
    kind.drop(bind)
