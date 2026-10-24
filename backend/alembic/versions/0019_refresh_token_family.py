"""Login sessions: refresh_tokens.family_id and users.sessions_revoked_at (B12 part 2)

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-25

Additive and safe on existing data:

- refresh_tokens.family_id (uuid, nullable, indexed): the login session a refresh token belongs
  to. A login starts a family (family_id = the row's own id); a rotation inherits it. Existing
  rows are backfilled with family_id = id: an old rotation chain then simply counts as separate
  sessions, which only matters for tokens issued before this deploy.
- users.sessions_revoked_at (timestamptz, nullable): when every session of the user was ended
  (password change, refresh-token reuse, deactivation). Access tokens issued before this deploy
  carry no session id; their WebSockets close when it is later than the token's ``iat``.

Downgrade drops both columns and the index.
"""

import sqlalchemy as sa

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("family_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE refresh_tokens SET family_id = id WHERE family_id IS NULL")
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.add_column(
        "users", sa.Column("sessions_revoked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "sessions_revoked_at")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "family_id")
