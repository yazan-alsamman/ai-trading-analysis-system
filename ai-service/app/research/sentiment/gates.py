"""Data gates G1-G5 (``docs/sentiment/PREREG_SENTIMENT.md`` §3) -> ``docs/sentiment/gates.md``.

    python -m app research sentiment gates

Reads what ``sentiment data`` wrote (it refuses if those files came from other raw data), writes
the report and the train-only class weights (G4) into ``app/config/sentiment.toml``. Counts only:
no statistic joins a headline or its label with a price or a volatility (G3 and G5 use the price
calendar, never a price). The report quotes at most four headline texts (two near-duplicate pairs;
licence CC BY-NC-ND 4.0, five at most in all)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from app.research.sentiment import data as sd

NEAR_EXAMPLES = 2  # pairs quoted in the report (four headline texts)


# ------------------------------------------------------------------------------------- helpers


def md_table(df: pd.DataFrame) -> str:
    """A pipe table (index dropped); floats are formatted by the caller."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


# ------------------------------------------------------------------------------------------ G1


SETS = {
    # which: (exact column, near column, kept column)
    "classifier": ("dup_exact", "dup_near", "in_classifier_set"),
    "index": ("idx_dup_exact", "idx_dup_near", "in_index_set"),
}


def g1_table(gold: pd.DataFrame, which: str = "classifier") -> pd.DataFrame:
    """Per year of the headline date: dated rows, exact and near duplicates removed, kept, for
    the classifier set or the index set."""
    exact, near, kept = SETS[which]
    y = gold["date"].dt.year.rename("year")
    t = pd.DataFrame({
        "rows": gold.groupby(y).size(),
        "exact removed": gold.groupby(y)[exact].sum(),
        "near removed": gold.groupby(y)[near].sum(),
        "kept": gold.groupby(y)[kept].sum(),
    }).astype(int)  # fmt: skip
    t.loc["all"] = t.sum()
    return t.reset_index()


def g1_exact_table(gold: pd.DataFrame) -> pd.DataFrame:
    """Exact duplicates by days to the kept headline they repeat (same day, 1-3, 4-30, over 30),
    with how many have a Price Sentiment different from the kept one."""
    by_id = gold.set_index("row_id")
    d = gold.loc[gold["dup_exact"]]
    kept = by_id.loc[d["dup_of"].to_numpy()]
    days = (d["date"].to_numpy() - kept["date"].to_numpy()) / np.timedelta64(1, "D")
    differs = d["price_sentiment"].to_numpy() != kept["price_sentiment"].to_numpy()
    bins = pd.cut(days, [-1, 0, 3, 30, np.inf], labels=["same day", "1-3 days", "4-30 days",
                                                       "over 30 days"])  # fmt: skip
    t = pd.DataFrame({"gap": bins, "n": 1, "label differs": differs})
    t = t.groupby("gap", observed=False).sum().astype(int)
    t.loc["all"] = t.sum()
    return t.reset_index()


def near_examples(gold: pd.DataFrame, k: int = NEAR_EXAMPLES) -> list[dict]:
    """The first ``k`` near-duplicates in (date, row_id) order with the kept headline they
    matched."""
    by_id = gold.set_index("row_id")
    out = []
    for r in gold.loc[gold["dup_near"]].head(k).itertuples():
        kept = by_id.loc[r.dup_of]
        out.append({
            "kept_date": str(kept["date"].date()), "kept": kept["headline"],
            "dropped_date": str(r.date.date()), "dropped": r.headline,
            "jaccard": float(r.dup_jaccard),
        })  # fmt: skip
    return out


# ------------------------------------------------------------------------------------------ G2


def read_gcf(path: Path, stop_before: date) -> pd.DataFrame:
    """The Yahoo ``GC=F`` file ``download`` wrote (``date,open,high,low,close,volume``, dated by
    the exchange's day); reading stops at the first line dated on or after ``stop_before``.
    Returns ``date``, ``open``, ``high``, ``low``, ``close``."""
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        header = [h.strip().lower() for h in f.readline().split(",")]
        if header[:5] != ["date", "open", "high", "low", "close"]:
            raise ValueError(f"{path.name}: unexpected header {header}")
        for line in f:
            if not line.strip():
                continue
            d_text, _, rest = line.partition(",")
            d = date.fromisoformat(d_text.strip()[:10])
            if d >= stop_before:
                break
            o, h, low, c = (float(x) for x in rest.split(",")[:4])
            rows.append((pd.Timestamp(d), o, h, low, c))
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])


def read_mt5_d1(path: Path, stop_before: date) -> pd.DataFrame:
    """An FxPro MT5 D1 "Export bars" file (tab-separated, header ``<DATE> [<TIME>] <OPEN> <HIGH>
    <LOW> <CLOSE> ...``, dates ``YYYY.MM.DD`` on the server clock), read only through
    ``app.data.raw.HistoryExport``, which stops at the first bar on or after ``stop_before``
    without decoding it. Returns ``date`` (the server day), ``close``."""
    from app.data.raw import HistoryExport

    lines = HistoryExport(path, cutoff=stop_before).lines()
    header = [h.strip().strip("<>").lower() for h in next(lines).split("\t")]
    if "date" not in header or "close" not in header:
        raise ValueError(f"{path.name}: unexpected header {header}")
    i_date, i_close = header.index("date"), header.index("close")
    rows = []
    for line in lines:
        if not line.strip():
            continue
        f = line.split("\t")
        rows.append((pd.Timestamp(f[i_date].replace(".", "-")), float(f[i_close])))
    return pd.DataFrame(rows, columns=["date", "close"])


G2_SOURCES = {
    "mt5": "FxPro MT5 XAUUSD D1 export",
    "gcf": "Yahoo Finance GC=F (COMEX gold futures, front contract) daily",
}


def g2_crosscheck(
    prices: pd.DataFrame,
    other: pd.DataFrame | None,
    first: date,
    rule: str,
    rule_min: float,
    diff: float,
    n_list: int,
) -> dict:
    """Dukascopy (Sunday-merged) closes against a cross-check series on their common dates from
    ``first`` (aligned by date only): close correlation, log-return correlation (returns between
    consecutive common dates), share and first dates of |log-return difference| > ``diff``.
    Pass: ``rule`` ("close_corr" or "return_corr") >= ``rule_min``. ``other`` None: pending."""
    if other is None:
        return {"status": "pending", "rule": rule, "rule_min": rule_min}
    a = prices.loc[prices["date"] >= pd.Timestamp(first), ["date", "close"]]
    j = a.merge(other[["date", "close"]], on="date", suffixes=("_duka", "_other"))
    j = j.sort_values("date").reset_index(drop=True)
    ra, rb = np.log(j["close_duka"]).diff(), np.log(j["close_other"]).diff()
    d = (ra - rb).abs()
    flagged = j.loc[d > diff, "date"].dt.date.astype(str).tolist()
    out = {
        "common_days": int(len(j)),
        "first": str(j["date"].iloc[0].date()) if len(j) else "",
        "last": str(j["date"].iloc[-1].date()) if len(j) else "",
        "close_corr": float(j["close_duka"].corr(j["close_other"])),
        "return_corr": float(ra.corr(rb)),
        "share_flagged": float((d > diff).sum() / d.notna().sum()) if d.notna().any() else 0.0,
        "flagged_count": len(flagged),
        "flagged_first": flagged[:n_list],
        "rule": rule,
        "rule_min": rule_min,
    }
    out["status"] = "pass" if out[rule] >= rule_min else "fail"
    return out


G2_HORIZONS = (1, 2, 5, 10)  # common dates per return in the investigation


def g2_diagnostics(prices: pd.DataFrame, other: pd.DataFrame | None, first: date) -> dict:
    """Investigation of a G2 result (descriptive; prices only, the pass rule is unchanged), on
    the same common dates as ``g2_crosscheck``: log-return correlation per year; over returns
    spanning 1, 2, 5 and 10 common dates (non-overlapping), where a difference in close time
    washes out and bad prints do not; lead / lag correlations (Dukascopy day t with the other's
    day t+1 and the reverse); and the other series' flat bars (open = high = low = close, a
    stale quote) on common dates, when it has OHLC."""
    if other is None:
        return {}
    a = prices.loc[prices["date"] >= pd.Timestamp(first), ["date", "close"]]
    j = a.merge(other, on="date", suffixes=("_duka", "_other"))
    j = j.sort_values("date").reset_index(drop=True)
    la, lb = np.log(j["close_duka"]), np.log(j["close_other"])
    ra, rb = la.diff(), lb.diff()
    y = j["date"].dt.year
    per_year = pd.DataFrame({"ra": ra, "rb": rb, "year": y}).groupby("year")
    out = {
        "per_year": pd.DataFrame(
            {
                "year": sorted(y.unique()),
                "common days": per_year.size().to_numpy(),
                "return corr": [f"{g['ra'].corr(g['rb']):.3f}" for _, g in per_year],
            }
        ),  # fmt: skip
        "horizons": {k: float(la.iloc[::k].diff().corr(lb.iloc[::k].diff())) for k in G2_HORIZONS},
        "duka_leads": float(ra.corr(rb.shift(-1))),
        "other_leads": float(rb.corr(ra.shift(-1))),
    }
    if {"open", "high", "low"} <= set(other.columns):
        flat = j["open"].eq(j["high"]) & j["high"].eq(j["low"]) & j["low"].eq(j["close_other"])
        out["flat"] = int(flat.sum())
        out["flat_before_2008"] = int((flat & (y < 2008)).sum())
    return out


def g2_source(cfg: sd.Config, status: dict[str, str]) -> tuple[str | None, pd.DataFrame | None]:
    """PREREG §2.3 order: the MT5 D1 export if present, else Yahoo GC=F, else none (pending)."""
    if status.get("mt5") == "ok":
        return "mt5", read_mt5_d1(cfg.files["mt5"].path, cfg.price_stop)
    if status.get("gcf") == "ok":
        return "gcf", read_gcf(cfg.files["gcf"].path, cfg.price_stop)
    return None, None


def g2_rule(cfg: sd.Config, source: str | None) -> tuple[str, float]:
    """MT5 (same instrument): close correlation >= 0.99; GC=F (futures): return correlation >=
    0.95 (closes differ by carry and settlement time). Pending: the GC=F rule is quoted."""
    if source == "mt5":
        return "close_corr", cfg.g2_min_close_corr
    return "return_corr", cfg.g2_min_return_corr


# ------------------------------------------------------------------------------------------ G3


def g3_table(kept: pd.DataFrame) -> pd.DataFrame:
    """Kept headlines per year whose date has no price bar: on a weekend, on a weekday without a
    bar (holiday or missing day); both move to the next price day (``trade_date``)."""
    y = kept["date"].dt.year.rename("year")
    weekend = kept["date"].dt.day_of_week >= 5
    t = pd.DataFrame({
        "headlines": kept.groupby(y).size(),
        "weekend": (kept["moved"] & weekend).groupby(y).sum(),
        "weekday, no bar": (kept["moved"] & ~weekend).groupby(y).sum(),
        "moved": kept["moved"].groupby(y).sum(),
    }).astype(int)  # fmt: skip
    t.loc["all"] = t.sum()
    return t.reset_index()


# ------------------------------------------------------------------------------------------ G4


def class_weights(labels: pd.Series) -> dict[str, float]:
    """Inverse class frequency, normalised so the sample-weighted mean is 1: n / (K * n_c)."""
    n_c = labels.value_counts()
    missing = [c for c in sd.LABELS if n_c.get(c, 0) == 0]
    if missing:
        raise ValueError(f"no train headline with label {missing}")
    n, k = len(labels), len(sd.LABELS)
    return {c: float(n / (k * n_c[c])) for c in sd.LABELS}


def g4_table(kept: pd.DataFrame) -> pd.DataFrame:
    """Per split: kept headlines, training-label shares, and the share that were "none"."""
    rows = []
    for s in sd.SPLITS:
        part = kept.loc[kept["split"] == s]
        sh = part["label"].value_counts(normalize=True)
        rows.append({
            "split": s, "headlines": len(part),
            **{c: pct(sh.get(c, 0.0)) for c in sd.LABELS},
            "of which none": pct(part["is_none"].mean() if len(part) else 0.0),
            "first": str(part["date"].min().date()), "last": str(part["date"].max().date()),
        })  # fmt: skip
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------ G5


def g5_table(
    kept: pd.DataFrame, calendar: pd.Series, first: date, last: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Price days from ``first`` to ``last`` (default: the last kept headline's trade date) with
    no kept headline on their ``trade_date``, per year (counts only). Years after the last
    headline are left out (every day there is empty)."""
    last = kept["trade_date"].max() if last is None else last
    cal = calendar[(calendar >= pd.Timestamp(first)) & (calendar <= last)]
    has = cal.isin(set(kept["trade_date"].dropna()))
    y = cal.dt.year.rename("year")
    t = pd.DataFrame({
        "price days": cal.groupby(y).size(),
        "zero-headline days": (~has).groupby(y).sum(),
    }).astype(int)  # fmt: skip
    t["share"] = (t["zero-headline days"] / t["price days"]).map(pct)
    return t.reset_index()


def g5_both(
    gold: pd.DataFrame, calendar: pd.Series, first: date
) -> tuple[pd.DataFrame, dict[str, float]]:
    """G5 on the classifier set and the index set over the same price days (to the last trade
    date of either), one table; and each set's zero-headline share over 2016-2018."""
    clf = gold.loc[gold["in_classifier_set"]]
    idx = gold.loc[gold["in_index_set"]]
    last = max(clf["trade_date"].max(), idx["trade_date"].max())
    a, b = g5_table(clf, calendar, first, last), g5_table(idx, calendar, first, last)
    t = pd.DataFrame({
        "year": a["year"], "price days": a["price days"],
        "zero, classifier set": a["zero-headline days"], "share, classifier": a["share"],
        "zero, index set": b["zero-headline days"], "share, index": b["share"],
    })  # fmt: skip
    yrs = a["year"].between(2016, 2018)
    days = a.loc[yrs, "price days"].sum()
    shares = {
        "classifier": float(a.loc[yrs, "zero-headline days"].sum() / days) if days else 0.0,
        "index": float(b.loc[yrs, "zero-headline days"].sum() / days) if days else 0.0,
    }
    return t, shares


# ------------------------------------------------------------------------------- summaries


def label_shares(gold: pd.DataFrame) -> dict[str, float]:
    """Shares of the dataset's Price Sentiment (positive / negative / neutral / none)."""
    sh = gold["price_sentiment"].value_counts(normalize=True)
    return {c: float(sh.get(c, 0.0)) for c in ("positive", "negative", "neutral", "none")}


def summarise(
    processed: dict, cfg: sd.Config, source: str | None, other: pd.DataFrame | None
) -> dict:
    """Every figure of the report, from what ``data`` wrote. ``source`` / ``other``: the G2
    cross-check series (``g2_source``), or None (pending)."""
    gold, man = processed["gold"], processed["manifest"]
    kept = gold.loc[gold["in_classifier_set"]].copy()
    index = gold.loc[gold["in_index_set"]]
    g5, g5_shares = g5_both(gold, processed["calendar"], cfg.price_first)
    rule, rule_min = g2_rule(cfg, source)
    train = kept.loc[kept["split"] == "train", "label"]
    fpb = processed["fpb"]
    return {
        "manifest": man,
        "years": gold.groupby(gold["date"].dt.year).size(),
        "shares_all": label_shares(gold),
        "shares_kept": label_shares(kept),
        "shares_index": label_shares(index),
        "g1": g1_table(gold, "classifier"),
        "g1_index": g1_table(gold, "index"),
        "index_moved": int(index["moved"].sum()),
        "near": near_examples(gold),
        "g1_exact": g1_exact_table(gold),
        "g2_source": source,
        "g2_diag": g2_diagnostics(processed["prices"], other, cfg.price_first),
        "g2": g2_crosscheck(
            processed["prices"],
            other,
            cfg.price_first,
            rule,
            rule_min,
            cfg.g2_return_diff,
            cfg.g2_list,
        ),  # fmt: skip
        "g3": g3_table(kept),
        "g4": g4_table(kept),
        "weights": class_weights(train),
        "g5": g5,
        "g5_2016_2018": g5_shares,
        "fpb_rows": len(fpb),
        "fpb_shares": fpb["label"].value_counts(normalize=True).reindex(sd.LABELS).fillna(0.0),
    }


# ---------------------------------------------------------------------------------------- report


def render(s: dict, cfg: sd.Config) -> str:
    man = s["manifest"]
    g, sp, pr = man["gold"], man["split"], man["prices"]
    gi = g["index_set"]
    out = [
        "# Gold-news sentiment: data gates G1-G5",
        "",
        "Generated by `python -m app research sentiment data` then `python -m app research "
        "sentiment gates` (`app/research/sentiment/`, config `app/config/sentiment.toml`). "
        "Registration: `docs/sentiment/PREREG_SENTIMENT.md` (DRAFT, not approved). Data work only: "
        "no model was trained, scored or loaded, and no figure here joins a headline or its label "
        "with a price or a volatility (G3 and G5 use the price calendar only).",
        "",
        "## Files (SHA-256)",
        "",
    ]
    files = pd.DataFrame([
        {"file": k, "path": f"`{cfg.files[k].path.relative_to(cfg.root).as_posix()}`",
         "status": v["status"], "sha256": f"`{v['sha256']}`" if v["sha256"] else "—"}
        for k, v in man["files"].items()
    ])  # fmt: skip
    out += [
        md_table(files),
        "",
        "The MT5 export's SHA-256, once recorded, covers only the bytes before its first bar on or "
        "after the lockbox start (read through `app.data.raw.HistoryExport`).",
        "",
    ]

    shares = pd.DataFrame([
        {"rows": "all dated", **{k: pct(v) for k, v in s["shares_all"].items()}},
        {"rows": "classifier set", **{k: pct(v) for k, v in s["shares_kept"].items()}},
        {"rows": "index set", **{k: pct(v) for k, v in s["shares_index"].items()}},
    ])  # fmt: skip
    years = s["years"]
    rec_years = pd.DataFrame(
        {"year": list(g["recovered_per_year"]), "recovered": list(g["recovered_per_year"].values())}
    )
    out += [
        "## Gold headlines (Sinha and Khandait, arXiv:2009.04202; CC BY-NC-ND 4.0)",
        "",
        f"- Rows in the file: {g['rows_raw']:,}. Date format DD-MM-YYYY "
        f"checked: {g['day_field_gt12']:,} rows parsed as DD-MM-YYYY have a day above 12, and "
        f"where the article URL carries a date it equals the file's date in "
        f"{g['url_date_equal']:,} of {g['url_date_rows']:,} rows.",
        f"- Dates that do not parse as DD-MM-YYYY: {g['unparsable_dates']} rows. Shapes: "
        + ", ".join(f"`{k}` {v}" for k, v in g["unparsable_shapes"].items())
        + f" (a truncated year, e.g. `0201-04-27`). {g['unparsable_url_date']} of them have a URL "
        f"date and in {g['unparsable_url_mmdd_match']} its month-day equals the raw value's.",
        f"- **Date recovery (PREREG §2.1, decided 2026-11-19):** the date is taken from the URL "
        f"when the URL's month and day equal the raw value's. Recovered: **{g['recovered']}**; "
        f"still dropped: **{g['date_dropped']}** (row ids of both in `processed/manifest.json`). "
        f"In {g['recovered_year_prefix_consistent']} of the {g['recovered']} recovered rows the "
        "URL's year begins with the raw year's digits (`0201` -> 201x; descriptive, not part of "
        "the rule). Recovered rows go through G1 and the split like any other row.",
        f"- Dated rows: {g['rows_dated']:,}; date range {g['first_date']} to {g['last_date']}.",
        f"- Classifier set (G1): {g['kept']:,} kept. Index set (G1): {gi['kept']:,} kept, of "
        f"which {gi['kept_test_years']:,} in the test years.",
        "- Training label (PREREG §2.2): none -> neutral, `is_none` kept.",
        "",
        "Recovered rows per year (URL date):",
        "",
        md_table(rec_years),
        "",
        "Price Sentiment shares:",
        "",
        md_table(shares),
        "",
        "Rows per year (dated rows, before G1):",
        "",
        md_table(pd.DataFrame({"year": years.index, "rows": years.to_numpy()})),
        "",
    ]

    out += [
        "## G1 duplicates",
        "",
        "Normalised text: lower case, every run of non-letters (punctuation, digits, symbols) "
        "becomes a space, spaces collapsed. Rows are taken in date order (file order on ties); "
        "the earliest is kept. Done before the split. Two sets (decided 2026-11-19):",
        "",
        f"- **Classifier set** (train / validation / test of the classifier): exact duplicates of "
        f"the normalised text dropped at any distance in time (so a recurring price-report "
        f"template cannot sit in two splits); then a headline whose token set has Jaccard >= "
        f"{cfg.near_jaccard} with a kept headline dated up to {cfg.window_days} days earlier "
        f"(same day included) is dropped.",
        f"- **Index set** (the daily index, PREREG §5): exact and near duplicates dropped only "
        f"when a kept headline is dated up to {cfg.window_days} days earlier (the same story on "
        "several sites); a template headline on another day is that day's news and stays.",
        "",
        "Classifier set:",
        "",
        md_table(s["g1"]),
        "",
        "Classifier set, exact duplicates by distance to the headline they repeat, and how many "
        "carry a different Price Sentiment from it (the kept label is the one used):",
        "",
        md_table(s["g1_exact"]),
        "",
        "Index set:",
        "",
        md_table(s["g1_index"]),
        "",
        f"Near-duplicate examples, classifier set (first {len(s['near'])} in date order):",
        "",
    ]
    for i, e in enumerate(s["near"], 1):
        out += [
            f'{i}. kept {e["kept_date"]}: "{e["kept"]}"; dropped {e["dropped_date"]}: '
            f'"{e["dropped"]}" (Jaccard {e["jaccard"]:.2f})'
        ]
    out += [
        "",
        f"**Split ({sp['chosen']}, classifier set):** train <= {sp['train_last']}, validation to "
        f"{sp['val_last']}, test after. The default test split (2016+) holds "
        f"{sp['test_count_default']:,} classifier-set headlines (rule: fallback if < "
        f"{sp['min_test']:,}). Classifier set: train {sp['counts']['train']:,} / validation "
        f"{sp['counts']['validation']:,} / test {sp['counts']['test']:,}. Checked: no normalised "
        f"text of the classifier set appears in two splits. Index set in the test years: "
        f"{gi['kept_test_years']:,}.",
        "",
    ]

    g2, src = s["g2"], s["g2_source"]
    rule_name = {"close_corr": "close correlation", "return_corr": "log-return correlation"}
    rule = f"{rule_name[g2['rule']]} >= {g2['rule_min']}"

    def rel(key: str) -> str:
        return cfg.files[key].path.relative_to(cfg.root).as_posix()

    out += ["## G2 prices", ""]
    if g2["status"] == "pending":
        out += [
            "**Pending.** Neither cross-check series is present: the FxPro MT5 D1 export "
            f"(`{rel('mt5')}`, asked from Fadi 2026-11-18) nor Yahoo `GC=F` (`{rel('gcf')}`). "
            "Rules when run: MT5 close correlation >= "
            f"{cfg.g2_min_close_corr}; `GC=F` log-return correlation >= {cfg.g2_min_return_corr}.",
            "",
        ]
    else:
        clock = (
            "MT5 bars are dated by the FxPro server day (Europe/Athens), not 00:00 UTC"
            if src == "mt5"
            else "Yahoo daily bars are dated by the exchange's trading day (New York), not 00:00 "
            "UTC (the lead / lag below points to a close earlier than Dukascopy's); futures also "
            "carry a contract roll and carry over spot"
        )
        out += [
            f"Source used: **{G2_SOURCES[src]}** (PREREG §2.3 order: the MT5 D1 export if present, "
            f"else `GC=F`; MT5 export present: {'yes' if src == 'mt5' else 'no'}). {clock}; the "
            "series are aligned **by date only**, so part of every daily return is measured over "
            "different hours.",
            "",
            f"Dukascopy (Sunday merged) vs this series, {g2['common_days']:,} common dates "
            f"{g2['first']} to {g2['last']}: log-return correlation {g2['return_corr']:.4f}, close "
            f"correlation {g2['close_corr']:.5f}, days with |log-return difference| > "
            f"{pct(cfg.g2_return_diff)}: {g2['flagged_count']} ({pct(g2['share_flagged'])}). "
            f"**{g2['status'].upper()}** (rule for this source: {rule}).",
            "",
            f"First {len(g2['flagged_first'])} flagged dates: "
            f"{', '.join(g2['flagged_first']) or 'none'}.",
            "",
        ]
        dg = s["g2_diag"]
        hz = ", ".join(f"{k} day{'s' if k > 1 else ''} {v:.4f}" for k, v in dg["horizons"].items())
        flat = (
            f" The cross-check series has {dg['flat']} flat bars (open = high = low = close, a "
            f"stale quote) on common dates, {dg['flat_before_2008']} of them before 2008."
            if "flat" in dg
            else ""
        )
        out += [
            "**Investigation of the flagged days** (descriptive, prices only; the rule and the "
            "result above are unchanged). Log-return correlation over returns spanning 1, 2, 5 "
            f"and 10 common dates (non-overlapping): {hz}. Dukascopy's day-t return against the "
            f"other's day t+1: {dg['duka_leads']:.3f}; the other's day t against Dukascopy's t+1: "
            f"{dg['other_leads']:.3f}.{flat} Log-return correlation per year:",
            "",
            md_table(dg["per_year"]),
            "",
        ]
    out += [
        f"Dukascopy XAUUSD D1 bid, bars read: {pr['bars_raw']:,} (to the last bar before "
        f"{cfg.price_stop}, the lockbox start; the reader stops there). Sunday bars: "
        f"{pr['sunday_bars']:,}, merged into Monday {pr['sunday_merged']:,}, dropped (no Monday) "
        f"{pr['sunday_dropped']:,}; Saturday bars {pr['saturday_bars']}. From {cfg.price_first}: "
        f"{pr['bars_from_first']:,} bars ({pr['first_price_day']} to {pr['last_price_day']}), "
        f"OHLC violations after the merge {pr['ohlc_violations']}, Garman-Klass variance <= 0 "
        f"(log_gk NaN) {pr['gk_nonpositive']}.",
        "",
    ]

    out += [
        "## G3 day alignment",
        "",
        "Headlines dated on a day without a Dukascopy bar (00:00 UTC days; Sunday bars are "
        "merged into Monday, so Sunday is never a price day) move to the next price day "
        "(`trade_date`). The calendar includes 2000-2002 for this alignment only. Classifier set:",
        "",
        md_table(s["g3"]),
        "",
        f"Index set: {s['index_moved']:,} of {gi['kept']:,} headlines moved.",
        "",
    ]

    w = s["weights"]
    out += [
        "## G4 label balance (classifier set)",
        "",
        md_table(s["g4"]),
        "",
        "Class weights from train only (n / (K n_c), written to `sentiment.toml`): "
        + ", ".join(f"{c} {w[c]:.4f}" for c in sd.LABELS)
        + ".",
        "",
    ]

    sh = s["g5_2016_2018"]
    out += [
        "## G5 coverage",
        "",
        f"Price days from {cfg.price_first} to the last headline's trade date with no headline "
        "of the set on them (counts only), both sets on the same price days.",
        "",
        md_table(s["g5"]),
        "",
        f"Zero-headline share over 2016-2018: classifier set {pct(sh['classifier'])}, index set "
        f"{pct(sh['index'])}.",
        "",
    ]

    fs = s["fpb_shares"]
    out += [
        "## FinancialPhraseBank (Malo et al. 2014; Sentences_AllAgree; CC BY-NC-SA 3.0)",
        "",
        f"Rows {s['fpb_rows']:,}: "
        + ", ".join(f"{c} {pct(fs[c])}" for c in sd.LABELS)
        + ". Used only for stage-1 training (S3); its labels are from an equity investor's "
        "point of view.",
        "",
    ]
    return "\n".join(out)


def run(cfg: sd.Config) -> str:
    """Verify the raw files, read the processed ones, write the report and the class weights."""
    status = sd.verify_files(cfg)
    processed = sd.load_processed(cfg)
    source, other = g2_source(cfg, status)
    s = summarise(processed, cfg, source, other)
    text = render(s, cfg)
    cfg.report.parent.mkdir(parents=True, exist_ok=True)
    cfg.report.write_text(text, encoding="utf-8", newline="\n")
    sd.write_class_weights(cfg.path, s["weights"])
    return text
