# منصة التداول الذكية

مشروع تخرج. مستودع واحد (Monorepo) يضم كل أجزاء المنصة.

| المجلد | المحتوى | المسؤول |
|---|---|---|
| `backend/` | FastAPI + Celery + PostgreSQL/TimescaleDB + Redis | Yazan |
| `ai-service/` | خدمة الذكاء (FastAPI) والنماذج والـ notebooks | Fadi |
| `web/` | لوحة الويب React + TS | Elias |
| `mobile/` | تطبيق Flutter | Batoul |
| `infra/` | إعدادات Nginx والنشر | Yazan |

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
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

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

قواعد الفروع والـ PR في [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).
