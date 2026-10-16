# News, posts and comments (Y18)

For the web (E13) and mobile (B11) pages. Base URL `/api/v1`; every endpoint needs a login
token (`Authorization: Bearer …`). News reading also works with an API key that has the
`news:read` scope. Lists are `Page[T]`: `{"items": [...], "total", "limit", "offset"}`.

- [News](#news): articles, search, sentiment, sources
- [Posts](#posts): the feed, attachments, editing, likes
- [Comments](#comments): threads
- [Follows and profiles](#follows-and-profiles)
- [Moderation](#moderation)
- [Real time and notifications](#real-time-and-notifications)

How news arrives (the built-in RSS fetcher and the ingestion API of the AI side) is described in
[news-ingestion.md](news-ingestion.md).

## News

### `GET /news`

Newest first (`published_at`). Query parameters, all optional:

| Parameter | |
|---|---|
| `instrument_id` | only articles tagged with this instrument |
| `sentiment` | `positive` \| `neutral` \| `negative` |
| `source` | a source key, e.g. `coindesk_rss` |
| `language` | e.g. `en`, `ar` |
| `since` | ISO time: published at or after |
| `q` | full-text search in title + summary (see below) |
| `limit` (≤ 100, default 30), `offset` | |

```json
{
  "items": [
    {
      "id": "5d0f6c0e-2f0b-4c55-9b0e-0d2c5f0b6a11",
      "source": {"key": "cointelegraph_rss", "name": "Cointelegraph"},
      "url": "https://cointelegraph.com/news/bitcoin-etf-inflows",
      "title": "Bitcoin ETF inflows hit a record",
      "summary": "Spot bitcoin ETFs took in ... (plain text, at most 2,000 characters)",
      "image_url": "https://images.cointelegraph.com/....jpg",
      "author": "Jane Doe",
      "language": "en",
      "published_at": "2026-10-16T13:56:15Z",
      "fetched_at": "2026-10-16T14:00:03Z",
      "sentiment": {"label": "positive", "score": 0.82, "model": "finbert-ft-v1",
                    "at": "2026-10-16T14:01:10Z"},
      "instruments": [{"instrument_id": "…", "symbol": "BTC/USDT", "relevance": 1.0}]
    }
  ],
  "total": 214, "limit": 30, "offset": 0
}
```

- `summary` is always plain text (HTML is stripped when stored). Open `url` for the article.
- `sentiment` is `null` until the AI side scores the article (FinBERT, F11).
- `instruments`: tags, most relevant first. `relevance` is 1.0 when the instrument is named in
  the title, 0.6 when only in the summary (built-in tagger); the AI side may set its own.

**Search (`q`)** uses Postgres full text with the `simple` configuration (index
`ix_news_articles_search`, GIN on `to_tsvector('simple', title || ' ' || summary)`): whole words,
case-insensitive, no stemming (`bitcoin` does not match `bitcoins`), the same for Arabic. Web
search syntax works: `etf record` (both words), `"gas fees"` (phrase), `bitcoin or ether`,
`bitcoin -etf` (without).

### `GET /news/{id}`

One article, same shape. 404 if unknown.

### `GET /news/sentiment`

Aggregate per instrument over a window, for the dashboard (and F13 on the AI side).

| Parameter | |
|---|---|
| `window` | `1h` \| `24h` (default) \| `7d`; other values → 422 |
| `instrument_id` | optional: only that instrument |

```json
{
  "window": "24h",
  "since": "2026-10-15T14:05:00Z",
  "overall": {"articles": 3, "scored": 2, "positive": 1, "neutral": 0, "negative": 1,
              "mean_score": 0.2, "weighted_score": null},
  "instruments": [
    {"instrument_id": "…", "symbol": "BTC/USDT", "articles": 3, "scored": 2,
     "positive": 1, "neutral": 0, "negative": 1, "mean_score": 0.2, "weighted_score": 0.4}
  ]
}
```

- Articles published in the window. `articles` counts all of them, `scored` those with a
  sentiment; the label counts and `mean_score` (−1..1) cover the scored ones only.
- `weighted_score` (per instrument): the mean score weighted by tag relevance,
  `Σ(score × relevance) / Σ(relevance)` over the scored articles.
- `overall` counts every article in the window, tagged or not.

### `GET /news/sources` · `PATCH /admin/news/sources/{id}`

The list (any logged-in user): `key`, `name`, `kind` (`rss`, `api`, `manual`), `url`,
`language`, `is_active`, `fetch_interval_minutes`, `last_fetched_at`, `last_error`, and
`articles` (stored count). Admins change `{"is_active": false}` or
`{"fetch_interval_minutes": 30}` (5–1440). A disabled RSS source is not fetched; a disabled
`api` source refuses ingested items. Existing articles stay listed.

## Posts

Analyses written by analysts, experts and admins (`POST_ROLES`). Everyone can read (subject to
visibility), comment and like.

### `POST /posts` (rate-limit cost 2)

```json
{
  "title": "BTC: range break or fake-out?",
  "body": "## Plan\n\nWatching **64k**. See the backtest below.",
  "instrument_id": "…",
  "timeframe": "1h",
  "direction": "bullish",
  "attachments": [{"type": "backtest", "id": "…"}],
  "visibility": "public"
}
```

| Field | |
|---|---|
| `title` | 1–140 characters, one line |
| `body` | Markdown, 1–20,000 characters, **stored as written** |
| `instrument_id`, `timeframe`, `direction` | optional; `direction`: `bullish` \| `bearish` \| `neutral` |
| `attachments` | up to 5 references, see below |
| `visibility` | `public` (default) \| `followers` (the author's followers, the author and admins) |

Answers 201 with the post. 403 for traders, 422 for invalid input (an unknown instrument, an
attachment you may not use, raw HTML), 429 over the daily limit (`POSTS_PER_DAY`, default 10
per rolling 24 h; `Retry-After` says when). The author's followers get a `new_post`
notification.

**Markdown rules.** The API never returns HTML: render the body as Markdown **with raw HTML
disabled** (web: `marked`/`markdown-it` with `html: false`; Flutter: `flutter_markdown`). Input
is refused (422) when it contains, outside code spans/blocks, raw HTML tags or comments, or a
link whose target is not relative, `http`, `https` or `mailto` (`javascript:`, `data:`,
`vbscript:` …, also when hidden with entities or whitespace). `price < 30k` is fine; so is HTML
inside a code block.

**Attachments** are references, resolved when the post is read:

| `type` | allowed when | summary returned |
|---|---|---|
| `backtest` | the author's own backtest | `strategy_key`, `symbol`, `timeframe`, `status`, `range_start`, `range_end`, `metrics` (`total_return_pct`, `max_drawdown_pct`, `sharpe`, `trades`, `win_rate_pct`) |
| `custom_strategy` | the author's own, or a public one | `name`, `kind`, `description`, `key` (`custom:<uuid>`, usable in previews and backtests) |
| `shared_workspace` | a workspace with a share link (anyone's) | `name`, `share_slug` (open `GET /workspaces/shared/{slug}`) |
| `signal` | any signal | `instrument_id`, `symbol`, `timeframe`, `strategy_key`, `side`, `price`, `strength`, `bar_time` |

Every resolved attachment has `available`. It becomes `{"type", "id", "available": false}` when
the target is gone or no longer visible to the reader (a strategy made private again, a
workspace unshared). The author's own private strategy is only shown to the author. A 422 lists
each bad attachment: `{"loc": ["body", "attachments", 2, "id"], "msg": "workspace not found or
not shared (share it first)"}`.

### `GET /posts` (the feed)

| Parameter | |
|---|---|
| `scope` | `all` (default) \| `following` (authors you follow) |
| `instrument_id`, `author_id`, `direction` | filters |
| `limit` (≤ 50, default 20), `offset` | |

Newest first. A post looks like this:

```json
{
  "id": "…",
  "author": {"id": "…", "display_name": "Lina Analyst", "role": "analyst"},
  "title": "BTC: range break or fake-out?",
  "body": "## Plan\n\nWatching **64k**. …",
  "instrument": {"id": "…", "symbol": "BTC/USDT"},
  "timeframe": "1h",
  "direction": "bullish",
  "attachments": [
    {"type": "backtest", "id": "…", "available": true, "strategy_key": "ma_crossover",
     "symbol": "BTC/USDT", "timeframe": "1h", "status": "completed",
     "range_start": "…", "range_end": "…",
     "metrics": {"total_return_pct": -12.8, "max_drawdown_pct": -28.7, "sharpe": -2.71,
                 "trades": 26, "win_rate_pct": 26.9}}
  ],
  "visibility": "public",
  "status": "published",
  "comments_count": 3,
  "likes_count": 12,
  "liked_by_me": false,
  "can_edit": false,
  "edited_at": null,
  "created_at": "2026-10-16T14:20:00Z"
}
```

- The feed shows published posts the reader may see: public ones, followers-only ones of
  authors the reader follows, and the reader's own. The reader's own **hidden** posts appear
  too, with `status: "hidden"`; nobody else sees them.
- `display_name` is the user's full name, or `user-1a2b3c4d` without one. E-mail addresses
  are never returned.
- `comments_count` and `likes_count` are counters kept in the post row (no counting on read).

### `GET /posts/{id}` · `PATCH /posts/{id}` · `DELETE /posts/{id}`

- `GET`: 404 when the reader may not see it (deleted, hidden, followers-only).
- `PATCH`: any subset of the create fields (`title`, `body`, `attachments`, `visibility` cannot
  be `null`). Only the author **within 24 hours** of publishing (`POST_EDIT_WINDOW_HOURS`),
  admins at any time; `edited_at` is set. 403 otherwise (`"Posts can be edited within 24
  hours"`, or for a post hidden by moderation). `can_edit` in the post tells the UI.
- `DELETE`: the author or an admin, 204. Soft delete: the post disappears (404) for everyone;
  admins still get it by id with `status: "deleted"`. Deleting does not refill the daily limit.

### `POST /posts/{id}/like` · `DELETE /posts/{id}/like`

Idempotent; both answer `{"liked": true, "likes_count": 12}`. The author gets one batched
`post_liked` notification per post and day. Only published posts can be liked (409).

## Comments

### `GET /posts/{id}/comments`

Top-level comments **oldest first**, paginated (`limit` ≤ 100, default 20, `offset`), each with
its first 20 replies inline:

```json
{
  "items": [
    {
      "id": "…", "post_id": "…", "parent_id": null,
      "author": {"id": "…", "display_name": "Omar Trader", "role": "trader"},
      "body": "What about ETH?",
      "status": "published",
      "created_at": "…", "edited_at": null, "can_edit": true,
      "replies": [
        {"id": "…", "post_id": "…", "parent_id": "<top id>", "author": {…}, "body": "Soon",
         "status": "published", "created_at": "…", "edited_at": null, "can_edit": false}
      ],
      "replies_count": 23,
      "more_replies": true
    }
  ],
  "total": 4, "limit": 20, "offset": 0
}
```

With `more_replies`, load the rest with `GET /posts/{id}/comments?parent_id=<top id>&offset=20`
(a `Page` of replies, oldest first).

**Placeholders** keep threads readable:

| `status` | `author` | `body` |
|---|---|---|
| `published` | set | the text |
| `deleted` | `null` | `null` (the text is erased) |
| `hidden` (moderation) | set | `null` for others; the author (and admins) still see it |

### `POST /posts/{id}/comments` (rate-limit cost 2)

`{"body": "…", "parent_id": "<comment id>"?}` → 201 with the comment. Plain text or light
Markdown, 1–2,000 characters, same input rules as posts. **Two levels**: a reply to a reply is
stored under the top-level comment (its `parent_id` is the top comment), and the author of the
comment you answered is notified. 409 on a post that is not published or a deleted parent, 429
over `COMMENTS_PER_HOUR` (default 60 per rolling hour).

### `PATCH /comments/{id}` · `DELETE /comments/{id}`

`PATCH {"body": "…"}`: the author, at any time, while published; sets `edited_at`. `DELETE`:
the author or an admin, 204 (soft delete, placeholder above).

## Follows and profiles

| Method | Path | |
|---|---|---|
| POST | `/users/{id}/follow` | `{"following": true, "followers_count": 8}`; idempotent. 400 for yourself or a user who is not an analyst or expert, 404 unknown |
| DELETE | `/users/{id}/follow` | `{"following": false, "followers_count": 7}`; idempotent |
| GET | `/me/following` | `Page` of `{"user": {id, display_name, role}, "since"}`, newest first |
| GET | `/me/followers` | the same, the people following you |
| GET | `/users/{id}/profile` | the public profile |

```json
{
  "id": "…",
  "display_name": "Lina Analyst",
  "role": "analyst",
  "member_since": "2026-09-01T10:00:00Z",
  "posts_count": 14,
  "followers_count": 8,
  "following_count": 2,
  "followable": true,
  "is_following": true,
  "recent_posts": [ /* up to 5 posts the viewer may see, post shape */ ],
  "public_strategies": [
    {"id": "…", "name": "RSI + EMA filter", "description": "…", "kind": "builder",
     "updated_at": "…"}
  ]
}
```

No e-mail and no ids of other users. 404 for unknown or deactivated users.

## Moderation

- `POST /reports` (cost 2): `{"target_type": "post" | "comment", "target_id": "…", "reason":
  "3-500 characters"}` → 201. Reporting the same content again returns the first report
  (200). 400 for your own content, 404 for content you cannot see, 429 over `REPORTS_PER_DAY`
  (default 20).
- `GET /admin/reports?status=open|resolved|all` (admin; default `open`), newest first:

  ```json
  {"id": "…", "target_type": "post", "target_id": "…", "reason": "pump and dump",
   "status": "open", "resolution": null, "created_at": "…", "resolved_at": null,
   "reporter": {"id": "…", "display_name": "Omar Trader", "role": "trader"},
   "target": {"status": "published", "post_id": "…",
              "author": {"id": "…", "display_name": "Lina Analyst"},
              "title": "Pump it", "excerpt": "…"},
   "open_reports_on_target": 2}
  ```

- `POST /admin/reports/{id}/resolve` (admin): `{"action": "hide" | "dismiss", "note": "shown to
  the author"?}`. `hide` sets the post or comment to `hidden` (it disappears from feeds and
  threads show the placeholder; the author still sees it with its status) and notifies the
  author (`content_hidden`, reason = `note` or the report's reason). `dismiss` changes nothing.
  Either way every open report on the same content is resolved. 409 if already resolved.

## Real time and notifications

WebSocket `/ws/market` ([websocket.md](websocket.md)):

- `{"op": "subscribe", "topic": "news"}` — every new article; with `"instrument_id"` only those
  tagged with it (`news:<uuid>`). Message `{"type": "news", "article": {…}}` (shape above, without
  `author`/`fetched_at`).
- Notifications arrive on the user's own topic as `{"type": "notification", ...}`.

Notification types ([notifications.md](notifications.md)), defaults in brackets:

| Type | When | Default channels |
|---|---|---|
| `new_post` | someone you follow published | in-app, push |
| `comment_reply` | a comment on your post / a reply to your comment | in-app, push |
| `post_liked` | "N people liked your post": one inbox row per post and day, updated by every like | **in-app only** (no switch) |
| `content_hidden` | moderation hid your content | in-app, email, push |

Push `data` for these: `{"screen": "post", "post_id", "comment_id"?}`. Nobody is notified about
their own actions.

## Limits (configuration)

| Setting | Default |
|---|---|
| `POST_ROLES` | `analyst,expert,admin` |
| `POST_EDIT_WINDOW_HOURS` | 24 |
| `POSTS_PER_DAY` / `COMMENTS_PER_HOUR` / `REPORTS_PER_DAY` | 10 / 60 / 20 |
| `CONTENT_CREATE_COST` | 2 (rate-limit units of POST /posts, comments, reports) |
