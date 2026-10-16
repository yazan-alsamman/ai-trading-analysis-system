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

## للبرومبتات القادمة
- أي إعداد جديد يُضاف إلى `.env.example` بقيمة افتراضية صالحة للإنتاج، فيصل إلى السيرفر تلقائياً في النشر التالي.
- أي خدمة جديدة تُضاف إلى `docker-compose.yml` (للتطوير) **وإلى** `infra/deploy/docker-compose.prod.yml` (للإنتاج) مع `mem_limit` و`cpus` و`restart: unless-stopped`، ومن دون أي منفذ عام.
- الـ migrations تُطبَّق تلقائياً عند النشر، لذلك يجب أن تكون آمنة على بيانات موجودة.
