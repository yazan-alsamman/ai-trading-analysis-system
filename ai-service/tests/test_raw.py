from datetime import date
from pathlib import Path

import pytest

from app.data.raw import HistoryExport, LockboxError

HEADER = b"<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\r\n"


def _bar(day: str, time: str) -> bytes:
    return f"{day}\t{time}\t1.1\t1.2\t1.0\t1.1\t5\t0\t1\r\n".encode()


def _export(tmp_path: Path, name: str, body: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(HEADER + body)
    return path


def test_lockbox_start_comes_from_the_config(tmp_path: Path) -> None:
    path = _export(tmp_path, "x.csv", b"")
    assert HistoryExport(path).cutoff == date(2026, 1, 10)


def test_reading_stops_at_the_first_bar_inside_the_lockbox(tmp_path: Path) -> None:
    body = _bar("2026.01.09", "23:54:00") + _bar("2026.01.12", "00:02:00")
    export = HistoryExport(_export(tmp_path, "XAUUSD_M1_201001110105_202610192259.csv", body))
    lines = list(export.lines())
    assert lines[0].startswith("<DATE>")
    assert lines[1:] == ["2026.01.09\t23:54:00\t1.1\t1.2\t1.0\t1.1\t5\t0\t1"]
    assert export.stopped_at_cutoff and export.lines_read == 1


def test_lines_after_the_cut_are_never_decoded(tmp_path: Path) -> None:
    # Bytes that are not UTF-8 after the cut would raise if the reader decoded them.
    body = _bar("2026.01.09", "21:00:00") + _bar("2026.01.10", "00:00:00") + b"\xff\xfe\x00junk\r\n"
    export = HistoryExport(_export(tmp_path, "h.csv", body))
    assert len(list(export.lines())) == 2
    assert export.stopped_at_cutoff


def test_a_file_that_ends_before_the_cut_is_read_whole(tmp_path: Path) -> None:
    body = _bar("2018.01.10", "00:00:00") + _bar("2026.01.09", "23:54:00")
    export = HistoryExport(_export(tmp_path, "AUDUSD_M1_201801100000_202601092354.csv", body))
    assert len(list(export.lines())) == 3
    assert not export.stopped_at_cutoff


def test_a_file_named_inside_the_lockbox_is_refused_before_it_is_opened(tmp_path: Path) -> None:
    missing = tmp_path / "XAUUSD_M1_202601120101_202610202356.csv"  # never created
    with pytest.raises(LockboxError):
        HistoryExport(missing)


def test_malformed_lines_pass_through_to_the_parser(tmp_path: Path) -> None:
    body = b"garbage line\r\n" + _bar("2026.01.12", "00:02:00")
    export = HistoryExport(_export(tmp_path, "m.csv", body))
    assert list(export.lines())[1:] == ["garbage line"]
