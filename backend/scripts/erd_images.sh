#!/usr/bin/env bash
# Render the ERD diagrams (docs/erd/mmd/*.mmd, written by scripts/erd.py) to SVG and PNG in
# docs/erd/img/ with mermaid-cli, for the report. Needs Node 18+ (npx downloads mermaid-cli and
# its headless Chromium on first use).
set -euo pipefail
cd "$(dirname "$0")/../../docs/erd"
mkdir -p img
MMDC="npx -y @mermaid-js/mermaid-cli@11.4.2"
for f in mmd/*.mmd; do
  name="$(basename "$f" .mmd)"
  $MMDC -q -i "$f" -o "img/$name.svg" -b white
  $MMDC -q -i "$f" -o "img/$name.png" -b white -s 2
  echo "rendered img/$name.svg img/$name.png"
done
