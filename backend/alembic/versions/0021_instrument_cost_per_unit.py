"""Instruments: a fixed trading cost per unit (cost_per_unit)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-25

Additive: a nullable column ``instruments.cost_per_unit`` (price units per unit of quantity,
round trip, >= 0; docs/risk-management.md#fixed-cost-per-unit), editable by an admin like the
other spec fields. Backtests and sizing use it instead of fee_bps / slippage_bps when it is set.

Data step (Fadi, 25 Oct): the fxpro XAU/USD gets 0.25 (spread and every trading cost, per oz,
per round trip) **only if it is still null**: a value an admin set is never overwritten, and
``spec_source`` is left as it is. Other instruments stay null.

Downgrade drops the column (and its check).
"""

import sqlalchemy as sa

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

# idempotent: a value that is already set (by an admin, or a re-run) is kept
SET_XAU_COST = (
    "UPDATE instruments SET cost_per_unit = 0.25 "
    "WHERE source = 'fxpro' AND symbol = 'XAU/USD' AND cost_per_unit IS NULL"
)


def upgrade() -> None:
    op.add_column("instruments", sa.Column("cost_per_unit", sa.Double(), nullable=True))
    op.create_check_constraint(
        "ck_instruments_cost_per_unit",
        "instruments",
        "cost_per_unit IS NULL OR cost_per_unit >= 0",
    )
    op.execute(SET_XAU_COST)


def downgrade() -> None:
    op.drop_constraint("ck_instruments_cost_per_unit", "instruments", type_="check")
    op.drop_column("instruments", "cost_per_unit")
