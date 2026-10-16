# News ingestion (for the AI side: F03 adapters, F11 FinBERT)

The platform stores news in `news_articles`. Two ways in:

1. **Built-in RSS fetcher** (already running): a beat task every 5 minutes fetches the active
   `rss` sources whose `fetch_interval_minutes` is due. Seeded: `coindesk_rss`,
   `cointelegraph_rss`, `investinglive_rss` (forex). Admins enable/disable them
   (`PATCH /admin/news/sources/{id}`).
2. **Ingestion API** (this document): your adapters (Finnhub, NewsAPI, …) push articles, and
   FinBERT pushes sentiment for existing articles.

Base URL: `http://187.127.76.76:8080/api/v1` (production), `http://localhost/api/v1` (local
stack through Nginx).

## Access: an API key with `news:write`

Only an **admin** account can create a key with `news:write`, and the key stops working if its
owner is no longer an admin. Ask an admin for one (or, as admin):

```bash
curl -s -X POST $BASE/me/api-keys -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name": "ai-news", "scopes": ["news:write", "news:read"], "rate_limit_per_minute": 120}'
# -> {"key": "tk_ab12cd34_…", ...}   shown once: store it as a secret (Colab: userdata)
```

Send it as `X-API-Key: tk_…`. Without the scope: 403. Rate limit: the admin tier (1,000
requests/minute) or the key's own `rate_limit_per_minute`.

## `POST /ingest/news`

Up to **200 articles** per request:

```json
{
  "articles": [
    {
      "source_key": "finnhub",
      "external_id": "finnhub-123456",
      "url": "https://example.com/article",
      "title": "Bitcoin climbs as ETF inflows grow",
      "summary": "Optional. HTML is stripped, then cut to 2,000 characters.",
      "published_at": "2026-10-16T12:30:00Z",
      "language": "en",
      "image_url": "https://example.com/img.jpg",
      "author": "Reuters",
      "instruments": [{"symbol": "BTC/USDT", "relevance": 0.9}, {"symbol": "ETH", "relevance": 0.4}],
      "sentiment": {"label": "positive", "score": 0.71, "model": "finbert-ft-v1"}
    }
  ]
}
```

| Field | Rules |
|---|---|
| `source_key` | `[a-z0-9_.-]`, 2–64. **Unknown keys create an `api` source** on first use; a source an admin disabled refuses items |
| `external_id` | your stable id, ≤ 255. With `source_key` it is the idempotency key |
| `url`, `image_url` | `http(s)` only |
| `title` | 1–500 (HTML stripped) |
| `published_at` | ISO 8601; without a zone = UTC; future times are clamped to now |
| `language` | optional, default the source's (`en`) |
| `instruments` | optional, ≤ 20. `symbol` is an instrument symbol (`BTC/USDT`, `EUR/USD`: that pair on every source) or an asset code (`BTC`: every pair with that base). **When given, they replace the article's tags**; unknown symbols are ignored and reported in `warnings`. When omitted, a new article is tagged by the built-in tagger and an existing one keeps its tags |
| `sentiment` | optional: `label` `positive`\|`neutral`\|`negative`, `score` −1..1, `model` ≤ 64. When omitted, a stored sentiment is kept |

Answer (200):

```json
{
  "inserted": 1,
  "updated": 0,
  "skipped": 2,
  "errors": [{"index": 3, "external_id": "x", "error": "url: Value error, must be an http(s) URL"}],
  "warnings": [{"index": 0, "external_id": "finnhub-123456", "error": "unknown symbols ignored: DOGE"}]
}
```

- **Idempotent**: `(source_key, external_id)` is unique. Sending the same article again is
  `skipped`; a changed field (title, summary, url, image, author, language, published_at,
  sentiment, tags) makes it `updated`. Retrying a whole batch after a timeout is safe.
- **Per-item errors**: each item is validated on its own; invalid ones are listed by `index`
  and the others are stored. Two items with the same key in one batch: the later one wins, the
  earlier one is reported as a duplicate.
- New articles published in the last 24 hours are pushed live on the WebSocket `news` topics.

## `POST /ingest/news/sentiment`

Score existing articles (up to **500** items), by id or by your key:

```json
{
  "items": [
    {"article_id": "5d0f6c0e-…", "label": "negative", "score": -0.64, "model": "finbert-ft-v1"},
    {"source_key": "cointelegraph_rss", "external_id": "…", "label": "neutral", "score": 0.02,
     "model": "finbert-ft-v1"}
  ]
}
```

→ `{"updated": 2, "errors": [{"index": 5, "external_id": null, "error": "article not found"}]}`.
The last write wins. Articles to score: `GET /news?limit=100` (articles with `sentiment: null`),
newest first; RSS articles have `external_id` = a hash of their URL, so use `article_id` for them.

## Python example (Colab or `ai-service`)

```python
import os, requests
from datetime import datetime, timezone

BASE = "http://187.127.76.76:8080/api/v1"
HEADERS = {"X-API-Key": os.environ["NEWS_API_KEY"]}   # Colab: userdata.get("NEWS_API_KEY")

# 1) push articles (e.g. from Finnhub)
articles = [{
    "source_key": "finnhub",
    "external_id": str(item["id"]),
    "url": item["url"],
    "title": item["headline"],
    "summary": item.get("summary"),
    "published_at": datetime.fromtimestamp(item["datetime"], timezone.utc).isoformat(),
    "image_url": item.get("image") or None,
    "instruments": [{"symbol": "BTC", "relevance": 1.0}],
} for item in finnhub_items]
for i in range(0, len(articles), 200):
    r = requests.post(f"{BASE}/ingest/news", json={"articles": articles[i:i + 200]},
                      headers=HEADERS, timeout=30)
    r.raise_for_status()
    print(r.json())

# 2) score unscored articles with FinBERT and push the sentiment
page = requests.get(f"{BASE}/news", params={"limit": 100}, headers=HEADERS, timeout=30).json()
todo = [a for a in page["items"] if a["sentiment"] is None]
texts = [f"{a['title']}. {a['summary'] or ''}" for a in todo]
results = finbert(texts)                       # your pipeline: [{"label", "score"}]
items = [{
    "article_id": a["id"],
    "label": res["label"].lower(),             # positive / neutral / negative
    "score": res["score"] if res["label"].lower() == "positive"
             else -res["score"] if res["label"].lower() == "negative" else 0.0,
    "model": "finbert-ft-v1",
} for a, res in zip(todo, results)]
r = requests.post(f"{BASE}/ingest/news/sentiment", json={"items": items}, headers=HEADERS,
                  timeout=30)
print(r.json())

# 3) what the dashboard shows
print(requests.get(f"{BASE}/news/sentiment", params={"window": "24h"}, headers=HEADERS,
                   timeout=30).json())
```

`score` convention: −1 (very negative) … +1 (very positive). The aggregate
(`GET /news/sentiment`) averages it per instrument; see [news-posts.md](news-posts.md).

## The built-in RSS fetcher

- Task `news.fetch` on the existing `worker` (beat every 5 minutes; `NEWS_RSS_ENABLED`,
  default `true`). Due feeds are fetched concurrently (at most 4 at a time).
- Per feed: **10 s for the whole request** (`NEWS_FETCH_TIMEOUT_SECONDS`), at most **2 MB**
  (`NEWS_FETCH_MAX_BYTES`, checked on `Content-Length` and while streaming), up to 3
  redirects, conditional GET with `If-None-Match` / `If-Modified-Since` (a 304 stores nothing).
  The task itself has a 60 s hard limit.
- Parsing with `feedparser` from bytes (it never fetches anything itself), off the event loop.
  HTML is stripped from titles and summaries; URLs are normalised (lower-case host, no
  fragment, no `utm_*`/`fbclid`/`gclid`/… parameters, sorted query) and `external_id` =
  sha256 of the normalised URL. Items without an http(s) link or a title are skipped. Items
  without a date get the fetch time (kept on later fetches).
- Errors (`HTTP 503`, `timeout after 10s`, `feed larger than … bytes`, `unparsable feed …`)
  are stored in the source's `last_error`; the next fetch happens after the interval.
- New articles are tagged by the built-in tagger (symbols and names, also Arabic, from
  `backend/app/news/aliases.py`).
- Retention: articles older than `NEWS_RETENTION_DAYS` (180) are deleted daily at 03:45 UTC.
