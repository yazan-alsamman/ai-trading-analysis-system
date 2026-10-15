# Build context: the repository root (see docker-compose.yml), so libs/ is reachable.
# Only the files whitelisted in backend/Dockerfile.dockerignore are sent to the builder.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# shared libraries first (the backend declares them as dependencies by name)
COPY libs/indicators /tmp/libs/indicators
COPY libs/strategies /tmp/libs/strategies
RUN pip install --no-cache-dir /tmp/libs/indicators /tmp/libs/strategies && rm -rf /tmp/libs

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
