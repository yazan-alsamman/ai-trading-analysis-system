"""news, posts and comments, price alerts

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-16

news_sources (+ three public RSS feeds), news_articles, news_article_instruments, posts,
comments, post_likes, follows, content_reports, price_alerts, and five new values of the
existing ``notification_type`` enum.

Additive only: new enum types, new tables and new enum values. No existing table is altered or
rewritten, so it is safe on a populated production database and quick to apply.

Enum values: ``ALTER TYPE ... ADD VALUE IF NOT EXISTS`` runs in an Alembic
``autocommit_block()``, i.e. outside the migration's transaction. Before PostgreSQL 12 the
statement cannot run inside a transaction block at all, and even on 12+ a value added inside a
transaction cannot be used until that transaction commits. ``IF NOT EXISTS`` makes a re-run
after a failure harmless. The downgrade cannot remove enum values (PostgreSQL has no
``DROP VALUE``): they stay, unused, and a later upgrade skips them. The downgrade deletes the
notifications that use them, because the 0010 code cannot read those rows.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

NEW_NOTIFICATION_TYPES = (
    "new_post",
    "comment_reply",
    "post_liked",
    "content_hidden",
    "price_alert",
)
ENUMS = {
    "news_source_kind": ("rss", "api", "manual"),
    "sentiment_label": ("positive", "neutral", "negative"),
    "post_direction": ("bullish", "bearish", "neutral"),
    "post_visibility": ("public", "followers"),
    "content_status": ("published", "hidden", "deleted"),
    "report_target": ("post", "comment"),
    "report_status": ("open", "resolved"),
    "price_alert_condition": ("above", "below", "crosses_above", "crosses_below", "change_pct"),
    "price_alert_repeat": ("once", "every"),
}
SEARCH_VECTOR = (
    "to_tsvector('simple'::regconfig, (title::text || ' '::text) || COALESCE(summary, ''::text))"
)
# Public feeds fetched by the built-in RSS task until the AI side's adapters (F03) push news.
RSS_SOURCES = (
    ("coindesk_rss", "CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("cointelegraph_rss", "Cointelegraph", "https://cointelegraph.com/rss"),
    ("investinglive_rss", "investingLive (forex)", "https://investinglive.com/feed/news"),
)


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def _ts(name: str, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("clock_timestamp()") if default else None,
        nullable=nullable,
    )


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _fk(column: str, table: str, ondelete: str = "CASCADE") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [f"{table}.id"], ondelete=ondelete)


def _desc(column: str):
    return sa.literal_column(f"{column} DESC")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in NEW_NOTIFICATION_TYPES:
            op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")

    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    # --- news --------------------------------------------------------------------------------
    sources = op.create_table(
        "news_sources",
        _id(),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", _enum("news_source_kind"), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "fetch_interval_minutes", sa.Integer(), server_default=sa.text("15"), nullable=False
        ),
        _ts("last_fetched_at", nullable=True, default=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("last_modified", sa.String(length=64), nullable=True),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.bulk_insert(
        sources,
        [
            {"key": key, "name": name, "kind": "rss", "url": url, "language": "en"}
            for key, name, url in RSS_SOURCES
        ],
    )

    op.create_table(
        "news_articles",
        _id(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=2000), nullable=True),
        sa.Column("author", sa.String(length=200), nullable=True),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        _ts("published_at", default=False),
        _ts("fetched_at"),
        sa.Column("sentiment_label", _enum("sentiment_label"), nullable=True),
        sa.Column("sentiment_score", sa.Double(), nullable=True),
        sa.Column("sentiment_model", sa.String(length=64), nullable=True),
        _ts("sentiment_at", nullable=True, default=False),
        _fk("source_id", "news_sources"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_news_articles_source_external"),
        sa.CheckConstraint(
            "sentiment_score IS NULL OR sentiment_score BETWEEN -1 AND 1",
            name="ck_news_articles_sentiment_score",
        ),
        sa.CheckConstraint(
            "summary IS NULL OR char_length(summary) <= 2000",
            name="ck_news_articles_summary_length",
        ),
    )
    op.create_index("ix_news_articles_published", "news_articles", [_desc("published_at")])
    op.create_index(
        "ix_news_articles_sentiment", "news_articles", ["sentiment_label", _desc("published_at")]
    )
    op.create_index(
        "ix_news_articles_source", "news_articles", ["source_id", _desc("published_at")]
    )
    op.create_index(
        "ix_news_articles_search",
        "news_articles",
        [sa.text(SEARCH_VECTOR)],
        postgresql_using="gin",
    )

    op.create_table(
        "news_article_instruments",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("relevance", sa.Double(), server_default=sa.text("1"), nullable=False),
        _fk("article_id", "news_articles"),
        _fk("instrument_id", "instruments"),
        sa.PrimaryKeyConstraint("article_id", "instrument_id"),
        sa.CheckConstraint(
            "relevance BETWEEN 0 AND 1", name="ck_news_article_instruments_relevance"
        ),
    )
    op.create_index(
        "ix_news_article_instruments_instrument", "news_article_instruments", ["instrument_id"]
    )

    # --- posts, comments, likes, follows, reports ---------------------------------------------
    op.create_table(
        "posts",
        _id(),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=True),
        sa.Column("timeframe", sa.String(length=8), nullable=True),
        sa.Column("direction", _enum("post_direction"), nullable=True),
        sa.Column(
            "attachments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("visibility", _enum("post_visibility"), server_default="public", nullable=False),
        sa.Column("status", _enum("content_status"), server_default="published", nullable=False),
        sa.Column("comments_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("likes_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        _ts("edited_at", nullable=True, default=False),
        _ts("created_at"),
        _fk("author_id", "users"),
        _fk("instrument_id", "instruments", "SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("comments_count >= 0 AND likes_count >= 0", name="ck_posts_counters"),
    )
    op.create_index(
        "ix_posts_published",
        "posts",
        [_desc("created_at")],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index("ix_posts_author_created", "posts", ["author_id", _desc("created_at")])
    op.create_index("ix_posts_instrument_created", "posts", ["instrument_id", _desc("created_at")])

    op.create_table(
        "comments",
        _id(),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", _enum("content_status"), server_default="published", nullable=False),
        _ts("created_at"),
        _ts("edited_at", nullable=True, default=False),
        _fk("post_id", "posts"),
        _fk("author_id", "users"),
        _fk("parent_id", "comments"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_post_created", "comments", ["post_id", "created_at"])
    op.create_index("ix_comments_parent_created", "comments", ["parent_id", "created_at"])
    op.create_index("ix_comments_author_created", "comments", ["author_id", _desc("created_at")])

    op.create_table(
        "post_likes",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _fk("post_id", "posts"),
        _fk("user_id", "users"),
        sa.PrimaryKeyConstraint("post_id", "user_id"),
    )
    op.create_index("ix_post_likes_post_created", "post_likes", ["post_id", "created_at"])

    op.create_table(
        "follows",
        sa.Column("follower_id", sa.Uuid(), nullable=False),
        sa.Column("followee_id", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _fk("follower_id", "users"),
        _fk("followee_id", "users"),
        sa.PrimaryKeyConstraint("follower_id", "followee_id"),
        sa.CheckConstraint("follower_id <> followee_id", name="ck_follows_not_self"),
    )
    op.create_index("ix_follows_followee", "follows", ["followee_id", "created_at"])

    op.create_table(
        "content_reports",
        _id(),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", _enum("report_target"), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", _enum("report_status"), server_default="open", nullable=False),
        sa.Column("resolution", sa.String(length=16), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        _ts("resolved_at", nullable=True, default=False),
        _ts("created_at"),
        _fk("reporter_id", "users"),
        _fk("resolved_by", "users", "SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reporter_id", "target_type", "target_id", name="uq_content_reports_reporter_target"
        ),
    )
    op.create_index(
        "ix_content_reports_status_created", "content_reports", ["status", "created_at"]
    )
    op.create_index("ix_content_reports_target", "content_reports", ["target_type", "target_id"])

    # --- price alerts ------------------------------------------------------------------------
    op.create_table(
        "price_alerts",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("condition", _enum("price_alert_condition"), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=True),
        sa.Column("repeat", _enum("price_alert_repeat"), server_default="once", nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _ts("last_triggered_at", nullable=True, default=False),
        sa.Column("trigger_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        _ts("expires_at", nullable=True, default=False),
        _ts("created_at"),
        _ts("updated_at"),
        _fk("user_id", "users"),
        _fk("instrument_id", "instruments"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("value > 0", name="ck_price_alerts_value_positive"),
        sa.CheckConstraint(
            "(condition = 'change_pct') = (window_minutes IS NOT NULL)",
            name="ck_price_alerts_window",
        ),
        sa.CheckConstraint(
            "(repeat = 'every') = (cooldown_minutes IS NOT NULL)", name="ck_price_alerts_cooldown"
        ),
    )
    op.create_index(
        "ix_price_alerts_active_instrument",
        "price_alerts",
        ["instrument_id"],
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_price_alerts_user_created", "price_alerts", ["user_id", _desc("created_at")]
    )


def downgrade() -> None:
    op.drop_table("price_alerts")
    op.drop_table("content_reports")
    op.drop_table("follows")
    op.drop_table("post_likes")
    op.drop_table("comments")
    op.drop_table("posts")
    op.drop_table("news_article_instruments")
    op.drop_table("news_articles")
    op.drop_table("news_sources")
    bind = op.get_bind()
    for name in reversed(ENUMS):
        postgresql.ENUM(name=name).drop(bind)
    # The notification_type values stay (PostgreSQL cannot drop enum values); the rows using
    # them are removed so the 0010 code never meets a value it does not know.
    values = ", ".join(f"'{v}'" for v in NEW_NOTIFICATION_TYPES)
    op.execute(f"DELETE FROM notifications WHERE type::text IN ({values})")
