"""News comments, paper trading, notification type paper_trade

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-16

Additive and safe on existing data:

- notification_type gains 'paper_trade' (``ALTER TYPE ... ADD VALUE IF NOT EXISTS`` in an
  autocommit block, as in 0011/0012/0017);
- news_articles.comments_count (integer, default 0: every existing article has no comment);
- news_comments: readers' comments on an article (docs/news-comments.md);
- paper_accounts, paper_positions, paper_orders: the simulated trading account of a user
  (docs/paper-trading.md). No existing row is read or changed.

Downgrade drops the tables and the column and deletes the notifications of type 'paper_trade'
(PostgreSQL cannot drop an enum value, so 0025 code must never read one).
"""

import sqlalchemy as sa

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

NOW = sa.text("clock_timestamp()")
UUID_DEFAULT = sa.text("gen_random_uuid()")


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True, server_default=UUID_DEFAULT)


def _user() -> sa.Column:
    return sa.Column(
        "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


def _instrument() -> sa.Column:
    return sa.Column(
        "instrument_id",
        sa.Uuid(),
        sa.ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'paper_trade'")

    op.add_column(
        "news_articles",
        sa.Column("comments_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "news_comments",
        _id(),
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("news_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey("news_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('published', 'hidden', 'deleted')", name="ck_news_comments_status"
        ),
    )
    op.create_index(
        "ix_news_comments_article_created",
        "news_comments",
        ["article_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_news_comments_parent", "news_comments", ["parent_id"])
    op.create_index(
        "ix_news_comments_author_created",
        "news_comments",
        ["author_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "paper_accounts",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("initial_balance", sa.Double(), nullable=False),
        sa.Column("balance", sa.Double(), nullable=False),
        sa.Column("leverage", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("leverage BETWEEN 1 AND 1000", name="ck_paper_accounts_leverage"),
        sa.CheckConstraint("initial_balance > 0", name="ck_paper_accounts_initial"),
    )
    op.create_table(
        "paper_positions",
        _id(),
        _user(),
        _instrument(),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("lots", sa.Double(), nullable=False),
        sa.Column("contract_size", sa.Double(), nullable=False),
        sa.Column("entry_price", sa.Double(), nullable=False),
        sa.Column("stop_loss", sa.Double(), nullable=True),
        sa.Column("take_profit", sa.Double(), nullable=True),
        sa.Column("margin", sa.Double(), nullable=False),
        sa.Column("cost", sa.Double(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(8), nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("checked_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_price", sa.Double(), nullable=True),
        sa.Column("close_reason", sa.String(16), nullable=True),
        sa.Column("pnl", sa.Double(), nullable=True),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_paper_positions_side"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_paper_positions_status"),
        sa.CheckConstraint("lots > 0", name="ck_paper_positions_lots"),
    )
    op.create_index(
        "ix_paper_positions_user_status",
        "paper_positions",
        ["user_id", "status", sa.text("opened_at DESC")],
    )
    op.create_index(
        "ix_paper_positions_open_instrument",
        "paper_positions",
        ["instrument_id"],
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_table(
        "paper_orders",
        _id(),
        _user(),
        _instrument(),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column("lots", sa.Double(), nullable=False),
        sa.Column("price", sa.Double(), nullable=True),
        sa.Column("stop_loss", sa.Double(), nullable=True),
        sa.Column("take_profit", sa.Double(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("reject_reason", sa.String(64), nullable=True),
        sa.Column("fill_price", sa.Double(), nullable=True),
        sa.Column(
            "position_id",
            sa.Uuid(),
            sa.ForeignKey("paper_positions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("checked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_paper_orders_side"),
        sa.CheckConstraint("type IN ('market', 'limit', 'stop')", name="ck_paper_orders_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'filled', 'cancelled', 'rejected')",
            name="ck_paper_orders_status",
        ),
        sa.CheckConstraint("lots > 0", name="ck_paper_orders_lots"),
    )
    op.create_index(
        "ix_paper_orders_user_created", "paper_orders", ["user_id", sa.text("created_at DESC")]
    )
    op.create_index(
        "ix_paper_orders_pending_instrument",
        "paper_orders",
        ["instrument_id"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_table("paper_orders")
    op.drop_table("paper_positions")
    op.drop_table("paper_accounts")
    op.drop_table("news_comments")
    op.drop_column("news_articles", "comments_count")
    op.execute("DELETE FROM notifications WHERE type = 'paper_trade'")
