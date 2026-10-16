#!/usr/bin/env bash
# Runs ON the VPS as deploy-trading (called by .github/workflows/deploy.yml):
#   bash /opt/trading/remote-deploy.sh <image-tag>
# Touches only /opt/trading, the compose project "trading", its own images and its own crontab.
set -euo pipefail
TAG="${1:?usage: remote-deploy.sh <image-tag>}"
APP=/opt/trading
cd "$APP"
dc() { docker compose -f docker-compose.yml --env-file .env --env-file image.env "$@"; }
rand() { tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1" || true; }

# 1. .env: generated once with fresh secrets; later deploys only append keys new in .env.example
if [ ! -f .env ]; then
  echo "Creating .env with generated secrets"
  pg_pass="$(rand 32)"
  sed -e "s|^ENVIRONMENT=.*|ENVIRONMENT=production|" \
      -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${pg_pass}|" \
      -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://trading:${pg_pass}@db:5432/trading|" \
      -e "s|^JWT_SECRET=.*|JWT_SECRET=$(rand 64)|" \
      -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=http://187.127.76.76:8080,http://localhost:5173|" \
      .env.example > .env
  chmod 600 .env
else
  while IFS= read -r line; do
    key="${line%%=*}"
    if [[ "$line" =~ ^[A-Z0-9_]+= ]] && ! grep -q "^${key}=" .env; then
      echo "Adding new setting ${key} to .env"
      printf '%s\n' "$line" >> .env
    fi
  done < .env.example
fi

# 2. switch image tag, keeping the previous one for rollback
prev=""
[ -f image.env ] && prev="$(sed -n 's/^IMAGE_TAG=//p' image.env)"
echo "IMAGE_TAG=${TAG}" > image.env
echo "Deploying ${TAG} (previous: ${prev:-none})"
dc pull --quiet
dc up -d --remove-orphans --wait --wait-timeout 180 || deploy_failed=1

# Our nginx keeps its config until reloaded, and `up` does not recreate it when only the
# bind-mounted nginx/default.conf changed. Reload OUR nginx container (never the host's) when the
# file differs from the last one applied; recreate it if the container sees a stale copy.
if [ -z "${deploy_failed:-}" ]; then
  conf_sum="$(sha256sum nginx/default.conf | cut -d' ' -f1)"
  if [ "$(cat .nginx.sha256 2>/dev/null || true)" != "$conf_sum" ]; then
    seen="$(dc exec -T nginx sha256sum /etc/nginx/conf.d/default.conf 2>/dev/null | cut -d' ' -f1 || true)"
    if [ "$seen" != "$conf_sum" ]; then
      echo "Nginx sees an old copy of its config: recreating our nginx service"
      dc up -d --no-deps --force-recreate nginx && echo "$conf_sum" > .nginx.sha256
    elif dc exec -T nginx nginx -t && dc exec -T nginx nginx -s reload; then
      echo "Nginx config changed: reloaded our nginx"
      echo "$conf_sum" > .nginx.sha256
    else
      echo "!!! New nginx config is invalid: kept the running one"
    fi
  fi
fi

health() {
  for _ in $(seq 1 30); do
    # through our own nginx container (busybox wget), so the host needs no curl
    if body="$(dc exec -T nginx wget -qO- -T 3 http://127.0.0.1/api/v1/health/ready 2>/dev/null)" \
       && grep -q '"status":"ok"' <<<"$body"; then
      echo "Healthy: $body"; return 0
    fi
    sleep 3
  done
  return 1
}

if [ -z "${deploy_failed:-}" ] && health; then
  echo "Deploy OK: ${TAG}"
else
  echo "!!! Deploy of ${TAG} failed health check"
  dc ps
  dc logs --tail 80 backend || true
  if [ -n "$prev" ] && [ "$prev" != "$TAG" ]; then
    echo "Rolling back to ${prev}"
    echo "IMAGE_TAG=${prev}" > image.env
    dc up -d --remove-orphans --wait --wait-timeout 180 || true
  fi
  exit 1
fi

# 3. keep only the current and previous image tags of OUR images (never a global prune)
for repo in ghcr.io/yazan-alsamman/ai-trading-backend ghcr.io/yazan-alsamman/ai-trading-ai-service; do
  docker image ls "$repo" --format '{{.Tag}}' | while read -r t; do
    if [ "$t" != "$TAG" ] && [ "$t" != "$prev" ]; then docker image rm "$repo:$t" >/dev/null || true; fi
  done
done

# 4. daily database backup in deploy-trading's own crontab (idempotent)
chmod +x "$APP/backup.sh"
mkdir -p "$APP/backups"
if ! command -v crontab >/dev/null; then echo "WARNING: crontab not available, daily backup not scheduled"; exit 0; fi
( crontab -l 2>/dev/null | grep -v 'trading-backup' || true
  echo "17 3 * * * $APP/backup.sh >> $APP/backups/backup.log 2>&1 # trading-backup" ) | crontab -
