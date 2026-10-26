import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from app import lockbox

EXPORT_DATE = date(2026, 10, 21)


@pytest.fixture
def box(tmp_path: Path) -> Path:
    root = tmp_path / "lockbox"
    root.mkdir()
    (root / "XAUUSD_M1_202601120101_202610202356.csv").write_bytes(b"not parsed\n")
    (root / "notes.txt").write_bytes(b"\x00\xff binary is fine")
    return root


def _seal(box: Path, tmp_path: Path) -> Path:
    return lockbox.seal(box, EXPORT_DATE, tmp_path / "manifests")


def test_manifest_lists_every_file_with_size_and_sha256(box: Path, tmp_path: Path) -> None:
    m = json.loads(_seal(box, tmp_path).read_text(encoding="utf-8"))
    assert m["export_date"] == "2026-10-21"
    assert [f["path"] for f in m["files"]] == [
        "XAUUSD_M1_202601120101_202610202356.csv",
        "notes.txt",
    ]
    xau = m["files"][0]
    assert xau["bytes"] == len(b"not parsed\n")
    assert xau["sha256"] == hashlib.sha256(b"not parsed\n").hexdigest()
    assert xau["symbol"] == "XAUUSD" and xau["timeframe"] == "M1"
    assert xau["name_first_server"] == "2026-01-12 01:01"
    assert "symbol" not in m["files"][1]


def test_manifest_is_named_by_date_and_never_overwritten(box: Path, tmp_path: Path) -> None:
    path = _seal(box, tmp_path)
    assert path.name == "MANIFEST-2026-10-21.json"
    with pytest.raises(FileExistsError):
        _seal(box, tmp_path)


def test_manifest_may_not_live_inside_the_lockbox(box: Path) -> None:
    with pytest.raises(ValueError):
        lockbox.seal(box, EXPORT_DATE, box / "manifests")


def test_verify_passes_on_intact_files(box: Path, tmp_path: Path) -> None:
    assert lockbox.verify(_seal(box, tmp_path), box) == []


def test_verify_reports_changed_added_and_missing_files(box: Path, tmp_path: Path) -> None:
    path = _seal(box, tmp_path)
    (box / "notes.txt").write_bytes(b"edited")
    (box / "new.csv").write_bytes(b"")
    (box / "XAUUSD_M1_202601120101_202610202356.csv").unlink()
    assert lockbox.verify(path, box) == [
        "missing: XAUUSD_M1_202601120101_202610202356.csv",
        "added: new.csv",
        "changed: notes.txt",
    ]


def test_verify_detects_an_edited_manifest(box: Path, tmp_path: Path) -> None:
    path = _seal(box, tmp_path)
    m = json.loads(path.read_text(encoding="utf-8"))
    m["files"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(m), encoding="utf-8")
    assert lockbox.verify(path, box) == [
        "the manifest itself was edited (files_digest does not match)"
    ]


def test_cli_seal_then_verify(box: Path, tmp_path: Path) -> None:
    out = tmp_path / "manifests"
    assert lockbox.main(["seal", str(box), "--export-date", "2026-10-21", "--out", str(out)]) == 0
    manifest = out / "MANIFEST-2026-10-21.json"
    assert lockbox.main(["verify", str(manifest), str(box)]) == 0
