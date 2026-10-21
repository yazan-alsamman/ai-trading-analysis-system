"""The only way research code reads an MT5 history export: it stops at the lockbox (D23).

An export may run past 2026-01-09 (the FxPro history exports of XAUUSD, EURUSD and GBPUSD do).
``HistoryExport`` reads the file line by line and stops at the first bar dated on or after
``lockbox_start`` on the server clock, before decoding it. Lines after that are never decoded,
parsed, hashed or returned; at most one read buffer past the cut is loaded by the operating system.

There is no switch to read past the cut. Opening the lockbox (P9) gets its own reader, with the
frozen versions logged."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.config import splits
from app.data.exports import name_fields

# A data line starts with the bar's server date, e.g. b"2026.01.09\t23:54:00\t...".
DATE_PREFIX = re.compile(rb"^\d{4}\.\d{2}\.\d{2}")


class LockboxError(RuntimeError):
    """A read would touch the sealed lockbox."""


@dataclass
class HistoryExport:
    path: Path
    cutoff: date | None = None  # defaults to the lockbox start in the research config
    stopped_at_cutoff: bool = False
    lines_read: int = 0  # data lines, header excluded
    bytes_read: int = 0  # header and data lines before the cut
    sha256: str = ""  # of exactly those bytes, so the input is pinned without the lockbox part

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.cutoff is None:
            self.cutoff = splits().lockbox_start
        first = name_fields(self.path.name).get("name_first_server")
        if first and date.fromisoformat(first[:10]) >= self.cutoff:
            raise LockboxError(f"{self.path.name} starts inside the lockbox; it is sealed")

    def raw_lines(self) -> Iterator[bytes]:
        """The header, then every data line before the cut, as bytes with their line endings."""
        cut = self.cutoff.strftime("%Y.%m.%d").encode()
        h = hashlib.sha256()
        self.stopped_at_cutoff, self.lines_read, self.bytes_read = False, 0, 0
        with open(self.path, "rb") as f:
            for n, raw in enumerate(f):
                if n and DATE_PREFIX.match(raw) and raw[:10] >= cut:
                    self.stopped_at_cutoff = True
                    break
                h.update(raw)
                self.bytes_read += len(raw)
                self.lines_read += bool(n)
                yield raw
        self.sha256 = h.hexdigest()

    def lines(self) -> Iterator[str]:
        """The header, then every data line before the cut, without line endings."""
        for n, raw in enumerate(self.raw_lines()):
            yield raw.decode("utf-8-sig" if n == 0 else "utf-8").rstrip("\r\n")
