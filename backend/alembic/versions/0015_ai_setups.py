"""AI engine storage: ai_setups, ai_setup_events, ai_model_versions, ai_setup_sizes,
ai_setup_explanations

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-21

Additive: five new tables with their keys, constraints and indexes; no existing table is
touched (the rule-signal engine keeps its own tables). Rows are written from ai-service
responses (B9), sizes (B10) and explanations (B9/B11). Downgrade drops the five tables.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# Kept literal here on purpose: migrations must not depend on application code.
STATES = "'DEVELOPING', 'ARMED', 'ACTIVE', 'CLOSED', 'EXPIRED', 'INVALIDATED'"
NOW = sa.text("clock_timestamp()")


def upgrade() -> None:
    op.create_table(
        "ai_setups",
        sa.Column("setup_id", sa.String(128), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.Uuid(),
            sa.ForeignKey("instruments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(4), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("entry", sa.Double(), nullable=True),
        sa.Column("sl", sa.Double(), nullable=True),
        sa.Column("tp", sa.Double(), nullable=True),
        sa.Column("r_multiple", sa.Double(), nullable=True),
        sa.Column("probability", sa.Double(), nullable=True),
        sa.Column("ev_r", sa.Double(), nullable=True),
        sa.Column("ev_r_lower", sa.Double(), nullable=True),
        sa.Column("grade", sa.String(4), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("horizon_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realized_r", sa.Double(), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("strategy_version", sa.String(64), nullable=True),
        sa.Column("model_version", sa.String(128), nullable=True),
        sa.Column("features_version", sa.String(64), nullable=True),
        sa.Column("first_request_id", sa.String(160), nullable=False),
        sa.Column("last_request_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint(f"state IN ({STATES})", name="ck_ai_setups_state"),
        sa.CheckConstraint("direction IN ('buy', 'sell')", name="ck_ai_setups_direction"),
        sa.CheckConstraint(
            "probability IS NULL OR probability BETWEEN 0 AND 1", name="ck_ai_setups_probability"
        ),
    )
    op.create_index("ix_ai_setups_open", "ai_setups", ["instrument_id", "profile", "state"])
    op.create_index("ix_ai_setups_created", "ai_setups", [sa.text("created_at DESC")])

    op.create_table(
        "ai_setup_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "setup_id",
            sa.String(128),
            sa.ForeignKey("ai_setups.setup_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(16), nullable=True),
        sa.Column("to_state", sa.String(16), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("realized_r", sa.Double(), nullable=True),
        sa.Column("request_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("setup_id", "to_state", "at", name="uq_ai_setup_events_setup_state_at"),
        sa.CheckConstraint(
            f"from_state IS NULL OR from_state IN ({STATES})", name="ck_ai_setup_events_from"
        ),
        sa.CheckConstraint(f"to_state IN ({STATES})", name="ck_ai_setup_events_to"),
    )

    op.create_table(
        "ai_model_versions",
        sa.Column("model_id", sa.String(128), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("training_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_hash", sa.String(128), nullable=True),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    # at most one active model
    op.create_index(
        "uq_ai_model_versions_one_active",
        "ai_model_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "ai_setup_sizes",
        sa.Column(
            "setup_id",
            sa.String(128),
            sa.ForeignKey("ai_setups.setup_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("lots", sa.Double(), nullable=False),
        sa.Column("risk_usd", sa.Double(), nullable=False),
        sa.Column("margin_required", sa.Double(), nullable=True),
        sa.Column("feasible", sa.Boolean(), nullable=False),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )

    op.create_table(
        "ai_setup_explanations",
        sa.Column(
            "setup_id",
            sa.String(128),
            sa.ForeignKey("ai_setups.setup_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("lang", sa.String(8), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("template_used", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("lang IN ('ar', 'en')", name="ck_ai_setup_explanations_lang"),
    )


def downgrade() -> None:
    # children first; their indexes and constraints go with them
    op.drop_table("ai_setup_explanations")
    op.drop_table("ai_setup_sizes")
    op.drop_table("ai_setup_events")
    op.drop_table("ai_model_versions")
    op.drop_table("ai_setups")
