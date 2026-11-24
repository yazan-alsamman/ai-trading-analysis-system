#!/usr/bin/env bash
# `nginx -t` of the host site templates in throwaway nginx containers (CI and local), with a
# throwaway self-signed certificate. Touches no host: nothing is installed anywhere.
#   bash infra/host-nginx/check.sh
# nginx 1.24 is what Ubuntu 24.04 ships (the VPS); 1.27 is current.
set -euo pipefail
HOST="${PUBLIC_HOSTNAME:-trading.yazanalsamman.com}"
here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/conf.d" "$work/live/$HOST"

# Git Bash on Windows: tools get Windows paths, and "/CN=..." must not become a path
native() { if command -v cygpath >/dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

MSYS_NO_PATHCONV=1 openssl req -x509 -nodes -newkey rsa:2048 -days 1 -subj "/CN=$HOST" \
  -keyout "$(native "$work/live/$HOST/privkey.pem")" \
  -out "$(native "$work/live/$HOST/fullchain.pem")" 2>/dev/null

for site in "$HOST.bootstrap.conf" "$HOST.conf"; do
  sed "s/__PUBLIC_HOSTNAME__/$HOST/g" "$here/$site" > "$work/conf.d/site.conf"
  for image in nginx:1.24-alpine nginx:1.27-alpine; do
    MSYS_NO_PATHCONV=1 docker run --rm \
      -v "$(native "$work/conf.d"):/etc/nginx/conf.d:ro" \
      -v "$(native "$work/live"):/etc/letsencrypt/live:ro" \
      "$image" nginx -t
    echo "ok: $site on $image"
  done
done
