"""Parse an FxPro MT5 "Export Bars" history into canonical UTC bars.

The export is tab-separated with the header ``<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE>`` and
optionally ``<TICKVOL> <VOL> <SPREAD>``. Times are bar open times on the server clock
(``Europe/Athens``: UTC+2 in winter, UTC+3 in EU summer time). Spread is in points.

Each line is first checked against the expected shape (date, time, numbers); lines that fail are
counted as ``field_count``, ``bad_timestamp`` or ``bad_number``. The rest is parsed by pyarrow in
chunks, so memory stays close to the size of the bars kept even for millions of M1 bars. OHLC
inconsistencies, off-grid times, times that do not exist or repeat on the server clock, and
duplicate timestamps are then removed and counted by reason as well: nothing is dropped silently.
Read the file through ``app.data.raw.HistoryExport`` so the lockbox is never touched."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv

from app.config import Instrument

REQUIRED = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE"]
PRICES = ["OPEN", "HIGH", "LOW", "CLOSE"]
INTEGERS = ["TICKVOL", "VOL", "SPREAD"]
BAR_COLUMNS = ["ts_utc", "open", "high", "low", "close", "tick_volume", "spread"]
MAX_EXAMPLES = 5
CHUNK_LINES = 500_000

STAMP = rb"\d{4}\.\d{2}\.\d{2}\t\d{2}:\d{2}:\d{2}"
NUMBER = rb"\t-?\d+(?:\.\d+)?"


@dataclass
class ParseResult:
    bars: pd.DataFrame  # BAR_COLUMNS, sorted by ts_utc, unique
    stats: dict = field(default_factory=dict)


class _Rejects:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.examples: list[dict] = []

    def add(self, name: str, n: int, examples: list[str] = ()) -> None:
        self.counts[name] = self.counts.get(name, 0) + n
        for raw in examples[: MAX_EXAMPLES - len(self.examples)]:
            self.examples.append({"reason": name, "raw": raw[:120]})


def _parse_chunk(
    buf: bytes,
    header: list[str],
    instrument: Instrument,
    timeframe: pd.Timedelta,
    server_tz: str,
    rejects: _Rejects,
) -> pd.DataFrame:
    """Bars of one chunk of well-shaped lines that pass the per-row checks, in file order."""
    types = {c: pa.float64() for c in PRICES} | {c: pa.int64() for c in INTEGERS if c in header}
    types |= {"DATE": pa.string(), "TIME": pa.string()}
    if buf:
        table = pacsv.read_csv(
            io.BytesIO(buf),
            read_options=pacsv.ReadOptions(column_names=header),
            parse_options=pacsv.ParseOptions(delimiter="\t"),
            convert_options=pacsv.ConvertOptions(column_types=types),
        )
    else:
        table = pa.table({col: pa.array([], types.get(col, pa.string())) for col in header})
    joined = pc.binary_join_element_wise(table["DATE"], table["TIME"], " ")
    server = pd.Series(
        pc.strptime(joined, format="%Y.%m.%d %H:%M:%S", unit="s", error_is_null=True).to_pandas()
    ).astype("datetime64[ns]")
    o, h, lo, c = (table[k].to_numpy().astype(float) for k in PRICES)
    tick = table["TICKVOL"].to_pandas() if "TICKVOL" in header else None
    spread = table["SPREAD"].to_numpy().astype(float) if "SPREAD" in header else None
    del table, joined

    reason = np.full(len(server), "", dtype=object)

    def flag(mask, name: str) -> None:
        reason[(reason == "") & np.asarray(mask)] = name

    flag(server.isna(), "bad_timestamp")  # the right shape but not a real date, e.g. month 13
    bad = (np.minimum.reduce([o, h, lo, c]) <= 0) | (h < np.maximum(o, c)) | (lo > np.minimum(o, c))
    flag(bad, "ohlc_inconsistent")
    flag((server.dt.floor(timeframe) != server).fillna(False), "off_grid")
    utc = server.dt.tz_localize(server_tz, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    flag(utc.isna() & server.notna(), "dst_gap_or_overlap")
    for name in pd.unique(reason[reason != ""]):
        rows = np.flatnonzero(reason == name)
        rejects.add(name, len(rows), [f"server {server.iloc[i]}" for i in rows[:MAX_EXAMPLES]])

    keep = reason == ""
    n = int(keep.sum())
    return pd.DataFrame(
        {
            "ts_utc": utc[keep].dt.as_unit("ns").reset_index(drop=True),
            "open": o[keep],
            "high": h[keep],
            "low": lo[keep],
            "close": c[keep],
            "tick_volume": pd.array(tick[keep], dtype="Int64")
            if tick is not None
            else pd.array([pd.NA] * n, dtype="Int64"),
            "spread": (spread[keep] * instrument.point).round(instrument.price_decimals)
            if spread is not None
            else np.full(n, np.nan),
        }
    )


def parse_export(
    raw_lines,
    instrument: Instrument,
    timeframe: pd.Timedelta,
    server_tz: str,
) -> ParseResult:
    """Parse the export's lines (bytes, header first) into UTC bars of ``timeframe``."""
    it = iter(raw_lines)
    header_line = next(it, b"").decode("utf-8-sig").rstrip("\r\n")
    header = [col.strip().strip("<>").upper() for col in header_line.split("\t")]
    missing = [col for col in REQUIRED if col not in header]
    if missing or header[:2] != ["DATE", "TIME"]:
        raise ValueError(f"unexpected export header: {header_line!r}")
    shape = re.compile(STAMP + NUMBER * (len(header) - 2) + rb"\r?\n?")
    stamp = re.compile(STAMP + rb"\t")
    rejects = _Rejects()
    chunks: list[pd.DataFrame] = []
    lines: list[bytes] = []
    rows_read = 0

    def flush() -> None:
        if lines:
            buf = b"".join(ln if ln.endswith(b"\n") else ln + b"\n" for ln in lines)
            lines.clear()
            chunks.append(_parse_chunk(buf, header, instrument, timeframe, server_tz, rejects))

    for raw in it:
        rows_read += 1
        if shape.fullmatch(raw):
            lines.append(raw)
            if len(lines) >= CHUNK_LINES:
                flush()
            continue
        if raw.count(b"\t") != len(header) - 1:
            name = "field_count"
        else:
            name = "bad_number" if stamp.match(raw) else "bad_timestamp"
        rejects.add(name, 1, [raw.decode("utf-8", "replace").rstrip("\r\n")])
    flush()

    if chunks:
        bars = pd.concat(chunks, ignore_index=True)
    else:
        bars = _parse_chunk(b"", header, instrument, timeframe, server_tz, rejects)
    chunks.clear()
    out_of_order = int((bars["ts_utc"].diff() < pd.Timedelta(0)).sum())
    # Duplicate timestamps: keep the first in file order.
    dup = bars["ts_utc"].duplicated(keep="first").to_numpy()
    if dup.any():
        cols = BAR_COLUMNS[1:]
        first = bars[~dup].set_index("ts_utc")
        later = bars[dup].reset_index(drop=True)
        ref = first.loc[later["ts_utc"], cols].reset_index(drop=True)
        same = (later[cols].eq(ref) | later[cols].isna()).all(axis=1).to_numpy()
        for name, mask in (("duplicate_identical", same), ("duplicate_conflicting", ~same)):
            if mask.any():
                shown = later["ts_utc"][mask][:MAX_EXAMPLES]
                rejects.add(name, int(mask.sum()), [f"utc {t}" for t in shown])
        bars = bars[~dup]

    kept = bars.sort_values("ts_utc", kind="stable").reset_index(drop=True)
    stats = {
        "columns_in_export": header,
        "rows_read": rows_read,
        "rows_kept": len(kept),
        "rows_rejected": rows_read - len(kept),
        "rejected_by_reason": dict(sorted(rejects.counts.items())),
        "rejected_examples": rejects.examples,
        "out_of_order_rows": out_of_order,
    }
    return ParseResult(kept[BAR_COLUMNS], stats)
