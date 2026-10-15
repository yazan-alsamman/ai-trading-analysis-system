"""market data: instruments, candles_1m hypertable, continuous aggregates

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15

1-minute candles are the only stored price data. Higher timeframes are hierarchical continuous
aggregates with real-time aggregation on:

    candles_1m -> candles_5m -> candles_15m -> candles_1h -> candles_4h
                                              candles_1h -> candles_1d

CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous) and the cagg policy functions cannot
run inside a transaction, hence the autocommit blocks.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

market_type = postgresql.ENUM("crypto", "forex", "stock", "commodity", name="market_type")

# (view, source relation, bucket, start_offset, end_offset, schedule_interval)
# Kept literal here on purpose: migrations must not depend on application code.
AGGREGATES = [
    ("candles_5m", "candles_1m", "5 minutes", "2 hours", "5 minutes", "1 minute"),
    ("candles_15m", "candles_5m", "15 minutes", "6 hours", "15 minutes", "5 minutes"),
    ("candles_1h", "candles_15m", "1 hour", "1 day", "1 hour", "15 minutes"),
    ("candles_4h", "candles_1h", "4 hours", "3 days", "4 hours", "1 hour"),
    ("candles_1d", "candles_1h", "1 day", "7 days", "1 day", "1 hour"),
]


def upgrade() -> None:
    market_type.create(op.get_bind())
    op.create_table(
        "instruments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("market", postgresql.ENUM(name="market_type", create_type=False), nullable=False),
        sa.Column("base_asset", sa.String(length=16), nullable=False),
        sa.Column("quote_asset", sa.String(length=16), nullable=False),
        sa.Column("price_precision", sa.Integer(), nullable=True),
        sa.Column("quantity_precision", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.CheckConstraint("source = lower(source)", name="ck_instruments_source_lower"),
        sa.CheckConstraint("symbol = upper(symbol)", name="ck_instruments_symbol_upper"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "symbol", name="uq_instruments_source_symbol"),
    )
    op.create_table(
        "candles_1m",
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Double(), nullable=False),
        sa.Column("high", sa.Double(), nullable=False),
        sa.Column("low", sa.Double(), nullable=False),
        sa.Column("close", sa.Double(), nullable=False),
        sa.Column("volume", sa.Double(), nullable=False),
        sa.Column("trades", sa.Integer(), nullable=True),
        sa.CheckConstraint("ts = date_trunc('minute', ts)", name="ck_candles_1m_ts_minute"),
        sa.CheckConstraint("high >= greatest(open, close)", name="ck_candles_1m_high"),
        sa.CheckConstraint("high >= low", name="ck_candles_1m_high_low"),
        sa.CheckConstraint("low <= least(open, close)", name="ck_candles_1m_low"),
        sa.CheckConstraint("volume >= 0", name="ck_candles_1m_volume"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("instrument_id", "ts"),
    )

    # The PK (instrument_id, ts) already serves every query; skip Timescale's extra ts index.
    op.execute(
        "SELECT create_hypertable('candles_1m', by_range('ts', INTERVAL '7 days'), "
        "create_default_indexes => false)"
    )
    op.execute(
        "ALTER TABLE candles_1m SET ("
        "timescaledb.compress, "
        "timescaledb.compress_segmentby = 'instrument_id', "
        "timescaledb.compress_orderby = 'ts DESC')"
    )
    op.execute("SELECT add_compression_policy('candles_1m', INTERVAL '30 days')")

    with op.get_context().autocommit_block():
        for view, source, bucket, *_ in AGGREGATES:
            # Timescale creates an (instrument_id, ts DESC) index on each materialization
            # hypertable automatically (timescaledb.create_group_indexes defaults to true).
            op.execute(
                f"""
                CREATE MATERIALIZED VIEW {view}
                WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
                SELECT instrument_id,
                       time_bucket(INTERVAL '{bucket}', ts) AS ts,
                       first(open, ts) AS open,
                       max(high) AS high,
                       min(low) AS low,
                       last(close, ts) AS close,
                       sum(volume) AS volume,
                       sum(trades)::bigint AS trades
                FROM {source}
                GROUP BY instrument_id, time_bucket(INTERVAL '{bucket}', ts)
                WITH NO DATA
                """
            )
        for view, _source, _bucket, start_offset, end_offset, schedule in AGGREGATES:
            op.execute(
                f"SELECT add_continuous_aggregate_policy('{view}', "
                f"start_offset => INTERVAL '{start_offset}', "
                f"end_offset => INTERVAL '{end_offset}', "
                f"schedule_interval => INTERVAL '{schedule}')"
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for view, *_ in reversed(AGGREGATES):
            op.execute(f"SELECT remove_continuous_aggregate_policy('{view}', if_exists => true)")
            op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view}")
    op.execute("SELECT remove_compression_policy('candles_1m', if_exists => true)")
    op.drop_table("candles_1m")
    op.drop_table("instruments")
    market_type.drop(op.get_bind())
