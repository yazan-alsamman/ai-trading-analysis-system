# Comments on news articles

Logged-in readers comment on news articles and reply to each other. Code:
`backend/app/news/comments.py`, routes in `backend/app/api/v1/news.py`, table `news_comments`
(migration 0026). Tests: `backend/tests/test_news_comments.py`.

## Rules

- **Who:** a logged-in user (JWT). API keys are refused (403), as for posts.
- **Body:** 1–2000 characters, trimmed.
- **Replies:** two levels. A reply to a reply is stored under the top-level comment
  (`parent_id` is always a top-level comment).
- **Cap:** `COMMENTS_PER_HOUR` comments per user per hour (shared setting with post comments),
  else 429 with `Retry-After`.
- **Edit:** the author only (`edited_at` is set). **Delete:** the author or an admin; a deleted
  comment is soft-deleted (body emptied) and left out of every list.
- **Moderation:** an admin hides or restores a comment. A hidden comment is shown only to its
  author (with `status: "hidden"`) and to admins.
- **Count:** `comments_count` on every article (list and detail) counts published comments,
  replies included. It is recomputed on every change.
- **Feature flag:** `NEWS_COMMENTS_ENABLED=false` turns every endpoint into 503.

## Endpoints

| Method | Path | |
|---|---|---|
| GET | `/api/v1/news/{article_id}/comments?limit&offset` | newest first, replies included |
| GET | `/api/v1/news/{article_id}/comments?parent_id=…` | the replies of one comment, oldest first |
| POST | `/api/v1/news/{article_id}/comments` | `{body, parent_id?}` → 201 |
| PATCH | `/api/v1/news/comments/{comment_id}` | `{body}` |
| DELETE | `/api/v1/news/comments/{comment_id}` | 204 |
| POST | `/api/v1/admin/news/comments/{comment_id}/moderate` | admin, `{hidden: bool}` → 204 |

A comment: `id, article_id, parent_id, author {id, display_name, role}, body,
status, created_at, edited_at, is_own, can_edit, can_delete`.
