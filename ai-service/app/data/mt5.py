"""Parser for MetaTrader 5 history exports (History Center -> Export Bars, tab-separated).

Expected header: ``<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE>`` and optionally ``<TICKVOL> <VOL>
<SPREAD>``. Timestamps are bar open times on the broker server clock; spread is in points and is the
minimum spread seen inside the bar."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from app.data.schema import BASE_TIMEFRAME, CANONICAL_COLUMNS, InstrumentSpec
from app.data.sessions import SERVER_TZ, is_open, server_to_utc

REQUIRED = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE"]
PRICES = ["OPEN", "HIGH", "LOW", "CLOSE"]
MAX_RAW_CHARS = 120


@dataclass
class ParseResult:
    bars: pd.DataFrame
    rejected: pd.DataFrame  # line (1-based, in the file), reason, raw
    stats: dict = field(default_factory=dict)


def parse_mt5_text(
    text: str,
    instrument: InstrumentSpec,
    source: str = "fxpro-mt5",
    server_tz: str = SERVER_TZ,
    last_bar_closed: bool = False,
) -> ParseResult:
    """Parse an MT5 export into canonical UTC bars.

    Malformed rows, OHLC inconsistencies, off-grid times and duplicate timestamps are removed and
    returned in ``rejected`` with a reason; nothing is dropped silently. The export's final bar may
    still have been forming when it was exported, so it is dropped unless ``last_bar_closed`` is set
    or the session closes right after it."""
    lines = text.splitlines()
    if not lines:
        raise ValueError("empty export")
    header = [c.strip().strip("<>").upper() for c in lines[0].split("\t")]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise ValueError(f"export header lacks {missing}: {lines[0]!r}")
    ncols = len(header)

    rows = [ln.split("\t") for ln in lines[1:]]
    line_no = np.arange(2, len(rows) + 2)
    good_shape = np.fromiter((len(r) == ncols for r in rows), bool, len(rows))
    reasons = np.where(good_shape, "", "field_count").astype(object)
    df = pd.DataFrame(
        [r if ok else [""] * ncols for r, ok in zip(rows, good_shape, strict=True)],
        columns=header,
        dtype=str,
    )
    for c in df.columns:
        df[c] = df[c].str.strip()

    def flag(mask: np.ndarray, reason: str) -> None:
        reasons[(reasons == "") & mask] = reason

    server_ts = pd.to_datetime(
        df["DATE"] + " " + df["TIME"], format="%Y.%m.%d %H:%M:%S", errors="coerce"
    )
    flag(server_ts.isna().to_numpy(), "bad_timestamp")

    nums = {c: pd.to_numeric(df[c], errors="coerce") for c in PRICES}
    optional = [c for c in ("TICKVOL", "SPREAD") if c in header]
    nums.update({c: pd.to_numeric(df[c], errors="coerce") for c in optional})
    flag(np.column_stack([nums[c].isna().to_numpy() for c in nums]).any(axis=1), "bad_number")

    o, h, lo, c = (nums[k].to_numpy() for k in PRICES)
    with np.errstate(invalid="ignore"):
        bad_ohlc = (
            (np.minimum.reduce([o, h, lo, c]) <= 0)
            | (h < np.maximum(o, c))
            | (lo > np.minimum(o, c))
            | (h < lo)
        )
    flag(bad_ohlc, "ohlc_inconsistent")

    off_grid = (server_ts.dt.floor(BASE_TIMEFRAME) != server_ts).fillna(False).to_numpy()
    flag(off_grid, "off_grid")

    ts_utc = server_to_utc(server_ts, server_tz)
    flag((ts_utc.isna() & server_ts.notna()).to_numpy(), "dst_gap_or_overlap")

    bars = pd.DataFrame(
        {
            "ts_utc": ts_utc.dt.as_unit("ns"),
            "open": nums["OPEN"],
            "high": nums["HIGH"],
            "low": nums["LOW"],
            "close": nums["CLOSE"],
            "tick_volume": nums["TICKVOL"].astype("Int64") if "TICKVOL" in nums else pd.NA,
            "spread": (nums["SPREAD"] * instrument.point).round(instrument.price_decimals)
            if "SPREAD" in nums
            else np.nan,
            "source": source,
        }
    )
    bars["tick_volume"] = bars["tick_volume"].astype("Int64")
    bars["spread"] = bars["spread"].astype("float64")
    bars["source"] = bars["source"].astype(str)

    valid = reasons == ""
    ts_valid = bars["ts_utc"].where(valid)
    out_of_order = int((ts_valid.dropna().diff() < pd.Timedelta(0)).sum())

    # Duplicates among otherwise valid rows: keep the first occurrence in file order.
    dup = ts_valid.duplicated(keep="first").to_numpy() & valid
    if dup.any():
        first = bars[valid & ~dup].set_index("ts_utc")
        cols = ["open", "high", "low", "close", "tick_volume", "spread"]
        later = bars[dup]
        same = (
            later[cols]
            .reset_index(drop=True)
            .eq(first.loc[later["ts_utc"], cols].reset_index(drop=True))
            | later[cols].reset_index(drop=True).isna()
        ).all(axis=1)
        reasons[np.flatnonzero(dup)] = np.where(
            same.to_numpy(), "duplicate_identical", "duplicate_conflicting"
        )
    valid = reasons == ""

    rejected = pd.DataFrame(
        {
            "line": line_no[~valid],
            "reason": reasons[~valid].astype(str),
            "raw": [lines[i - 1][:MAX_RAW_CHARS] for i in line_no[~valid]],
        }
    )
    out = bars[valid].sort_values("ts_utc", kind="stable").reset_index(drop=True)

    tail_dropped = None
    if len(out) and not last_bar_closed:
        last = out["ts_utc"].iloc[-1]
        if is_open(pd.DatetimeIndex([last + BASE_TIMEFRAME]), instrument.session)[0]:
            tail_dropped = last.isoformat()
            out = out.iloc[:-1]

    stats = {
        "rows_read": len(rows),
        "rows_kept": len(out),
        "rows_rejected": int((~valid).sum()),
        "rejected_by_reason": {k: int(v) for k, v in rejected["reason"].value_counts().items()},
        "out_of_order_rows": out_of_order,
        "tail_bar_dropped": tail_dropped,
        "columns_in_export": header,
    }
    return ParseResult(out[CANONICAL_COLUMNS].reset_index(drop=True), rejected, stats)


def read_mt5_export(path: Path, instrument: InstrumentSpec, **kwargs) -> ParseResult:
    text = Path(path).read_bytes().decode("utf-8-sig")
    return parse_mt5_text(text, instrument, **kwargs)
