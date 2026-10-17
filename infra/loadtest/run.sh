#!/usr/bin/env bash
# Load test of the LOCAL compose stack (C2). NEVER run it against the production server: k6 runs
# in a container on this machine's compose network and talks to the local Nginx only.
#
#   infra/loadtest/run.sh            # from the repo root; HOLD_SECONDS=150 VUS=200 WS_CLIENTS=200
#
# 1. restarts the stack with the production mem_limit / cpus (compose.limits.yml);
# 2. creates 200 analyst accounts load-NNN@example.com with tokens (make_users.py);
# 3. samples `docker stats` every ~2 s while simulate-live rewrites the BTC/USDT 1m candle every
#    second and k6 runs load.js (200 API users + 200 WebSocket clients);
# 4. prints the summary (summarize.py), deletes the load- accounts and puts the normal dev stack
#    back (KEEP_LIMITS=1 / KEEP_USERS=1 to skip).
set -euo pipefail

case "${DOCKER_HOST:-}" in
  "" | unix://* | npipe://*) ;;
  *) echo "refusing: DOCKER_HOST=$DOCKER_HOST is not the local Docker daemon" >&2; exit 2 ;;
esac

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
HERE=infra/loadtest
OUT=$HERE/out
HOLD_SECONDS=${HOLD_SECONDS:-150}
VUS=${VUS:-200}
WS_CLIENTS=${WS_CLIENTS:-200}
K6_IMAGE=${K6_IMAGE:-grafana/k6:0.54.0}
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: keep container paths as they are
mkdir -p "$OUT"
rm -f "$OUT/stats.csv" "$OUT/summary.json"

# Nginx first and alone: it has a fixed address (NGINX_IP) that a container recreated in the same
# `up` could otherwise be handed while Nginx is being replaced.
stack() {
  docker compose "$@" up -d --no-deps nginx
  docker compose "$@" up -d --wait db redis backend worker worker-backtest beat nginx
  # the dev backend has no healthcheck, so --wait does not cover uvicorn's start-up (migrations,
  # spawning the workers, warm-up): wait for readiness through Nginx before anything is measured
  for _ in $(seq 1 90); do
    docker compose exec -T nginx wget -qO- -T 3 http://127.0.0.1/api/v1/health/ready 2> /dev/null \
      | grep -q '"status":"ok"' && return 0
    sleep 1
  done
  echo "backend not ready after 90 s" >&2
  return 1
}

echo "== stack with production limits"
# EXTRA_COMPOSE=file.yml: one more override on top, e.g. to try other limits
stack -f docker-compose.yml -f $HERE/compose.limits.yml ${EXTRA_COMPOSE:+-f "$EXTRA_COMPOSE"}

echo "== accounts and tokens"
docker compose exec -T backend python - "$(( VUS > WS_CLIENTS ? VUS : WS_CLIENTS ))" \
  < $HERE/make_users.py > "$OUT/tokens.json"

NET=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' \
  "$(docker compose ps -q nginx)")
MOUNT=$ROOT/$HERE
command -v cygpath > /dev/null && MOUNT=$(cygpath -w "$MOUNT")

echo "== docker stats sampler"
CONTAINERS=$(docker compose ps -q)  # this stack only
( while true; do
    docker stats --no-stream --format '{{.Name}},{{.MemUsage}},{{.CPUPerc}}' $CONTAINERS \
      >> "$OUT/stats.csv"
  done ) &
SAMPLER=$!
trap 'kill $SAMPLER 2> /dev/null || true' EXIT

echo "== simulate-live (1 s) + k6 (${VUS} API users, ${WS_CLIENTS} WebSocket clients, hold ${HOLD_SECONDS}s)"
docker compose exec -d backend python -m app.cli simulate-live --symbol BTC/USDT \
  --source binance --interval 1 --duration $(( HOLD_SECONDS + 60 ))
docker run --rm --network "$NET" -v "$MOUNT:/scripts" -w /scripts \
  -e HOLD_SECONDS="$HOLD_SECONDS" -e VUS="$VUS" -e WS_CLIENTS="$WS_CLIENTS" \
  "$K6_IMAGE" run --quiet load.js || echo "k6 exited with $? (thresholds or errors)"
kill $SAMPLER 2> /dev/null || true

echo "== summary"
"${PYTHON:-python}" $HERE/summarize.py "$OUT" | tee "$OUT/summary.md"

if [ -z "${KEEP_USERS:-}" ]; then
  docker compose exec -T backend python -m app.cli purge-demo --prefix load- --yes
fi
if [ -z "${KEEP_LIMITS:-}" ]; then
  echo "== normal dev stack back"
  stack -f docker-compose.yml
fi
