"""The only way research code reads an MT5 history export: it stops at the lockbox (D23).

An export may run past 2026-01-09 (the FxPro history exports of XAUUSD, EURUSD and GBPUSD do).
``HistoryExport.lines`` reads the file line by line and stops at the first bar dated on or after
``lockbox_start`` on the server clock, before decoding it. Lines after that are never decoded,
parsed or returned; at most one read buffer past the cut is loaded by the operating system.

There is no switch to read past the cut. Opening the lockbox (P9) gets its own reader, with the
frozen versions logged."""

from __future__ import annotations

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
    lines_read: int = 0

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.cutoff is None:
            self.cutoff = splits().lockbox_start
        first = name_fields(self.path.name).get("name_first_server")
        if first and date.fromisoformat(first[:10]) >= self.cutoff:
            raise LockboxError(f"{self.path.name} starts inside the lockbox; it is sealed")

    def lines(self) -> Iterator[str]:
        """The header, then every data line before the cut, without line endings."""
        cut = self.cutoff.strftime("%Y.%m.%d").encode()
        self.stopped_at_cutoff, self.lines_read = False, 0
        with open(self.path, "rb") as f:
            header = f.readline()
            if not header:
                return
            yield header.decode("utf-8-sig").rstrip("\r\n")
            for raw in f:
                if DATE_PREFIX.match(raw) and raw[:10] >= cut:
                    self.stopped_at_cutoff = True
                    return
                self.lines_read += 1
                yield raw.decode("utf-8").rstrip("\r\n")
