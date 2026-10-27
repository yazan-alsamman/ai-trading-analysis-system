# Chart image analysis with Gemini (Y14)

A logged-in user uploads a screenshot of a price chart and gets a structured, checked analysis:
- trend, patterns, support and resistance, indicators seen;
- an idea (buy, sell or wait, with a confidence);
- a short summary in Arabic or English.

It is an educational aid and **not financial advice**: every result carries a fixed disclaimer
added by the backend.

**Code:** `backend/app/vision/`
- `images.py`: upload checks and re-encoding;
- `gemini.py`: the model call;
- `schemas.py`: the result and its checks;
- `service.py`: duplicates, quota, storage, history;
- `prompts/chart_v1.md`: the prompt.

The API is `app/api/v1/chart_analysis.py`, and the table is `chart_analyses` (migration 0023).
It runs in the backend only; ai-service is not involved.

## 1. Flow

1. **Feature check.** The feature must be on: `GEMINI_API_KEY` is set and
   `CHART_ANALYSIS_ENABLED=true`. Otherwise every endpoint answers 503 `not_configured`, and
   the rest of the platform is unaffected.
2. **Upload checks**, on one dedicated thread per API worker so the event loop never waits:
   - the type comes from the **magic bytes** (PNG, JPEG, WebP), never from the header or file
     name; anything else is 415;
   - at most `CHART_IMAGE_MAX_BYTES` (5 MB), else 413;
   - at least 200 × 200 px, and at most 40 Mpx **before decoding** (a decompression bomb is
     never decoded; Pillow's own `MAX_IMAGE_PIXELS` guard is set to the same value), else 422.
3. **Re-encoding with Pillow:**
   - the EXIF orientation is applied, the image is converted to RGB, and the longest side is
     scaled to at most 1568 px;
   - every metadata entry (EXIF, ICC, text) is dropped;
   - it is sent as PNG, or as a quality-90 JPEG when the PNG would be over 1 MB.
4. **Duplicates.** The same user, image (SHA-256 of the upload), language and hints within
   24 h returns the stored result (`cached: true`), with no model call and no quota.
5. **Slot.** At most `CHART_ANALYSIS_MAX_CONCURRENT` (1) analyses run at a time per API worker,
   so 2 for the backend. A request waits up to 10 s for a slot, then gets 503 `busy` with
   `Retry-After: 10`, and no quota is taken.
6. **Quota.** One unit of the daily quota is taken (Redis, per user per UTC day). When it is
   used up: 429 with `Retry-After` = seconds to 00:00 UTC.
7. **Gemini.** The official `google-genai` SDK, async (`client.aio.models.generate_content`),
   with one client per process.
   - The image goes first (`Part.from_bytes`), then the request text (language and hints).
   - Structured output: `response_mime_type="application/json"`,
     `response_schema=ModelChartAnalysis`, temperature 0.2, and the versioned prompt as the
     system instruction.
   - `response.parsed` is validated again with Pydantic. Free text is never parsed.
8. **Checks by code.** See §2. The disclaimer is added in the requested language.
9. **Storage.** The row is stored and returned.

## 2. Result schema

| Field | |
|---|---|
| `is_chart` | false: the image is not a price chart. Every other field is empty, the API answers 422 `not_a_chart`, and the call **counts** against the quota |
| `symbol_guess`, `timeframe_guess` | only from visible text, else null |
| `trend`, `trend_strength` | `up` / `down` / `sideways`, and 0–1 |
| `patterns` | `[{name, confidence 0–1, description}]` |
| `support_levels`, `resistance_levels` | numbers, only when the price axis is readable |
| `indicators_seen` | `[{name, reading}]` |
| `idea` | `{action: buy/sell/wait, confidence 0–1, entry, stop_loss, take_profit, risk_reward}`, with every price nullable |
| `summary` | 2–4 sentences in the requested language |
| `reasoning`, `warnings` | lists of strings |
| `disclaimer` | fixed per language, **added by the backend** |

Checks by code (`schemas.finalize`). These never reject a whole result:
- confidences and `trend_strength` are clamped to 0..1;
- non-positive or non-finite prices are dropped;
- the idea's prices must be on the right side: for a buy, stop < entry < target; for a sell,
  target < entry < stop. Otherwise the three prices are dropped and a warning is added;
- `risk_reward` is **computed** from the kept prices (|target − entry| / |entry − stop|), never
  taken from the model.

### Example (English)

`POST /api/v1/analysis/chart-image` (multipart: `image=@xau15m.png`, `language=en`,
`symbol=XAU/USD`, `timeframe=15m`) returns 200:

```json
{
  "id": "6f1c…", "created_at": "2026-10-27T09:12:44Z", "status": "ok", "language": "en",
  "symbol_hint": "XAU/USD", "timeframe_hint": "15m",
  "model": "gemini-3.6-flash", "prompt_version": "chart_v1",
  "image": {"sha256": "9b2e…", "bytes": 412337, "width": 1920, "height": 1080, "mime": "image/png"},
  "result": {
    "is_chart": true, "symbol_guess": "XAU/USD", "timeframe_guess": "15m",
    "trend": "up", "trend_strength": 0.7,
    "patterns": [{"name": "ascending triangle", "confidence": 0.62,
                  "description": "Flat resistance near 2412 with higher lows since 2385."}],
    "support_levels": [2385.0, 2396.5], "resistance_levels": [2412.0],
    "indicators_seen": [{"name": "RSI(14)", "reading": "about 61, rising"}],
    "idea": {"action": "buy", "confidence": 0.55, "entry": 2413.0, "stop_loss": 2403.0,
             "take_profit": 2433.0, "risk_reward": 2.0},
    "summary": "Price is making higher lows under a flat resistance at 2412. A close above it would make a continuation likely; until then the range holds.",
    "reasoning": ["Higher lows since 2385", "RSI above 50 and rising"],
    "warnings": ["Few candles visible to the left of the pattern"],
    "disclaimer": "This is an automated analysis for educational purposes only, not financial advice. Trading decisions and their risks are yours alone."
  },
  "error": null,
  "usage": {"input_tokens": 1830, "output_tokens": 640, "latency_ms": 4210},
  "cached": false
}
```

### Example (Arabic)

The same image with `language=ar`. Only the texts change; enums and numbers stay as they are:

```json
{
  "status": "ok", "language": "ar",
  "result": {
    "is_chart": true, "trend": "up", "trend_strength": 0.7,
    "patterns": [{"name": "مثلث صاعد", "confidence": 0.62,
                  "description": "مقاومة أفقية قرب 2412 مع قيعان صاعدة منذ 2385."}],
    "idea": {"action": "buy", "confidence": 0.55, "entry": 2413.0, "stop_loss": 2403.0,
             "take_profit": 2433.0, "risk_reward": 2.0},
    "summary": "السعر يصنع قيعاناً صاعدة تحت مقاومة أفقية عند 2412. الإغلاق فوقها يجعل استمرار الصعود مرجّحاً، وحتى ذلك يبقى النطاق قائماً.",
    "reasoning": ["قيعان صاعدة منذ 2385", "مؤشر RSI فوق 50 وصاعد"],
    "warnings": ["عدد الشموع الظاهرة قبل النموذج قليل"],
    "disclaimer": "هذا التحليل آلي ولأغراض تعليمية فقط، وليس نصيحة مالية. قرار التداول ومخاطره عليك وحدك."
  }
}
```

## 3. Endpoints (`/api/v1/analysis/chart-image`, JWT users)

| Method | Path | |
|---|---|---|
| POST | `` | multipart: `image` (required), `language` (`ar`/`en`; default: the user's notification-preferences language, else `ar`), `symbol` and `timeframe` hints. Synchronous: returns the stored analysis. Costs `RATE_LIMIT_EXPENSIVE_COST` units of the per-minute rate limit |
| GET | `` | your history, newest first, `limit` (≤ 100) and `offset` → `{items, total, limit, offset}` |
| GET | `/quota` | `{limit, used, remaining, resets_at}` (UTC day) |
| GET | `/{id}` | one of your analyses; 404 for anyone else's |
| DELETE | `/{id}` | 204; 404 for anyone else's. The quota is not given back |

**Errors** (`detail = {code, message, …}`). None of them is ever a 500.

| Status | `code` | When |
|---|---|---|
| 413 | `image_too_large` | over `CHART_IMAGE_MAX_BYTES` (Nginx refuses over 6 MB first) |
| 415 | `unsupported_image` | not PNG, JPEG or WebP by its bytes |
| 422 | `image_too_small`, `image_too_many_pixels`, `invalid_image` | the checks above (no quota) |
| 422 | `not_a_chart` | the model says it is not a chart (counted; `analysis_id` given) |
| 422 | `blocked`, `empty_answer`, `invalid_answer`, `could_not_analyse` | a blocked or safety answer, an empty or invalid structured answer, or a 4xx from the model (counted) |
| 429 | `quota_exceeded` | daily quota used up; `Retry-After` |
| 503 | `not_configured` | no key, the feature off, or the key refused by Google |
| 503 | `busy` | no free slot within 10 s; `Retry-After: 10` (no quota) |
| 503 | `model_busy`, `model_unavailable`, `timeout` | 429 or 5xx after 2 retries with backoff, a network error, or no answer within `CHART_VISION_TIMEOUT_SECONDS`; `Retry-After: 30`. The quota unit is given back and the row is stored as `error` |

## 4. Quotas, limits and cost

| Setting | Default | |
|---|---|---|
| `CHART_ANALYSIS_DAILY_LIMIT_TRADER` | 5 | analyses per UTC day |
| `CHART_ANALYSIS_DAILY_LIMIT_ANALYST` | 20 | |
| `CHART_ANALYSIS_DAILY_LIMIT_EXPERT` | 20 | |
| `CHART_ANALYSIS_DAILY_LIMIT_ADMIN` | 100 | |
| `CHART_ANALYSIS_MAX_CONCURRENT` | 1 | in flight per API worker (2 workers: 2) |
| `CHART_IMAGE_MAX_BYTES` | 5242880 | 5 MB; Nginx allows 6m on this route only, with a 60 s read timeout |
| `CHART_VISION_TIMEOUT_SECONDS` | 45 | the whole call, retries included |

A duplicate within 24 h is free. `not_chart` and refused answers count, because the model ran.
Service failures (503) do not.

**Cost per call (estimate).**
- Tokens: one image of at most 1568 px (on the order of 1,000–1,600 input tokens), plus the
  prompt (about 700), plus the JSON answer and the model's thinking (about 500–1,000 output
  tokens). `output_tokens` stores the answer plus the thinking, as both are billed.
- At Google's listed prices for Gemini 3.6 Flash:
  - the introductory rate until 31 Dec 2026 ($0.75 input / $3.75 output per 1M tokens) gives
    about **$0.003–0.005 per call**;
  - the standard rate from 1 Jan 2027 ($1.50 / $7.50) gives about **$0.006–0.010 per call**.
- At these rates, 100 traders using their full 5 a day comes to about $1.5–5 a day.
- Check the current rates on https://ai.google.dev/gemini-api/docs/pricing. Every row stores
  `input_tokens` and `output_tokens`, and `/admin/system/status` sums the last 24 h.

## 5. Prompt versioning

The system instruction is `backend/app/vision/prompts/<version>.md`; today that is `chart_v1`.
Every row stores `prompt_version`. A change to the wording is a **new file** (`chart_v2.md`)
and a new `PROMPT_VERSION` in `gemini.py`, never an edit of an old one, so stored results
always say which prompt produced them.

The `chart_v1` rules:
- analyse only what is visible;
- never invent an unreadable price (use null);
- keep confidences calibrated, and prefer `wait` with a low confidence when the chart is
  unclear;
- say "high-probability" or "likely", never "guaranteed";
- answer in the requested language;
- set `is_chart=false` for anything that is not a price chart;
- do not add a disclaimer (the backend adds it).

**Model id.** `CHART_VISION_MODEL` (`gemini-3.6-flash`). To see the ids a key can use, run this
locally, never at startup in production:
`python -c "from google import genai; print([m.name for m in genai.Client(api_key='…').models.list()])"`

## 6. Privacy

- **Images are never stored.** Only the SHA-256 of the upload, its size, dimensions and type
  are kept, with the result, the hints and the token counts.
- The re-encoded image (no metadata) is sent to Google's Gemini API for this one call, under
  Google's API terms. Users should not upload screenshots that show account numbers or personal
  data.
- Logs carry the model, token counts, latency, attempts and `is_chart`; never the image, its
  base64 or the key. The SDK's own loggers are kept at WARNING.
- A user can delete any of their analyses (`DELETE /{id}`), and deleting the user deletes them
  all (`ON DELETE CASCADE`).

## 7. Memory (measured)

The backend container has two API workers. It was measured locally from the production image,
with 2 workers and a fake Gemini that answers after 2 s: 3 rounds of **4 parallel uploads of
3000 × 2000 noisy JPEGs, 4.5 MB each** (the worst case under 5 MB).

| Version | cgroup peak | OOM kills at 544m |
|---|---|---|
| first version (PNG always, decoding on the default thread pool) | 744 MiB (at 1g) | **2 workers killed** |
| final: one image thread per worker, in-place Pillow steps, JPEG above 1 MB, one analysis per worker | 508 MiB, 479 MiB anonymous (at 544m) | 0 |

- An idle backend is about 296 MiB, about 175 MiB per worker.
- One analysis adds about 40 MiB to a worker: decoding about 10, the SDK import 13, the call
  about 15.
- The heavy uploads add about 190 MiB at the peak. The load test's normal API peak was
  400 MiB, so the backend `mem_limit` goes from **544m to 640m (+96m)**, which leaves room for
  both at once. The sum of all limits goes from 3424 MiB to **3520 MiB** (about 45% of the
  7.8 GB host).

## 8. How to enable it on the server

1. In GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**.
   Name it `GEMINI_API_KEY` and paste the key from https://aistudio.google.com/apikey.
2. Merge to `main` (or **Actions → Deploy → Run workflow**). The step "Gemini API key into
   .env" masks the key and writes it into `/opt/trading/.env` **only if it is missing or
   empty**; an existing value is never overwritten.
   - With no secret, it prints `GEMINI_API_KEY not set in GitHub: skipped` and the deploy goes
     on.
   - The next step's `up -d` runs with the new image tag, which recreates the backend so it
     reads the key. Nothing else needs a restart.
3. Check that `GET /api/v1/admin/system/status` shows `"chart_analysis": {"enabled": true,
   "model": "gemini-3.6-flash", …}`. While it shows `"enabled": false`,
   `"disabled_reason": "GEMINI_API_KEY is not set"`, the feature is off, which is not an error.
4. Smoke test as any user: `GET /api/v1/analysis/chart-image/quota` returns 200. Then one
   `POST` with a chart screenshot returns `status: ok`.

**To rotate the key:** the deploy never overwrites a value, so either edit `GEMINI_API_KEY=`
in `/opt/trading/.env` by hand and recreate the backend, or empty it and run Deploy with the
new secret. **To turn the feature off without removing the key:** set
`CHART_ANALYSIS_ENABLED=false` and recreate the backend.
