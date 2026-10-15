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

## التطوير بدون Docker (backend)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

قواعد الفروع والـ PR في [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).
