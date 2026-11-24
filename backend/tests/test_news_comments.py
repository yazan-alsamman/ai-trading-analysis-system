"""Readers' comments on news articles (docs/news-comments.md): create, replies (two levels),
newest-first listing, the article's comments_count, edit/delete rights, admin moderation,
the hourly cap and API keys refused."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.news import NewsArticle, NewsSource
from app.models.user import UserRole
from tests.utils import bearer

NEWS = "/api/v1/news"


@pytest.fixture
async def article(session: AsyncSession) -> NewsArticle:
    source = await session.scalar(select(NewsSource).where(NewsSource.key == "coindesk_rss"))
    row = NewsArticle(
        source_id=source.id,
        external_id="c1",
        url="https://example.com/gold",
        title="Gold steadies ahead of the Fed",
        published_at=datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
    )
    session.add(row)
    await session.commit()
    return row


@pytest.fixture
async def people(make_user):
    alice = await make_user("alice@example.com")
    bob = await make_user("bob@example.com")
    admin = await make_user("boss@example.com", role=UserRole.admin)
    return {
        name: (user, bearer(create_access_token(user)))
        for name, user in (("alice", alice), ("bob", bob), ("admin", admin))
    }


async def _comment(client, article, headers, body="Nice", **extra):
    res = await client.post(
        f"{NEWS}/{article.id}/comments", json={"body": body, **extra}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _count(client, article, headers) -> int:
    res = await client.get(f"{NEWS}/{article.id}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["comments_count"]


async def test_comment_reply_and_count(client: AsyncClient, article, people) -> None:
    alice, a_h = people["alice"]
    _, b_h = people["bob"]
    assert await _count(client, article, a_h) == 0
    first = await _comment(client, article, a_h, "Gold looks strong")
    assert first["author"]["id"] == str(alice.id) and first["is_own"] and first["can_edit"]
    assert first["parent_id"] is None and first["status"] == "published"
    reply = await _comment(client, article, b_h, "Agreed", parent_id=first["id"])
    assert reply["parent_id"] == first["id"]
    # a reply to a reply is stored under the top-level comment
    nested = await _comment(client, article, a_h, "Thanks", parent_id=reply["id"])
    assert nested["parent_id"] == first["id"]
    assert await _count(client, article, b_h) == 3

    listed = (await client.get(f"{NEWS}/{article.id}/comments", headers=b_h)).json()
    assert listed["total"] == 3
    assert [c["id"] for c in listed["items"]] == [nested["id"], reply["id"], first["id"]]
    assert [c["is_own"] for c in listed["items"]] == [False, True, False]
    replies = (
        await client.get(
            f"{NEWS}/{article.id}/comments", params={"parent_id": first["id"]}, headers=b_h
        )
    ).json()
    assert [c["id"] for c in replies["items"]] == [reply["id"], nested["id"]]  # oldest first

    # the list endpoint shows the count too
    page = (await client.get(NEWS, headers=b_h)).json()
    assert next(a for a in page["items"] if a["id"] == str(article.id))["comments_count"] == 3


async def test_edit_and_delete_rights(client: AsyncClient, article, people) -> None:
    _, a_h = people["alice"]
    _, b_h = people["bob"]
    _, admin_h = people["admin"]
    mine = await _comment(client, article, a_h, "First take")
    other = await _comment(client, article, b_h, "Second take")

    res = await client.patch(f"{NEWS}/comments/{mine['id']}", json={"body": "x"}, headers=b_h)
    assert res.status_code == 403
    res = await client.patch(
        f"{NEWS}/comments/{mine['id']}", json={"body": "Edited take"}, headers=a_h
    )
    assert res.status_code == 200 and res.json()["body"] == "Edited take"
    assert res.json()["edited_at"] is not None

    assert (await client.delete(f"{NEWS}/comments/{mine['id']}", headers=b_h)).status_code == 403
    assert (await client.delete(f"{NEWS}/comments/{mine['id']}", headers=a_h)).status_code == 204
    assert (await client.delete(f"{NEWS}/comments/{mine['id']}", headers=a_h)).status_code == 404
    # an admin deletes anyone's comment
    res = await client.delete(f"{NEWS}/comments/{other['id']}", headers=admin_h)
    assert res.status_code == 204
    assert await _count(client, article, a_h) == 0
    listed = (await client.get(f"{NEWS}/{article.id}/comments", headers=a_h)).json()
    assert listed["total"] == 0


async def test_admin_hides_and_restores(client: AsyncClient, article, people) -> None:
    _, a_h = people["alice"]
    _, b_h = people["bob"]
    _, admin_h = people["admin"]
    c = await _comment(client, article, a_h, "Borderline")
    moderate = f"{NEWS.replace('/news', '/admin/news')}/comments/{c['id']}/moderate"
    assert (await client.post(moderate, json={"hidden": True}, headers=b_h)).status_code == 403
    assert (await client.post(moderate, json={"hidden": True}, headers=admin_h)).status_code == 204
    assert await _count(client, article, b_h) == 0
    bob_view = (await client.get(f"{NEWS}/{article.id}/comments", headers=b_h)).json()
    assert bob_view["total"] == 0
    alice_view = (await client.get(f"{NEWS}/{article.id}/comments", headers=a_h)).json()
    assert [x["status"] for x in alice_view["items"]] == ["hidden"]
    assert (await client.post(moderate, json={"hidden": False}, headers=admin_h)).status_code == 204
    assert await _count(client, article, b_h) == 1


async def test_validation_errors_and_cap(
    client: AsyncClient, article, people, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, a_h = people["alice"]
    url = f"{NEWS}/{article.id}/comments"
    assert (await client.post(url, json={"body": ""}, headers=a_h)).status_code == 422
    assert (await client.post(url, json={"body": "x" * 2001}, headers=a_h)).status_code == 422
    missing = "/api/v1/news/00000000-0000-0000-0000-000000000000/comments"
    assert (await client.post(missing, json={"body": "hi"}, headers=a_h)).status_code == 404
    res = await client.post(
        url, json={"body": "hi", "parent_id": "00000000-0000-0000-0000-000000000000"}, headers=a_h
    )
    assert res.status_code == 404
    assert (await client.get(url)).status_code == 401

    monkeypatch.setattr(get_settings(), "comments_per_hour", 2)
    await _comment(client, article, a_h, "one")
    await _comment(client, article, a_h, "two")
    res = await client.post(url, json={"body": "three"}, headers=a_h)
    assert res.status_code == 429 and int(res.headers["Retry-After"]) > 0

    monkeypatch.setattr(get_settings(), "news_comments_enabled", False)
    assert (await client.get(url, headers=a_h)).status_code == 503
