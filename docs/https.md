# تفعيل HTTPS على trading.yazanalsamman.com

المنصة اليوم على `http://187.127.76.76:8080`. هذا الدليل يضيف `https://trading.yazanalsamman.com` **دون أن يتغيّر
8080 ودون لمس أي موقع آخر على السيرفر**.

## كيف يعمل

```
المتصفح ──https──> nginx السيرفر (systemd، المنفذ 443، يملكه السيرفر)
                     └─ موقع واحد جديد: trading.yazanalsamman.com ──http──> 127.0.0.1:8090
                                                                     └─ حاوية nginx الخاصة بنا (المنفذ 8090)
                                                                          └─ backend / موقع الويب (نفس :8080)
```

- **حاوية nginx الخاصة بنا** تستمع على منفذين (`infra/nginx/default.conf`)، ويتشارك الاثنان الموقع نفسه من الملف
  `infra/nginx/trading-site.inc` حتى لا يختلفا:
  - **80** (منشور كـ `8080` كما هو اليوم): لا يثق بأي ترويسة `X-Forwarded-For` أو `X-Forwarded-Proto` يرسلها العميل.
  - **8090** (منشور على `127.0.0.1:8090` فقط): يثق بعنوان العميل الحقيقي والبروتوكول (`https`) القادمين من nginx
    السيرفر.
- **ممّن يثق المنفذ 8090؟** فقط من شبكة Docker الخاصة بنا (`DOCKER_SUBNET` = `172.30.57.0/24`):
  - اتصال السيرفر بالمنفذ المنشور على loopback يمرّ عبر docker-proxy، فيصل إلى الحاوية من **بوابة** الشبكة.
  - Docker يأخذ البوابة من `DOCKER_IP_RANGE`، فهي `172.30.57.128` وليست `.1`. لذلك نثق بالشبكة كلها لا بعنوان واحد.
  - تحققنا من ذلك في CI على Docker لينكس (خطوة "Host-proxy entry 8090") وفي تجربة محلية.
  - تستطيع التأكد على السيرفر بالأمر في الخطوة 6.
- **لماذا `127.0.0.1` فقط؟** Docker يتجاوز ufw للمنافذ المنشورة، فأي منفذ داخلي يجب أن يُربط على `127.0.0.1`. المنفذ 8090
  لا يُفتح للإنترنت أبداً.
- **الأوامر كلها هنا يدوية**، تنفّذها أنت (root) بعد دمج هذا التغيير ونشره:
  - لا CI ولا مستخدم النشر يستطيع تشغيل certbot أو تعديل `/etc/nginx`.
  - النشر ينسخ ملفات القالب فقط إلى `/opt/trading/host-nginx/`، ولا يطبّقها.

> **قواعد:** لا تعدّل ملف أي موقع آخر، ولا إعداداً عاماً في nginx، ولا ufw، ولا حاويات أخرى. شغّل دائماً `nginx -t`
> قبل `systemctl reload nginx` (reload وليس restart).

بعد النشر يمكنك التأكد أن المنفذ 8090 يعمل: سجل النشر يطبع `Port 8090 (HTTPS proxy entry): ok`، أو من السيرفر:

```bash
curl -s http://127.0.0.1:8090/api/v1/health/ready      # {"status":"ok",...}
```

## الخطوات (على السيرفر، كـ root)

ضع الاسم في متغير مرة واحدة، فكل الأوامر التالية تستخدمه:

```bash
HOST=trading.yazanalsamman.com
```

### 1. DNS

- **ماذا تفعل:** عند مزوّد DNS الخاص بـ yazanalsamman.com أضف سجلاً من نوع `A`، الاسم `trading`، والقيمة
  `187.127.76.76`. لا تضف AAAA.
- **للتحقق** (من أي جهاز، قد يأخذ دقائق):

  ```bash
  dig +short trading.yazanalsamman.com      # النجاح: 187.127.76.76
  ```

- **إن فشل:** انتظر انتشار السجل، وتأكد أنك عدّلت المنطقة الصحيحة. لا تكمل قبل أن يظهر العنوان.

### 2. نسخة احتياطية من إعدادات nginx

```bash
cp -a /etc/nginx /root/nginx-backup-$(date +%F)
ls -d /root/nginx-backup-*      # النجاح: المجلد موجود
```

### 3. ملف الموقع الأولي (المنفذ 80 فقط) للحصول على الشهادة

لماذا ملف أولي؟ ملف الموقع الكامل يشير إلى ملفات الشهادة، وهي غير موجودة قبل certbot، فيفشل `nginx -t`.

**أولاً، تحقّق من طريقة السيرفر في تنظيم المواقع:**

```bash
grep -n "include" /etc/nginx/nginx.conf
ls /etc/nginx/sites-enabled /etc/nginx/conf.d
```

- إن كان هناك `include /etc/nginx/sites-enabled/*;`، وهو المعتاد في أوبونتو، فاتبع الأوامر كما هي.
- إن كانت المواقع في `conf.d/*.conf`، فضع الملف هناك بدل الرابط.

**ثم ثبّت الملف الأولي:**

```bash
mkdir -p /var/www/trading-acme
sed "s/__PUBLIC_HOSTNAME__/$HOST/g" /opt/trading/host-nginx/$HOST.bootstrap.conf \
  > /etc/nginx/sites-available/$HOST.conf
ln -s /etc/nginx/sites-available/$HOST.conf /etc/nginx/sites-enabled/$HOST.conf
nginx -t && systemctl reload nginx
```

- **النجاح:** `syntax is ok` و`test is successful`. بعدها `curl -I http://$HOST/` يعيد `404` من هذا الموقع.
- **إن فشل `nginx -t`:**
  1. لا تعمل reload.
  2. احذف الرابط: `rm /etc/nginx/sites-enabled/$HOST.conf`.
  3. أعد `nginx -t`.
  4. أرسل لي الخطأ.

### 4. الشهادة (لهذا الاسم فقط)

اخترنا `certbot certonly --webroot`: certbot يكتب الشهادة فقط، ولا يعدّل أي ملف nginx، ولا يقترب من شهادات المواقع
الأخرى. لا تستخدم `--expand`، ولا تضف أسماء أخرى.

```bash
certbot --version     # إن لم يكن مثبتاً: apt install certbot  (المواقع الأخرى تستخدمه غالباً)
certbot certonly --webroot -w /var/www/trading-acme -d $HOST \
  --deploy-hook "systemctl reload nginx"
ls /etc/letsencrypt/live/$HOST/      # النجاح: fullchain.pem و privkey.pem
certbot renew --dry-run --cert-name $HOST     # النجاح: "Congratulations, all simulated renewals succeeded"
```

- **إن فشل:** تحقق من DNS (الخطوة 1). وتحقق أن الملف الأولي مفعّل:
  `curl http://$HOST/.well-known/acme-challenge/x` يجب أن يعيد 404 من nginx، لا خطأ اتصال.
- **التجديد التلقائي:**
  - المؤقّت نفسه الذي يجدّد شهادات المواقع الأخرى يجدّد هذه أيضاً: `systemctl list-timers | grep certbot`.
  - التجديد يستخدم مسار `/.well-known/acme-challenge/` الموجود في الملف الكامل.
  - بعده يعمل `reload` بفضل `--deploy-hook`.

### 5. ملف الموقع الكامل (HTTPS)

```bash
sed "s/__PUBLIC_HOSTNAME__/$HOST/g" /opt/trading/host-nginx/$HOST.conf \
  > /etc/nginx/sites-available/$HOST.conf
nginx -t && systemctl reload nginx
```

- **النجاح:** `test is successful`. على nginx 1.25 أو أحدث قد يظهر تحذير "listen ... http2 is deprecated"؛ هذا
  تحذير فقط، والسطر يعمل على 1.24 (أوبونتو 24.04) وعلى الأحدث.
- **الملف** يخدم هذا الاسم فقط:
  - لا `default_server` ولا wildcard؛
  - HSTS بمدة سنة **بدون `includeSubDomains`**، فلا يتأثر أي موقع آخر من yazanalsamman.com.
- **إن فشل `nginx -t`:** أعد الملف الأولي (الخطوة 3)، ثم `nginx -t && systemctl reload nginx`.

### 6. التحقق

```bash
curl -I https://$HOST/api/v1/health/ready
# النجاح: HTTP/2 200 و strict-transport-security: max-age=31536000

curl -I http://$HOST/
# النجاح: 301 إلى https://trading.yazanalsamman.com/

curl -s https://$HOST/ | grep -c 'id="root"'
# النجاح: 1 (موقع الويب)

# WebSocket عبر wss (يجب أن يرد pong). استبدل البريد وكلمة المرور بحساب حقيقي:
TOKEN=$(curl -s -X POST https://$HOST/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"<email>","password":"<password>"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
python3 - "$HOST" "$TOKEN" <<'PY'
import asyncio, json, sys
import websockets  # إن لم يكن مثبتاً: pip install websockets (أو جرّب من جهازك)
async def main():
    async with websockets.connect(f"wss://{sys.argv[1]}/ws/market?token={sys.argv[2]}") as ws:
        await ws.send(json.dumps({"op": "ping"}))
        while (msg := json.loads(await ws.recv()))["type"] != "pong":
            pass
        print("wss OK:", msg)
asyncio.run(main())
PY

# العنوان الحقيقي للعميل يصل إلى حاويتنا: افتح الصفحة من هاتفك ثم
cd /opt/trading && docker compose -p trading --env-file .env --env-file image.env logs --tail 20 nginx | grep via=
# النجاح: <عنوان هاتفك> via=172.30.57.128 ... proto=https  (via = بوابة شبكتنا، داخل 172.30.57.0/24)

# مواقع أخرى ما زالت تعمل:
curl -I https://yazanalsamman.com
# النجاح: نفس الرد الذي كان قبل التغيير
```

- **إن أعاد `/api/v1/health/ready` الرمز 502:**
  1. تحقق أن حاويتنا تستمع: `curl -s http://127.0.0.1:8090/api/v1/health/ready`.
  2. إن لم تستمع، فالنشر الأخير لم يتم: راجع سجل Deploy في GitHub Actions.
- **إن ظهر عنوان `via=` خارج `172.30.57.0/24`:** الحاوية لن تثق بالعنوان المُرسل، وسيظهر عنوان البوابة بدل عنوان العميل.
  أرسل لي السطر.

### 7. التراجع (عند أي مشكلة)

```bash
rm /etc/nginx/sites-enabled/$HOST.conf
nginx -t && systemctl reload nginx
```

- الشهادة يمكن أن تبقى، فلا تضر أحداً.
- المنصة تبقى تعمل على `http://187.127.76.76:8080` كما كانت.
- عند الحاجة، النسخة الاحتياطية في `/root/nginx-backup-<التاريخ>`.

### 8. بعد أن يعمل HTTPS: إعدادات التطبيق

هذه القيم **لا يغيّرها النشر تلقائياً**:
- النشر يضيف فقط المفاتيح الجديدة إلى `.env`، ولا يغيّر قيمة موجودة.
- ضبط `PUBLIC_BASE_URL` على https قبل أن يعمل الموقع سيكسر روابط الدفع المطلقة.

لذلك تضبطها يدوياً، وفقط بعد نجاح الخطوة 6:

```bash
cd /opt/trading
cp .env .env.bak-$(date +%F)
sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=https://trading.yazanalsamman.com,http://187.127.76.76:8080|' .env
sed -i 's|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://trading.yazanalsamman.com|' .env
grep -E '^(CORS_ORIGINS|PUBLIC_BASE_URL|PUBLIC_HOSTNAME)=' .env
docker compose -p trading --env-file .env --env-file image.env up -d --no-deps backend
```

- **النجاح:**
  - حاوية `trading-backend-1` أعيد إنشاؤها فقط؛
  - `curl -s https://$HOST/api/v1/health/ready` يعيد `"status":"ok"`.
- **التراجع:** `cp .env.bak-<التاريخ> .env`، ثم أعد أمر `up -d --no-deps backend` نفسه.
- **`PUBLIC_HOSTNAME`** يُضاف تلقائياً (`trading.yazanalsamman.com`). هو للتوثيق والروابط فقط، ويظهر في
  `/admin/system/status`.

## موقع الويب والتطبيق

- **موقع الويب (`web/`):**
  - يستخدم في صورة الإنتاج المسار النسبي `/api/v1` (`VITE_API_BASE_URL`)، فيتبع بروتوكول الصفحة:
    https على `https://trading…`، وhttp على `:8080`.
  - لا يستخدم WebSocket حالياً، فلا يوجد `ws://` مكتوب في الكود.
  - صفحات الويب لا تحمل CSP من nginx، فلا شيء يمنع `wss://` إلى نفس الموقع.
  - `VITE_SITE_URL` في `deploy.yml` (روابط canonical و sitemap) ما زال `http://187.127.76.76:8080`. غيّره إلى
    `https://trading.yazanalsamman.com` في PR صغير بعد نجاح الخطوة 6.
- **تطبيق Flutter (لبتول):**
  - عنوان الـ API: `https://trading.yazanalsamman.com/api/v1`.
  - عنوان WebSocket: `wss://trading.yazanalsamman.com/ws/market?token=<JWT>`، أو `?api_key=<key>`.
  - لا تغيير في المسارات أو العقد؛ البروتوكول والاسم فقط.
  - يبقى `http://187.127.76.76:8080` يعمل كما هو خلال الانتقال.
