"""Export the public API contract (T07) from the FastAPI app.

    python scripts/openapi.py            # write docs/api/openapi.json and docs/api/openapi.yaml
    python scripts/openapi.py --check    # exit 1 if they are out of date (CI)

The document is built by ``app/api/openapi.py`` (operationIds, security, error responses,
examples). Settings that show up in it (rate-limit costs) take their defaults, so the export
does not depend on the machine's ``.env``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
OUT = ROOT / "docs" / "api"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("ENVIRONMENT", "development")
os.chdir(BACKEND / "scripts")  # no .env here: every setting at its default

import yaml  # noqa: E402

from app.api.openapi import build  # noqa: E402
from app.main import app  # noqa: E402


def render() -> dict[Path, str]:
    schema = build(app)
    as_json = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    as_yaml = yaml.safe_dump(schema, sort_keys=False, allow_unicode=True, width=100)
    return {OUT / "openapi.json": as_json, OUT / "openapi.yaml": as_yaml}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, content in render().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    if args.check:
        for path in stale:
            print(f"out of date: {path.relative_to(ROOT)}")
        if stale:
            print("run: python backend/scripts/openapi.py")
            return 1
        print("OpenAPI document up to date")
        return 0
    print(f"wrote {len(stale)} of 2 files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
