#!/usr/bin/env bash
# Daily pg_dump of the trading database (cron of deploy-trading, see remote-deploy.sh).
# Keeps 7 days in /opt/trading/backups.
set -euo pipefail
cd /opt/trading
mkdir -p backups
user="$(sed -n 's/^POSTGRES_USER=//p' .env)"
db="$(sed -n 's/^POSTGRES_DB=//p' .env)"
out="backups/trading-$(date +%F).dump"
docker compose -f docker-compose.yml --env-file .env --env-file image.env \
  exec -T db pg_dump -U "$user" -Fc "$db" > "$out.tmp"
mv "$out.tmp" "$out"
find backups -name 'trading-*.dump' -mtime +7 -delete
echo "$(date -Is) backup ok: $out ($(du -h "$out" | cut -f1))"
