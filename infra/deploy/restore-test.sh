#!/usr/bin/env bash
# Restore test of a backup made by backup.sh (pg_dump -Fc), following TimescaleDB's procedure:
#   CREATE EXTENSION timescaledb; SELECT timescaledb_pre_restore(); pg_restore;
#   SELECT timescaledb_post_restore();
# into a FRESH, throw-away TimescaleDB container, then compares row counts of the main tables with
# a source database. Touches nothing else (its own container, removed at the end). Fails (exit 1)
# when a table is missing or differs from the source, there is no alembic revision, or candles_1m
# is not a hypertable; the last line says "restore test: ok" or "restore test: FAILED".
# Also run by .github/workflows/backup-offsite.yml on the decrypted off-site copy (no source).
#
#   bash infra/deploy/restore-test.sh <dump file> [<source container> <source user> <source db>]
#
# Locally:  docker compose exec -T db pg_dump -U trading -Fc trading > /tmp/trading.dump
#           bash infra/deploy/restore-test.sh /tmp/trading.dump aitradinganalysissystem-db-1 trading trading
set -euo pipefail
DUMP="${1:?usage: restore-test.sh <dump> [<source container> <user> <db>]}"
SRC="${2:-}"; SRC_USER="${3:-trading}"; SRC_DB="${4:-trading}"
NAME="trading-restore-test-$$"
IMAGE="timescale/timescaledb:2.17.2-pg16"
TABLES="users instruments candles_1m candles_1h signals signal_plans backtests backtest_trades
custom_strategies workspaces notifications news_articles posts comments price_alerts
subscriptions invoices conversations messages"

# Git Bash on Windows rewrites "/tmp/..." arguments into Windows paths: keep container paths as
# they are, and give docker cp a native host path (no-op on Linux)
export MSYS_NO_PATHCONV=1
HOST_DUMP="$DUMP"
command -v cygpath >/dev/null 2>&1 && HOST_DUMP="$(cygpath -w "$DUMP")"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "starting $IMAGE as $NAME"
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=restore -e POSTGRES_USER=trading \
  -e POSTGRES_DB=postgres "$IMAGE" >/dev/null
for _ in $(seq 1 60); do
  docker exec "$NAME" pg_isready -U trading -q 2>/dev/null && break
  sleep 1
done
sleep 2  # the image restarts postgres once after its init scripts
for _ in $(seq 1 60); do
  docker exec "$NAME" pg_isready -U trading -q 2>/dev/null && break
  sleep 1
done
psql_r() { docker exec -i "$NAME" psql -U trading -v ON_ERROR_STOP=1 -qAt "$@"; }

ERRORS="$(mktemp)"
started=$(date +%s)
docker cp "$HOST_DUMP" "$NAME:/tmp/trading.dump"
psql_r -d postgres -c "CREATE DATABASE trading"
psql_r -d trading -c "CREATE EXTENSION IF NOT EXISTS timescaledb"
psql_r -d trading -c "SELECT timescaledb_pre_restore()" >/dev/null
# --no-owner: the roles of the source need not exist here; errors are listed, not fatal
docker exec "$NAME" pg_restore -U trading -d trading --no-owner /tmp/trading.dump 2> "$ERRORS" || true
psql_r -d trading -c "SELECT timescaledb_post_restore()" >/dev/null
echo "restore took $(( $(date +%s) - started )) s; pg_restore messages: $(grep -c . "$ERRORS" || true)"
grep -v "already exists" "$ERRORS" | head -5 || true

count() {  # container user db table
  docker exec "$1" psql -U "$2" -d "$3" -qAt -c "SELECT count(*) FROM $4" 2>/dev/null || echo "-"
}
printf '%-22s %12s %12s\n' table source restored
status=0
for t in $TABLES; do
  restored="$(count "$NAME" trading trading "$t")"
  source="-"
  [ -n "$SRC" ] && source="$(count "$SRC" "$SRC_USER" "$SRC_DB" "$t")"
  mark=""
  if [ "$restored" = "-" ]; then mark=" <-- missing"; status=1; fi
  if [ -n "$SRC" ] && [ "$source" != "$restored" ]; then mark=" <-- differs"; status=1; fi
  printf '%-22s %12s %12s%s\n' "$t" "$source" "$restored" "$mark"
done
rev="$(psql_r -d trading -c 'SELECT version_num FROM alembic_version' 2>/dev/null || true)"
hyper="$(psql_r -d trading -c "SELECT string_agg(hypertable_name, ',') FROM timescaledb_information.hypertables" 2>/dev/null || true)"
echo "alembic revision: ${rev:-none}"
echo "hypertables: ${hyper:-none}"
if [[ ",$hyper," == *",candles_1m,"* ]]; then
  echo "candles_1m is a hypertable: yes"
else
  echo "candles_1m is a hypertable: NO"; status=1
fi
[ -n "$rev" ] || status=1
if [ "$status" = 0 ]; then echo "restore test: ok"; else echo "restore test: FAILED"; fi
exit $status
