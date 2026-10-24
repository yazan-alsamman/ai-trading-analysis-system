"""Feed credentials: the cTrader Open API tokens, encrypted (B1)

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-25

Additive: a new, empty table ``feed_credentials`` (one row per provider). The OAuth access and
refresh tokens are stored encrypted (Fernet, key derived from JWT_SECRET; app/feeds/secrets.py).
Downgrade drops the table.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_credentials",
        sa.Column("provider", sa.String(32), primary_key=True),
        sa.Column("env", sa.String(8), nullable=False),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "accounts", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "linked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("env IN ('demo', 'live')", name="ck_feed_credentials_env"),
    )


def downgrade() -> None:
    op.drop_table("feed_credentials")
