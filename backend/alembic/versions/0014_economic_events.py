"""economic calendar: economic_events (one row per observed version of an event)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-20

Additive: one new table with its indexes and constraints; no existing table is touched. Rows
are written by the calendar.refresh task (ForexFactory weekly JSON) and the admin CSV import
(history). Downgrade drops the table.
"""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economic_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("impact", sa.String(8), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("time_label", sa.String(32), nullable=True),
        sa.Column("actual", sa.String(32), nullable=True),
        sa.Column("forecast", sa.String(32), nullable=True),
        sa.Column("previous", sa.String(32), nullable=True),
        sa.Column("actual_value", sa.Double(), nullable=True),
        sa.Column("forecast_value", sa.Double(), nullable=True),
        sa.Column("previous_value", sa.Double(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("event_key", "content_hash", name="uq_economic_events_key_hash"),
        sa.CheckConstraint(
            "impact IN ('high', 'medium', 'low', 'holiday')", name="ck_economic_events_impact"
        ),
        sa.CheckConstraint(
            "source IN ('forexfactory_live', 'forexfactory_kaggle', 'manual')",
            name="ck_economic_events_source",
        ),
        sa.CheckConstraint("currency = upper(currency)", name="ck_economic_events_currency"),
    )
    op.create_index(
        "ix_economic_events_key_fetched",
        "economic_events",
        ["event_key", sa.text("fetched_at DESC")],
    )
    op.create_index("ix_economic_events_scheduled", "economic_events", ["scheduled_at"])
    op.create_index(
        "ix_economic_events_currency_impact",
        "economic_events",
        ["currency", "impact", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_table("economic_events")  # its indexes and constraints go with it
