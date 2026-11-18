"""The five on the Nasdaq 100 (app/research/five_nas.py): the index's costs and the line filter."""

from app.research import five_nas as fn
from app.research import gold_lab as gl


def test_index_costs_apply_only_inside_the_run() -> None:
    seen = {}

    @fn.with_index_costs
    def probe():
        seen["c"], seen["s"] = gl.COMMISSION, gl.SL_SLIP

    before = (gl.COMMISSION, gl.SL_SLIP)
    probe()
    assert (seen["c"], seen["s"]) == (3.0, 0.5)
    assert (gl.COMMISSION, gl.SL_SLIP) == before  # gold's costs are back


def test_index_reader_converts_server_time_and_moves_nothing() -> None:
    """The index exports are read with the server clock only (docs/data_quality/INDEX_CLOCK.md)."""
    import pandas as pd

    from app.research import gold_exam as ge

    head = b"<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
    rows = []
    for day, first in ((b"2024.07.08", 3), (b"2024.12.09", 3)):  # summer (UTC+3) and winter (UTC+2)
        for k in range(120):
            h, m = first + k // 60, k % 60
            bar = b"\t100.00\t100.50\t99.50\t100.25\t10\t0\t50\n"
            rows.append(day + b"\t%02d:%02d:00" % (h, m) + bar)
    fr = ge.index_frames_from_lines([head, *rows])
    t = fr["5m"]["ts_utc"]
    assert t.iloc[0] == pd.Timestamp("2024-07-08 00:00", tz="UTC")  # 03:00 Athens summer time
    assert pd.Timestamp("2024-12-09 01:00", tz="UTC") in set(t)  # 03:00 Athens winter time
    assert len(t) == 48 and abs(fr["5m"]["spread_mean"].iloc[0] - 0.50) < 1e-9


def test_lines_start_at_the_first_full_day(tmp_path) -> None:
    f = tmp_path / "x.csv"
    f.write_bytes(b"<DATE>\t<TIME>\n2015.12.31\t23:59:00\n2016.01.04\t01:00:00\n")
    assert list(fn.lines(f)) == [b"<DATE>\t<TIME>\n", b"2016.01.04\t01:00:00\n"]
