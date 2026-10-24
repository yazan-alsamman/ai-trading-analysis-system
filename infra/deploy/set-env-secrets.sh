#!/usr/bin/env bash
# Runs ON the VPS (called by .github/workflows/deploy.yml before remote-deploy.sh):
#   printf 'KEY=value\n...' | ssh vps 'bash /opt/trading/set-env-secrets.sh'
# Writes each KEY=value read on stdin into /opt/trading/.env ONLY when the key is missing or has
# an empty value; a key that already has a value is kept (never overwritten). Values come on
# stdin (never in argv, so never in `ps` or the CI log) and are never printed: only the key names
# and what was done. No `set -x`.
set -euo pipefail
APP="${TRADING_DIR:-/opt/trading}"
cd "$APP"
if [ ! -f .env ]; then
  echo "set-env-secrets: no .env yet (the first deploy creates it); nothing written"
  cat >/dev/null
  exit 0
fi
while IFS= read -r line || [ -n "$line" ]; do
  key="${line%%=*}"
  value="${line#*=}"
  [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || continue
  [ -n "$value" ] || continue
  if grep -q "^${key}=." .env; then
    echo "set-env-secrets: ${key} already set on the server: kept"
    continue
  fi
  tmp="$(mktemp "$APP/.env.XXXXXX")"
  chmod 600 "$tmp"
  grep -v "^${key}=" .env > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  mv "$tmp" .env
  echo "set-env-secrets: ${key} written"
done
