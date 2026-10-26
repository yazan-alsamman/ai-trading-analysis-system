# النشر على السيرفر (CI/CD)

المنصة منشورة على VPS من Hostinger (Ubuntu 24.04، 2 vCPU، 8GB). **السيرفر يستضيف مشاريع أخرى حيّة يستخدمها الناس**، لذلك كل ما يخص مشروعنا معزول تماماً.

## الروابط
| | |
|---|---|
| موقع الويب | http://187.127.76.76:8080/ |
| API | `http://187.127.76.76:8080/api/v1/...` |
| التوثيق (Swagger) | http://187.127.76.76:8080/docs (مطفأ افتراضياً، انظر «تشغيل /docs يوم العرض») |
| الجاهزية | http://187.127.76.76:8080/api/v1/health/ready |
| جودة البيانات | http://187.127.76.76:8080/api/v1/health/data (503 إذا كانت أداة `degraded` أو `no_data`؛ لا يؤثر على النشر، انظر [data-quality.md](data-quality.md)) |
| التقويم الاقتصادي | `GET /api/v1/calendar/events` (بتسجيل دخول)، والاستيراد التاريخي `POST /api/v1/admin/calendar/import`، انظر [economic-calendar.md](economic-calendar.md) |
| WebSocket | `ws://187.127.76.76:8080/ws/market` |
| HTTPS (بعد خطوات [https.md](https.md)) | `https://trading.yazanalsamman.com` و `wss://trading.yazanalsamman.com/ws/market` عبر nginx السيرفر إلى `127.0.0.1:8090` |

لا يوجد دومين حالياً، ولذلك لا يوجد HTTPS. عند إضافة دومين نضع أمامه موقع nginx للسيرفر مع certbot.

## كيف يعمل
1. كل PR يشغّل CI (`.github/workflows/ci.yml`)، ولا يتم الدمج إلا وهو أخضر.
2. بعد الدمج إلى `main` ونجاح CI عليه، يعمل `Deploy` (`.github/workflows/deploy.yml`) تلقائياً:
   - يبني صور `ai-trading-backend` و`ai-trading-ai-service` و`ai-trading-web` (nginx مع موقع الويب المبني من `web/`) ويرفعها إلى GHCR بوسم هو أول 12 حرفاً من الـ commit.
   - يتصل بالسيرفر عبر SSH بالمستخدم `deploy-trading`، وينسخ ملفات الـ stack إلى `/opt/trading`، ثم يشغّل `infra/deploy/remote-deploy.sh`.
   - السكربت يسحب الصور ويشغّل الـ stack. الـ backend يطبّق `alembic upgrade head` عند الإقلاع، والـ workers لا تبدأ إلا بعد أن يصبح الـ backend سليماً.
   - إذا فشل فحص `/api/v1/health/ready` يعود السكربت تلقائياً إلى الوسم السابق ويفشل الـ workflow.
3. لإعادة النشر يدوياً: Actions ← Deploy ← Run workflow.
4. لفحص حالة السيرفر للقراءة فقط: Actions ← Server inspect ← Run workflow.
5. نسخة احتياطية مشفّرة خارج السيرفر يومياً: Actions ← Off-site backup (انظر «النسخ خارج السيرفر»).

## قواعد السيرفر المشترك (لا تُكسر)
- لا نلمس أي حاوية أو شبكة أو volume أو موقع nginx لا يخص مشروع Compose المسمى `trading`.
- ممنوع `docker system prune` و`docker image prune` العام، وممنوع إعادة تشغيل Docker أو السيرفر، وممنوع `apt upgrade`.
- المنفذ العام الوحيد لمشروعنا هو `8080` (حاوية nginx). قاعدة البيانات مربوطة على `127.0.0.1:5435` فقط، وRedis والـ backend بلا منافذ على المضيف.
- الشبكة المستخدمة `172.30.57.0/24`: العناوين الديناميكية من `172.30.57.128/25` فقط (`DOCKER_IP_RANGE`)، وعنوان Nginx
  الثابت `172.30.57.10` خارجها. منافذ المشاريع الأخرى المحجوزة هي 80، 443، 3000-3005، 5000، 5432-5434، 6380، 9000، 9001، 27017.
- لكل حاوية حد للذاكرة والمعالج، ومجموع حدود الذاكرة 3424MiB (≈3.34GiB، نحو 43% من 7.8GB على السيرفر المشترك بلا swap) بعد إضافة `feed-ctrader` (128m، 0.25 CPU، B1)، وسجلات Docker محدودة بـ 30MB لكل حاوية.
- `cpus:` سقف وليس حجزاً (مجموع سقوفنا 6.5 على سيرفر بـ 2 vCPU)، لذلك لكل خدماتنا `cpu_shares: 512` (الافتراضي 1024):
  عند انشغال السيرفر تأخذ المشاريع الأخرى ضعف وزننا من المعالج، وعندما يكون هادئاً نستطيع استخدام سقوفنا.

## على السيرفر
```
/opt/trading/
  docker-compose.yml   # نسخة من infra/deploy/docker-compose.prod.yml
  .env                 # يُولَّد مرة واحدة بأسرار عشوائية (600)، والإعدادات الجديدة في .env.example تُضاف إليه تلقائياً
  image.env            # IMAGE_TAG الحالي
  nginx/default.conf   # نسخة من infra/nginx/default.conf
  backups/             # pg_dump يومي الساعة 03:17، ويُحتفظ به 7 أيام
```
أوامر مفيدة (بعد `ssh -i ~/.ssh/trading_deploy deploy-trading@187.127.76.76`):
```bash
cd /opt/trading
alias dc='docker compose -f docker-compose.yml --env-file .env --env-file image.env'
dc ps
dc logs -f --tail 100 backend
dc exec backend python -m app.cli create-admin --email you@example.com --password '...'
dc exec backend python -m app.cli seed-instruments
```
للوصول إلى قاعدة البيانات من جهازك عبر نفق SSH:
```bash
ssh -i ~/.ssh/trading_deploy -L 5435:127.0.0.1:5435 deploy-trading@187.127.76.76
# ثم اتصل بـ localhost:5435، واسم المستخدم وكلمة السر موجودان في /opt/trading/.env
```

## الإشعارات (Y15)
- خدمة جديدة **`telegram-bot`** (نفس صورة الـ backend، 128MB، بلا منفذ): تستقبل أوامر تيليغرام
  بالـ long polling. إذا كان `TELEGRAM_BOT_TOKEN` فارغاً تبقى خاملة (لا تخرج، حتى لا يفشل
  `up --wait`).
- الـ `worker` يستهلك الآن الطابورين `celery,notifications`، ولم نضف worker جديداً.
- القنوات معطّلة طالما إعداداتها فارغة، والتطبيق يعمل عادياً. لتفعيلها أضف القيم في
  `/opt/trading/.env` ثم أعد النشر (Actions ← Deploy ← Run workflow):

| القناة | المتغيرات |
|---|---|
| تيليغرام | `TELEGRAM_BOT_TOKEN` (من @BotFather)، اختياري `TELEGRAM_BOT_USERNAME`، `TELEGRAM_MODE=polling` |
| البريد | `SMTP_HOST`، `SMTP_PORT=587`، `SMTP_USER`، `SMTP_PASSWORD`، `SMTP_FROM`، `SMTP_STARTTLS=true` |
| Push | `FCM_PROJECT_ID`، `FCM_CREDENTIALS_JSON` (ملف service account كـ JSON في سطر واحد، أو مسار ملف داخل الحاوية) |

- فحص بعد النشر (من أي جهاز، بتوكن مستخدم):
  ```bash
  curl -s http://187.127.76.76:8080/api/v1/health/ready
  curl -s -H "Authorization: Bearer $TOKEN" http://187.127.76.76:8080/api/v1/me/notifications/channels
  curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
       -d '{"channel":"in_app"}' http://187.127.76.76:8080/api/v1/me/notifications/test
  curl -s -H "Authorization: Bearer $TOKEN" http://187.127.76.76:8080/api/v1/me/notifications/unread-count
  ```

## الأخبار والمنشورات وتنبيهات الأسعار (Y18)
- لا خدمات جديدة. الـ `worker` الحالي ينفّذ جلب RSS (`news.fetch` كل 5 دقائق) وتقييم تنبيهات
  الأسعار (`alerts.evaluate` كل دقيقة)، والـ `beat` يجدولهما.
- Migration `0011` إضافية فقط: جداول جديدة، وقيم جديدة لـ `notification_type` عبر
  `ALTER TYPE ... ADD VALUE IF NOT EXISTS` خارج المعاملة (autocommit). عند الرجوع تبقى القيم.
- متغيرات جديدة (كلها لها قيم افتراضية آمنة، تُضاف تلقائياً إلى `.env` على السيرفر):
  `NEWS_RSS_ENABLED=true`، `NEWS_FETCH_TIMEOUT_SECONDS=10`، `NEWS_FETCH_MAX_BYTES=2097152`،
  `NEWS_RETENTION_DAYS=180`، `POST_ROLES=analyst,expert,admin`، `POST_EDIT_WINDOW_HOURS=24`،
  `POSTS_PER_DAY=10`، `COMMENTS_PER_HOUR=60`، `REPORTS_PER_DAY=20`، `CONTENT_CREATE_COST=2`،
  `PRICE_ALERT_LIMIT_TRADER=20`، `PRICE_ALERT_LIMIT_ANALYST=100`،
  `PRICE_ALERT_LIMIT_EXPERT=100`، `PRICE_ALERT_LIMIT_ADMIN=100`.
- لإيقاف جلب RSS: `NEWS_RSS_ENABLED=false` ثم إعادة النشر، أو تعطيل مصدر واحد من
  `PATCH /api/v1/admin/news/sources/{id}`.
- مفتاح `news:write` لفادي يُنشئه حساب مدير (`POST /api/v1/me/api-keys`).
- فحص بعد النشر:
  ```bash
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/news?limit=3"
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/news/sources"
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/news/sentiment?window=24h"
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/posts?limit=5"
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/me/price-alerts"
  ```

## الخبراء والاشتراكات والمحادثة (Y19)
- لا خدمات جديدة. التجديدات الشهرية/السنوية تنفّذها مهمة `subscriptions.renew` كل 10 دقائق (طابور `maintenance`).
- الدفع **تجريبي فقط** (`PAYMENT_PROVIDER=demo`): لا أموال حقيقية ولا مفاتيح مزوّد. صفحة الدفع التجريبية
  على `/api/v1/pay/demo/{checkout_id}`، وتقبل البطاقات التجريبية فقط.
- Migration `0012` إضافية فقط، وقيم enum الجديدة (`notification_type`، `post_visibility=subscribers`،
  `report_target=message`) تُضاف خارج المعاملة كما في 0011.
- متغيرات جديدة (قيم افتراضية آمنة، تُضاف تلقائياً إلى `.env`): `PAYMENT_PROVIDER=demo`،
  `PAYMENT_DEMO_WEBHOOK_SECRET=` (فارغ = سرّ يُولَّد ويُحفظ في Redis)، `PAYMENT_DEMO_TOOLS=false`،
  `PAYMENT_RETURN_URL=`، `PUBLIC_BASE_URL=`، `PLATFORM_FEE_PCT=20`، `SUBSCRIPTION_GRACE_DAYS=3`،
  `CHECKOUT_TTL_MINUTES=30`، `CHAT_MESSAGES_PER_MINUTE=30`، `CHAT_MESSAGES_PER_DAY=2000`،
  `CHAT_EDIT_WINDOW_MINUTES=15`، `CHAT_NOTIFY_COLLAPSE_MINUTES=5`.
- روابط الدفع مطلقة تلقائياً (Nginx يمرّر `Host` مع المنفذ :8080)؛ `PUBLIC_BASE_URL` اختياري لفرض عنوان آخر. و
  `PAYMENT_DEMO_TOOLS=true` لعرض أداة تقديم الوقت (fast-forward) في العروض التقديمية.
- فحص بعد النشر:
  ```bash
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/experts"
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/conversations"
  # checkout تجريبي (بحساب متداول وخطة موجودة) ثم فتح صفحة الدفع التجريبية:
  curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json'        -d '{"plan_id":"<plan id>"}' http://187.127.76.76:8080/api/v1/subscriptions/checkout
  curl -s "http://187.127.76.76:8080/api/v1/pay/demo/<checkout_id>" | grep -o '<title>[^<]*'
  ```

## التقويم الاقتصادي (B6)
- لا خدمات جديدة ولا أسرار. الـ `worker` ينفّذ `calendar.refresh` (يفحصه الـ `beat` كل 15 دقيقة،
  ويرسل طلباً واحداً فقط إلى ForexFactory كل 4 ساعات على الأكثر، ولا شيء لمدة 6 ساعات بعد 429/403).
- Migration `0014` تنشئ جدول `economic_events` وفهارسه فقط، ولا تلمس أي جدول آخر.
- متغيرات جديدة بقيم افتراضية آمنة: `CALENDAR_ENABLED=true`، `CALENDAR_FF_URL`،
  `CALENDAR_FETCH_INTERVAL_MINUTES=240`، `CALENDAR_FETCH_TIMEOUT_SECONDS=15`،
  `CALENDAR_FETCH_MAX_BYTES=2097152`، `CALENDAR_BACKOFF_HOURS=6`، `CALENDAR_CURRENCIES=USD`.
- Nginx يقبل حتى 51MB على مسار الاستيراد وحده (`/api/v1/admin/calendar/import`).
- البيانات التاريخية (Kaggle) لا تُرفع إلى المستودع أبداً: يرفعها المدير بنفسه عبر
  `POST /api/v1/admin/calendar/import` (الخطوات في [economic-calendar.md](economic-calendar.md)).
- فحص بعد النشر:
  ```bash
  curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" http://187.127.76.76:8080/api/v1/admin/calendar/refresh
  curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://187.127.76.76:8080/api/v1/admin/system/status | python3 -c 'import sys,json;print(json.load(sys.stdin)["calendar"])'
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/calendar/events?min_impact=medium"
  ```

## عقد ai-service وجداول الذكاء الاصطناعي (B7 + B8)
- لا خدمات جديدة ولا أسرار، ولا شيء يستدعي ai-service بشكل مجدول بعد (هذا B9). العقد مسودة حتى يوافق فادي:
  [ai-contract.md](ai-contract.md).
- Migration `0015` تنشئ خمسة جداول جديدة فقط (`ai_setups`، `ai_setup_events`، `ai_model_versions`،
  `ai_setup_sizes`، `ai_setup_explanations`) ولا تلمس أي جدول آخر.
- متغيرات جديدة بقيم افتراضية آمنة: `AI_EVALUATE_TIMEOUT_SECONDS=10`، `AI_SIZE_TIMEOUT_SECONDS=5`،
  `AI_EXPLAIN_TIMEOUT_SECONDS=30`، `AI_MAX_RETRIES=2`، `AI_BARS_15M=500`، `AI_BARS_1H=500`، `AI_BARS_4H=300`.
- حد ذاكرة `ai-service` من 256m إلى **512m** (بموافقة يزن)، والمعالج كما هو (0.5). مجموع حدود ذاكرة مشروعنا
  من 3040MiB إلى **3296MiB** (≈3.22GiB)، أي نحو 41% من 7.8GB على سيرفر مشترك بلا swap: db 768،
  redis 192، backend 544، worker 384، worker-backtest 512، beat 192، telegram-bot 128، ai-service 512،
  nginx 64. هذه سقوف وليست استهلاكاً فعلياً.
- فحص بعد النشر (حساب مدير):
  ```bash
  curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://187.127.76.76:8080/api/v1/admin/ai/models
  curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://187.127.76.76:8080/api/v1/admin/ai/setups?limit=5"
  ```

## إعدادات مخاطرة AI والصفقات المأخوذة (B10)
- لا خدمات جديدة ولا أسرار. Migration `0016` إضافية: `risk_profiles.leverage` (افتراضي 100 لكل الملفات الموجودة)
  و`risk_profiles.balance_set_at` (فارغ)، و`source` و`computed_at` في `ai_setup_sizes`، وجدول جديد `ai_setup_takes`.
- متغيرات جديدة بقيم افتراضية آمنة: `AI_SIZE_MODE=auto`، `AI_SIZE_CONCURRENCY=4`، `AI_DEFAULT_RISK_PCT=1.0`،
  `AI_DEFAULT_DAILY_LOSS_PCT=3.0`، `AI_DEFAULT_MAX_DRAWDOWN_PCT=10.0`. التفاصيل في
  [risk-management.md](risk-management.md#ai-setups-b10).
- لا توجد إعدادات AI في الإنتاج بعد، لذلك `/ai/setups/{id}/size` و`/take` تعيد 404 وهذا متوقع.
- فحص بعد النشر:
  ```bash
  curl -s -H "Authorization: Bearer $TOKEN" http://187.127.76.76:8080/api/v1/me/risk-profile   # leverage 100 و ai_risk
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" http://187.127.76.76:8080/api/v1/ai/setups/x/size  # 404
  curl -s -H "Authorization: Bearer $TOKEN" http://187.127.76.76:8080/api/v1/me/ai/trades   # {"items":[],"total":0,...}
  ```

## تنبيهات إعدادات AI والإشعارات العالقة (B11)
- لا خدمات جديدة ولا أسرار. Migration `0017` إضافية: قيمة `ai_setup` لنوع الإشعار، وجدولا `ai_setup_outbox` و`ai_alert_follows`،
  وعمود `next_attempt_at` (فارغ للصفوف الموجودة) وفهرس جزئي على `notification_deliveries`.
- مهمتان جديدتان على طابور `notifications` (خدمة `worker`): `ai_alerts.dispatch` كل 30 ثانية (استعلام مفهرس واحد حين لا يوجد شيء)،
  و`notifications.sweep` كل دقيقة (يعيد إرسال الإشعارات التي ضاعت مهمة إرسالها، ويعلّم ما هو أقدم من يوم `skipped` بدل
  إرساله، ويكتب سطراً واحداً `requeued=N expired=M`).
- متغيرات جديدة بقيم افتراضية آمنة: `AI_ALERTS_ENABLED=true`، `AI_ALERTS_BATCH=50`، `AI_ALERTS_MAX_ATTEMPTS=8`،
  `AI_ALERTS_MAX_AGE_SECONDS=900`، `AI_EXPLAIN_LANGS=ar,en`، `NOTIFICATION_SWEEP_AFTER_SECONDS=120`، `NOTIFICATION_SWEEP_BATCH=500`، `NOTIFICATION_SWEEP_MAX_AGE_SECONDS=86400`.
  التفاصيل في [notifications.md](notifications.md#ai-setup-alerts-b11).
- فحص بعد النشر (حساب مدير):
  ```bash
  curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://187.127.76.76:8080/api/v1/admin/ai/outbox"   # total 0
  curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://187.127.76.76:8080/api/v1/admin/system/status | python3 -c 'import sys,json;print(json.load(sys.stdin)["ai_alerts"])'
  curl -s -H "Authorization: Bearer $TOKEN" http://187.127.76.76:8080/api/v1/me/ai/follows   # []
  ```

## HTTPS على trading.yazanalsamman.com
- حاوية nginx الخاصة بنا تستمع أيضاً على المنفذ 8090، منشوراً على `127.0.0.1:8090` فقط، و8080 لم يتغير. موقع واحد
  جديد في nginx السيرفر يمرّر `https://trading.yazanalsamman.com` إليه.
- القالب في `infra/host-nginx/`. النشر ينسخه إلى `/opt/trading/host-nginx/` ولا يطبّقه: الخطوات يدوية (root) في
  [https.md](https.md).
- النشر يفحص 8090 فحصاً إضافياً لا يُفشل النشر، فيكتب `Port 8090 (HTTPS proxy entry): ok` أو تحذيراً.
- `CORS_ORIGINS` و`PUBLIC_BASE_URL` تُضبط يدوياً بعد نجاح HTTPS (https.md، الخطوة 8)، ولا يغيّرها النشر.

## توزيع المهام على الـ workers (T05/T07 + hardening)
- `worker` (`-Q celery,notifications`): المسار الحي فقط: محرك الإشارات (`signals.*`)، تنبيهات الأسعار
  (`alerts.*`)، وإرسال الإشعارات والملخصات، وفحص جودة البيانات (`data_quality.check`)، وجلب التقويم
  الاقتصادي (`calendar.refresh`: طلب واحد كل 4 ساعات، 15 ثانية كحد أقصى).
- `worker-backtest` (`-Q backtests,maintenance`): الاختبارات التاريخية، والمهام غير العاجلة على طابور
  `maintenance`: جلب RSS وتنظيف الأخبار (`news.*`)، تنظيف التوكنات والمفاتيح (`housekeeping.*`)،
  احتفاظ صندوق الإشعارات (`notifications.cleanup`)، التجديدات (`subscriptions.renew`)، والملخص اليومي (`ops.*`).

## حذف حسابات التجربة (purge-demo)
سكربتات التحقق تنشئ حسابات بأسماء مثل `y19-…@example.com` و`e2e-…`. لحذفها مع كل ما تملكه:
```bash
python -m app.cli purge-demo --prefix y19-              # تجربة فقط: يعرض ما سيُحذف
python -m app.cli purge-demo --prefix y19- --yes        # حذف فعلي
python -m app.cli purge-demo --prefix e2e- --instrument-prefix E2E --yes
```
يرفض البادئات القصيرة (أقل من 3 أحرف) وحذف آخر مدير. **لا يُشغَّل على سيرفر الإنتاج من هنا** (لا SSH)؛ على
الإنتاج يحتاج تنفيذاً يدوياً مقصوداً عبر workflow مخصص لاحقاً.

## النسخ الاحتياطي والاستعادة
- **النسخ**: `backup.sh` يعمل يومياً الساعة 03:17 من crontab المستخدم `deploy-trading`:
  `pg_dump -Fc` إلى `/opt/trading/backups/trading-YYYY-MM-DD.dump`، ويحتفظ بـ 7 أيام.
- **اختبار الاستعادة** (محلياً، يلمس حاوية مؤقتة فقط ثم يحذفها):
  ```bash
  docker compose exec -T db pg_dump -U trading -Fc trading > /tmp/trading.dump
  bash infra/deploy/restore-test.sh /tmp/trading.dump aitradinganalysissystem-db-1 trading trading
  ```
  يقارن عدد الصفوف في الجداول الرئيسية (ومنها `candles_1m` و`candles_1h`) بين المصدر والنسخة المستعادة.
  آخر نتيجة: كل الجداول متطابقة (candles_1m 331,303 صف)، الاستعادة 13 ثانية لنسخة 16.6MB.
- **الاستعادة على السيرفر** (يدوياً عند الحاجة فقط، وتلمس stack الـ trading وحده). TimescaleDB يحتاج
  `timescaledb_pre_restore()` قبل `pg_restore` و`timescaledb_post_restore()` بعده:
  ```bash
  cd /opt/trading
  dc() { docker compose -f docker-compose.yml --env-file .env --env-file image.env "$@"; }
  dc stop backend worker worker-backtest beat telegram-bot          # لا كتابة أثناء الاستعادة
  dc exec -T db psql -U trading -d postgres -c "DROP DATABASE trading WITH (FORCE)"
  dc exec -T db psql -U trading -d postgres -c "CREATE DATABASE trading"
  dc exec -T db psql -U trading -d trading -c "CREATE EXTENSION IF NOT EXISTS timescaledb"
  dc exec -T db psql -U trading -d trading -c "SELECT timescaledb_pre_restore()"
  dc exec -T db pg_restore -U trading -d trading --no-owner < backups/trading-YYYY-MM-DD.dump
  dc exec -T db psql -U trading -d trading -c "SELECT timescaledb_post_restore()"
  dc up -d --wait                                                  # يعيد تشغيل الخدمات
  ```
  (`pg_restore` يقرأ الملف من stdin، فلا حاجة لنسخه داخل الحاوية.)

## النسخ خارج السيرفر (GitHub Actions)
النسخ اليومية على السيرفر وحده تضيع مع قرصه، لذلك يعمل workflow **Off-site backup**
(`.github/workflows/backup-offsite.yml`) يومياً الساعة 06:40 UTC، ويمكن تشغيله يدوياً من Actions ← Off-site backup ← Run workflow:
1. **على السيرفر قراءة فقط**: أمر `find` واحد في `/opt/trading/backups` يحدد أحدث `trading-*.dump`، ثم `scp` لهذا
   الملف. لا كتابة ولا أي أمر آخر. يفشل إذا كان عمر أحدث نسخة أكثر من 26 ساعة (أي أن النسخ اليومي على السيرفر لم يعمل).
2. يشفّر النسخة على الـ runner بـ `gpg --symmetric --cipher-algo AES256` بكلمة السر `BACKUP_PASSPHRASE`.
3. يفك التشفير مرة أخرى ويستعيد النسخة في حاوية TimescaleDB جديدة (`infra/deploy/restore-test.sh`): عدد الصفوف،
   الـ alembic revision، وهل `candles_1m` hypertable. أي خلل يُفشل التشغيل.
4. يرفع **الملف المشفّر فقط** كـ artifact باسم `trading-db-YYYY-MM-DD`. النسخة غير المشفّرة لا تُرفع أبداً، لأن أي شخص
   يستطيع قراءة الريبو يستطيع تنزيل الـ artifacts.
5. ملخص التشغيل يعرض اسم النسخة وحجمها وعمرها وsha256 ونتيجة اختبار الاستعادة.

**إعداد لمرة واحدة**: Settings ← Secrets and variables ← Actions ← New repository secret، الاسم `BACKUP_PASSPHRASE`،
والقيمة كلمة سر طويلة عشوائية (مثلاً ناتج `openssl rand -base64 32`). **احتفظ بنسخة منها خارج GitHub** (في مدير كلمات
سر مثلاً): GitHub لا يعرض الـ secret بعد حفظه، وبدونها لا يمكن فك أي نسخة. إذا لم يكن الـ secret موجوداً يفشل الـ workflow
برسالة واضحة ولا ينسخ شيئاً.

**الاحتفاظ**: 14 يوماً على GitHub (نسخة يومية بحجم ~16MB، أي حوالي 250MB من مساحة Actions)، و7 أيام على السيرفر.

**التنزيل وفك التشفير** (على جهازك):
```bash
gh run list --workflow "Off-site backup" --limit 5
gh run download <run-id> -n trading-db-YYYY-MM-DD        # أو من صفحة التشغيل ← Artifacts (ملف zip، فكّه أولاً)
gpg --decrypt --output trading-YYYY-MM-DD.dump trading-YYYY-MM-DD.dump.gpg   # يطلب كلمة السر
```
**الاستعادة محلياً** (للتحقق، حاوية مؤقتة فقط): `bash infra/deploy/restore-test.sh trading-YYYY-MM-DD.dump`

**الاستعادة على السيرفر** (عند فقدان النسخ هناك): انسخ الملف المفكوك إلى مجلد النسخ ثم اتبع خطوات «الاستعادة على
السيرفر» أعلاه بنفس الاسم:
```bash
scp -i ~/.ssh/trading_deploy trading-YYYY-MM-DD.dump deploy-trading@187.127.76.76:/opt/trading/backups/
```

## المراقبة والسجلات والحِمل
- `GET /api/v1/admin/system/status` (للمدير): الإصدار ومدة التشغيل، قاعدة البيانات (الحجم، الاتصالات،
  الـ migration)، Redis، طوابير Celery والـ workers وآخر تشغيل لكل مهمة مجدولة، حداثة بيانات السوق،
  قنوات الإشعارات، أخطاء 5xx في آخر ساعة، والـ WebSocket لكل عمليات الـ API (كل عملية تكتب أرقامها في Redis كل
  30 ثانية: `api_processes` و`clients` و`processes`) مع أرقام العملية التي خدمت الطلب (`process_*`). `GET /api/v1/health/live` للحياة فقط.
- السجلات: سطر واحد لكل طلب (`app.request`) فيه `request_id` (يُعاد في ترويسة `X-Request-ID`) والمسار
  والحالة والمدة والمستخدم. `LOG_FORMAT=auto` يعني JSON في الإنتاج. `APP_VERSION` يُثبَّت في الصورة عند البناء.
- اتصالات قاعدة البيانات: `DB_POOL_SIZE=5` و`DB_MAX_OVERFLOW=10` لكل عملية، و`DB_POOL_TIMEOUT=10`: عند
  الضغط ينتظر الطلب 10 ثوانٍ على الأكثر ثم يحصل على `503` مع `Retry-After` بدل 500.
- اختبار الحِمل: `infra/loadtest/` (k6 على الـ stack المحلي بحدود الإنتاج، **لا يُشغَّل على السيرفر**). آخر نتيجة
  (عمليتا backend، 1.5 CPU للـ backend ولقاعدة البيانات): 40 طلباً في الثانية، p50 بين 1.6 و2.4 ثانية (كان ~3.2)، وفشل
  ~2% كلها `503` (كان 6.3%). الـ backend وقاعدة البيانات ما زالا عند سقفيهما. التفاصيل في `infra/loadtest/README.md`.

## السعة (Y20 الجزء الثاني)
- الـ backend يعمل بعمليتي uvicorn (`API_WORKERS`، فارغ = 2 في الإنتاج و1 في التطوير). الاسم ليس `WEB_CONCURRENCY`
  لأن uvicorn يقرأ هذا المتغير بنفسه ويتعطل إذا وُجد فارغاً.
- ما تم فحصه لعمليتين: تحديد المعدل وقفل الدخول وحدود اتصالات WebSocket في Redis (مشتركة)؛ توزيع WebSocket عبر
  Redis Pub/Sub (كل عملية تستقبل كل رسالة لعملائها)؛ حضور المحادثة في Redis؛ عدّاد 5xx في Redis؛ سرّ webhook الدفع
  التجريبي يُنشأ بـ `SET NX`؛ الـ warm-up لكل عملية؛ إنشاء المدير الأول عند الإقلاع صار تحت قفل `pg_advisory_xact_lock`
  (كانت العمليتان تتسابقان)؛ وأرقام WebSocket في `/admin/system/status` صارت مجموع كل العمليات.
- أسوأ حالة لاتصالات قاعدة البيانات (`max_connections=100`): الـ backend 2 × (5 + 10) = 30، والـ `worker` عمليتا Celery
  × 8 (دفعة الإشعارات، NullPool) = 16، والـ `worker-backtest` 2 × 2 = 4، و`telegram-bot` 2، و`beat` 0، و`pg_dump` 1،
  وجلسات يدوية ~3، أي ~56 من 100.
- الحدود قبل/بعد: الـ backend من 384m / 1.0 CPU إلى 544m / 1.5 CPU (أعلى قمة 400MiB)، وقاعدة البيانات من 1.0 إلى 1.5
  CPU، و`cpu_shares: 512` للجميع. مجموع الذاكرة من 2880MiB إلى 3040MiB، ومجموع سقوف المعالج من 5.5 إلى 6.5.

## ترحيل الشبكة لمرة واحدة (Y20 الجزء الثاني)
كان عنوان Nginx ثابتاً (`172.30.57.10`) والعناوين الأخرى ديناميكية من نفس الشبكة، فقد تأخذ حاويةٌ أُعيد إنشاؤها مع Nginx
في نفس `up` عنوانَه. الآن للشبكة `ip_range: 172.30.57.128/25` (`DOCKER_IP_RANGE`)، وNginx خارجه. Docker لا يغيّر IPAM
لشبكة موجودة، لذلك `remote-deploy.sh` يفعل ذلك **مرة واحدة**:
- يجد شبكتنا بوسوم compose (`com.docker.compose.project=trading`، الشبكة `trading_default`) ويقارن `IPAM.Config` بالـ
  `ip_range` المطلوب.
- إذا لم يكن موجوداً: يطبع `=== ONE-TIME NETWORK MIGRATION`، ثم `docker compose down --remove-orphans` لمشروعنا فقط
  (**بدون `-v`**، فالبيانات تبقى)، ويحذف شبكتنا إن بقيت، ثم `up -d --wait` العادي يعيد إنشاءها.
- في النشر التالي يجد الـ `ip_range` فيتخطى ذلك. لا `prune` ولا أي شبكة أو حاوية لمشروع آخر.
- **توقف المنصة** من `down` حتى ينجح فحص الصحة: ~45 ثانية محلياً، ومتوقع 1-2 دقيقة على السيرفر، مرة واحدة عند دمج Y20
  الجزء الثاني.
- إذا فشل الإقلاع بعد الترحيل يعود السكربت إلى الصورة السابقة على الشبكة الجديدة كالعادة (جُرّب محلياً).

## تشغيل /docs يوم العرض
في الإنتاج Swagger UI و`/redoc` و`/openapi.json` مطفأة افتراضياً (`API_DOCS_ENABLED=` فارغ). لتشغيلها:
```bash
cd /opt/trading
sed -i 's/^API_DOCS_ENABLED=.*/API_DOCS_ENABLED=true/' .env
docker compose -p trading -f docker-compose.yml --env-file .env --env-file image.env up -d --no-deps --force-recreate backend
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/docs   # 200
```
لإطفائها بعد العرض (نفس الأمر بقيمة فارغة):
```bash
cd /opt/trading
sed -i 's/^API_DOCS_ENABLED=.*/API_DOCS_ENABLED=/' .env
docker compose -p trading -f docker-compose.yml --env-file .env --env-file image.env up -d --no-deps --force-recreate backend
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/docs   # 404
```
- الأمر يعيد إنشاء حاوية `backend` الخاصة بمشروعنا فقط (`--no-deps`)، ولا يمس nginx ولا أي مشروع آخر.
- **تحذير**: أطفئها بعد العرض مباشرة. النشر لا يغيّر قيمة موجودة في `.env` (يضيف المفاتيح الجديدة فقط)، فتبقى
  `/docs` مفتوحة للعموم إلى أن تُعاد القيمة فارغة.

## للبرومبتات القادمة
- أي إعداد جديد يُضاف إلى `.env.example` بقيمة افتراضية صالحة للإنتاج، فيصل إلى السيرفر تلقائياً في النشر التالي.
- أي خدمة جديدة تُضاف إلى `docker-compose.yml` (للتطوير) **وإلى** `infra/deploy/docker-compose.prod.yml` (للإنتاج) مع `mem_limit` و`cpus` و`cpu_shares: 512` و`restart: unless-stopped`، ومن دون أي منفذ عام.
- الـ migrations تُطبَّق تلقائياً عند النشر، لذلك يجب أن تكون آمنة على بيانات موجودة.

## بث cTrader الحي (B1)
- خدمة جديدة **`feed-ctrader`** (نفس صورة الـ backend، `python -m app.feeds.ctrader`، 128m و0.25 CPU و`restart: unless-stopped`، بلا منفذ: اتصال WebSocket صادر فقط). مجموع حدود الذاكرة من 3296MiB إلى **3424MiB**، ومجموع سقوف المعالج من 6.5 إلى 6.75.
- خاملة افتراضياً (`CTRADER_ENABLED=false`): تفحص كل دقيقة وتكتب سطراً واحداً في الساعة، ولا تتصل بـ cTrader حتى يُربط الحساب ويُفعَّل الإعداد.
- النشر يكتب `CTRADER_CLIENT_ID` و`CTRADER_CLIENT_SECRET` من أسرار GitHub في `/opt/trading/.env` **فقط إذا كان المفتاح غير موجود أو فارغاً**، عبر `set-env-secrets.sh` على stdin ودون طباعة القيم. خطوات التفعيل في docs/ctrader-feed.md.

## فلتر الدرجة في تنبيهات AI (B11b)
- إعداد جديد `AI_GRADES_ENABLED=false` (في `.env.example`، يصل في النشر التالي). في v1 لا يُرجع ai-service درجات (`grade` دائماً null)، فلا يُطبَّق `min_grade` ويصل تنبيه ARMED لكل متابع. `min_grade` يبقى محفوظاً كما هو.
- يُفعَّل (`true`) فقط حين يُرجع ai-service درجات، ثم إعادة تشغيل `worker` و`backend`. بلا migration وبلا خدمة جديدة.
