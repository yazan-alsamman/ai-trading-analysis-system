# منصة التداول الذكية

مشروع تخرج. مستودع واحد (Monorepo) يضم كل أجزاء المنصة.

| المجلد | المحتوى | المسؤول |
|---|---|---|
| `backend/` | FastAPI + Celery + PostgreSQL/TimescaleDB + Redis | Yazan |
| `ai-service/` | خدمة الذكاء (FastAPI) والنماذج والـ notebooks | Fadi |
| `web/` | لوحة الويب React + TS | Elias |
| `mobile/` | تطبيق Flutter | Batoul |
| `infra/` | إعدادات Nginx والنشر | Yazan |
| `libs/indicators/` | مكتبة المؤشرات الفنية المشتركة (`trading-indicators`) للـ backend والاستراتيجيات وفريق الذكاء | Yazan |
| `libs/strategies/` | الاستراتيجيات العامة (`trading-strategies`، نمط Strategy) | Yazan |
| `libs/backtest/` | محرك الاختبار التاريخي (`trading-backtest`) | Yazan |

## النشر

المنصة منشورة على http://187.127.76.76:8080/docs ، وكل دمج إلى `main` ينشر تلقائياً بعد نجاح CI. التفاصيل وقواعد السيرفر المشترك في [docs/deployment.md](docs/deployment.md).

## التشغيل محلياً

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000/docs
- فحص الجاهزية: http://localhost:8000/api/v1/health/ready
- خدمة الذكاء: http://localhost:8001/docs
- عبر Nginx: http://localhost/api/v1/health

إذا كان المنفذ 5432 أو 6379 مستخدماً على جهازك، غيّر `POSTGRES_PORT` / `REDIS_PORT` في `.env`.

## التطوير بدون Docker (backend)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ../libs/indicators -e ../libs/strategies -e ../libs/backtest   # المكتبات المحلية أولاً (pip لا يدعم مسارات نسبية في pyproject)
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

صورة Docker للـ backend والـ worker تُبنى من جذر المستودع (`context: .`) حتى تثبّت `libs/indicators`؛
الملفات المرسلة للبناء محددة في `backend/Dockerfile.dockerignore`.

### الاختبارات

الاختبارات تعمل على PostgreSQL/TimescaleDB حقيقية (وليس SQLite). تُنشأ قاعدة `trading_test`
تلقائياً وتُطبَّق عليها الـ migrations، وكل اختبار يعمل داخل transaction يُلغى في النهاية.

```bash
docker compose up -d db redis
cd backend
# الافتراضي: postgresql+asyncpg://trading:trading@localhost:5432/trading_test
export TEST_DATABASE_URL=postgresql+asyncpg://trading:trading@localhost:5432/trading_test
pytest -q
```

## المصادقة والأدوار (JWT + RBAC)

- الأدوار: `trader` (الافتراضي عند التسجيل)، `analyst`، `expert`، `admin`.
  الأدوار غير هرمية، إلا أن `admin` يمر من كل الصلاحيات.
- `POST /api/v1/auth/register` ثم `POST /api/v1/auth/login` يعيد `access_token` (30 دقيقة)
  و `refresh_token` (14 يوماً). أرسل الأول في الترويسة `Authorization: Bearer <token>`.
- `POST /api/v1/auth/refresh` يبدّل الـ refresh token بزوج جديد (rotation). إعادة استخدام
  refresh token ملغى تُلغي كل جلسات المستخدم.
- في `/docs` استخدم زر **Authorize** (البريد في خانة username).
- حماية endpoint بدور معيّن: `Depends(require_roles(UserRole.analyst, UserRole.expert))`
  من `app.api.deps`.

### إنشاء أول مدير

إما عبر الأمر (يُنشئ المدير، أو يرقّي المستخدم الموجود إلى admin دون تغيير كلمة مروره):

```bash
cd backend
python -m app.cli create-admin --email admin@example.com --password 'Admin12345'
# داخل Docker:
docker compose exec backend python -m app.cli create-admin --email admin@example.com --password 'Admin12345'
```

أو بضبط `FIRST_ADMIN_EMAIL` و `FIRST_ADMIN_PASSWORD` في `.env`: عند الإقلاع، إذا لم يوجد أي
مدير، يُنشأ هذا الحساب كمدير.

في الإنتاج (`ENVIRONMENT=production`) يرفض الخادم الإقلاع إذا كان `JWT_SECRET` هو `change-me`
أو أقصر من 32 حرفاً.

## بيانات السوق (الشموع)

- مصدر الحقيقة الوحيد هو شموع الدقيقة في الجدول `candles_1m` (TimescaleDB hypertable).
  الأطر الأعلى `5m, 15m, 1h, 4h, 1d` هي continuous aggregates هرمية
  (`5m ← 1m`, `15m ← 5m`, `1h ← 15m`, `4h ← 1h`, `1d ← 1h`) مع real-time aggregation،
  لذلك تظهر الشمعة التي ما زالت تتشكّل فوراً. **لا تكتب أبداً في الأطر الأعلى.**
- كل الأوقات UTC، و `ts` هو بداية الشمعة ويجب أن يكون على رأس الدقيقة.
- القراءة (أي مستخدم مسجّل):
  `GET /api/v1/market/instruments/{id}/candles?timeframe=1h&start=...&end=...&limit=500`
  يعيد `{instrument_id, timeframe, candles: [{time, open, high, low, close, volume}]}`
  حيث `time` بالثواني (unix) مناسب مباشرة لـ Lightweight Charts. بدون `start` يعيد آخر `limit` شمعة.
- الكتابة (admin، للـ backfill): `POST /api/v1/admin/instruments/{id}/candles` بجسم
  `{"candles": [{"ts": "...Z" أو unix seconds, "open", "high", "low", "close", "volume", "trades"?}]}`
  (حتى 5000 شمعة 1m في الطلب، upsert). الـ collectors داخل الخادم تستدعي
  `market_service.upsert_candles()` مباشرة.
- سياسات التحديث تعيد حساب نافذة حديثة فقط (أقدمها لـ `5m`: آخر ساعتين). عند كتابة بيانات أقدم من ساعة
  عبر الـ API أو أمر الـ seed يُحدَّث الـ aggregates تلقائياً للأيام المتأثرة؛ إن كتبت بيانات قديمة
  بطريقة أخرى فاستدعِ `market_service.refresh_aggregates(start, end)` بعد الـ commit.

```bash
cd backend
python -m app.cli seed-instruments                       # 5 أزواج Binance + 4 من Twelve Data
python -m app.cli seed-demo-candles --symbol BTC/USDT --source binance --days 30
# داخل Docker:
docker compose exec backend python -m app.cli seed-instruments
docker compose exec backend python -m app.cli seed-demo-candles --symbol BTC/USDT --source binance --days 30
```

`seed-demo-candles` يولّد **بيانات وهمية** (random walk) لتطوير الرسوم البيانية فقط، وليست أسعاراً حقيقية.

## المؤشرات الفنية

مكتبة مستقلة في [libs/indicators](libs/indicators/README.md) (numpy + pandas فقط، بدون look-ahead،
مطابقة لـ TA-Lib حتى `1e-8`). للـ notebooks في Colab/Kaggle:

```bash
pip install "git+https://github.com/yazan-alsamman/ai-trading-analysis-system@main#subdirectory=libs/indicators"
```

في الـ API: `GET /api/v1/indicators` (الكتالوج) و `POST /api/v1/market/instruments/{id}/indicators`
بجسم `{"timeframe": "1h", "limit": 500, "indicators": [{"name": "rsi", "params": {"length": 14}}, {"name": "macd"}]}`
يعيد لكل output نقاط `{time, value}` جاهزة لـ Lightweight Charts، مع تحميل تاريخ الإحماء تلقائياً.

## الاستراتيجيات والإشارات الحية

ست استراتيجيات عامة في [libs/strategies](libs/strategies/README.md): `ma_crossover`, `rsi_reversal`,
`macd_cross`, `bollinger_reversion`, `supertrend_flip`, `donchian_breakout`. الإشارة حدث على شمعة
**مغلقة** (بدون look-ahead) وتُنفَّذ عند افتتاح الشمعة التالية.

- `GET /api/v1/strategies` الكتالوج، و `POST /api/v1/strategies/{key}/preview` لتجربة استراتيجية على
  التاريخ (إشارات + markers لـ Lightweight Charts + خطوط المؤشرات).
- `POST /api/v1/me/strategies` لتفعيل استراتيجية على سوق وإطار زمني (حتى 20 لكل مستخدم)،
  و `GET /api/v1/signals` للإشارات (`mine=true` لإشارات استراتيجياتي فقط).
- المحرك الحي: خدمة `beat` في docker compose تشغّل `signals.tick` كل دقيقة؛ الـ worker يقيّم كل
  (سوق، إطار) أُغلقت شمعته مرة واحدة لكل إعداد مميز مهما كان عدد المستخدمين، يخزّن الإشارة
  (idempotent) وينشرها على `signals:{instrument_id}` وعلى `user:{id}` لمن فعّل `notify`.

## مفاتيح API وتحديد المعدل

للبرامج الخارجية (بوتات، Colab): أنشئ مفتاحاً عبر `POST /api/v1/me/api-keys` (بـ JWT) وأرسله في
الترويسة `X-API-Key: tk_...`. للمفتاح صلاحيات محددة (`market:read`, `indicators:read`,
`strategies:read`, `signals:read`, `stream`) ولا يصل أبداً إلى `/auth/*` أو `/users/me` أو `/me/*`
أو `/admin/*`. كل طلبات `/api/v1` (عدا `/health`) محدودة في الدقيقة: trader 60، analyst/expert 300،
admin 1000، مع ترويسات `RateLimit-*` و 429 + `Retry-After` عند التجاوز. الدليل الكامل بالإنجليزية
مع أمثلة curl و Python في [docs/api-keys.md](docs/api-keys.md).

## اختبار الاستراتيجيات تاريخياً (Backtesting)

حزمة [libs/backtest](libs/backtest/README.md) تشغّل أي استراتيجية (أو إطار إشارات جاهز) على
بيانات تاريخية: التنفيذ عند افتتاح الشمعة التالية (بدون look-ahead)، رسوم وانزلاق على كل صفقة،
long_only / long_short، وقف خسارة وجني أرباح وحد أقصى لمدة الصفقة، ومقاييس كاملة (العائد، CAGR،
أقصى تراجع، Sharpe، Sortino، Calmar، نسبة الربح، profit factor، مقارنة بالشراء والاحتفاظ).
في الـ API: `POST /api/v1/backtests` يضع الاختبار في طابور Celery مستقل (`worker-backtest`)
ويصل التقدم عبر WebSocket؛ النتائج والصفقات وCSV والمقارنة في [docs/backtesting.md](docs/backtesting.md).

## الاستراتيجيات المخصصة (Builder + Composite)

يبني المستخدم استراتيجيته دون كتابة كود: **Builder** (شروط على المؤشرات والأسعار مجمّعة بـ AND/OR
في مستند JSON) أو **Composite** (2–5 استراتيجيات عامة أو مخصصة تصوّت معاً: all / any / majority /
weighted). المفتاح `custom:<uuid>` يعمل في كل مكان يعمل فيه مفتاح عام: المعاينة، الـ backtests
(مع لقطة من التعريف في `config.strategy`)، `/me/strategies` ومحرك الإشارات الحي. واجهات
`/api/v1/me/custom-strategies` و `/api/v1/custom-strategies/{schema,validate,public}`؛ الدليل الكامل
بالإنجليزية (للمحررات في الويب والموبايل) في [docs/custom-strategies.md](docs/custom-strategies.md).

## مساحات العمل (Workspaces)

كل مستخدم يحفظ شاشات تداول متعددة (تبويبات): التخطيط، الرسوم، الأدوات والإطارات الزمنية،
المؤشرات، الاستراتيجيات، الرسومات وقائمة المراقبة، في مستند JSON واحد مُتحقَّق منه عبر
`/api/v1/me/workspaces`. التعديل من جهازين محمي بـ `version` (409 عند التعارض) وكل تغيير يصل إلى
الأجهزة الأخرى عبر رسالة `workspace_updated` على قناة المستخدم. الدليل الكامل للواجهات (Web و Flutter)
في [docs/workspaces.md](docs/workspaces.md) و JSON Schema في
[docs/workspace-state.schema.json](docs/workspace-state.schema.json).

## التحديثات الحية (WebSocket)

`ws://<host>/ws/market?token=<access JWT>`: اشترك في `candles` لأي instrument وأي إطار زمني
فتصلك الشمعة الحالية فور تغيّرها (Redis Pub/Sub، يعمل مع عدة workers). البروتوكول الكامل ومثال
JavaScript مع Lightweight Charts في [docs/websocket.md](docs/websocket.md).

لتطوير الرسوم الحية قبل وجود الـ collectors:

```bash
docker compose exec backend python -m app.cli simulate-live --symbol BTC/USDT --source binance --interval 2
```

الاختبارات تحتاج Redis أيضاً: `TEST_REDIS_URL` (الافتراضي `REDIS_URL` ثم `redis://localhost:6379/0`).

قواعد الفروع والـ PR في [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).
