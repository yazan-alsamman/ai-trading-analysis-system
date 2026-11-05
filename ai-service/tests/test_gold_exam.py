"""Gold lockbox exam (app/research/gold_exam.py): the guards that keep the read to one, the hash
check, the decision and the tick-source check. Nothing here reads the lockbox."""

import hashlib
import json

import pytest

from app.research import gold_exam as ge


def test_run_needs_the_flag_and_runs_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ge, "LOG", tmp_path / "gold_exam_log.json")
    with pytest.raises(ge.ExamError, match="--open-lockbox"):
        ge.run(tmp_path, open_lockbox=False)
    ge.LOG.write_text("{}", encoding="utf-8")
    with pytest.raises(ge.ExamError, match="runs once"):
        ge.run(tmp_path, open_lockbox=True)


def test_the_file_must_match_the_manifest(tmp_path) -> None:
    data = b"<DATE>\t<TIME>\n"
    (tmp_path / "X.csv").write_bytes(data)
    entry = {"path": "X.csv", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    manifest = tmp_path / "MANIFEST.json"
    manifest.write_text(json.dumps({"files": [entry]}), encoding="utf-8")
    assert ge.checked_file(tmp_path, manifest, "X.csv")[1] == entry["sha256"]
    (tmp_path / "X.csv").write_bytes(data + b"2026")
    with pytest.raises(ge.ExamError, match="does not match"):
        ge.checked_file(tmp_path, manifest, "X.csv")
    with pytest.raises(ge.ExamError, match="not in"):
        ge.checked_file(tmp_path, manifest, "Y.csv")


def test_the_decision_follows_section_4() -> None:
    assert ge.decide(0.001) == "Pass"
    assert ge.decide(0.0) == "Not confirmed"
    assert ge.decide(-0.10) == "Not confirmed"
    assert ge.decide(-0.101) == "Fail"


def _log(tmp_path, part: str, ticks: str) -> None:
    d = tmp_path / "ID" / "Agent-127.0.0.1-3000" / "logs"
    d.mkdir(parents=True)
    lines = ["CS\t0\t10:00:00\tTester\tGOLD,M5: testing of Experts\\GoldCombo.ex5 from 2026.01.12",
             f"CS\t0\t10:00:00\tTester\t  Part={part}",
             f"CS\t0\t10:00:01\tTicks\t{ticks}"]  # fmt: skip
    (d / "20261105.log").write_bytes("\r\n".join(lines).encode("utf-16-le"))


@pytest.mark.parametrize(
    ("ticks", "real"),
    [
        ("GOLD : real ticks begin from 2026.01.02 00:00:00", True),
        ("GOLD : real ticks begin from 2026.02.02 00:00:00", False),
        ("GOLD : real ticks begin from 2026.01.02 00:00:00, every tick generation used", False),
        (
            "GOLD : 2026.01.12 00:00 - 2026.10.21 00:00  no real ticks, every tick generation used",
            False,
        ),
    ],
)
def test_the_tick_source_of_the_exam_run(tmp_path, ticks, real) -> None:
    _log(tmp_path, "exam", ticks)
    lines = ge.tick_source(tmp_path)
    assert lines == [ticks] and ge.real_ticks(lines) is real


def test_no_exam_run_counts_as_not_real(tmp_path) -> None:
    _log(tmp_path, "2024-2022", "GOLD : real ticks begin from 2026.01.02 00:00:00")
    assert ge.tick_source(tmp_path) == [] and not ge.real_ticks([])
