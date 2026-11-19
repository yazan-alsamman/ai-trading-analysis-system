"""Gold-news sentiment data (``docs/sentiment/PREREG_SENTIMENT.md`` §2-§3): file checks, loaders,
normalisation, deduplication (G1), the date split, prices and the headline-day alignment (G3).

    python -m app research sentiment download [--prices-from PATH]
    python -m app research sentiment data

``data`` checks every raw file against its SHA-256 in ``app/config/sentiment.toml`` and stops on a
mismatch, then writes ``data/sentiment/processed/{gold_headlines,fpb,xauusd_d1}.parquet`` and
``manifest.json`` (counts only, no headline text). Nothing under ``data/sentiment/`` is committed.

No function here relates a headline (or its label) to a price or a volatility: the price file is
used for its prices (the volatility study, after approval) and for its calendar (which dates have
a bar), and only the calendar meets the headlines, to move weekend and holiday headlines to the
next price day. The Dukascopy reader stops at the first bar on or after the lockbox start
(2026-01-10) without decoding the rest of the line."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.lockbox import sha256_file

ROOT = Path(__file__).resolve().parents[3]  # ai-service/
CONFIG = ROOT / "app" / "config" / "sentiment.toml"
LOCKBOX_START = date(2026, 1, 10)  # CLAUDE.md, D23
LABELS = ("negative", "neutral", "positive")
PRICE_SENTIMENTS = (*LABELS, "none")
SPLITS = ("train", "validation", "test")
KAGGLE_DATASET = "ankurzing/sentiment-analysis-in-commodity-market-gold"

GOLD_COLUMNS = {
    "Dates": "date_raw",
    "URL": "url",
    "News": "headline",
    "Price Direction Up": "dir_up",
    "Price Direction Constant": "dir_constant",
    "Price Direction Down": "dir_down",
    "Asset Comparision": "asset_comparison",  # sic, the dataset's spelling
    "Past Information": "past_info",
    "Future Information": "future_info",
    "Price Sentiment": "price_sentiment",
}
FLAG_COLUMNS = (
    "dir_up", "dir_constant", "dir_down", "asset_comparison", "past_info", "future_info",
)  # fmt: skip
GOLD_DATE_FORMAT = "%d-%m-%Y"
_URL_DATE = re.compile(r"(?<!\d)((?:19|20)\d\d)-(\d\d)-(\d\d)(?!\d)")
_TRUNCATED = re.compile(r"^(\d{4})-(\d\d)-(\d\d)$")  # e.g. 0201-04-27: year cut, YYYY-MM-DD order
PRICE_COLUMNS = ("open", "high", "low", "close", "volume")


class ChecksumError(RuntimeError):
    """A raw file is missing or differs from the SHA-256 recorded in ``sentiment.toml``."""


# --------------------------------------------------------------------------------------- config


@dataclass(frozen=True)
class DataFile:
    key: str
    path: Path
    sha256: str
    optional: bool
    source: str
    # an FxPro MT5 export: read and hashed only through app.data.raw.HistoryExport, which stops at
    # the lockbox start (CLAUDE.md data rules); its SHA-256 covers the bytes before the cut
    mt5_export: bool = False


@dataclass(frozen=True)
class Config:
    path: Path
    root: Path  # data/sentiment
    raw: Path
    processed: Path
    report: Path
    files: dict[str, DataFile]
    near_jaccard: float
    window_days: int
    min_test: int
    default_split: tuple[date, date]  # (train_last, val_last)
    fallback_split: tuple[date, date]
    price_first: date
    price_stop: date
    g2_min_close_corr: float  # pass rule against the MT5 D1 export
    g2_min_return_corr: float  # pass rule against Yahoo GC=F (futures: another instrument)
    g2_return_diff: float
    g2_list: int
    class_weights: dict[str, float] = field(default_factory=dict)
    base: Path = ROOT  # ai-service/, what the paths above are resolved against


def _date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def load_config(path: Path = CONFIG, base: Path = ROOT) -> Config:
    """Read ``sentiment.toml``; paths are resolved against ``base`` (ai-service/)."""
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    p = raw["paths"]
    root = base / p["root"]
    files = {
        key: DataFile(
            key=key,
            path=root / spec["path"],
            sha256=spec.get("sha256", ""),
            optional=bool(spec.get("optional", False)),
            source=spec.get("source", ""),
            mt5_export=bool(spec.get("mt5_export", False)),
        )
        for key, spec in raw["files"].items()
    }
    sp, pr, g = raw["split"], raw["prices"], raw["gates"]
    stop = _date(pr["stop_before"])
    if stop > LOCKBOX_START:
        raise ValueError(f"prices.stop_before {stop} is after the lockbox start {LOCKBOX_START}")
    return Config(
        path=path,
        root=root,
        raw=base / p["raw"],
        processed=base / p["processed"],
        report=base / p["report"],
        files=files,
        near_jaccard=float(raw["dedupe"]["near_jaccard"]),
        window_days=int(raw["dedupe"]["window_days"]),
        min_test=int(sp["min_test"]),
        default_split=(_date(sp["default"]["train_last"]), _date(sp["default"]["val_last"])),
        fallback_split=(_date(sp["fallback"]["train_last"]), _date(sp["fallback"]["val_last"])),
        price_first=_date(pr["first_date"]),
        price_stop=stop,
        g2_min_close_corr=float(g["g2_min_close_corr"]),
        g2_min_return_corr=float(g["g2_min_return_corr"]),
        g2_return_diff=float(g["g2_return_diff"]),
        g2_list=int(g["g2_list"]),
        class_weights={k: float(v) for k, v in raw.get("class_weights", {}).items()},
        base=base,
    )


def file_sha256(f: DataFile, stop_before: date) -> str:
    """SHA-256 of a raw file. An MT5 export is read only through ``HistoryExport`` (CLAUDE.md data
    rules): the hash covers the header and the lines before the first bar dated on or after
    ``stop_before`` (server date); nothing after the cut is read."""
    if not f.mt5_export:
        return sha256_file(f.path)
    from app.data.raw import HistoryExport

    h = HistoryExport(f.path, cutoff=stop_before)
    for _ in h.raw_lines():
        pass
    return h.sha256


def record_sha256(config_path: Path, key: str, sha: str) -> None:
    """Write ``sha`` into the empty ``sha256 = ""`` line of ``[files.<key>]`` in ``sentiment.toml``
    (first acquisition of an optional file). A recorded value is never overwritten."""
    text = config_path.read_text(encoding="utf-8")
    head, sep, rest = text.partition(f"\n[files.{key}]\n")
    if not sep:
        raise ValueError(f"{config_path} has no [files.{key}] table")
    end = rest.find("\n[")
    table, tail = (rest, "") if end < 0 else (rest[:end], rest[end:])
    m = re.search(r'^sha256 = "([0-9a-f]*)"', table, flags=re.M)
    if not m:
        raise ValueError(f"[files.{key}] has no sha256 line")
    if m[1]:
        if m[1] != sha:
            raise ChecksumError(f"{key}: SHA-256 {sha} != recorded {m[1]}")
        return
    table = table[: m.start()] + f'sha256 = "{sha}"' + table[m.end() :]
    config_path.write_text(head + sep + table + tail, encoding="utf-8", newline="\n")


def verify_files(cfg: Config) -> dict[str, str]:
    """Check every raw file's SHA-256; return ``{key: "ok" | "missing"}``. A required file that is
    missing or any file that differs raises ``ChecksumError``. An optional file may be missing; if
    it is present its SHA-256 must be recorded and match."""
    status = {}
    for key, f in cfg.files.items():
        if not f.path.is_file():
            if f.optional:
                status[key] = "missing"
                continue
            raise ChecksumError(f"{key}: {f.path} not found (get it with: {f.source})")
        if not f.sha256:
            raise ChecksumError(
                f"{key}: {f.path} is present but no SHA-256 is recorded in {cfg.path.name}; "
                "record it before using the file"
            )
        got = file_sha256(f, cfg.price_stop)
        if got != f.sha256:
            raise ChecksumError(f"{key}: SHA-256 {got} != recorded {f.sha256} ({f.path})")
        status[key] = "ok"
    return status


def write_class_weights(config_path: Path, weights: dict[str, float]) -> None:
    """Rewrite the ``[class_weights]`` table (the last table of ``sentiment.toml``) in place."""
    text = config_path.read_text(encoding="utf-8")
    marker = "\n[class_weights]\n"
    head, sep, _ = text.partition(marker)
    if not sep:
        raise ValueError(f"{config_path} has no [class_weights] table")
    body = "".join(f"{k} = {weights[k]:.6f}\n" for k in sorted(weights))
    new = head + marker + body
    if new != text:
        config_path.write_text(new, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------------------------- download


def _extract_member(archive: Path, member: str, target: Path) -> None:
    """Copy one named member of a zip to ``target`` (no other member is written)."""
    with zipfile.ZipFile(archive) as z, z.open(member) as src, open(target, "wb") as dst:
        shutil.copyfileobj(src, dst)


def _fetch(url: str, target: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as r, open(target, "wb") as f:  # noqa: S310
        if r.status != 200:
            raise OSError(f"{url}: HTTP {r.status}")
        shutil.copyfileobj(r, f)


def download(cfg: Config, prices_from: Path | None = None) -> dict[str, str]:
    """Fetch the raw files into ``data/sentiment/raw/`` (skipping files already present), then
    ``verify_files``. Kaggle needs a token (``KAGGLE_API_TOKEN`` or ``kaggle.json``); the
    Dukascopy file is copied from ``prices_from`` (made with the command in ``sentiment.toml``);
    the G2 cross-check is the MT5 D1 export if present (placed by hand), else Yahoo ``GC=F``; both
    are optional, a failure is reported, not raised, and a new file's SHA-256 is recorded in
    ``sentiment.toml`` on first sight (verified like the others after that)."""
    f = cfg.files
    for d in {x.path.parent for x in f.values()}:
        d.mkdir(parents=True, exist_ok=True)
    if not f["gold_zip"].path.is_file():
        cmd = [sys.executable, "-m", "kaggle", "datasets", "download", "-d", KAGGLE_DATASET,
               "-p", str(f["gold_zip"].path.parent)]  # fmt: skip
        subprocess.run(cmd, check=True)
    if not f["gold"].path.is_file():
        _extract_member(f["gold_zip"].path, f["gold"].path.name, f["gold"].path)
    if not f["fpb_zip"].path.is_file():
        _fetch(f["fpb_zip"].source, f["fpb_zip"].path)
    if not f["fpb"].path.is_file():
        member = "FinancialPhraseBank-v1.0/" + f["fpb"].path.name
        _extract_member(f["fpb_zip"].path, member, f["fpb"].path)
    if not f["dukascopy"].path.is_file():
        if prices_from is None:
            src = f["dukascopy"].source
            raise ChecksumError(f"dukascopy: pass --prices-from (made with: {src})")
        shutil.copyfile(prices_from, f["dukascopy"].path)
    # G2 cross-check (PREREG §2.3): the MT5 D1 export if it has been placed in raw/prices/ (its
    # SHA-256 is recorded on first sight), otherwise Yahoo GC=F (downloaded once, then pinned)
    if f["mt5"].path.is_file():
        if not f["mt5"].sha256:
            record_sha256(cfg.path, "mt5", file_sha256(f["mt5"], cfg.price_stop))
    elif not f["gcf"].path.is_file():
        try:
            fetch_gcf(f["gcf"].path, date(2000, 1, 1), cfg.price_stop)
        except Exception as e:  # noqa: BLE001 - any failure leaves G2 pending, never half a file
            f["gcf"].path.unlink(missing_ok=True)
            print(f"gcf: not downloaded ({e!r}); G2 stays pending", file=sys.stderr)
    if f["gcf"].path.is_file() and not f["gcf"].sha256:
        record_sha256(cfg.path, "gcf", sha256_file(f["gcf"].path))
    return verify_files(load_config(cfg.path, cfg.base))  # reread: a SHA-256 may be new


def fetch_gcf(target: Path, start: date, stop_before: date) -> None:
    """Yahoo Finance gold futures ``GC=F`` daily bars from ``start`` to the day before
    ``stop_before`` (yfinance's ``end`` is exclusive, so no lockbox-period bar is requested), as
    ``date,open,high,low,close,volume``. Bars are dated by the exchange's day (not 00:00 UTC)."""
    import yfinance as yf

    df = yf.download(
        "GC=F", start=start.isoformat(), end=stop_before.isoformat(), interval="1d",
        auto_adjust=False, actions=False, progress=False, multi_level_index=False,
    )  # fmt: skip
    if df is None or df.empty:
        raise OSError("GC=F: no data returned")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    d = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    df = df.set_axis(d.rename("date")).loc[lambda x: x.index < pd.Timestamp(stop_before)]
    df = df.dropna(subset=["close"])
    df.reset_index().to_csv(target, index=False, date_format="%Y-%m-%d", lineterminator="\n")


# ------------------------------------------------------------------------------------ headlines


def parse_gold_dates(values: pd.Series) -> pd.Series:
    """``DD-MM-YYYY`` strings to day timestamps; anything else becomes NaT (reported)."""
    return pd.to_datetime(values.str.strip(), format=GOLD_DATE_FORMAT, errors="coerce")


def url_date(url: str) -> pd.Timestamp:
    """The first ``YYYY-MM-DD`` in a URL (many article URLs carry one), else NaT. It replaces a
    file date only through ``recover_date`` (truncated years, PREREG §2.1)."""
    m = _URL_DATE.search(url)
    if not m:
        return pd.NaT
    try:
        return pd.Timestamp(f"{m[1]}-{m[2]}-{m[3]}")
    except ValueError:
        return pd.NaT


def recover_date(raw: str, url: str) -> date | None:
    """The date of a headline row (PREREG §2.1, decided 2026-11-19). A raw ``DD-MM-YYYY`` value is
    taken as is (the URL is not consulted). A truncated-year value ``YYYY-MM-DD`` such as
    ``0201-04-27`` takes the URL's date when the URL carries one whose month and day equal the raw
    value's. Anything else: None (the row is dropped and counted)."""
    raw = raw.strip()
    try:
        return datetime.strptime(raw, GOLD_DATE_FORMAT).date()
    except ValueError:
        pass
    m = _TRUNCATED.match(raw)
    if not m:
        return None
    u = url_date(url)
    if pd.isna(u) or (u.month, u.day) != (int(m[2]), int(m[3])):
        return None
    return u.date()


def date_shape(text: str) -> str:
    """A raw date with every digit replaced by 9 (``28-01-2016`` -> ``99-99-9999``)."""
    return re.sub(r"\d", "9", text.strip())


def load_gold(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The gold headlines with tidy columns, ``label`` (none -> neutral), ``is_none``, ``row_id``
    (0-based row in the file), ``url_date`` and ``date_recovered``. Returns ``(rows,
    unparsable)``. ``unparsable`` lists every row whose raw date is not ``DD-MM-YYYY`` (row id, raw
    date, its shape, URL date, ``recovered``; no headline). Of those, rows whose date
    ``recover_date`` sets from the URL are in ``rows`` with ``date_recovered``; the others are
    dropped."""
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    missing = set(GOLD_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    df = df[list(GOLD_COLUMNS)].rename(columns=GOLD_COLUMNS)
    df.insert(0, "row_id", np.arange(len(df), dtype=np.int64))
    df["date"] = parse_gold_dates(df["date_raw"])
    for c in FLAG_COLUMNS:
        v = pd.to_numeric(df[c], errors="coerce")
        if not v.isin([0, 1]).all():
            raise ValueError(f"{path.name}: column {c} has values other than 0/1")
        df[c] = v.astype(np.int8)
    df["price_sentiment"] = df["price_sentiment"].str.strip().str.lower()
    bad = sorted(set(df["price_sentiment"]) - set(PRICE_SENTIMENTS))
    if bad:
        raise ValueError(f"{path.name}: unknown Price Sentiment values {bad}")
    df["is_none"] = df["price_sentiment"].eq("none")
    df["label"] = df["price_sentiment"].where(~df["is_none"], "neutral")
    df["url_date"] = pd.to_datetime(df["url"].map(url_date))
    na = df["date"].isna()
    found = [recover_date(r, u) for r, u in zip(df.loc[na, "date_raw"], df.loc[na, "url"],
                                                strict=True)]  # fmt: skip
    rec = pd.Series(
        np.array([np.datetime64(d, "ns") if d else np.datetime64("NaT", "ns") for d in found],
                 dtype="datetime64[ns]"),
        index=df.index[na],
    )  # fmt: skip
    df["date_recovered"] = False
    df.loc[rec.index, "date_recovered"] = rec.notna()
    # one resolution whatever the environment (the parquet round trip must give the same frame)
    df["date"] = df["date"].astype("datetime64[ns]").where(~na, rec)
    cols = ["row_id", "date_raw", "url_date"]
    unparsable = df.loc[na, cols].reset_index(drop=True)
    unparsable["shape"] = unparsable["date_raw"].map(date_shape)
    unparsable["recovered"] = df.loc[na, "date_recovered"].to_numpy()
    unparsable["date"] = df.loc[na, "date"].to_numpy()
    rows = df.loc[df["date"].notna()].drop(columns="date_raw").reset_index(drop=True)
    return rows, unparsable


def load_fpb(path: Path) -> pd.DataFrame:
    """FinancialPhraseBank ``Sentences_AllAgree.txt``: latin-1 lines ``sentence@label``."""
    rows = []
    for n, line in enumerate(path.read_text(encoding="latin-1").splitlines(), start=1):
        if not line.strip():
            continue
        sentence, sep, label = line.rpartition("@")
        label = label.strip()
        if not sep or label not in LABELS:
            raise ValueError(f"{path.name} line {n}: not 'sentence@label'")
        rows.append((sentence.strip(), label))
    return pd.DataFrame(rows, columns=["sentence", "label"])


# ------------------------------------------------------------------------------------ G1 dedupe

_NOT_LETTER = re.compile(r"[^a-z\s]+")
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lower case; every run of characters other than a-z and white space (punctuation, digits,
    symbols, non-ASCII) becomes one space; spaces collapsed and trimmed."""
    return _SPACES.sub(" ", _NOT_LETTER.sub(" ", text.lower())).strip()


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Token-set Jaccard; 0 when both sets are empty."""
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _dup_flags(
    norm: list[str],
    days: np.ndarray,
    row_ids: np.ndarray,
    near_jaccard: float,
    window_days: int,
    exact_any_distance: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(dup_exact, dup_near, dup_of, dup_jaccard)`` for rows already in (date, row_id) order.

    ``exact_any_distance`` True (classifier set): a row whose normalised text was seen before, at
    any date, is an exact duplicate. False (index set): only a kept row with the same text dated
    at most ``window_days`` earlier (same day included) makes it one. Then, either way, a row whose
    token set has Jaccard >= ``near_jaccard`` with a kept row in that window is a near duplicate
    (the window is searched oldest day first, the first match counts)."""
    n = len(norm)
    dup_exact = np.zeros(n, dtype=bool)
    dup_near = np.zeros(n, dtype=bool)
    dup_of = np.full(n, -1, dtype=np.int64)
    dup_j = np.full(n, np.nan)
    first_seen: dict[str, int] = {}
    kept_by_day: dict[date, list[tuple[int, str, frozenset[str]]]] = {}
    window = [timedelta(days=k) for k in range(window_days, -1, -1)]  # oldest day first
    for i, (text, day) in enumerate(zip(norm, days, strict=True)):
        if exact_any_distance:
            if text in first_seen:
                dup_exact[i], dup_of[i], dup_j[i] = True, first_seen[text], 1.0
                continue
            first_seen[text] = row_ids[i]
        candidates = [c for back in window for c in kept_by_day.get(day - back, ())]
        if not exact_any_distance:
            same = next((rid for rid, other, _ in candidates if other == text), None)
            if same is not None:
                dup_exact[i], dup_of[i], dup_j[i] = True, same, 1.0
                continue
        tokens = frozenset(text.split())
        match = None
        for rid, _, other in candidates:
            j = jaccard(tokens, other)
            if j >= near_jaccard:
                match = (rid, j)
                break
        if match:
            dup_near[i], dup_of[i], dup_j[i] = True, match[0], match[1]
        else:
            kept_by_day.setdefault(day, []).append((row_ids[i], text, tokens))
    return dup_exact, dup_near, dup_of, dup_j


def dedupe(df: pd.DataFrame, near_jaccard: float, window_days: int) -> pd.DataFrame:
    """G1 before any split, two sets (PREREG §3, decided 2026-11-19). Rows are taken in (date,
    row_id) order and normalised (``norm``).

    Classifier set (train / validation / test of the classifier): exact duplicates of the
    normalised text at any distance in time, then near duplicates (Jaccard >= ``near_jaccard``
    with a kept row at most ``window_days`` earlier). Columns ``dup_exact``, ``dup_near``,
    ``dup_of`` (``row_id`` of the matched row, else -1), ``dup_jaccard``, ``in_classifier_set``.

    Index set (the daily index, PREREG §5): exact and near duplicates dropped only within
    ``window_days`` of a kept row (the same story on several sites); a template headline on
    another day stays. Columns ``idx_dup_exact``, ``idx_dup_near``, ``idx_dup_of``,
    ``in_index_set``. Returns a copy in that order."""
    out = df.sort_values(["date", "row_id"], kind="mergesort").reset_index(drop=True)
    out["norm"] = out["headline"].map(normalise)
    norm = out["norm"].tolist()
    days = out["date"].dt.date.to_numpy()
    row_ids = out["row_id"].to_numpy()
    ex, ne, of, j = _dup_flags(norm, days, row_ids, near_jaccard, window_days, True)
    out["dup_exact"], out["dup_near"], out["dup_of"], out["dup_jaccard"] = ex, ne, of, j
    out["in_classifier_set"] = ~(ex | ne)
    ex, ne, of, _ = _dup_flags(norm, days, row_ids, near_jaccard, window_days, False)
    out["idx_dup_exact"], out["idx_dup_near"], out["idx_dup_of"] = ex, ne, of
    out["in_index_set"] = ~(ex | ne)
    return out


# ---------------------------------------------------------------------------------------- split


@dataclass(frozen=True)
class SplitChoice:
    name: str  # "default" | "fallback"
    train_last: date
    val_last: date
    test_count_default: int  # kept headlines in test under the default boundaries
    counts: dict[str, int]  # kept headlines per split under the chosen boundaries


def assign_split(dates: pd.Series, train_last: date, val_last: date) -> pd.Series:
    """train: date <= train_last; validation: up to val_last; test: after."""
    d = dates.dt.date
    out = np.where(d <= train_last, "train", np.where(d <= val_last, "validation", "test"))
    return pd.Series(out, index=dates.index)


def choose_split(
    kept_dates: pd.Series,
    default: tuple[date, date],
    fallback: tuple[date, date],
    min_test: int,
) -> SplitChoice:
    """PREREG §2.5: the default boundaries unless their test split holds fewer than ``min_test``
    kept headlines, then the fallback (decided on the count alone)."""

    def counts(b: tuple[date, date]) -> dict[str, int]:
        s = assign_split(kept_dates, *b).value_counts()
        return {k: int(s.get(k, 0)) for k in SPLITS}

    c_default = counts(default)
    if c_default["test"] >= min_test:
        return SplitChoice("default", *default, c_default["test"], c_default)
    return SplitChoice("fallback", *fallback, c_default["test"], counts(fallback))


def assert_disjoint(norm: pd.Series, split: pd.Series) -> None:
    """No normalised headline text may appear in two splits."""
    n = pd.DataFrame({"norm": norm, "split": split}).groupby("norm")["split"].nunique()
    shared = int((n > 1).sum())
    if shared:
        raise AssertionError(f"{shared} normalised headline texts appear in more than one split")


# --------------------------------------------------------------------------------------- prices


def read_dukascopy(path: Path, stop_before: date) -> pd.DataFrame:
    """Dukascopy ``timestamp,open,high,low,close,volume`` (ms, UTC, one bar a day from 00:00 UTC).
    Reading stops at the first line dated on or after ``stop_before``: only its timestamp field is
    parsed and nothing after it is read. Returns ``date`` (day, tz-naive UTC) and the prices."""
    stop_ms = int(pd.Timestamp(stop_before, tz="UTC").value // 1_000_000)
    rows = []
    with open(path, encoding="ascii", newline="") as f:
        header = f.readline().strip().split(",")
        if header != ["timestamp", *PRICE_COLUMNS]:
            raise ValueError(f"{path.name}: unexpected header {header}")
        for line in f:
            ts_text, _, rest = line.partition(",")
            ts = int(ts_text)
            if ts >= stop_ms:
                break
            rows.append((ts, *map(float, rest.strip().split(","))))
    df = pd.DataFrame(rows, columns=["timestamp", *PRICE_COLUMNS])
    t = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    if not (t == t.dt.floor("D")).all():
        raise ValueError(f"{path.name}: a bar does not start at 00:00 UTC")
    if not t.is_monotonic_increasing or t.duplicated().any():
        raise ValueError(f"{path.name}: timestamps not strictly increasing")
    df.insert(0, "date", t.dt.tz_localize(None).astype("datetime64[ns]"))
    return df.drop(columns="timestamp")


def merge_sundays(bars: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Fold each Sunday bar into the next day's Monday bar: open = Sunday open, high / low = max /
    min of both, close = Monday close, volume = sum (``merged_sunday`` set on that Monday). A
    Sunday whose next bar is not the following Monday is dropped. No Sunday bar remains."""
    b = bars.sort_values("date").reset_index(drop=True).copy()
    b["merged_sunday"] = False
    sunday = (b["date"].dt.day_of_week == 6).to_numpy()
    nxt = b["date"].shift(-1)
    monday_next = sunday & (nxt - b["date"]).eq(pd.Timedelta(days=1)).to_numpy()
    s = np.flatnonzero(monday_next)
    m = s + 1
    b.loc[m, "open"] = b.loc[s, "open"].to_numpy()
    b.loc[m, "high"] = np.maximum(b.loc[m, "high"].to_numpy(), b.loc[s, "high"].to_numpy())
    b.loc[m, "low"] = np.minimum(b.loc[m, "low"].to_numpy(), b.loc[s, "low"].to_numpy())
    b.loc[m, "volume"] = b.loc[m, "volume"].to_numpy() + b.loc[s, "volume"].to_numpy()
    b.loc[m, "merged_sunday"] = True
    stats = {
        "sunday_bars": int(sunday.sum()),
        "sunday_merged": int(len(s)),
        "sunday_dropped": int(sunday.sum() - len(s)),
        "saturday_bars": int((b["date"].dt.day_of_week == 5).sum()),
    }
    return b.loc[~sunday].reset_index(drop=True), stats


def ohlc_violations(bars: pd.DataFrame) -> pd.DataFrame:
    """Bars with high below open / close / low, low above open / close, a price <= 0 or a NaN."""
    o, h, low, c = (bars[k] for k in ("open", "high", "low", "close"))
    bad = (
        (h < np.maximum(o, c)) | (low > np.minimum(o, c)) | (h < low) | (low <= 0)
        | bars[["open", "high", "low", "close"]].isna().any(axis=1)
    )  # fmt: skip
    return bars.loc[bad]


def garman_klass(o, h, low, c) -> np.ndarray:
    """Garman-Klass daily variance 0.5 ln(H/L)^2 - (2 ln 2 - 1) ln(C/O)^2."""
    hl = np.log(np.asarray(h, float) / np.asarray(low, float))
    co = np.log(np.asarray(c, float) / np.asarray(o, float))
    return 0.5 * hl**2 - (2.0 * np.log(2.0) - 1.0) * co**2


def add_gk(bars: pd.DataFrame) -> pd.DataFrame:
    """``gk_var`` and ``log_gk`` (NaN where gk_var <= 0)."""
    out = bars.copy()
    out["gk_var"] = garman_klass(out["open"], out["high"], out["low"], out["close"])
    g = out["gk_var"].to_numpy()
    out["log_gk"] = np.log(g, out=np.full_like(g, np.nan), where=g > 0)
    return out


def align_trade_dates(dates: pd.Series, calendar: pd.Series) -> pd.Series:
    """G3: each headline date moved to the first price day on or after it (itself if it has a
    bar); NaT after the last price day."""
    cal = np.sort(calendar.to_numpy(dtype="datetime64[ns]"))
    i = np.searchsorted(cal, dates.to_numpy(dtype="datetime64[ns]"), side="left")
    out = np.full(len(i), np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
    ok = i < len(cal)
    out[ok] = cal[i[ok]]
    return pd.Series(out, index=dates.index)


# ------------------------------------------------------------------------------------- pipeline


@dataclass
class Built:
    gold: pd.DataFrame  # every parsed headline, with dedupe flags, split, trade_date
    unparsable: pd.DataFrame
    fpb: pd.DataFrame
    calendar: pd.Series  # every price day (Sunday-merged), first bar to price_stop
    prices: pd.DataFrame  # from price_first, with gk_var / log_gk
    split: SplitChoice
    price_stats: dict[str, int]
    violations: pd.DataFrame  # from price_first, after the merge
    files: dict[str, str]  # verify_files status
    manifest: dict = field(default_factory=dict)


def build_prices(cfg: Config) -> tuple[pd.Series, pd.DataFrame, dict[str, int], pd.DataFrame]:
    """``(calendar, prices, stats, violations)``: Sunday-merged bars before ``price_stop``. The
    calendar keeps every year (to align 2000-2002 headlines); the prices start at
    ``price_first``."""
    raw = read_dukascopy(cfg.files["dukascopy"].path, cfg.price_stop)
    merged, stats = merge_sundays(raw)
    calendar = merged["date"].copy()
    prices = add_gk(merged.loc[merged["date"] >= pd.Timestamp(cfg.price_first)])
    prices = prices.reset_index(drop=True)
    violations = ohlc_violations(prices)
    stats = {
        **stats,
        "bars_raw": int(len(raw)),
        "bars_from_first": int(len(prices)),
        "first_price_day": str(prices["date"].iloc[0].date()),
        "last_price_day": str(prices["date"].iloc[-1].date()),
        "ohlc_violations": int(len(violations)),
        "gk_nonpositive": int(prices["log_gk"].isna().sum()),
    }
    return calendar, prices, stats, violations


def build(cfg: Config) -> Built:
    """Every step of ``data`` in order; nothing is written."""
    files = verify_files(cfg)
    gold, unparsable = load_gold(cfg.files["gold"].path)
    gold = dedupe(gold, cfg.near_jaccard, cfg.window_days)
    choice = choose_split(
        gold.loc[gold["in_classifier_set"], "date"],
        cfg.default_split,
        cfg.fallback_split,
        cfg.min_test,
    )
    gold["split"] = assign_split(gold["date"], choice.train_last, choice.val_last)
    clf = gold["in_classifier_set"]
    assert_disjoint(gold.loc[clf, "norm"], gold.loc[clf, "split"])
    calendar, prices, stats, violations = build_prices(cfg)
    gold["trade_date"] = align_trade_dates(gold["date"], calendar)
    gold["moved"] = gold["trade_date"].ne(gold["date"])
    fpb = load_fpb(cfg.files["fpb"].path)
    built = Built(gold, unparsable, fpb, calendar, prices, choice, stats, violations, files)
    built.manifest = manifest(cfg, built)
    return built


def date_checks(gold: pd.DataFrame, unparsable: pd.DataFrame) -> dict:
    """Evidence on the file's date column (descriptive). Rows whose raw date parsed as
    ``DD-MM-YYYY``: how many have a day above 12 (so the order is day-month) and how many carry a
    URL date equal to theirs. Unparsable rows: their shapes, how many have a URL date whose
    month-day equals the raw value's last five characters (``YYYY-MM-DD`` shape), how many were
    recovered (``recover_date``), recovered rows per year, and how many recovered years begin
    with the raw year's digits (``0201`` -> 201x; descriptive, not part of the rule)."""
    gold = gold.loc[~gold["date_recovered"]]
    has = gold["url_date"].notna()
    u = unparsable
    u_has = u["url_date"].notna()
    mmdd = u.loc[u_has, "date_raw"].str.strip().str[-5:] == u.loc[u_has, "url_date"].dt.strftime(
        "%m-%d"
    )
    rec = u["recovered"].astype(bool)
    years = u.loc[rec, "date"].dt.year.value_counts()
    prefix_ok = pd.Series(
        [str(d.year).startswith(r.strip()[:4].lstrip("0") or "-")
         for r, d in zip(u.loc[rec, "date_raw"], u.loc[rec, "date"], strict=True)], dtype=bool
    )  # fmt: skip
    return {
        "day_field_gt12": int((gold["date"].dt.day > 12).sum()),
        "url_date_rows": int(has.sum()),
        "url_date_equal": int((gold.loc[has, "url_date"] == gold.loc[has, "date"]).sum()),
        "unparsable_shapes": {k: int(v) for k, v in u["shape"].value_counts().sort_index().items()},
        "unparsable_url_date": int(u_has.sum()),
        "unparsable_url_mmdd_match": int(mmdd.sum()),
        "recovered": int(rec.sum()),
        "recovered_per_year": {str(k): int(v) for k, v in years.sort_index().items()},
        "recovered_year_prefix_consistent": int(prefix_ok.sum()),
        "date_dropped": int((~u["recovered"]).sum()),
    }


def manifest(cfg: Config, b: Built) -> dict:
    """Counts and choices of a build (no headline text)."""
    g = b.gold
    return {
        "files": {k: {"sha256": cfg.files[k].sha256, "status": s} for k, s in b.files.items()},
        "gold": {
            "rows_raw": int(len(g) + (~b.unparsable["recovered"]).sum()),
            "unparsable_dates": int(len(b.unparsable)),
            "unparsable_row_ids": b.unparsable["row_id"].astype(int).tolist(),
            "recovered_row_ids": b.unparsable.loc[b.unparsable["recovered"], "row_id"]
            .astype(int)
            .tolist(),
            "date_dropped_row_ids": b.unparsable.loc[~b.unparsable["recovered"], "row_id"]
            .astype(int)
            .tolist(),
            **date_checks(g, b.unparsable),
            "rows_dated": int(len(g)),
            "dup_exact": int(g["dup_exact"].sum()),
            "dup_near": int(g["dup_near"].sum()),
            "kept": int(g["in_classifier_set"].sum()),
            "index_set": {
                "dup_exact": int(g["idx_dup_exact"].sum()),
                "dup_near": int(g["idx_dup_near"].sum()),
                "kept": int(g["in_index_set"].sum()),
                "kept_test_years": int((g["in_index_set"] & g["split"].eq("test")).sum()),
            },
            "first_date": str(g["date"].min().date()),
            "last_date": str(g["date"].max().date()),
        },
        "split": {
            "chosen": b.split.name,
            "train_last": str(b.split.train_last),
            "val_last": str(b.split.val_last),
            "test_count_default": b.split.test_count_default,
            "min_test": cfg.min_test,
            "counts": b.split.counts,
        },
        "prices": b.price_stats,
        "fpb": {"rows": int(len(b.fpb))},
    }


def save(cfg: Config, b: Built) -> None:
    cfg.processed.mkdir(parents=True, exist_ok=True)
    b.gold.to_parquet(cfg.processed / "gold_headlines.parquet", index=False)
    b.fpb.to_parquet(cfg.processed / "fpb.parquet", index=False)
    b.prices.to_parquet(cfg.processed / "xauusd_d1.parquet", index=False)
    cal = pd.DataFrame({"date": b.calendar})
    cal.to_parquet(cfg.processed / "price_calendar.parquet", index=False)
    text = json.dumps(b.manifest, indent=2, sort_keys=True) + "\n"
    (cfg.processed / "manifest.json").write_text(text, encoding="utf-8")


def load_processed(cfg: Config) -> dict:
    """The files ``save`` wrote; refuses if they were built from other raw files."""
    path = cfg.processed / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found: run `python -m app research sentiment data`")
    man = json.loads(path.read_text(encoding="utf-8"))
    for key, f in cfg.files.items():
        if man["files"].get(key, {}).get("sha256", "") != f.sha256:
            raise ChecksumError(f"{key}: processed files come from other raw data; rerun data")
    return {
        "manifest": man,
        "gold": pd.read_parquet(cfg.processed / "gold_headlines.parquet"),
        "fpb": pd.read_parquet(cfg.processed / "fpb.parquet"),
        "prices": pd.read_parquet(cfg.processed / "xauusd_d1.parquet"),
        "calendar": pd.read_parquet(cfg.processed / "price_calendar.parquet")["date"],
    }
