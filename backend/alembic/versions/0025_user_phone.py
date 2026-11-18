"""Verified WhatsApp phone of a user: users.phone_e164, users.phone_verified_at

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-16

Additive and safe on existing data (docs/otp.md, LightOTP): two nullable columns on ``users``,
a unique constraint on ``phone_e164`` (NULLs do not collide, so every existing row satisfies it)
and a check that a set number is E.164 (``+`` then 7 to 15 digits). Every existing user keeps
NULL in both. No row is written or changed.

Downgrade drops the constraints and the two columns (the verified numbers are lost).
"""

import sqlalchemy as sa

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_e164", sa.String(length=16), nullable=True))
    op.add_column(
        "users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint("uq_users_phone_e164", "users", ["phone_e164"])
    op.create_check_constraint(
        "ck_users_phone_e164",
        "users",
        "phone_e164 IS NULL OR phone_e164 ~ '^\\+[1-9][0-9]{6,14}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_phone_e164", "users", type_="check")
    op.drop_constraint("uq_users_phone_e164", "users", type_="unique")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_e164")
