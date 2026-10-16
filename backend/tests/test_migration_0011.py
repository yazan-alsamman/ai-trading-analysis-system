"""Migration 0011: the new notification_type values exist, the seeded RSS sources are there."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationType


async def test_notification_type_values(session: AsyncSession) -> None:
    values = (
        (
            await session.execute(
                text(
                    "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_type.oid = enumtypid "
                    "WHERE typname = 'notification_type' ORDER BY enumsortorder"
                )
            )
        )
        .scalars()
        .all()
    )
    assert values == [t.value for t in NotificationType]


async def test_seeded_sources_and_indexes(session: AsyncSession) -> None:
    keys = (
        (
            await session.execute(
                text("SELECT key FROM news_sources WHERE kind = 'rss' ORDER BY key")
            )
        )
        .scalars()
        .all()
    )
    assert {"coindesk_rss", "cointelegraph_rss", "investinglive_rss"} <= set(keys)
    indexes = set(
        (
            await session.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE tablename IN "
                    "('news_articles', 'posts', 'comments', 'price_alerts')"
                )
            )
        ).scalars()
    )
    assert {
        "ix_news_articles_published",
        "ix_news_articles_sentiment",
        "ix_news_articles_search",
        "ix_posts_published",
        "ix_comments_post_created",
        "ix_price_alerts_active_instrument",
    } <= indexes
