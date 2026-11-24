# يوم العرض النهائي (15 يناير 2027)

قائمة تحقق يتبعها يزن **في اليوم السابق (14 يناير) وصباح يوم العرض**. كل فحص هنا **قراءة فقط**، إلا ما هو مذكور صراحة
(إنشاء حسابات العرض، تشغيل `/docs`، التراجع). قواعد السيرفر المشترك في [deployment.md](deployment.md#قواعد-السيرفر-المشترك-لا-تُكسر)
تبقى كما هي: لا نلمس إلا مشروع Compose المسمى `trading`.

اختصارات تُستخدم أدناه (على جهازك):
```bash
BASE=http://187.127.76.76:8080/api/v1
read -s -p "admin password: " PW; echo
ADMIN_TOKEN=$(curl -s -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"<admin email>\",\"password\":\"$PW\"}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')
st() { curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/admin/system/status" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)$1, indent=1))"; }
```
وعلى السيرفر (عند الحاجة فقط):
```bash
cd /opt/trading
dc() { docker compose -p trading -f docker-compose.yml --env-file .env --env-file image.env "$@"; }
```

## 0. الجدول الزمني
| متى | ماذا |
|---|---|
| 14 يناير (اليوم السابق) | Actions ← **Prod smoke** ← Run workflow، وكل بنود القسم 1، وإنشاء حسابات العرض (القسم 2)، وتشغيل **Off-site backup** يدوياً مرة |
| 15 يناير، قبل العرض بساعة | Prod smoke مرة أخرى، تشغيل `/docs` (القسم 3)، تجربة تحليل شارت واحد من الويب |
| أثناء العرض | إذا تعطّل شيء: القسم 4 (التراجع) |
| بعد العرض مباشرة | إطفاء `/docs`، حذف حسابات العرض (القسم 2)، Prod smoke أخير |

## 1. ما يجب أن يعمل وكيف تتحقق
أسهل طريقة: **Actions ← Prod smoke ← Run workflow** (انظر [deployment.md](deployment.md#الفحص-بعد-النشر-prod-smoke-y20)). كل سطر
`ok` أو `warn` أو `fail`، والـ job يفشل فقط عند عطل حقيقي. السطر المتوقع لكل بند مكتوب أدناه، مع أمر قراءة بديل.

| البند | سطر prod-smoke المتوقع | أمر قراءة بديل |
|---|---|---|
| المنصة حيّة | `ok   health: 200`، `ok   ready: database, redis and migrations ok`، `ok   web: index.html with <div id="root">` | `curl -s $BASE/health/ready` |
| جودة البيانات | `ok   data: ok (fxpro:XAU/USD ok)` (و`warn` مع `degraded` يعني نقصاً في الشموع: انظر [data-quality.md](data-quality.md)) | `curl -s $BASE/health/data` |
| بث cTrader | `ok   ctrader feed: on, state streaming, connected on, last tick …, token expires YYYY-MM-DD (N days, refreshed under 7)` | `st '["feeds"]["ctrader"]'` |
| B9 تقييم AI | `ok   ai evaluate: on (fxpro:XAU/USD), last run ok at …` (تشغيل كل 15 دقيقة + 20 ثانية) | `st '["ai_evaluate"]'` |
| الدرجات | `ok   ai grades: off` (v1 بلا درجات، وهذا هو المتوقع) | `st '["ai_alerts"]'` |
| Y14 تحليل الشارت | `ok   chart analysis: on (gemini-3.6-flash)` و`ok   chart quota: limit …, used …` | `st '["chart_analysis"]'` |
| Y16 حسم التوقعات | `ok   resolver: last run … (ok), backlog N` (backlog صغير) | `curl -s -H "Authorization: Bearer $ADMIN_TOKEN" $BASE/admin/predictions/resolver` |
| Y17 التوصيات | `ok   recommendations: …` | `curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE/me/recommendations?limit=3"` |
| التقويم الاقتصادي | `ok   calendar refresh: N rows, last success …` و`ok   calendar: N events in the last 7 days` | `st '["calendar"]'` |

**توكن cTrader.** توكن حساب الـ demo المربوط ينتهي في **2026-11-24**، والـ feed يجدّده تلقائياً عندما يبقى أقل من 7 أيام
(كل تجديد يعطي ~30 يوماً جديدة، ويغيّر الـ refresh token أيضاً). لذلك يوم 14 يناير يجب أن يكون تاريخ الانتهاء في السطر أعلاه **بعد
2027-01-16**. إذا كان قبله أو كانت الحالة `token_error`/`disconnected`: اربط الحساب من جديد حسب [ctrader-feed.md](ctrader-feed.md)
(قبل العرض بيوم، لا في يومه). إذا كان `connected off` في عطلة نهاية الأسبوع فهذا طبيعي (السوق مغلق)؛ 15 يناير 2027 يوم جمعة،
والسوق مفتوح.

**تاريخ Kaggle في التقويم.** البث الحي يعطي الأسبوع الحالي فقط، فوجود أحداث في 2019 يعني أن التاريخ محمّل:
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BASE/calendar/events?start=2019-01-07T00:00:00Z&end=2019-01-14T00:00:00Z&currencies=USD" \
  | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["items"]), "events in 2019-01-07..14")'
```
صفر يعني أن التاريخ غير محمّل: التحميل يدوي من المدير حسب [economic-calendar.md](economic-calendar.md) (`POST /admin/calendar/import`).
الأحداث القادمة تعمل بدونه، لكن تاريخ كل حدث (`/calendar/events/{event_key}/history`) يكون فارغاً.

**النسخ الاحتياطي.**
- على السيرفر (قراءة فقط): `ls -lt /opt/trading/backups | head -3` يجب أن يُظهر نسخة اليوم (03:17).
- خارج السيرفر: Actions ← **Off-site backup**: آخر تشغيل أخضر، وشغّله يدوياً مرة في 14 يناير
  ([deployment.md](deployment.md#النسخ-خارج-السيرفر-github-actions)).

## 2. حسابات العرض (حساب لكل دور)
حساب لكل دور: `trader` و`analyst` و`expert` و`admin`، كلها ببادئة **`demo-`** حتى يمكن حذفها معاً بعد العرض. **لا توضع
كلمات السر في الريبو أبداً**: ولّدها على جهازك (`openssl rand -base64 18`) واحفظها في مدير كلمات السر.

```bash
# 1. التسجيل (نقطة النهاية العامة)، لكل دور
for role in trader analyst expert admin; do
  read -s -p "password for demo-$role: " P; echo
  curl -s -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
    -d "{\"email\":\"demo-$role@yazanalsamman.com\",\"password\":\"$P\",\"full_name\":\"Demo ${role^}\"}" \
    | python3 -c 'import json,sys; b=json.load(sys.stdin); print(b.get("id"), b.get("email"))'
done
# 2. الأدوار (حساب مدير): analyst و expert و admin؛ الـ trader يبقى trader
curl -s -X PATCH "$BASE/admin/users/<user id>/role" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"role":"analyst"}'
```
اختياري لعرض أغنى: حساب الـ trader يتابع XAU/USD في AI (`PUT /me/ai/follows/{instrument_id}/intraday`) ويفعّل استراتيجية،
وحساب الـ expert ينشئ ملفاً وخطة (`PUT /me/expert-profile`، `POST /me/plans`).

**الحذف بعد العرض** (يدوياً على السيرفر، تجربة أولاً ثم حذف فعلي؛ يحذف الحسابات وكل ما تملكه، ويرفض حذف آخر مدير):
```bash
dc exec -T backend python -m app.cli purge-demo --prefix demo-          # يعرض ما سيُحذف فقط
dc exec -T backend python -m app.cli purge-demo --prefix demo- --yes    # حذف فعلي
```

## 3. `/docs` يوم العرض
مطفأة افتراضياً في الإنتاج. التشغيل والإطفاء (إعادة إنشاء الـ `backend` وحده) في
[deployment.md](deployment.md#تشغيل-docs-يوم-العرض). **أطفئها بعد العرض مباشرة**: النشر لا يغيّر قيمة موجودة في `.env`.

## 4. التراجع
كل الأوامر على السيرفر داخل `/opt/trading` ولمشروع `trading` فقط (`dc` أعلاه). لا `prune`، ولا إعادة تشغيل Docker أو السيرفر.

**4.1 الرجوع إلى وسم الصورة السابق** (إذا كسر آخر نشر شيئاً). `remote-deploy.sh` يحتفظ بوسمين فقط: الحالي والسابق.
```bash
cat image.env                                                  # الوسم الحالي
docker image ls ghcr.io/yazan-alsamman/ai-trading-backend --format '{{.Tag}}  {{.CreatedSince}}'
echo "IMAGE_TAG=<الوسم السابق>" > image.env
dc up -d --wait                                                # نفس ما يفعله النشر عند الفشل
curl -s http://127.0.0.1:8080/api/v1/health/ready
```
الـ migrations إضافية فقط، فالصورة السابقة تعمل على قاعدة البيانات الأحدث. النشر التالي من `main` يعيد الوسم الجديد، لذلك
أصلح المشكلة بـ PR (أو revert) بعد العرض. البديل البطيء (~15 دقيقة): revert على `main` ← CI ← Deploy.

**4.2 إطفاء ميزة بإعداد واحد** (بلا نشر). أعد إنشاء الحاويات التي تقرأ الإعداد فقط، ولا شيء غيرها:

| الميزة | الإعداد في `.env` | الحاويات التي يُعاد إنشاؤها |
|---|---|---|
| B9 تقييم AI (لا طلبات جديدة إلى ai-service) | `AI_EVALUATE_ENABLED=false` | `worker` و`beat` (المهمة تُجدول وتُنفَّذ هناك، كما في [ai-contract.md](ai-contract.md#11-enabling-it-on-the-server))، و`backend` فقط إن أردت أن يعرض `/admin/system/status` القيمة الجديدة (انقطاع ثوانٍ في الـ API) |
| Y14 تحليل الشارت (503 `not_configured`، وباقي المنصة يعمل) | `CHART_ANALYSIS_ENABLED=false` | `backend` فقط |

```bash
cp .env .env.bak-$(date +%F-%H%M)                              # نسخة قبل أي تعديل (لا تطبع .env)
sed -i 's/^CHART_ANALYSIS_ENABLED=.*/CHART_ANALYSIS_ENABLED=false/' .env
dc up -d --no-deps --force-recreate backend
# أو لتقييم AI:
sed -i 's/^AI_EVALUATE_ENABLED=.*/AI_EVALUATE_ENABLED=false/' .env
dc up -d --no-deps --force-recreate worker beat
```
للتشغيل من جديد: نفس الأمر بالقيمة `true`. هذا المسار نفسه (إطفاء تحليل الشارت بإعداد واحد وإعادة إنشاء الـ backend ثم 503)
يُختبر في كل CI (`backend/tests_e2e/test_11_chart_analysis.py`).

## 5. حدود معروفة تُقال بوضوح في العرض
- **لا احتمالات في v1، فلا معايرة بعد.** ai-service يعمل بالقواعد دون نموذج (contract 0.2.1): `probability` و`grade` فارغة،
  و`brier_score` فارغ و`calibration` قائمة فارغة في `/predictions/stats`. المتاح الآن: نسبة الإصابة، النتائج، متوسط R
  ومتوسط العائد. المعايرة تمتلئ تلقائياً عندما يرجع ai-service احتمالات ([predictions.md](predictions.md)).
- **AI على الشموع التاريخية مقابل الحية (قاعدة الـ spread).** الشموع المستوردة من cTrader (backfill) بلا spread، وشمعة القرار
  يجب أن يكون لها spread، وإلا لا يُستدعى ai-service ويُسجَّل `decision_bar_no_spread`. لذلك الإعدادات تُولَّد فقط على الشموع الحية
  منذ ربط البث، والتاريخ يُرسل كسياق فقط ([ai-contract.md](ai-contract.md)، [ctrader-feed.md](ctrader-feed.md)).
- **تحليل Gemini استشاري.** كل نتيجة تحمل تنبيه «ليس نصيحة مالية» يضيفه الـ backend، والأرقام قد تكون خاطئة إذا كانت
  الصورة غير واضحة. الصور تُرسل إلى Google لهذا الطلب فقط ولا تُخزَّن. حصة يومية لكل دور، والسعر القياسي لـ Gemini
  يبدأ في 2027 ([chart-analysis.md](chart-analysis.md)).
- **التوصيات ليست توقعات.** الدرجة ترتّب ما تنظر إليه أولاً من نتائج سابقة، وليست احتمالاً ولا ضماناً
  ([recommendations.md](recommendations.md)).
- **الدفع تجريبي فقط** (`PAYMENT_PROVIDER=demo`، بطاقة 4242).

## 6. ما يحتاجه الويب والموبايل من الـ backend للعرض
| الميزة | نقاط النهاية | التوثيق |
|---|---|---|
| الدخول والحساب | `POST /auth/register`، `/auth/login`، `/auth/refresh`، `GET /users/me` | [security.md](security.md) |
| السوق والشارت الحي | `GET /market/instruments`، `/market/instruments/{id}/candles`، `POST .../indicators`، WebSocket `/ws/market` | [websocket.md](websocket.md)، [instruments.md](instruments.md) |
| الاستراتيجيات والإشارات | `/strategies`، `/me/strategies`، `/signals`، `/me/signal-plans`، `/me/custom-strategies` | [custom-strategies.md](custom-strategies.md)، [risk-management.md](risk-management.md) |
| إعدادات AI (B9-B11) | `PUT /me/ai/follows/{instrument_id}/{profile}`، `GET /predictions?source=ai`، `/ai/setups/{id}/size`، `/ai/setups/{id}/explanation`، `POST/DELETE /ai/setups/{id}/take`، `/me/ai/trades`، موضوع WebSocket `ai_setups` | [risk-management.md](risk-management.md#ai-setups-b10)، [notifications.md](notifications.md) |
| دقة التوقعات (Y16) | `GET /predictions`، `/predictions/{id}`، `/predictions/stats` | [predictions.md](predictions.md) |
| التوصيات (Y17) | `GET /me/recommendations`، `/recommendations/strategies?instrument_id=&timeframe=` | [recommendations.md](recommendations.md) |
| تحليل صورة الشارت (Y14) | `POST /analysis/chart-image` (multipart)، `GET /analysis/chart-image`، `/quota`، `GET/DELETE /{id}`؛ 503 `not_configured` = أخفِ الميزة | [chart-analysis.md](chart-analysis.md) |
| التقويم الاقتصادي | `GET /calendar/events`، `/calendar/events/{event_key}/history` | [economic-calendar.md](economic-calendar.md) |
| الإشعارات | `/me/notifications`، `/me/notifications/unread-count`، `/me/notifications/channels`، WebSocket | [notifications.md](notifications.md) |
| الأخبار والمنشورات والتنبيهات | `/news`، `/posts`، `/me/price-alerts` | [news-posts.md](news-posts.md)، [price-alerts.md](price-alerts.md) |
| الخبراء والاشتراكات والمحادثة | `/experts`، `/me/plans`، `/subscriptions/checkout`، `/conversations` | [subscriptions.md](subscriptions.md)، [chat.md](chat.md) |
| الاختبار التاريخي | `POST /backtests`، `/backtests/{id}`، `/backtests/compare` | [backtesting.md](backtesting.md) |

العقد الكامل: `docs/api/openapi.json` (و`/docs` يوم العرض).
