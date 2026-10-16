# النشر على السيرفر (CI/CD)

المنصة منشورة على VPS من Hostinger (Ubuntu 24.04، 2 vCPU، 8GB). **السيرفر يستضيف مشاريع أخرى حيّة يستخدمها الناس**، لذلك كل ما يخص مشروعنا معزول تماماً.

## الروابط
| | |
|---|---|
| API | `http://187.127.76.76:8080/api/v1/...` |
| التوثيق (Swagger) | http://187.127.76.76:8080/docs |
| الجاهزية | http://187.127.76.76:8080/api/v1/health/ready |
| WebSocket | `ws://187.127.76.76:8080/ws/market` |

لا يوجد دومين حالياً، ولذلك لا يوجد HTTPS. عند إضافة دومين نضع أمامه موقع nginx للسيرفر مع certbot.

## كيف يعمل
1. كل PR يشغّل CI (`.github/workflows/ci.yml`)، ولا يتم الدمج إلا وهو أخضر.
2. بعد الدمج إلى `main` ونجاح CI عليه، يعمل `Deploy` (`.github/workflows/deploy.yml`) تلقائياً:
   - يبني صورتي `ai-trading-backend` و`ai-trading-ai-service` ويرفعهما إلى GHCR بوسم هو أول 12 حرفاً من الـ commit.
   - يتصل بالسيرفر عبر SSH بالمستخدم `deploy-trading`، وينسخ ملفات الـ stack إلى `/opt/trading`، ثم يشغّل `infra/deploy/remote-deploy.sh`.
   - السكربت يسحب الصور ويشغّل الـ stack. الـ backend يطبّق `alembic upgrade head` عند الإقلاع، والـ workers لا تبدأ إلا بعد أن يصبح الـ backend سليماً.
   - إذا فشل فحص `/api/v1/health/ready` يعود السكربت تلقائياً إلى الوسم السابق ويفشل الـ workflow.
3. لإعادة النشر يدوياً: Actions ← Deploy ← Run workflow.
4. لفحص حالة السيرفر للقراءة فقط: Actions ← Server inspect ← Run workflow.

## قواعد السيرفر المشترك (لا تُكسر)
- لا نلمس أي حاوية أو شبكة أو volume أو موقع nginx لا يخص مشروع Compose المسمى `trading`.
- ممنوع `docker system prune` و`docker image prune` العام، وممنوع إعادة تشغيل Docker أو السيرفر، وممنوع `apt upgrade`.
- المنفذ العام الوحيد لمشروعنا هو `8080` (حاوية nginx). قاعدة البيانات مربوطة على `127.0.0.1:5435` فقط، وRedis والـ backend بلا منافذ على المضيف.
- الشبكة المستخدمة `172.30.57.0/24`، ومنافذ المشاريع الأخرى المحجوزة هي 80، 443، 3000-3005، 5000، 5432-5434، 6380، 9000، 9001، 27017.
- لكل حاوية حد للذاكرة والمعالج، ومجموع الحدود حوالي 2.7GB، وسجلات Docker محدودة بـ 30MB لكل حاوية.

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
- لا خدمات جديدة. التجديدات الشهرية/السنوية ينفّذها الـ `worker` عبر مهمة `subscriptions.renew` كل ساعة (الدقيقة 7).
- الدفع **تجريبي فقط** (`PAYMENT_PROVIDER=demo`): لا أموال حقيقية ولا مفاتيح مزوّد. صفحة الدفع التجريبية
  على `/api/v1/pay/demo/{checkout_id}`، وتقبل البطاقات التجريبية فقط.
- Migration `0012` إضافية فقط، وقيم enum الجديدة (`notification_type`، `post_visibility=subscribers`،
  `report_target=message`) تُضاف خارج المعاملة كما في 0011.
- متغيرات جديدة (قيم افتراضية آمنة، تُضاف تلقائياً إلى `.env`): `PAYMENT_PROVIDER=demo`،
  `PAYMENT_DEMO_WEBHOOK_SECRET=` (فارغ = سرّ يُولَّد ويُحفظ في Redis)، `PAYMENT_DEMO_TOOLS=false`،
  `PAYMENT_RETURN_URL=`، `PUBLIC_BASE_URL=`، `PLATFORM_FEE_PCT=20`، `SUBSCRIPTION_GRACE_DAYS=3`،
  `CHECKOUT_TTL_MINUTES=30`، `CHAT_MESSAGES_PER_MINUTE=30`، `CHAT_MESSAGES_PER_DAY=2000`،
  `CHAT_EDIT_WINDOW_MINUTES=15`، `CHAT_NOTIFY_COLLAPSE_MINUTES=5`.
- اختياري على السيرفر: `PUBLIC_BASE_URL=http://187.127.76.76:8080` لتصبح روابط الدفع مطلقة، و
  `PAYMENT_DEMO_TOOLS=true` لعرض أداة تقديم الوقت (fast-forward) في العروض التقديمية.
- فحص بعد النشر:
  ```bash
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/experts"
  curl -s -H "Authorization: Bearer $TOKEN" "http://187.127.76.76:8080/api/v1/conversations"
  # checkout تجريبي (بحساب متداول وخطة موجودة) ثم فتح صفحة الدفع التجريبية:
  curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json'        -d '{"plan_id":"<plan id>"}' http://187.127.76.76:8080/api/v1/subscriptions/checkout
  curl -s "http://187.127.76.76:8080/api/v1/pay/demo/<checkout_id>" | grep -o '<title>[^<]*'
  ```

## للبرومبتات القادمة
- أي إعداد جديد يُضاف إلى `.env.example` بقيمة افتراضية صالحة للإنتاج، فيصل إلى السيرفر تلقائياً في النشر التالي.
- أي خدمة جديدة تُضاف إلى `docker-compose.yml` (للتطوير) **وإلى** `infra/deploy/docker-compose.prod.yml` (للإنتاج) مع `mem_limit` و`cpus` و`restart: unless-stopped`، ومن دون أي منفذ عام.
- الـ migrations تُطبَّق تلقائياً عند النشر، لذلك يجب أن تكون آمنة على بيانات موجودة.
