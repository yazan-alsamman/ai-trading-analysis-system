"""MT5 "Export Bars" file names: SYMBOL_TIMEFRAME_YYYYMMDDHHMM_YYYYMMDDHHMM.csv (server time)."""

from __future__ import annotations

import re
from datetime import datetime

EXPORT_NAME = re.compile(r"^([A-Z0-9]+)_([A-Z]+[0-9]+)_(\d{12})_(\d{12})\.csv$")
NAME_TIME = "%Y%m%d%H%M"


def name_fields(name: str) -> dict:
    """What the file name says (symbol, timeframe, first and last bar in server time), or an empty
    dict for other names. Reads nothing from the file."""
    m = EXPORT_NAME.match(name)
    if not m:
        return {}
    symbol, timeframe, first, last = m.groups()
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "name_first_server": datetime.strptime(first, NAME_TIME).strftime("%Y-%m-%d %H:%M"),
        "name_last_server": datetime.strptime(last, NAME_TIME).strftime("%Y-%m-%d %H:%M"),
    }
