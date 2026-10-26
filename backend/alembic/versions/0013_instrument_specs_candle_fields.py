"""instrument contract specs, session calendar, candle spread/source/received_at

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-19

instruments: nullable contract specs (contract_size, tick_size, lot_step, min_lot, max_lot,
quote_currency, margin_rate, price_basis, session_calendar, spec_source, spec_updated_at) with
check constraints. Data step: the fxpro XAU/USD instrument is created if missing, and the seeded
instruments get *typical* specs (spec_source 'typical') in every column that is still null, so
a re-run never overwrites a value that is already set. The twelvedata XAU/USD is left untouched.

candles_1m: nullable spread, source and received_at. TimescaleDB adds nullable columns without
a default to a compressed hypertable as a catalog change only (no chunk is rewritten or
decompressed). It refuses ``ADD CONSTRAINT`` on any hypertable with compression enabled, even
``NOT VALID``, so ``spread >= 0`` is enforced by the API schema (CandleIn) instead of a check.
The continuous aggregates are not changed: spread stays on 1m only.

Downgrade drops the new columns. The fxpro XAU/USD row is kept (deleting it would cascade to its
candles); upgrading again finds it and fills only what is null.
"""

import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# Kept literal here on purpose: migrations must not depend on application code.
FXPRO_SESSION_CALENDAR = {
    "tz": "America/New_York",
    "week_open": {"day": "sun", "time": "18:00"},
    "week_close": {"day": "fri", "time": "16:55"},
    "daily_breaks": [{"start": "16:55", "end": "18:00"}],
    "holidays": [],
}

_FX = {"contract_size": 100_000, "lot_step": 0.01, "min_lot": 0.01, "max_lot": 100}


def _crypto(tick_size: float, lot_step: float) -> dict:
    """1 lot = 1 coin; tick from the price precision, step from the quantity precision."""
    return {
        "contract_size": 1,
        "tick_size": tick_size,
        "lot_step": lot_step,
        "min_lot": lot_step,
        "price_basis": "last",
    }


# (source, symbol) -> typical specs; quote_currency is the instrument's quote_asset.
TYPICAL_SPECS = {
    ("fxpro", "XAU/USD"): {
        "contract_size": 100,
        "tick_size": 0.01,
        "lot_step": 0.01,
        "min_lot": 0.01,
        "max_lot": 100,
        "price_basis": "bid",
        "session_calendar": FXPRO_SESSION_CALENDAR,
    },
    ("twelvedata", "EUR/USD"): {**_FX, "tick_size": 0.00001, "price_basis": "bid"},
    ("twelvedata", "GBP/USD"): {**_FX, "tick_size": 0.00001, "price_basis": "bid"},
    ("twelvedata", "USD/JPY"): {**_FX, "tick_size": 0.001, "price_basis": "bid"},
    ("binance", "BTC/USDT"): _crypto(0.01, 0.00001),
    ("binance", "ETH/USDT"): _crypto(0.01, 0.0001),
    ("binance", "BNB/USDT"): _crypto(0.01, 0.001),
    ("binance", "SOL/USDT"): _crypto(0.01, 0.01),
    ("binance", "XRP/USDT"): _crypto(0.0001, 0.1),
}

SPEC_COLUMNS = (
    "contract_size",
    "tick_size",
    "lot_step",
    "min_lot",
    "max_lot",
    "price_basis",
    "session_calendar",
)

INSTRUMENT_CHECKS = {
    "ck_instruments_contract_size": "contract_size IS NULL OR contract_size > 0",
    "ck_instruments_tick_size": "tick_size IS NULL OR tick_size > 0",
    "ck_instruments_lot_step": "lot_step IS NULL OR lot_step > 0",
    "ck_instruments_min_lot": "min_lot IS NULL OR min_lot > 0",
    "ck_instruments_max_lot": "max_lot IS NULL OR max_lot > 0",
    "ck_instruments_lot_range": "min_lot IS NULL OR max_lot IS NULL OR min_lot <= max_lot",
    "ck_instruments_margin_rate": "margin_rate IS NULL OR (margin_rate > 0 AND margin_rate <= 1)",
    "ck_instruments_price_basis": "price_basis IS NULL OR price_basis IN ('bid', 'mid', 'last')",
}


def upgrade() -> None:
    op.add_column("instruments", sa.Column("contract_size", sa.Double(), nullable=True))
    op.add_column("instruments", sa.Column("tick_size", sa.Double(), nullable=True))
    op.add_column("instruments", sa.Column("lot_step", sa.Double(), nullable=True))
    op.add_column("instruments", sa.Column("min_lot", sa.Double(), nullable=True))
    op.add_column("instruments", sa.Column("max_lot", sa.Double(), nullable=True))
    op.add_column("instruments", sa.Column("quote_currency", sa.String(16), nullable=True))
    op.add_column("instruments", sa.Column("margin_rate", sa.Double(), nullable=True))
    op.add_column("instruments", sa.Column("price_basis", sa.String(8), nullable=True))
    op.add_column(
        "instruments",
        sa.Column("session_calendar", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("instruments", sa.Column("spec_source", sa.String(32), nullable=True))
    op.add_column(
        "instruments", sa.Column("spec_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    for name, condition in INSTRUMENT_CHECKS.items():
        op.create_check_constraint(name, "instruments", condition)

    # Nullable, no default: a catalog-only change on the compressed hypertable.
    op.add_column("candles_1m", sa.Column("spread", sa.Double(), nullable=True))
    op.add_column("candles_1m", sa.Column("source", sa.String(32), nullable=True))
    op.add_column("candles_1m", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))

    seed(op.get_bind())


def seed(bind) -> None:
    """Create the fxpro XAU/USD if missing and fill the typical specs that are still null.
    Safe to run any number of times: nothing that is already set is overwritten."""
    bind.execute(
        sa.text(
            "INSERT INTO instruments (symbol, source, market, base_asset, quote_asset, "
            "price_precision) "
            "VALUES ('XAU/USD', 'fxpro', 'commodity', 'XAU', 'USD', 2) "
            "ON CONFLICT (source, symbol) DO NOTHING"
        )
    )
    fill = sa.text(
        """
        UPDATE instruments SET
            contract_size = coalesce(contract_size, :contract_size),
            tick_size = coalesce(tick_size, :tick_size),
            lot_step = coalesce(lot_step, :lot_step),
            min_lot = coalesce(min_lot, :min_lot),
            max_lot = coalesce(max_lot, :max_lot),
            quote_currency = coalesce(quote_currency, quote_asset),
            price_basis = coalesce(price_basis, :price_basis),
            session_calendar = coalesce(session_calendar, CAST(:session_calendar AS jsonb)),
            spec_source = coalesce(spec_source, 'typical'),
            spec_updated_at = coalesce(spec_updated_at, now())
        WHERE source = :source AND symbol = :symbol
        """
    )
    for (source, symbol), spec in TYPICAL_SPECS.items():
        values = {name: spec.get(name) for name in SPEC_COLUMNS}
        calendar = values["session_calendar"]
        values["session_calendar"] = json.dumps(calendar) if calendar is not None else None
        bind.execute(fill, {**values, "source": source, "symbol": symbol})


def downgrade() -> None:
    op.drop_column("candles_1m", "received_at")
    op.drop_column("candles_1m", "source")
    op.drop_column("candles_1m", "spread")
    for name in reversed(INSTRUMENT_CHECKS):
        op.drop_constraint(name, "instruments", type_="check")
    for column in (
        "spec_updated_at",
        "spec_source",
        "session_calendar",
        "price_basis",
        "margin_rate",
        "quote_currency",
        "max_lot",
        "min_lot",
        "lot_step",
        "tick_size",
        "contract_size",
    ):
        op.drop_column("instruments", column)
