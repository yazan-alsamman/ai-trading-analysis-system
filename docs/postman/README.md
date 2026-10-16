# Postman collection

The whole REST API in one Postman collection: **every endpoint**, each with a saved example
response (captured from a real run) plus its main error cases, tests on every request, and
automatic login/refresh.

| File | |
|---|---|
| `AI-Trading-Platform.postman_collection.json` | The collection (Postman v2.1) |
| `environments/Production.postman_environment.json` | The VPS: `http://187.127.76.76:8080` |
| `environments/Local.postman_environment.json` | Docker Compose: `http://localhost` (use `http://localhost:8000` for a bare uvicorn) |
| `tools/` | Generator: `spec.py` (the requests), `capture_examples.py`, `build_collection.py` |

## Use it

1. Postman → **Import** → the collection and both environments.
2. Select an environment and fill in `user_email` / `user_password` (and `admin_email` /
   `admin_password` for the Admin folder). Secrets stay in your local Postman: never commit
   filled-in environments.
3. Send any request. The collection's pre-request script logs in, caches the access token
   until it expires and refreshes it with the refresh token; `/admin/*` requests use a separate
   admin token.

No account? Send **Auth → Register**: with `user_email` empty, the new account becomes the
collection's user. Some requests (sharing a workspace, publishing a strategy) need the analyst
role; for a trader they answer 403 and the runner skips what depends on them.

### بالعربي

استورد ملف الـ collection وملفّي الـ environments، اختر بيئة (السيرفر أو المحلي) واكتب بريدك
وكلمة المرور فقط؛ التوكن يُجلب ويُجدَّد تلقائياً. كل request فيه مثال response حقيقي وأمثلة
للأخطاء المهمة، ويمكن تشغيل الـ collection كاملة بالترتيب من الـ Runner.

## Structure

```
01 · Health                 07 · Risk Management        13 · Community
02 · Auth                   08 · Custom Strategies      14 · Price Alerts
03 · Users (me)             09 · Backtests              15 · Notifications
04 · Market Data            10 · Workspaces             16 · Admin
05 · Indicators             11 · API Keys                    Users · Market Data
06 · Strategies & Signals        Using an API key            API Keys & Rate Limits
                            12 · News                        News & Moderation · Notifications
                                                        17 · Realtime (WebSocket)
```

Folders are ordered for the **Collection Runner** / Newman: each folder creates what it needs,
uses it and deletes it again, and ids flow between requests through environment variables
(`instrument_id`, `workspace_id`, `backtest_id`, …). A 429 is waited out (`Retry-After`) and the
request is sent again. Postman v2.1 files cannot hold WebSocket requests, so folder 17 documents
`/ws/market` (URL, messages, close codes) for a **New → WebSocket** tab.

```bash
npx newman run docs/postman/AI-Trading-Platform.postman_collection.json \
  -e docs/postman/environments/Local.postman_environment.json \
  --env-var user_email=you@example.com --env-var user_password='...' \
  --env-var admin_email=admin@example.com --env-var admin_password='...'
```

On production, Register, Admin and the create requests write real data: prefer Local for full
runs.

## Updating after an API change

The JSON files are generated; edit `tools/spec.py`, never the collection by hand.

1. Add a `Req` for each new endpoint to `tools/spec.py` (in the folder where it belongs, in
   run order), with a realistic body, `captures` for ids that later requests need and
   `variants` for the important errors.
2. `cd backend && python ../docs/postman/tools/build_collection.py --check` lists every API
   route missing from `spec.py` (and stale ones).
3. Start a local stack with demo data (`seed-instruments`, `seed-demo-candles`, a Celery
   worker for backtests) and run
   `python docs/postman/tools/capture_examples.py --admin-email … --admin-password …`
   to refresh `tools/examples.json`.
4. `python docs/postman/tools/build_collection.py` writes the collection and environments;
   run Newman as above before committing.
