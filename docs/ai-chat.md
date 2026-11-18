# AI assistant chat

A text assistant in the apps that answers questions about the markets on the platform, using
Gemini (the same `GEMINI_API_KEY` as chart analysis). Code: `backend/app/assistant/chat.py`,
prompt `backend/app/assistant/prompts/assistant_v1.md`, routes `backend/app/api/v1/ai_chat.py`.
Tests: `backend/tests/test_ai_chat.py` (Gemini is never called in tests).

It is educational, **not financial advice**: every answer carries a disclaimer added by the
backend, and the prompt tells the model it is not a financial adviser.

## How it works

1. **Stateless.** The app sends the whole conversation with every question (1–20 turns of
   `{role: user|assistant, content ≤ 2000 chars}`, the last one from the user). Nothing of the
   conversation is stored on the server; only a log line with the token usage.
2. **Market context.** At each question the backend builds a text block from its own database
   and sends it before the conversation, so the model never has to invent numbers:
   - the instrument (`instrument_id` in the request, else the gold feed instrument): latest
     price and 24 h change;
   - news sentiment and the 5 latest headlines;
   - high-impact USD economic events in the next 48 h.
   Each part is optional; a part that fails is left out.
3. **Model.** `AI_CHAT_MODEL` (empty: the chart-analysis model), timeout
   `AI_CHAT_TIMEOUT_SECONDS` (40), at most `AI_CHAT_MAX_OUTPUT_TOKENS` (1200), one retry.
4. **Language.** `language: ar|en`; default is the user's notification language.

## Quota

Per user per UTC day in Redis: `AI_CHAT_DAILY_LIMIT_TRADER/ANALYST/EXPERT/ADMIN`
(30/100/100/300). Used up: 429 `quota_exceeded` with `Retry-After` = seconds to 00:00 UTC.
A call that fails on the model side (5xx, `blocked`) gives its unit back. The rate-limit cost of
a call is `AI_CHAT_COST` (3).

## Endpoints

| Method | Path | |
|---|---|---|
| POST | `/api/v1/ai/chat` | `{messages, language?, instrument_id?}` → `{reply, language, model, usage, quota, disclaimer}` |
| GET | `/api/v1/ai/chat/quota` | `{limit, used, remaining, resets_at}` |

## Errors (`detail.code`)

| Status | Code | |
|---|---|---|
| 503 | `not_configured` | no `GEMINI_API_KEY`, or `AI_CHAT_ENABLED=false` |
| 503 | `model_busy`, `model_unavailable`, `timeout` | with `Retry-After` |
| 422 | `blocked`, `empty_answer`, `could_not_answer` | the model gave no usable answer |
| 429 | `quota_exceeded` | with `Retry-After` |
| 404 | | unknown `instrument_id` |
