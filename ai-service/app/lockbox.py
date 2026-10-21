"""Seal the primary lockbox (D23): hash the 2026 export files without parsing them.

    python -m app lockbox seal LOCKBOX_DIR --export-date 2026-10-21 [--out docs/lockbox]
    python -m app lockbox verify docs/lockbox/MANIFEST-2026-10-21.json LOCKBOX_DIR

``seal`` writes a dated manifest with each file's name, size and SHA-256. Bytes are only fed to the
hash: no line is decoded, parsed, counted or summarised, so nothing about the market data can leak
before P9. ``verify`` re-hashes the files and reports any file that was added, removed or changed.
Standard library only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from app.data.exports import name_fields

MANIFEST_VERSION = 1
CHUNK = 1 << 20
RULE = (
    "Primary lockbox (D23): 2026-01-10 to the export date. Never opened, plotted, loaded or "
    "summarised before P9; opened once, with --open-lockbox and the frozen versions logged."
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def scan(root: Path) -> list[dict]:
    """Every file under ``root``, sorted by relative path, with its size and SHA-256."""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    return [
        {
            "path": p.relative_to(root).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": sha256_file(p),
            **name_fields(p.name),
        }
        for p in files
    ]


def files_digest(files: list[dict]) -> str:
    """SHA-256 over the (path, bytes, sha256) triples: one value that pins the whole lockbox."""
    lines = "".join(f"{f['path']}\t{f['bytes']}\t{f['sha256']}\n" for f in files)
    return hashlib.sha256(lines.encode()).hexdigest()


def seal(root: Path, export_date: date, out_dir: Path, note: str = "") -> Path:
    root, out_dir = root.resolve(), out_dir.resolve()
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")
    if out_dir == root or root in out_dir.parents:
        raise ValueError("the manifest must not be written inside the lockbox")
    files = scan(root)
    if not files:
        raise ValueError(f"{root} has no files")
    path = out_dir / f"MANIFEST-{export_date.isoformat()}.json"
    if path.exists():
        raise FileExistsError(f"{path} exists; a seal is never overwritten")
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "sealed_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "export_date": export_date.isoformat(),
        "rule": RULE,
        "note": note,
        "hash": "sha256 of the raw file bytes; no content was parsed",
        "files_digest": files_digest(files),
        "files": files,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


def verify(manifest_path: Path, root: Path) -> list[str]:
    """Differences between the manifest and the files now under ``root`` (empty when intact)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sealed = {f["path"]: f for f in manifest["files"]}
    if files_digest(manifest["files"]) != manifest["files_digest"]:
        return ["the manifest itself was edited (files_digest does not match)"]
    now = {f["path"]: f for f in scan(root.resolve())}
    problems = [f"missing: {p}" for p in sorted(sealed.keys() - now.keys())]
    problems += [f"added: {p}" for p in sorted(now.keys() - sealed.keys())]
    for p in sorted(sealed.keys() & now.keys()):
        if (sealed[p]["bytes"], sealed[p]["sha256"]) != (now[p]["bytes"], now[p]["sha256"]):
            problems.append(f"changed: {p}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("seal", help="hash the lockbox files and write a dated manifest")
    s.add_argument("lockbox_dir", type=Path)
    s.add_argument("--export-date", type=date.fromisoformat, required=True)
    s.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "docs/lockbox")
    s.add_argument("--note", default="")
    v = sub.add_parser("verify", help="re-hash the lockbox files and compare with a manifest")
    v.add_argument("manifest", type=Path)
    v.add_argument("lockbox_dir", type=Path)
    args = ap.parse_args(argv)

    if args.command == "seal":
        path = seal(args.lockbox_dir, args.export_date, args.out, args.note)
        n = len(json.loads(path.read_text(encoding="utf-8"))["files"])
        print(f"sealed {n} files: {path}")
        return 0
    problems = verify(args.manifest, args.lockbox_dir)
    for p in problems:
        print(p, file=sys.stderr)
    print("intact" if not problems else f"{len(problems)} difference(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
