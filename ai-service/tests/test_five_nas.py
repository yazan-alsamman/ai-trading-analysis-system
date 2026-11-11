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


def test_lines_start_at_the_first_full_day(tmp_path) -> None:
    f = tmp_path / "x.csv"
    f.write_bytes(b"<DATE>\t<TIME>\n2015.12.31\t23:59:00\n2016.01.04\t01:00:00\n")
    assert list(fn.lines(f)) == [b"<DATE>\t<TIME>\n", b"2016.01.04\t01:00:00\n"]
